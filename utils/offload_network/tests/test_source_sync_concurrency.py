"""Long admissions must not block new research or returned-result analysis."""
import threading
import time
import urllib.error

import pytest

from lib.file_lock import file_lock
from research_workflows.client import Client
from research_workflows.common import atomic, load
from research_workflows.project_queue import ProjectQueue
from research_workflows.project_storage import Project
from research_workflows.publication import resolve_record
from tests.test_project_return import project as project_fixture
from tests.test_research_workflows import api as api_fixture, worker as worker_fixture, compiled, drive

project, api, worker = project_fixture, api_fixture, worker_fixture


def freeze_at(root, worker, identity):
    root.mkdir()
    return compiled(root, worker, edit=lambda raw: raw.update(
        submission_id=identity, return_policy={"include_inputs": True}))


def test_slow_admission_allows_enqueue_and_analysis_but_fences_duplicate_sync(
    tmp_path, worker, project, monkeypatch
):
    config, origins = project
    _, first = freeze_at(tmp_path / "first", worker, "finished")
    with ProjectQueue(config) as queue:
        queue.enqueue(first, "local", origins)
        queue.sync(now=True)
    assert drive(worker, "finished")["state"] == "completed"
    with ProjectQueue(config) as queue:
        finished = queue.sync(now=True)[0]
        record = next(queue.project.root / p for p in finished["publications"] if "/report/" in p)
    _, second = freeze_at(tmp_path / "second", worker, "slow")
    _, third = freeze_at(tmp_path / "third", worker, "new-research")
    with ProjectQueue(config) as queue:
        queue.enqueue(second, "local", origins)
    entered, release = threading.Event(), threading.Event()
    request, calls, failures = Client.request, [], []

    def delayed(client, path, data=None, *args, **kwargs):
        if path == "/v2/workflows" and data["submission_id"] == "slow":
            calls.append(path)
            entered.set()
            assert release.wait(15), "test did not release the admission"
        return request(client, path, data, *args, **kwargs)

    def synchronize():
        try:
            with ProjectQueue(config) as queue:
                queue.sync(now=True)
        except BaseException as exc:
            failures.append(exc)

    monkeypatch.setattr(Client, "request", delayed)
    thread = threading.Thread(target=synchronize, daemon=True)
    thread.start()
    try:
        assert entered.wait(10)
        with ProjectQueue(config) as queue:
            # No second network call may synchronize this same owned workflow.
            assert queue.sync(now=True)[1]["phase"] == "queued"
            with pytest.raises(TimeoutError):
                queue.retry("slow")
            returned = resolve_record(queue.project, record, "report.evidence", "result.json")
            assert load(returned)["equal"] is True
            queue.enqueue(third, "local", origins)
            assert queue.status()[2]["workflow_id"] == "new-research"
    finally:
        release.set()
        thread.join(timeout=15)
    assert not thread.is_alive() and not failures
    assert len(calls) == 1
    assert worker.db.execute("SELECT COUNT(*) FROM workflows WHERE id='slow'").fetchone()[0] == 1


def test_known_admission_fence_survives_later_delivery_timeout(tmp_path, worker, api, project, monkeypatch):
    config, origins = project
    spec, directory = freeze_at(tmp_path / "source", worker, "already-finished")
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
    api.submit_plan(directory)
    assert drive(worker, spec["submission_id"])["terminal"]
    request = Client.request

    def lost_delivery(client, path, *args, **kwargs):
        if path.endswith("/delivery"):
            raise TimeoutError("synthetic delivery timeout after known admission")
        return request(client, path, *args, **kwargs)

    monkeypatch.setattr(Client, "request", lost_delivery)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["phase"] == "remote" and row["transport_failures"] == 1
        assert row["error"].startswith("TimeoutError:")
    monkeypatch.setattr(Client, "workflow_status", lambda *args: (_ for _ in ()).throw(
        urllib.error.HTTPError("http://127.0.0.1", 404, "missing", {}, None)))
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["state"] == "needs_attention" and "do not silently rerun" in row["error"]
    assert worker.db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 1


@pytest.mark.parametrize('scope', ['queue', 'separate'])
def test_result_collection_retains_global_storage_lock(tmp_path, worker, project, monkeypatch, scope):
    config, origins = project
    raw = load(config)
    raw['recovery']['collection_lock_scope'] = scope
    atomic(config, raw)
    _, directory = freeze_at(tmp_path / "source", worker, "collect")
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        queue.sync(now=True)
        lock = queue.root / ('collection.lock' if scope == 'separate' else 'queue.lock')
    drive(worker, "collect")
    collect, checks = Client.collect, []

    def checked(client, *args, **kwargs):
        with pytest.raises(TimeoutError):
            with file_lock(lock, timeout=0):
                pass
        checks.append(True)
        return collect(client, *args, **kwargs)

    monkeypatch.setattr(Client, "collect", checked)
    with ProjectQueue(config) as queue:
        assert queue.sync(now=True)[0]["phase"] == "completed"
    assert checks == [True]


