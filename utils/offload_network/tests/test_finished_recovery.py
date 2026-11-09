"""Finished-attempt recovery preserves failures and rejects incomplete identities."""
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import sqlite3
import tarfile
from types import SimpleNamespace

import pytest

from offload_service.core import CapacityError, Conflict, Worker
from research_workflows.common import atomic, load, sha
from research_workflows.finished_recovery import check_container, pending, recovery_ids

JOB = 'wf-completed-fixture'
ATTEMPT = 'offload-' + 'e' * 32
IMAGE = 'sha256:' + 'a' * 64


@pytest.fixture
def finished(tmp_path):
    with Worker(tmp_path / 'worker', [], backend='trusted-local', min_free_mb=1, max_store_mb=16) as worker:
        work = worker.root / 'work' / ATTEMPT
        work.mkdir(); (work / 'blobs').mkdir()
        payload = {'backend': 'docker', 'image_id': IMAGE, 'inputs': [], 'workflow_mounts': [],
                   'template': {'max_output_mb': 1, 'max_work_mb': 2, 'memory_mb': 128,
                                'cpus': .5, 'pids': 32, 'timeout_s': 60}}
        yield worker, work, payload


def archive(work, *, exit_code=0, identity=JOB):
    execution = {'job_id': identity, 'phase': 'exited', 'exit_code': exit_code}
    target = work / (JOB + '.result.tar.gz')
    with tarfile.open(target, 'w:gz') as stream:
        for name, raw in [('status.json', json.dumps(execution).encode()), ('artifacts/value.json', b'{"value":7}')]:
            member = tarfile.TarInfo(name); member.size = len(raw)
            stream.addfile(member, io.BytesIO(raw))
    atomic(work / 'status.json', {'job_id': JOB, 'phase': 'exited', 'result_sha256': sha(target)})
    return target


@pytest.mark.parametrize('exit_code', [0, 7])
def test_common_collection_keeps_real_success_or_failure(finished, exit_code):
    worker, work, payload = finished
    original = archive(work, exit_code=exit_code)
    state, receipt = worker._collect_completed_result(JOB, payload, work, exit_code, recovery=True)
    assert state == ('succeeded' if exit_code == 0 else 'failed')
    assert receipt['exit_code'] == exit_code and receipt['result_sha256'] == sha(original)
    assert sha(worker.root / 'results' / (JOB + '.tar.gz')) == sha(original)
    assert not list((worker.root / 'results').glob('.completed-recovery-*'))
    # A crash after copying bytes can repeat verification, never replace a conflict.
    assert worker._collect_completed_result(JOB, payload, work, exit_code, recovery=True) == (state, receipt)


@pytest.mark.parametrize('damage', ['hash', 'job', 'exit', 'running', 'existing_result', 'input'])
def test_recovery_rejects_changed_or_incomplete_results(finished, damage, monkeypatch):
    worker, work, payload = finished
    original = archive(work, identity='another-job' if damage == 'job' else JOB)
    if damage == 'hash':
        with original.open('ab') as f: f.write(b'changed')
    elif damage == 'running':
        value = load(work / 'status.json'); value['phase'] = 'running'; atomic(work / 'status.json', value)
    elif damage == 'existing_result':
        (worker.root / 'results' / (JOB + '.tar.gz')).write_bytes(b'conflict')
    elif damage == 'input':
        def changed(_): raise ValueError('input changed')
        monkeypatch.setattr(worker, 'verify_extra_inputs', changed)
    with pytest.raises((ValueError, RuntimeError, Conflict)):
        worker._collect_completed_result(JOB, payload, work, 3 if damage == 'exit' else 0, recovery=True)
    assert original.exists()
    assert not list((worker.root / 'results').glob('.completed-recovery-*'))


def test_recovery_reserves_actual_expansion_and_retains_archive_on_capacity_failure(finished):
    worker, work, payload = finished
    original = archive(work)
    worker.max_store_mb = 0
    with pytest.raises(CapacityError):
        worker._collect_completed_result(JOB, payload, work, 0, recovery=True)
    assert original.exists() and not list((worker.root / 'results').iterdir())


