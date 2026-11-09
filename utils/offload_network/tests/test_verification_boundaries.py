"""No persistent hash cache: deduplicate only within explicit trust boundaries."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading

import pytest

from offload_service.core import Worker
from research_workflows.common import atomic, load, sha
from research_workflows.objects import ObjectStore
from tests.test_research_workflows import worker as worker_fixture, compiled

worker = worker_fixture


def test_shared_data_verified_once_per_admission_and_again_on_next_call(tmp_path, worker, monkeypatch):
    spec, _ = compiled(tmp_path, worker)
    store = worker.workflows.objects
    ident = spec["jobs"][0]["inputs"]["values"]["object_sha256"]
    get, calls = store.get, []

    def observed(identity):
        calls.append(identity)
        return get(identity)

    monkeypatch.setattr(store, "get", observed)
    worker.workflows.preflight(spec)
    assert calls.count(ident) == 1
    worker.workflows.preflight(spec)
    assert calls.count(ident) == 2  # No cross-request stat-only/digest cache.
    bad = deepcopy(spec)
    remote = next(job for job in bad["jobs"] if job["id"] == "remote")
    remote["inputs"]["values"]["version"] = "missing-version"
    with pytest.raises(KeyError, match="registered dataset unavailable"):
        worker.workflows.preflight(bad)  # Same object cannot bypass its alias binding.


def test_changed_tree_and_commit_cannot_detach_from_archived_manifest(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "value.txt").write_text("original")
    store = ObjectStore(tmp_path / "store", max_object_mb=4, max_store_mb=32, min_free_mb=1)
    ident = store.ingest(source)
    root, manifest = store.get(ident)
    (root / "data/value.txt").write_text("modified")
    manifest["files"]["value.txt"] = {"bytes": 8, "sha256": sha(root / "data/value.txt")}
    atomic(root / "OBJECT.json", manifest)
    atomic(root / "COMMITTED.json", {"object_sha256": ident, "manifest": manifest})
    assert sha(root / "archive.tar.gz") == ident
    with pytest.raises(ValueError, match="invalid object commit"):
        store.get(ident)


def test_docker_mount_data_verified_before_create_and_after_execution(tmp_path, worker, monkeypatch):
    spec, _ = compiled(tmp_path, worker)
    store = worker.workflows.objects
    ident = spec["jobs"][0]["inputs"]["values"]["object_sha256"]
    payload = {"backend": "docker", "workflow_mounts": [{"object_sha256": ident, "target": "inputs/data"}]}
    work = tmp_path / "docker-work"
    work.mkdir()
    get, calls = store.get, []

    def observed(identity):
        calls.append(identity)
        return get(identity)

    monkeypatch.setattr(store, "get", observed)
    monkeypatch.setattr(Worker, "docker_command", lambda *a: ["docker", "create", "--workdir", "/work", "image"])
    worker.prepare_extra_inputs(work, payload)
    assert calls == [] and (work / "blobs/inputs/data").is_dir()
    command = worker.docker_command(work, "attempt", payload)
    assert calls == [ident] and any("target=/work/blobs/inputs/data,readonly" in arg for arg in command)
    worker.verify_extra_inputs(payload)
    assert calls == [ident, ident]
    (store.directory(ident) / "data/values.json").write_text("changed")
    with pytest.raises(ValueError):
        worker.docker_command(work, "attempt", payload)
    with pytest.raises(ValueError):
        worker.verify_extra_inputs(payload)


def test_slow_new_admission_does_not_lock_control_plane_or_duplicate_identity(tmp_path, worker, monkeypatch):
    spec, _ = compiled(tmp_path, worker)
    worker.workflows.submit(spec)
    slow = deepcopy(spec)
    slow["submission_id"] = "slow-new"
    entered, release, cancelled = threading.Event(), threading.Event(), threading.Event()
    preflight, calls = worker.workflows.preflight, []

    def delayed(raw):
        calls.append(raw["submission_id"])
        entered.set()
        assert release.wait(10), "test admission not released"
        return preflight(raw)

    def cancel_existing():
        result = worker.workflows.cancel(spec["submission_id"])
        cancelled.set()
        return result

    monkeypatch.setattr(worker.workflows, "preflight", delayed)
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(worker.workflows.submit, slow)
        try:
            assert entered.wait(5)
            duplicate = pool.submit(worker.workflows.submit, slow)
            cancellation = pool.submit(cancel_existing)
            assert cancelled.wait(2), "unrelated control-plane request was blocked by preflight"
        finally:
            release.set()
        a, b = first.result(timeout=10), duplicate.result(timeout=10)
        assert cancellation.result(timeout=10)["terminal"]
    assert sorted([a[1], b[1]]) == [False, True]
    assert calls == ["slow-new"]
    assert not worker.workflows.admission_locks