def test_slow_collection_allows_enqueue_while_other_collection_and_duplicate_sync_wait(
    tmp_path, worker, project, monkeypatch
):
    config, origins = project
    raw = load(config)
    raw['recovery']['collection_lock_scope'] = 'separate'
    atomic(config, raw)
    plans = {key: freeze_at(tmp_path / key, worker, key)[1]
        for key in ['collect-first', 'collect-second', 'new-research']}
    with ProjectQueue(config) as queue:
        for key in ['collect-first', 'collect-second']:
            queue.enqueue(plans[key], 'local', origins)
        queue.sync(now=True)
    for key in ['collect-first', 'collect-second']:
        assert drive(worker, key)['terminal']
    entered, release = threading.Event(), threading.Event()
    original, calls, failures = Client.collect, [], []

    def collect(client, key, *args, **kwargs):
        calls.append(key)
        if key == 'collect-first':
            entered.set()
            assert release.wait(15), 'test did not release the first collection'
        elif key == 'collect-second':
            assert release.is_set(), 'shared-store collections must stay serialized'
        return original(client, key, *args, **kwargs)

    def synchronize():
        try:
            with ProjectQueue(config) as queue:
                queue.sync(now=True, workflows=['collect-first'])
        except BaseException as error:
            failures.append(error)

    monkeypatch.setattr(Client, 'collect', collect)
    thread = threading.Thread(target=synchronize, daemon=True)
    thread.start()
    try:
        assert entered.wait(10)
        with ProjectQueue(config) as queue:
            receipt = queue.enqueue_receipt(plans['new-research'], 'local', origins, lock_timeout=.5)
            assert receipt['queue_acknowledged']
            queue.sync(now=True, workflows=['collect-first', 'collect-second'])
            assert queue._row('collect-first')['phase'] == 'collecting'
            assert queue._row('collect-second')['phase'] == 'collecting'
            assert queue._row('new-research')['phase'] == 'queued'
            assert calls == ['collect-first']
    finally:
        release.set()
        thread.join(timeout=15)
    assert not thread.is_alive() and not failures
    with ProjectQueue(config) as queue:
        queue.sync(now=True, workflows=['collect-second'])
        for key in ['collect-first', 'collect-second']:
            assert queue._row(key)['phase'] == 'completed'
    assert calls == ['collect-first', 'collect-second']
    assert worker.db.execute('SELECT COUNT(*) FROM workflows').fetchone()[0] == 2


@pytest.mark.parametrize('value', [True, 1, None, [], {}, 'unsafe'])
def test_invalid_collection_lock_scope_is_rejected_before_servicing_work(project, value):
    config, _ = project
    raw = load(config)
    raw['recovery']['collection_lock_scope'] = value
    atomic(config, raw)
    with pytest.raises(ValueError, match='collection_lock_scope'):
        Project(config)


def test_collection_lock_choice_preserves_original_workflow_and_origin_binding(tmp_path, worker, project):
    config, origins = project
    spec, _ = freeze_at(tmp_path / 'source', worker, 'binding')
    before = Project(config).binding(spec, origins)
    raw = load(config)
    raw['recovery']['collection_lock_scope'] = 'separate'
    atomic(config, raw)
    assert Project(config).binding(spec, origins) == before


def test_outbox_staging_does_not_hold_source_queue_lock(tmp_path, worker, project, monkeypatch):
    config, origins = project
    _, first = freeze_at(tmp_path / "first", worker, "slow-outbox")
    _, second = freeze_at(tmp_path / "second", worker, "next-candidate")
    entered, release = threading.Event(), threading.Event()
    original = ProjectQueue._stage_source_outbox
    errors = []

    def delayed(self, plan, required):
        if not entered.is_set():
            entered.set()
            assert release.wait(15), "test did not release outbox staging"
        return original(self, plan, required)

    def slow():
        try:
            with ProjectQueue(config) as queue:
                queue.enqueue(first, "local", origins)
        except BaseException as exc:
            errors.append(exc)

    monkeypatch.setattr(ProjectQueue, "_stage_source_outbox", delayed)
    thread = threading.Thread(target=slow, daemon=True)
    thread.start()
    try:
        assert entered.wait(10)
        with ProjectQueue(config) as queue:
            with file_lock(queue.root / "queue.lock", timeout=0):
                pass
            queue.enqueue(second, "local", origins)
            assert queue._row("next-candidate")["phase"] == "queued"
    finally:
        release.set()
        thread.join(timeout=15)
    assert not thread.is_alive() and not errors
    with ProjectQueue(config) as queue:
        assert queue._row("slow-outbox")["phase"] == "queued"
        assert queue._row("next-candidate")["phase"] == "queued"