def inspection(root, payload):
    return {'Id': 'b'*64, 'Name': '/' + ATTEMPT, 'Image': IMAGE, 'RestartCount': 0,
        'State': {'Status': 'exited', 'Running': False, 'Paused': False, 'Restarting': False,
                  'Dead': False, 'OOMKilled': False, 'ExitCode': 0,
                  'StartedAt': '2026-09-11T20:00:00Z', 'FinishedAt': '2026-09-11T20:00:02Z'},
        'Config': {'Entrypoint': ['python'], 'Cmd': ['-I', '/work/runner.py', '/work/manifest.json'],
                   'WorkingDir': '/work', 'User': f'{os.getuid()}:{os.getgid()}' if os.name != 'nt' else '1000:1000'},
        'HostConfig': {'NetworkMode': 'none', 'ReadonlyRootfs': True, 'Privileged': False,
                       'CapAdd': None, 'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges'],
                       'Memory': 128<<20, 'MemorySwap': 128<<20, 'NanoCpus': 500000000, 'PidsLimit': 32},
        'Mounts': [{'Destination': '/work', 'Type': 'bind', 'Source': str(root / 'work' / ATTEMPT), 'RW': True},
                   {'Destination': '/work/blobs', 'Type': 'bind', 'Source': str(root / 'work' / ATTEMPT / 'blobs'), 'RW': False}]}


@pytest.mark.parametrize('damage', ['none', 'live', 'image', 'restart', 'workspace', 'writable_blob', 'network', 'limits', 'exit_type', 'timeout', 'command'])
def test_completed_container_identity_and_boundary(finished, damage):
    worker, work, payload = finished
    value = inspection(worker.root, payload)
    if damage == 'live': value['State'].update(Status='running', Running=True)
    if damage == 'image': value['Image'] = 'sha256:' + 'c'*64
    if damage == 'restart': value['RestartCount'] = 1
    if damage == 'workspace': value['Mounts'][0]['Source'] += '-other'
    if damage == 'writable_blob': value['Mounts'][1]['RW'] = True
    if damage == 'network': value['HostConfig']['NetworkMode'] = 'bridge'
    if damage == 'limits': value['HostConfig']['Memory'] *= 2
    if damage == 'exit_type': value['State']['ExitCode'] = False
    if damage == 'timeout': value['State']['FinishedAt'] = '2026-09-11T20:02:00Z'
    if damage == 'command': value['Config']['Cmd'] = ['other.py']
    if damage == 'none': assert check_container(worker.root, {'attempt': ATTEMPT}, payload, value) == 0
    else:
        with pytest.raises(ValueError): check_container(worker.root, {'attempt': ATTEMPT}, payload, value)


@pytest.mark.parametrize('value', [True, None, 'wf-one', ['wf-one', 'wf-one'], [{}], ['../escape']])
def test_recovery_is_an_explicit_unique_job_selection(value):
    with pytest.raises(ValueError): recovery_ids(value)


def test_recovery_default_is_empty_and_named_jobs_are_retained():
    assert recovery_ids([]) == frozenset()
    assert recovery_ids([JOB]) == {JOB}


@pytest.mark.parametrize('case', ['running', 'terminal', 'queued', 'preparing', 'cancelled', 'unselected', 'unknown', 'trusted'])
def test_pending_recovery_preserves_state_and_rejects_unselected_work(case):
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE jobs(id TEXT, state TEXT, attempt TEXT, cancel INTEGER)')
    state = {'terminal': 'succeeded', 'queued': 'queued', 'preparing': 'preparing'}.get(case, 'running')
    db.execute('INSERT INTO jobs VALUES(?,?,?,?)', (JOB, state, ATTEMPT, int(case == 'cancelled')))
    if case == 'unselected':
        db.execute('INSERT INTO jobs VALUES(?,?,?,?)', ('wf-unselected', 'running', 'offload-other', 0))
    worker = SimpleNamespace(db=db, backend='trusted-local' if case == 'trusted' else 'docker')
    before = [dict(row) for row in db.execute('SELECT * FROM jobs')]
    try:
        requested = {'wf-unknown'} if case == 'unknown' else {JOB}
        if case in ('running', 'terminal'):
            rows = pending(worker, requested)
            assert rows == ([] if case == 'terminal' else before)
        else:
            with pytest.raises(ValueError):
                pending(worker, requested)
        assert [dict(row) for row in db.execute('SELECT * FROM jobs')] == before
    finally:
        db.close()


