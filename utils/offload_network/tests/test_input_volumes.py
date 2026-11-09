"""Immutable staging, bounded reservations and attempt-scoped recovery."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from offload_service.core import CapacityError
from research_workflows import input_volumes as volumes
from research_workflows.common import atomic, load
from research_workflows.planner import plan
from research_workflows.simulation import configuration
from research_workflows.worker import WorkflowWorker


ATTEMPT = 'offload-' + 'a' * 32
OTHER = 'offload-' + 'b' * 32


@pytest.mark.parametrize('transport,backend', [('bad', 'docker'), (None, 'docker'),
                                             ('docker-volume', 'trusted-local')])
def test_transport_validation_precedes_creating_a_worker(tmp_path, transport, backend):
    config = configuration()
    config['input_transport'] = transport
    with pytest.raises(ValueError):
        WorkflowWorker(tmp_path / 'worker', [], backend=backend, workflow_config=config)
    assert not (tmp_path / 'worker').exists()


@pytest.mark.parametrize('damage', ['none', 'bytes', 'size', 'extra', 'symlink', 'hardlink'])
@pytest.mark.skipif(os.name == 'nt', reason='local execution of the Linux Docker helper requires POSIX')
def test_volume_helper_verifies_actual_bytes_inventory_and_link_types(tmp_path, damage):
    data = b'invented-input-data'
    root = tmp_path / 'stage' / '0'
    root.mkdir(parents=True)
    target = root / 'data.bin'
    target.write_bytes(data)
    expected = tmp_path / 'expected.json'
    atomic(expected, [{'index': 0, 'files': {'data.bin': {
        'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}}}])
    if damage == 'bytes': target.write_bytes(b'x' * len(data))
    if damage == 'size': target.write_bytes(data + b'x')
    if damage == 'extra': (root / 'extra').write_bytes(b'x')
    if damage == 'symlink': (root / 'link').symlink_to(target)
    if damage == 'hardlink': os.link(target, root / 'link')
    code = volumes.HELPER.replace("'/expected.json'", repr(str(expected))).replace(
        "'/stage'", repr(str(tmp_path / 'stage')))
    result = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True,
                            text=True, timeout=10)
    if damage == 'none':
        assert result.returncode == 0, result.stderr
        returned = json.loads(result.stdout)['objects'][0]
        assert (returned['status'], returned['bytes'], returned['files']) == ('VERIFIED', len(data), 1)
        assert target.read_bytes() == data
        assert target.stat().st_mode & 0o444 == 0o444
    else:
        assert result.returncode != 0
        assert 'staged' in result.stderr


@pytest.fixture
def accounting_worker(tmp_path):
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE jobs (attempt TEXT, state TEXT)')
    db.executemany('INSERT INTO jobs VALUES (?, ?)', [(ATTEMPT, 'running'), (OTHER, 'running')])
    worker = SimpleNamespace(root=tmp_path, db=db, db_lock=threading.RLock(),
                             input_volume_lock=threading.Lock(), max_store_mb=100)
    yield worker
    db.close()


def test_concurrent_volume_copies_are_reserved_against_store_budget(accounting_worker, monkeypatch):
    worker = accounting_worker
    monkeypatch.setattr(volumes, 'live_tree_bytes', lambda _: 0)
    monkeypatch.setattr(volumes.shutil, 'disk_usage', lambda _: SimpleNamespace(free=1 << 40))
    other = volumes.directory(worker, OTHER)
    other.mkdir(parents=True)
    atomic(other / 'TRANSPORT.json', {'reserved_bytes': 75 << 20, 'owned_volumes_removed': False})
    with pytest.raises(CapacityError, match='storage budget'):
        volumes.reserve_inputs(worker, ATTEMPT, 50 << 20, 0, {})
    atomic(other / 'TRANSPORT.json', {'reserved_bytes': 75 << 20, 'owned_volumes_removed': True})
    volumes.reserve_inputs(worker, ATTEMPT, 50 << 20, 0, {})
    assert load(volumes.directory(worker, ATTEMPT) / 'TRANSPORT.json')['reserved_bytes'] == 50 << 20


def test_physical_reserve_is_checked_before_copy(accounting_worker, monkeypatch):
    monkeypatch.setattr(volumes, 'live_tree_bytes', lambda _: 0)
    monkeypatch.setattr(volumes.shutil, 'disk_usage', lambda _: SimpleNamespace(free=99))
    with pytest.raises(CapacityError, match='host space'):
        volumes.reserve_inputs(accounting_worker, ATTEMPT, 50, 50, {})
    assert not (volumes.directory(accounting_worker, ATTEMPT) / 'TRANSPORT.json').exists()


def test_input_aliases_keep_the_logical_input_limit(accounting_worker):
    worker = accounting_worker
    worker.stop = threading.Event()
    calls = []
    def get(identity):
        calls.append(identity)
        return worker.root / 'object', {'files': {'data.bin': {'bytes': 600000, 'sha256': 'a' * 64}}}
    worker.workflows = SimpleNamespace(objects=SimpleNamespace(get=get))
    payload = {'template': {'timeout_s': 300, 'max_input_mb': 1, 'max_work_mb': 1}}
    with pytest.raises(CapacityError, match='per-job input budget'):
        volumes.stage(worker, worker.root / 'work', ATTEMPT, payload,
                      [('a' * 64, 'inputs/first'), ('a' * 64, 'inputs/second')])
    assert calls == ['a' * 64]
    receipt = load(volumes.directory(worker, ATTEMPT) / 'TRANSPORT.json')
    assert receipt['logical_input_bytes'] == 1200000
    assert receipt['status'] == 'FAILED' and 'reserved_bytes' not in receipt


@pytest.mark.parametrize('damage', ['owner', 'attempt', 'name'])
def test_cleanup_rejects_foreign_volumes_and_never_uses_global_removal(tmp_path, damage):
    calls = []
    worker = SimpleNamespace(root=tmp_path)
    name = ATTEMPT + '-input-0' if damage != 'name' else 'unrelated-volume'
    labels = {volumes.OWNER_LABEL: volumes.owner_id(worker), volumes.ATTEMPT_LABEL: ATTEMPT}
    if damage == 'owner': labels[volumes.OWNER_LABEL] = 'foreign'
    if damage == 'attempt': labels[volumes.ATTEMPT_LABEL] = OTHER
    def docker(*args):
        calls.append(args)
        if args[:2] == ('volume', 'ls'): return name
        if args[:2] == ('volume', 'inspect'): return json.dumps([{'Labels': labels}])
        pytest.fail('foreign volume reached removal')
    worker._docker = docker
    with pytest.raises(ValueError): volumes.cleanup(worker, ATTEMPT)
    assert f'label={volumes.OWNER_LABEL}={volumes.owner_id(worker)}' in calls[0]
    assert f'label={volumes.ATTEMPT_LABEL}={ATTEMPT}' in calls[0]


def test_cleanup_recovers_owned_volumes_without_a_staging_receipt(tmp_path):
    calls = []
    worker = SimpleNamespace(root=tmp_path)
    name = ATTEMPT + '-input-0'
    def docker(*args):
        calls.append(args)
        if args[:2] == ('volume', 'ls'): return name
        if args[:2] == ('volume', 'inspect'):
            return json.dumps([{'Labels': {volumes.OWNER_LABEL: volumes.owner_id(worker),
                                           volumes.ATTEMPT_LABEL: ATTEMPT}}])
        assert args == ('volume', 'rm', name)
        return name
    worker._docker = docker
    volumes.cleanup(worker, ATTEMPT)
    assert calls[-1] == ('volume', 'rm', name)


def docker_worker(root, transport):
    config = configuration(os.environ['OFFLOAD_RESEARCH_TEST_IMAGE'])
    config['input_transport'] = transport
    config['runtimes']['python'].update(timeout_s=300, memory_mb=256, cpus=0.5)
    return WorkflowWorker(root, [], backend='docker', workflow_config=config,
                          concurrency=1, min_free_mb=0, max_store_mb=256)


def admit_invented(worker, root):
    code = root / 'code'
    code.mkdir()
    (code / 'main.py').write_text("import pathlib,sys\npathlib.Path(sys.argv[1]).write_text('{}')\n")
    target = root / 'plan'
    plan({'schema': 'marketmaker.research_offload_workflow.v1', 'submission_id': 'input-test',
          'jobs': [{'id': 'one', 'kind': 'producer', 'runtime': 'python',
                    'capsule': {'source': str(code)}, 'entrypoint': 'main.py',
                    'args': ['{output.report}'],
                    'outputs': {'report': {'type': 'json', 'path': 'artifacts/report.json'}}}]}, target)
    from research_workflows.common import sha
    for archive in (target / 'objects').glob('*.tar.gz'):
        ident = sha(archive)
        worker.workflows.objects.begin(ident, archive.stat().st_size)
        worker.workflows.objects.append(ident, 0, archive.read_bytes())
        worker.workflows.objects.commit(ident)
    worker.workflows.submit(load(target / 'WORKFLOW.json'))
    worker.workflows.tick()
    return worker.workflows.status('input-test')['nodes'][0]['job_id']


@pytest.mark.skipif(not os.environ.get('OFFLOAD_RESEARCH_TEST_IMAGE'), reason='opt-in actual Docker recovery test')
def test_actual_docker_recovery_uses_persisted_transport_and_preserves_foreign_volume(tmp_path):
    own = foreign = attempt = None
    worker = docker_worker(tmp_path / 'worker', 'docker-volume')
    try:
        job_id = admit_invented(worker, tmp_path)
        claim = worker._claim()
        assert claim[0] == job_id
        _, attempt, payload = claim
        assert payload['workflow_input_transport'] == 'docker-volume'
        own, foreign = attempt + '-input-0', attempt + '-input-99'
        for name, owner in [(own, volumes.owner_id(worker)), (foreign, 'foreign-owner')]:
            worker._docker('volume', 'create', '--label', f'{volumes.OWNER_LABEL}={owner}',
                           '--label', f'{volumes.ATTEMPT_LABEL}={attempt}', name)
        worker._docker('container', 'create', '--name', attempt, '--network=none',
                       '--read-only', '--cap-drop=ALL', payload['image_id'], 'python', '-c', 'pass')
        # No helper result/transport receipt exists: model a crash after Docker
        # allocation, using a normally admitted and durably claimed job.
        assert not (volumes.directory(worker, attempt) / 'TRANSPORT.json').exists()
        worker.close()
        worker = docker_worker(tmp_path / 'worker', 'bind')
        assert worker.status(job_id)['state'] == 'interrupted'
        with pytest.raises(RuntimeError): worker._docker('volume', 'inspect', own)
        with pytest.raises(RuntimeError): worker._docker('container', 'inspect', attempt)
        assert json.loads(worker._docker('volume', 'inspect', foreign))[0]['Name'] == foreign
    finally:
        worker.close()
        if attempt:
            subprocess.run(['docker', 'container', 'rm', '-f', attempt], capture_output=True, timeout=30)
        for name in (own, foreign):
            if name:
                subprocess.run(['docker', 'volume', 'rm', name], capture_output=True, timeout=30)


@pytest.mark.parametrize('fault', ['corrupt-copy', 'cancel', 'stop'])
@pytest.mark.skipif(not os.environ.get('OFFLOAD_RESEARCH_TEST_IMAGE'), reason='opt-in actual Docker failure test')
def test_actual_staging_failure_or_stop_cleans_up_before_job_execution(tmp_path, monkeypatch, fault):
    original_run = subprocess.run
    corrupted = tmp_path / 'main.py'
    original_code = "import pathlib,sys\npathlib.Path(sys.argv[1]).write_text('{}')\n"
    corrupted.write_text('x' * len(original_code))
    copied = []
    with docker_worker(tmp_path / 'worker', 'docker-volume') as worker:
        job_id = admit_invented(worker, tmp_path)
        def run(args, **kwargs):
            result = original_run(args, **kwargs)
            if args[:2] == ['docker', 'cp'] and not copied:
                copied.append(args[-1])
                if fault == 'corrupt-copy':
                    replacement = original_run(['docker', 'cp', str(corrupted), args[-1] + '/main.py'],
                                               capture_output=True, text=True, timeout=30)
                    assert replacement.returncode == 0, replacement.stderr
                elif fault == 'cancel':
                    worker.cancel(job_id)
                else:
                    worker.stop.set()
            return result
        monkeypatch.setattr(volumes.subprocess, 'run', run)
        result = worker.process_next()
        assert copied
        assert result['state'] == {'corrupt-copy': 'failed', 'cancel': 'cancelled', 'stop': 'interrupted'}[fault]
        receipt = result['receipt']['workflow_input_transport']
        assert receipt['owned_volumes_removed'] is True
        assert receipt['status'] == ('FAILED' if fault == 'corrupt-copy' else 'STOPPED')
        if fault == 'corrupt-copy': assert 'staged file hash differs' in receipt['error']
        assert not (worker.root / 'work' / result['receipt']['attempt'] / 'artifacts/report.json').exists()
        assert worker._docker('volume', 'ls', '--quiet', '--filter',
                              f'label={volumes.OWNER_LABEL}={volumes.owner_id(worker)}') == ''


@pytest.mark.skipif(not os.environ.get('OFFLOAD_RESEARCH_TEST_IMAGE'), reason='opt-in actual Docker alias test')
def test_repeated_object_uses_one_verified_volume_with_two_read_only_mounts(tmp_path):
    from research_workflows.common import sha
    code, source = tmp_path / 'code', tmp_path / 'source'
    code.mkdir(); source.mkdir()
    (source / 'value.bin').write_bytes(b'invented repeated source')
    (code / 'main.py').write_text(
        "import json,os,pathlib,sys\n"
        "a,b,out=map(pathlib.Path,sys.argv[1:])\n"
        "sa,sb=a.stat(),b.stat()\n"
        "row={'equal_bytes':a.read_bytes()==b.read_bytes(),"
        "'same_file':(sa.st_dev,sa.st_ino)==(sb.st_dev,sb.st_ino),"
        "'read_only':[bool(os.statvfs(p).f_flag & os.ST_RDONLY) for p in (a,b)]}\n"
        "out.write_text(json.dumps(row))\n")
    target = tmp_path / 'plan'
    plan({'schema': 'marketmaker.research_offload_workflow.v1', 'submission_id': 'repeated-input',
          'jobs': [{'id': 'one', 'kind': 'producer', 'runtime': 'python',
                    'capsule': {'source': str(code)}, 'entrypoint': 'main.py',
                    'inputs': {name: {'mode': 'bundle', 'source': str(source)} for name in ('first', 'second')},
                    'args': ['{input.first}/value.bin', '{input.second}/value.bin', '{output.report}'],
                    'outputs': {'report': {'type': 'json', 'path': 'artifacts/report.json'}}}]}, target)
    with docker_worker(tmp_path / 'worker', 'docker-volume') as worker:
        for archive in (target / 'objects').glob('*.tar.gz'):
            ident, data = sha(archive), archive.read_bytes()
            worker.workflows.objects.begin(ident, len(data))
            worker.workflows.objects.append(ident, 0, data)
            worker.workflows.objects.commit(ident)
        worker.workflows.submit(load(target / 'WORKFLOW.json'))
        worker.workflows.tick()
        result = worker.process_next()
        assert result['state'] == 'succeeded', result
        record = result['receipt']['workflow_input_transport']
        assert len(record['objects']) == 2
        aliases = [r for r in record['objects'] if len(r['targets']) == 2]
        assert len(aliases) == 1
        assert sorted(aliases[0]['targets']) == ['inputs/first', 'inputs/second']
        assert record['logical_input_bytes'] == record['reserved_bytes'] + aliases[0]['bytes']
        assert record['owned_volumes_removed'] is True
        report = load(worker.root / 'work' / result['receipt']['attempt'] / 'artifacts/report.json')
        assert report == {'equal_bytes': True, 'same_file': True, 'read_only': [True, True]}
        assert worker._docker('volume', 'ls', '--quiet', '--filter',
                              f'label={volumes.OWNER_LABEL}={volumes.owner_id(worker)}') == ''
