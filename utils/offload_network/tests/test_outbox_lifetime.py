"""Cleanup cannot delete archives still needed by an unacknowledged enqueue."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from lib.file_lock import file_lock
from research_workflows.common import atomic, load, sha
import research_workflows.project_queue as pq
from research_workflows.project_queue import ProjectQueue
from tests.test_project_return import project as project_fixture
from tests.test_research_workflows import api as api_fixture, worker as worker_fixture, compiled, drive
from tests.test_source_sync_concurrency import freeze_at

project, api, worker = project_fixture, api_fixture, worker_fixture


@pytest.fixture
def completed_source(tmp_path, worker, project):
    config, origins = project
    _, old = freeze_at(tmp_path / 'old', worker, 'old-result')
    with ProjectQueue(config) as queue:
        row = queue.enqueue(old, 'local', origins)
        required = set(json.loads(row['objects']))
        queue.sync(now=True)
    assert drive(worker, 'old-result')['state'] == 'completed'
    with ProjectQueue(config) as queue:
        assert queue.sync(now=True)[0]['phase'] == 'completed'
        cache = queue._stage_source_outbox(old, required)
        assert {p.stem.removesuffix('.tar') for p in cache.glob('*.tar.gz')} == required
    return config, origins, old, required, cache


def cleanup(queue):
    queue._release_outbox(queue.project.bulk(), completing='old-result')


@pytest.mark.parametrize('pause', ['retained_verification', 'outbox_hash'])
@pytest.mark.parametrize('new_reference', ['enqueue_pin', 'committed_request'])
def test_cleanup_allows_new_admission_and_rechecks_late_references(
    tmp_path, worker, completed_source, monkeypatch, pause, new_reference
):
    """Exercise sync, including its lock scope, while slow cleanup is in flight."""
    import research_workflows.client as client

    config, origins, _, required, cache = completed_source
    _, new = freeze_at(tmp_path / 'late', worker, 'late-reference')
    entered, release = threading.Event(), threading.Event()
    local = threading.local()
    release_outbox, verify, hashing = ProjectQueue._release_outbox, client.verify_object, pq.sha
    checked, errors = [], []

    def wait_here(ident):
        if getattr(local, 'cleaning', False) and not entered.is_set():
            checked.append(ident)
            entered.set()
            assert release.wait(15), 'test did not release cleanup verification'

    def cleanup_scope(self, *args, **kwargs):
        local.cleaning = True
        try:
            return release_outbox(self, *args, **kwargs)
        finally:
            local.cleaning = False

    def verify_slow(directory, ident, **kwargs):
        if pause == 'retained_verification':
            wait_here(ident)
        return verify(directory, ident, **kwargs)

    def hash_slow(path):
        if pause == 'outbox_hash' and Path(path).parent == cache:
            wait_here(Path(path).name.removesuffix('.tar.gz'))
        return hashing(path)

    def synchronize():
        try:
            with ProjectQueue(config) as queue:
                queue.sync(now=True, workflows=['old-result'])
        except BaseException as error:
            errors.append(error)

    monkeypatch.setattr(ProjectQueue, '_release_outbox', cleanup_scope)
    monkeypatch.setattr(client, 'verify_object', verify_slow)
    monkeypatch.setattr(pq, 'sha', hash_slow)
    with ProjectQueue(config) as queue:
        # Reconcile the same verified delivery after an interrupted cleanup.
        queue._update('old-result', phase='awaiting_ack')
    thread = threading.Thread(target=synchronize, daemon=True)
    thread.start()
    try:
        assert entered.wait(10)
        ident = checked[0]
        assert ident in required
        with ProjectQueue(config) as queue:
            with file_lock(queue.root / 'queue.lock', timeout=0):
                assert queue._row('old-result')['phase'] == 'awaiting_ack'
            # Workflow ownership remains fenced even though queue.lock is free.
            with pytest.raises(TimeoutError):
                queue.retry('old-result')
            if new_reference == 'committed_request':
                row = queue.enqueue(new, 'local', origins)
                assert ident in json.loads(row['objects'])
                release.set()
                thread.join(timeout=15)
            else:
                with queue._retain_outbox_during_enqueue({ident}):
                    release.set()
                    thread.join(timeout=15)
                    assert (cache / (ident + '.tar.gz')).is_file()
            assert not thread.is_alive() and not errors
            assert queue._row('old-result')['phase'] == 'completed'
            assert (cache / (ident + '.tar.gz')).is_file()
    finally:
        release.set()
        thread.join(timeout=15)


@pytest.mark.parametrize('change', ['replace_outbox', 'replace_retained_archive', 'replace_manifest'])
def test_cleanup_refuses_changed_identity_after_verification(completed_source, monkeypatch, change):
    import research_workflows.client as client

    config, _, _, _, cache = completed_source
    verify, changed = client.verify_object, []

    def mutate(directory, ident, **kwargs):
        result = verify(directory, ident, **kwargs)
        if not changed:
            path = {'replace_outbox': cache / (ident + '.tar.gz'),
                    'replace_retained_archive': Path(directory) / 'archive.tar.gz',
                    'replace_manifest': Path(directory) / 'OBJECT.json'}[change]
            replacement = path.with_name(path.name + '.replacement')
            replacement.write_bytes(path.read_bytes())
            os.replace(replacement, path)
            changed.append(ident)
        return result

    monkeypatch.setattr(client, 'verify_object', mutate)
    with ProjectQueue(config) as queue:
        with pytest.raises(ValueError, match='changed during verification'):
            cleanup(queue)
    assert len(changed) == 1
    assert sha(cache / (changed[0] + '.tar.gz')) == changed[0]


def test_failed_cleanup_retains_awaiting_ack_and_resumes_without_execution(completed_source, worker, monkeypatch):
    import research_workflows.client as client

    config, _, _, required, cache = completed_source
    original, verify = ProjectQueue._release_outbox, client.verify_object
    attempts = [tuple(row) for row in worker.db.execute('SELECT id,attempt FROM jobs ORDER BY id')]

    def fail_cleanup(self, *args, **kwargs):
        def fail(*args, **kwargs):
            raise ValueError('synthetic retained archive corruption')
        with monkeypatch.context() as patch:
            patch.setattr(client, 'verify_object', fail)
            return original(self, *args, **kwargs)

    monkeypatch.setattr(ProjectQueue, '_release_outbox', fail_cleanup)
    with ProjectQueue(config) as queue:
        queue._update('old-result', phase='awaiting_ack')
        row = queue.sync(now=True)[0]
        assert row['phase'] == 'awaiting_ack' and row['state'] == 'needs_attention'
        assert 'synthetic retained archive corruption' in row['error']
        assert {p.name.removesuffix('.tar.gz') for p in cache.glob('*.tar.gz')} == required
        monkeypatch.setattr(ProjectQueue, '_release_outbox', original)
        assert client.verify_object is verify
        queue.retry('old-result')
        assert queue.sync(now=True)[0]['phase'] == 'completed'
        assert not list(cache.glob('*.tar.gz'))
    assert [tuple(row) for row in worker.db.execute('SELECT id,attempt FROM jobs ORDER BY id')] == attempts


@pytest.mark.parametrize('pause', ['before_stage', 'after_stage', 'after_hash'])
def test_live_enqueue_survives_cleanup_and_releases_after_completion(
    tmp_path, worker, completed_source, monkeypatch, pause
):
    config, origins, _, required, cache = completed_source
    _, new = freeze_at(tmp_path / 'new', worker, 'new-result')
    entered, release = threading.Event(), threading.Event()
    original_stage, original_sha = ProjectQueue._stage_source_outbox, pq.sha
    staged, errors, receipts = [], [], []

    def wait_here():
        entered.set()
        assert release.wait(15), 'cleanup did not release the live enqueue'

    def stage(self, plan, required):
        if pause == 'before_stage':
            wait_here()
        result = original_stage(self, plan, required)
        staged.append(True)
        if pause == 'after_stage':
            wait_here()
        return result

    def hashing(path):
        value = original_sha(path)
        if (pause == 'after_hash' and staged and not entered.is_set()
                and threading.current_thread().name == 'live-enqueue' and Path(path).parent == cache):
            wait_here()
        return value

    def enqueue():
        try:
            with ProjectQueue(config) as queue:
                receipts.append(queue.enqueue_receipt(new, 'local', origins, lock_timeout=5))
        except BaseException as error:
            errors.append(error)

    monkeypatch.setattr(ProjectQueue, '_stage_source_outbox', stage)
    monkeypatch.setattr(pq, 'sha', hashing)
    thread = threading.Thread(target=enqueue, name='live-enqueue', daemon=True)
    thread.start()
    try:
        assert entered.wait(10)
        before = {p.name: (p.stat().st_ino, sha(p)) for p in cache.glob('*.tar.gz')}
        assert len(before) == len(required)
        with ProjectQueue(config) as queue:
            cleanup(queue)
        assert {p.name: (p.stat().st_ino, sha(p)) for p in cache.glob('*.tar.gz')} == before
    finally:
        release.set()
        thread.join(timeout=15)
    assert not thread.is_alive() and not errors
    assert len(receipts) == 1 and receipts[0]['queue_acknowledged'] is True
    monkeypatch.setattr(ProjectQueue, '_stage_source_outbox', original_stage)
    monkeypatch.setattr(pq, 'sha', original_sha)
    with ProjectQueue(config) as queue:
        assert not list((queue.root / 'outbox-enqueues').glob('*.json'))
        assert len(queue.status()) == 2
        cleanup(queue)  # The committed request now owns the same archives.
        assert len(list(cache.glob('*.tar.gz'))) == len(required)
        queue.sync(now=True)
    assert drive(worker, 'new-result')['state'] == 'completed'
    with ProjectQueue(config) as queue:
        assert queue.sync(now=True)[1]['phase'] == 'completed'
        assert not list(cache.glob('*.tar.gz'))


def test_one_failed_enqueue_does_not_release_another_live_enqueue(
    tmp_path, worker, completed_source, monkeypatch
):
    config, origins, _, required, cache = completed_source
    _, first = freeze_at(tmp_path / 'first', worker, 'failed-enqueue')
    _, second = freeze_at(tmp_path / 'second', worker, 'live-enqueue')
    ready = [threading.Event(), threading.Event()]
    release = [threading.Event(), threading.Event()]
    errors, receipts = {}, {}
    original = ProjectQueue._stage_source_outbox

    def staging(self, plan, required):
        result = original(self, plan, required)
        index = 0 if Path(plan) == first else 1
        ready[index].set()
        assert release[index].wait(15)
        if index == 0:
            raise OSError('synthetic source failure after staging')
        return result

    def enqueue(index, plan):
        try:
            with ProjectQueue(config) as queue:
                receipts[index] = queue.enqueue_receipt(plan, 'local', origins, lock_timeout=5)
        except BaseException as error:
            errors[index] = error

    monkeypatch.setattr(ProjectQueue, '_stage_source_outbox', staging)
    threads = [threading.Thread(target=enqueue, args=(i, plan), daemon=True)
               for i, plan in enumerate((first, second))]
    try:
        for thread in threads:
            thread.start()
        assert all(event.wait(10) for event in ready)
        release[0].set()
        threads[0].join(timeout=10)
        assert isinstance(errors.get(0), OSError) and 'synthetic source failure' in str(errors[0])
        with ProjectQueue(config) as queue:
            cleanup(queue)
            assert len(list(cache.glob('*.tar.gz'))) == len(required)
            assert len(list((queue.root / 'outbox-enqueues').glob('*.json'))) == 1
    finally:
        for event in release:
            event.set()
        for thread in threads:
            thread.join(timeout=15)
    assert all(not thread.is_alive() for thread in threads)
    assert set(errors) == {0} and receipts[1]['queue_acknowledged'] is True


def test_cleanup_releases_unrelated_archives_while_enqueue_is_live(
    tmp_path, worker, completed_source, monkeypatch
):
    config, origins, _, required, cache = completed_source
    other = tmp_path / 'other'
    other.mkdir()

    def edit(raw):
        code = other / 'code/job.py'
        code.write_text(code.read_text() + '\n# distinct completed source\n')
        raw.update(submission_id='other-result', return_policy={'include_inputs': True})

    _, previous = compiled(other, worker, edit=edit)
    with ProjectQueue(config) as queue:
        row = queue.enqueue(previous, 'local', origins)
        other_objects = set(json.loads(row['objects']))
        queue.sync(now=True)
    assert drive(worker, 'other-result')['state'] == 'completed'
    with ProjectQueue(config) as queue:
        assert queue.sync(now=True)[1]['phase'] == 'completed'
        queue._stage_source_outbox(previous, other_objects)
    exclusive = other_objects - required
    assert exclusive
    _, new = freeze_at(tmp_path / 'new', worker, 'live-enqueue')
    entered, release = threading.Event(), threading.Event()
    original, errors = ProjectQueue._stage_source_outbox, []

    def pause(self, plan, objects):
        result = original(self, plan, objects)
        entered.set()
        assert release.wait(15)
        return result

    def enqueue():
        try:
            with ProjectQueue(config) as queue:
                queue.enqueue_receipt(new, 'local', origins, lock_timeout=5)
        except BaseException as error:
            errors.append(error)

    monkeypatch.setattr(ProjectQueue, '_stage_source_outbox', pause)
    thread = threading.Thread(target=enqueue, daemon=True)
    thread.start()
    try:
        assert entered.wait(10)
        with ProjectQueue(config) as queue:
            cleanup(queue)
        assert all(sha(cache / (ident + '.tar.gz')) == ident for ident in required)
        assert all(not (cache / (ident + '.tar.gz')).exists() for ident in exclusive)
    finally:
        release.set()
        thread.join(timeout=15)
    assert not thread.is_alive() and not errors


def test_killed_source_releases_references_without_a_time_expiry(tmp_path, worker, completed_source):
    config, origins, _, required, cache = completed_source
    _, new = freeze_at(tmp_path / 'new', worker, 'killed-enqueue')
    ready = tmp_path / 'source-ready'
    child = """import json, pathlib, sys, time
