"""A timed-out Docker create must not release inputs before the daemon settles."""
import json
import os
import subprocess

import pytest

from offload_service.core import Template, Worker


IMAGE = 'sha256:' + 'a' * 64


@pytest.fixture
def claimed(tmp_path):
    script = tmp_path / 'never_run.py'
    script.write_text("raise RuntimeError('a failed create must not execute the model')\n")
    template = Template('create-test', script, cpus=.5, memory_mb=128,
                        max_input_mb=1, max_work_mb=8, max_output_mb=4, timeout_s=30)
    with Worker(tmp_path / 'worker', [template], backend='trusted-local', min_free_mb=0) as worker:
        # Exercise normal admission/sealing and durable claims, with only Docker
        # observations substituted. No real Docker operation occurs in this fixture.
        worker.backend = 'docker'
        worker.images[template.name] = IMAGE
        worker.submit({'job_id': 'timed-create', 'template': template.name})
        yield worker, worker._claim()


def inspection(worker, attempt):
    return {'Id': 'b' * 64, 'Name': '/' + attempt, 'Image': IMAGE,
            'Config': {'Entrypoint': ['python'],
                       'Cmd': ['-I', '/work/runner.py', '/work/manifest.json'],
                       'WorkingDir': '/work'},
            'State': {'Status': 'created', 'Running': False, 'Pid': 0},
            'Mounts': [{'Destination': '/work', 'Type': 'bind', 'RW': True,
                        'Source': str(worker.root / 'work' / attempt)}]}


def timed_create(monkeypatch, worker, observed, removed):
    calls = []

    def docker(*args, **kwargs):
        calls.append(args)
        if args[:2] == ('container', 'create'):
            raise subprocess.TimeoutExpired(['docker', *args], 60)
        assert args[:2] == ('container', 'inspect')
        if observed[0] is None:
            raise RuntimeError('No such container')
        return json.dumps([observed[0]])

    monkeypatch.setattr(worker, '_docker', docker)
    monkeypatch.setattr(worker, '_remove_container', removed.append)
    return calls


def test_missing_after_create_timeout_retains_attempt_and_cleanup_reservation(claimed, monkeypatch):
    worker, claim = claimed
    job, attempt, _ = claim
    observed, removed = [None], []
    calls = timed_create(monkeypatch, worker, observed, removed)
    worker._execute(*claim)
    before = worker.status(job)
    assert before['state'] == 'running' and worker.stop.is_set()
    assert before['receipt']['docker_create_uncertain'] is True
    assert 'docker_create_resolution' not in before['receipt']
    assert 'No such container' in before['receipt']['termination_error']
    assert removed == []
    assert worker._claim() is None
    with pytest.raises(RuntimeError, match='No such container'):
        worker._recover()
    assert worker.status(job) == before and removed == []
    # The same daemon request becomes visible later. Recover it without creating
    # or starting another workload and retain the original unresolved receipt.
    observed[0] = inspection(worker, attempt)
    worker._recover()
    after = worker.status(job)
    assert after['state'] == 'interrupted' and removed == [attempt]
    recovery = after['receipt']['docker_create_recovery']
    assert recovery['previous_receipt'] == before['receipt']
    assert recovery['new_execution'] is False
    assert sum(args[:2] == ('container', 'create') for args in calls) == 1
    assert not (worker.root / 'work' / attempt / 'status.json').exists()


def test_observed_create_timeout_is_cleaned_before_terminal_failure(claimed, monkeypatch):
    worker, claim = claimed
    job, attempt, _ = claim
    removed = []
    timed_create(monkeypatch, worker, [inspection(worker, attempt)], removed)
    worker._execute(*claim)
    result = worker.status(job)
    assert result['state'] == 'failed' and not worker.stop.is_set()
    assert removed == [attempt]
    assert result['receipt']['docker_create_resolution']['container_id'] == 'b' * 64
    assert 'TimeoutExpired' in result['receipt']['error']
    assert not (worker.root / 'work' / attempt / 'status.json').exists()


def test_recovery_retains_positive_creation_before_uncertain_removal(claimed, monkeypatch):
    worker, claim = claimed
    job, attempt, _ = claim
    observed, removed = [None], []
    timed_create(monkeypatch, worker, observed, removed)
    worker._execute(*claim)
    observed[0] = inspection(worker, attempt)

    def removal_response_lost(name):
        observed[0] = None
        raise subprocess.TimeoutExpired(['docker', 'container', 'rm', name], 30)

    monkeypatch.setattr(worker, '_remove_container', removal_response_lost)
    with pytest.raises(subprocess.TimeoutExpired):
        worker._recover()
    retained = worker.status(job)
    assert retained['state'] == 'running'
    assert retained['receipt']['docker_create_resolution']['container_id'] == 'b' * 64
    monkeypatch.setattr(worker, '_remove_container', removed.append)
    worker._recover()
    assert worker.status(job)['state'] == 'interrupted' and removed == [attempt]