@pytest.mark.parametrize('deduplicated', [False, True])
@pytest.mark.parametrize('damage', [False, True])
def test_recovery_checks_each_legacy_or_shared_volume_alias(finished, deduplicated, damage):
    worker, work, payload = finished
    identity = 'c' * 64
    targets = ['inputs/first', 'inputs/second']
    payload.update(workflow_input_transport='docker-volume',
                   workflow_mounts=[{'object_sha256': identity, 'target': t} for t in targets])
    value = inspection(worker.root, payload)
    objects = ([{'object_sha256': identity, 'target': targets[0], 'targets': targets}] if deduplicated
               else [{'object_sha256': identity, 'target': t} for t in targets])
    record = worker.root / 'workflow_input_transports' / ATTEMPT
    record.mkdir(parents=True)
    atomic(record / 'TRANSPORT.json', {'attempt': ATTEMPT, 'status': 'VERIFIED',
                                      'owned_volumes_removed': False, 'objects': objects})
    for i, target in enumerate(targets):
        value['Mounts'].append({'Destination': '/work/blobs/' + target, 'Type': 'volume',
                               'Name': ATTEMPT + '-input-' + str(0 if deduplicated else i), 'RW': False})
    if damage:
        value['Mounts'][-1]['Name'] = 'foreign-volume'
        with pytest.raises(ValueError, match='volume identity'):
            check_container(worker.root, {'attempt': ATTEMPT}, payload, value)
    else:
        assert check_container(worker.root, {'attempt': ATTEMPT}, payload, value) == 0


@pytest.mark.parametrize('transport', ['bind', 'docker-volume'])
@pytest.mark.skipif(not os.environ.get('OFFLOAD_RESEARCH_TEST_IMAGE'), reason='opt-in actual Docker completed-recovery test')
def test_actual_docker_completion_survives_controller_cleanup_failure(tmp_path, monkeypatch, transport):
    from research_workflows.worker import WorkflowWorker

    image = os.environ['OFFLOAD_RESEARCH_TEST_IMAGE']
    limits = {'cpus': .5, 'memory_mb': 256, 'pids': 64, 'max_work_mb': 16,
              'max_output_mb': 8, 'max_input_mb': 8, 'timeout_s': 90}
    config = {'enabled': True, 'input_transport': transport,
              'runtimes': {'python': {'image': image, **limits}},
              'capacity': {k: limits[k] for k in ('cpus', 'memory_mb', 'pids', 'max_work_mb')},
              'max_object_mb': 8, 'max_store_mb': 32, 'min_free_mb': 1}
    source = tmp_path / 'source'; source.mkdir()
    (source / 'main.py').write_text('from pathlib import Path\np=Path("artifacts");p.mkdir(exist_ok=True)\n(p/"value.json").write_text("{\\"value\\":7}")\n')
    root = tmp_path / 'worker'
    with WorkflowWorker(root, [], backend='docker', workflow_config=config,
                        concurrency=1, min_free_mb=1, max_store_mb=64) as first:
        capsule = first.workflows.objects.ingest(source)
        spec = {'schema': 'marketmaker.research_offload_workflow.v1', 'submission_id': 'completed-fixture',
                'jobs': [{'id': 'one', 'kind': 'producer', 'runtime': 'python', 'capsule': capsule,
                          'entrypoint': 'main.py', 'outputs': {'value': {'type': 'json', 'path': 'artifacts/value.json'}}}]}
        first.workflows.submit(spec); first.workflows.tick()
        job = first.workflows.status('completed-fixture')['nodes'][0]['job_id']
        def lost_control(_): raise RuntimeError('controlled cleanup connection loss')
        monkeypatch.setattr(first, '_remove_container', lost_control)
        first.process_next()
        before = first.status(job)
        assert before['state'] == 'running' and first.stop.is_set()
        attempt = before['receipt']['attempt'] if 'attempt' in before['receipt'] else first.db.execute('SELECT attempt FROM jobs WHERE id=?', (job,)).fetchone()[0]
        assert before['receipt']['termination_error'] == 'controlled cleanup connection loss'
        assert load(root / 'work' / attempt / 'status.json')['phase'] == 'exited'
    recovered_config = {**config, 'recover_completed': [job]}
    with WorkflowWorker(root, [], backend='docker', workflow_config=recovered_config,
                        concurrency=1, min_free_mb=1, max_store_mb=64) as second:
        result = second.status(job)
        assert result['state'] == 'succeeded'
        assert result['receipt']['attempt'] == attempt
        assert result['receipt']['recovered_completion']['new_execution'] is False
        assert result['receipt']['recovered_completion']['previous_receipt'] == before['receipt']
        second.workflows.tick()
        status = second.workflows.status('completed-fixture')
        assert status['state'] == 'completed' and status['nodes'][0]['attempt'] == 1
        output = status['nodes'][0]['outputs']['ports']['value']['object_sha256']
        directory, _ = second.workflows.objects.get(output)
        assert load(directory / 'data/value.json') == {'value': 7}
        if transport == 'docker-volume':
            assert result['receipt']['workflow_input_transport']['owned_volumes_removed']
        assert load(root / 'recoveries' / attempt / 'COMPLETED.json')['container_termination_confirmed']