def test_outbox_identity_hash_does_not_hold_source_queue_lock(tmp_path, worker, project, monkeypatch):
    """Staged archive SHA must not run under queue.lock; a slow hash cannot stall FIFO admission."""
    import research_workflows.project_queue as pq

    config, origins = project
    _, first = freeze_at(tmp_path / "first", worker, "slow-hash")
    _, second = freeze_at(tmp_path / "second", worker, "next-candidate")
    staged, release = threading.Event(), threading.Event()
    original_stage = ProjectQueue._stage_source_outbox
    original_sha = pq.sha
    errors, hashing = [], []

    def stage(self, plan, required):
        cache = original_stage(self, plan, required)
        staged.set()
        return cache

    def delayed_sha(path):
        if staged.is_set() and not hashing and str(path).endswith(".tar.gz"):
            hashing.append(True)
            assert release.wait(15), "test did not release outbox identity hash"
        return original_sha(path)

    def slow():
        try:
            with ProjectQueue(config) as queue:
                queue.enqueue(first, "local", origins)
        except BaseException as exc:
            errors.append(exc)

    monkeypatch.setattr(ProjectQueue, "_stage_source_outbox", stage)
    monkeypatch.setattr(pq, "sha", delayed_sha)
    thread = threading.Thread(target=slow, daemon=True)
    thread.start()
    try:
        assert staged.wait(10)
        deadline = time.monotonic() + 10
        while not hashing and time.monotonic() < deadline:
            time.sleep(0.05)
        assert hashing, "shipped enqueue did not hash staged outbox archives"
        with ProjectQueue(config) as queue:
            with file_lock(queue.root / "queue.lock", timeout=0):
                pass
            queue.enqueue(second, "local", origins)
            assert queue._row("next-candidate")["phase"] == "queued"
    finally:
        release.set()
        thread.join(timeout=15)
    assert not thread.is_alive() and not errors
    with ProjectQueue(config) as queue:
        assert queue._row("slow-hash")["phase"] == "queued"
        assert queue._row("next-candidate")["phase"] == "queued"


def test_slow_source_capacity_scan_does_not_hold_shared_storage_lock(
    tmp_path, worker, project, monkeypatch
):
    config, origins = project
    _, first = freeze_at(tmp_path / "first", worker, "slow-preflight")
    _, second = freeze_at(tmp_path / "second", worker, "next-candidate")
    with ProjectQueue(config) as queue:
        queue.enqueue(first, "local", origins)
    entered, release = threading.Event(), threading.Event()
    capacity, errors, delayed_threads = Project.capacity, [], []

    def delayed(self, *args, **kwargs):
        if threading.get_ident() in delayed_threads and not entered.is_set():
            entered.set()
            assert release.wait(15), "test did not release source preflight"
        return capacity(self, *args, **kwargs)

    def synchronize():
        delayed_threads.append(threading.get_ident())
        try:
            with ProjectQueue(config) as queue:
                queue.sync(now=True, workflows=["slow-preflight"])
        except BaseException as exc:
            errors.append(exc)

    monkeypatch.setattr(Project, "capacity", delayed)
    thread = threading.Thread(target=synchronize, daemon=True)
    thread.start()
    try:
        assert entered.wait(10)
        with ProjectQueue(config) as queue:
            # Capacity observation does not reserve bytes or mutate shared
            # evidence. Another researcher can enqueue and admit work now.
            queue.enqueue(second, "local", origins)
            queue.sync(now=True, workflows=["next-candidate"])
            assert queue._row("next-candidate")["phase"] == "remote"
            # Moving observational work never relinquishes workflow ownership.
            queue.sync(now=True, workflows=["slow-preflight"])
            assert queue._row("slow-preflight")["phase"] == "queued"
            with pytest.raises(TimeoutError):
                queue.retry("slow-preflight")
    finally:
        release.set()
        thread.join(timeout=15)
    assert not thread.is_alive() and not errors
    with ProjectQueue(config) as queue:
        assert queue._row("slow-preflight")["phase"] == "remote"
    assert worker.db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 2


def test_remote_admission_proceeds_while_shared_storage_is_owned(tmp_path, worker, project):
    config, origins = project
    _, directory = freeze_at(tmp_path / "source", worker, "independent-admission")
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        # Simulate another workflow's long collection holding the shared lock.
        # This pass only reads retained immutable inputs and polls/admit remote
        # work. The final/partial collection paths still acquire the lock.
        with file_lock(queue.root / "queue.lock", timeout=0):
            queue.sync(now=True, workflows=["independent-admission"])
            assert queue._row("independent-admission")["phase"] == "remote"
    assert worker.db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 1