@pytest.mark.parametrize('damage', ['id', 'name', 'image', 'entrypoint', 'command', 'directory', 'mount'])
def test_unrelated_inspection_cannot_release_timed_out_create(claimed, monkeypatch, damage):
    worker, claim = claimed
    job, attempt, _ = claim
    found = inspection(worker, attempt)
    if damage == 'id': found['Id'] = 'invalid'
    if damage == 'name': found['Name'] += '-other'
    if damage == 'image': found['Image'] = 'sha256:' + 'c' * 64
    if damage == 'entrypoint': found['Config']['Entrypoint'] = ['sh']
    if damage == 'command': found['Config']['Cmd'] = ['another.py']
    if damage == 'directory': found['Config']['WorkingDir'] = '/other'
    if damage == 'mount': found['Mounts'][0]['Source'] += '-other'
    removed = []
    timed_create(monkeypatch, worker, [found], removed)
    worker._execute(*claim)
    assert worker.status(job)['state'] == 'running' and worker.stop.is_set()
    assert removed == []


@pytest.mark.skipif(not os.environ.get('OFFLOAD_RESEARCH_TEST_IMAGE'),
                    reason='opt-in actual Docker create-timeout recovery')
def test_actual_docker_delayed_create_keeps_verified_volumes_until_recovery(tmp_path, monkeypatch):
    from research_workflows.common import load, atomic
    from research_workflows.simulation import configuration
    from research_workflows.worker import WorkflowWorker

    config = configuration(os.environ['OFFLOAD_RESEARCH_TEST_IMAGE'])
    config['input_transport'] = 'docker-volume'
    # The first actual-host probe spent its 300-second setup budget during a
    # 63-byte Docker copy, before reaching this controlled fault. Keep every
    # check and allow a separately declared longer setup window under that load.
    config['runtimes']['python'].update(timeout_s=900, memory_mb=256, cpus=.5)
    root = tmp_path / 'worker'
    code = tmp_path / 'code'; code.mkdir()
    (code / 'main.py').write_text("raise RuntimeError('this controlled failed create never runs')\n")
    kwargs = dict(backend='docker', workflow_config=config, concurrency=1,
                  min_free_mb=0, max_store_mb=256)
    with WorkflowWorker(root, [], **kwargs) as first:
        capsule = first.workflows.objects.ingest(code)
        first.workflows.submit({'schema': 'marketmaker.research_offload_workflow.v1',
            'submission_id': 'delayed-create-fixture', 'jobs': [
                {'id': 'one', 'kind': 'producer', 'runtime': 'python', 'capsule': capsule,
                 'entrypoint': 'main.py', 'outputs': {
                     'value': {'type': 'json', 'path': 'artifacts/value.json'}}}]})
        first.workflows.tick()
        claim = first._claim(); job, attempt, payload = claim
        original = first._docker
        seen = {}

        def delayed(*args, **kwargs):
            if args[:2] == ('container', 'create'):
                seen['container_id'] = original(*args, **kwargs)
                raise subprocess.TimeoutExpired(['docker', *args], 60)
            if args[:2] == ('container', 'inspect'):
                raise RuntimeError('controlled temporary absence after create timeout')
            return original(*args, **kwargs)

        monkeypatch.setattr(first, '_docker', delayed)
        first._execute(*claim)
        before = first.status(job)
        assert before['state'] == 'running' and first.stop.is_set()
        assert before['receipt']['docker_create_uncertain'] is True
        transport = root / 'workflow_input_transports' / attempt / 'TRANSPORT.json'
        staged = load(transport)
        assert staged['status'] == 'VERIFIED' and not staged.get('owned_volumes_removed', False)
        actual = json.loads(original('container', 'inspect', attempt))[0]
        assert actual['Id'] == seen['container_id'] and actual['State']['Status'] == 'created'
        assert actual['State']['Pid'] == 0
        for index in range(len(staged['objects'])):
            volume = json.loads(original('volume', 'inspect', attempt + '-input-' + str(index)))[0]
            assert volume['Labels']['marketmaker.offload.attempt'] == attempt
        assert not (root / 'work' / attempt / 'status.json').exists()
        atomic(tmp_path / 'BEFORE_RECOVERY.json', {'receipt': before, 'transport': staged,
                                                  'container_id': actual['Id']})
    with WorkflowWorker(root, [], **kwargs) as recovered:
        after = recovered.status(job)
        assert after['state'] == 'interrupted'
        assert after['receipt']['docker_create_recovery']['previous_receipt'] == before['receipt']
        assert after['receipt']['docker_create_recovery']['new_execution'] is False
        assert load(transport)['owned_volumes_removed'] is True
        with pytest.raises(RuntimeError):
            recovered._docker('container', 'inspect', attempt)
        for index in range(len(staged['objects'])):
            with pytest.raises(RuntimeError):
                recovered._docker('volume', 'inspect', attempt + '-input-' + str(index))
        atomic(tmp_path / 'ACTUAL_DOCKER_RESULT.json', {
            'status': 'TIMED_OUT_CREATE_RECONCILED_WITHOUT_STARTING_WORKLOAD',
            'before': before, 'after': after, 'input_transport': 'docker-volume',
            'container_id': actual['Id'], 'image': payload['image_id'],
            'labels_preserved_until_recovery': True, 'model_executed': False})