from research_workflows.project_queue import ProjectQueue
original = ProjectQueue._stage_source_outbox
def pause(self, plan, required):
    result = original(self, plan, required)
    pathlib.Path(sys.argv[4]).write_text('staged')
    time.sleep(120)
    return result
ProjectQueue._stage_source_outbox = pause
with ProjectQueue(sys.argv[1]) as queue:
    queue.enqueue(sys.argv[2], 'local', json.loads(sys.argv[3]))
"""
    env = dict(os.environ, PYTHONPATH=str(Path(pq.__file__).resolve().parents[1]), PYTHONDONTWRITEBYTECODE='1')
    with (tmp_path / 'child.log').open('wb') as log:
        process = subprocess.Popen([sys.executable, '-B', '-c', child, str(config), str(new),
            json.dumps(origins), str(ready)], env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        assert ready.exists() and process.poll() is None, (tmp_path / 'child.log').read_text()
        with ProjectQueue(config) as queue:
            cleanup(queue)
            assert len(list(cache.glob('*.tar.gz'))) == len(required)
            records = list((queue.root / 'outbox-enqueues').glob('*.json'))
            assert len(records) == 1
            future = time.time() + 86400
            os.utime(records[0], (future, future))
        process.kill()
        assert process.wait(timeout=10) != 0
        with ProjectQueue(config) as queue:
            assert records[0].exists()  # No Python finally ran in the killed source.
            cleanup(queue)
            assert not records[0].exists() and not list(cache.glob('*.tar.gz'))
            assert len(queue.status()) == 1 and queue.status()[0]['workflow_id'] == 'old-result'
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)


def test_enqueue_failure_removes_its_reference_and_retains_original_error(completed_source, monkeypatch):
    config, origins, old, required, cache = completed_source

    def fail(*args):
        raise OSError('synthetic staging failure')

    monkeypatch.setattr(ProjectQueue, '_stage_source_outbox', fail)
    with ProjectQueue(config) as queue:
        with pytest.raises(OSError, match='synthetic staging failure'):
            queue.enqueue(old, 'local', origins)
        assert not list((queue.root / 'outbox-enqueues').glob('*.json'))
        cleanup(queue)
        assert not list(cache.glob('*.tar.gz'))


@pytest.mark.parametrize('damage', ['name', 'schema', 'objects_type', 'hash', 'duplicates', 'record_link', 'lock_link'])
def test_invalid_reference_prevents_archive_cleanup(tmp_path, completed_source, damage):
    config, _, _, required, cache = completed_source
    with ProjectQueue(config) as queue:
        token = 'a' * 32
        record = queue.root / 'outbox-enqueues' / (token + '.json')
        lock = queue.root / 'outbox-enqueue-locks' / (token + '.lock')
        value = {'schema': 'marketmaker.outbox_enqueue.v1', 'objects': sorted(required)}
        if damage == 'name':
            record = record.with_name('invalid.json')
        elif damage == 'schema':
            value['schema'] = 'unknown'
        elif damage == 'objects_type':
            value['objects'] = 'not-a-list'
        elif damage == 'hash':
            value['objects'] = ['invalid']
        elif damage == 'duplicates':
            value['objects'] = [min(required)] * 2
        atomic(record, value)
        if damage in {'record_link', 'lock_link'}:
            outside = tmp_path / 'unrelated-file'
            outside.write_text(json.dumps(value))
            target = record if damage == 'record_link' else lock
            target.parent.mkdir(parents=True, exist_ok=True)
            target.unlink(missing_ok=True)
            target.symlink_to(outside)
        before = {p.name: sha(p) for p in cache.glob('*.tar.gz')}
        with pytest.raises(ValueError, match='reference|SHA-256|symlink'):
            cleanup(queue)
        assert {p.name: sha(p) for p in cache.glob('*.tar.gz')} == before
