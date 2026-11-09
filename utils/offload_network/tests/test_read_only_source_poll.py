"""Status reconciliation must not scan historical bulk evidence.

Synthetic loopback workflows only. Admission, local metadata, collection,
publication and immutable identity guards remain independently exercised.
"""
import urllib.error

import pytest

from research_workflows.client import Client
from research_workflows.common import atomic, load
from research_workflows.project_queue import ProjectQueue
from research_workflows.project_storage import Project, StorageUnavailable
from research_workflows.simulation import configuration
from tests.test_partial_project_return import prepared
from tests.test_project_return import api, project, worker, freeze
from tests.test_research_workflows import compiled, drive


def admitted(tmp_path, worker, project):
    config, origins = project
    spec, directory = freeze(tmp_path, worker)
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        assert queue.sync(now=True)[0]["phase"] == "remote"
    return config, spec


def no_bulk(*args, **kwargs):
    raise AssertionError("status polling touched bulk evidence")


def no_upload(*args, **kwargs):
    raise AssertionError("capacity-blocked or previously admitted work was uploaded")


def no_collection(*args, **kwargs):
    raise AssertionError("capacity-blocked evidence collection was entered")


def blocked_capacity(*args, **kwargs):
    raise StorageUnavailable("synthetic bulk capacity exhausted")


def acknowledgements(worker):
    return worker.db.execute(
        "SELECT COUNT(*) FROM workflow_deliveries WHERE acknowledged IS NOT NULL"
    ).fetchone()[0]


def test_remote_poll_does_not_resolve_scan_or_upload_bulk(tmp_path, worker, project, monkeypatch):
    config, _ = admitted(tmp_path, worker, project)
    monkeypatch.setattr(Project, "bulk", no_bulk)
    monkeypatch.setattr(Client, "upload", no_upload)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["phase"] == "remote" and row["error"] is None
        assert row["transport_failures"] == 0
    assert worker.db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 1


def test_lost_admission_reconciles_without_bulk_or_reexecution(tmp_path, worker, api, project, monkeypatch):
    config, origins = project
    spec, directory = freeze(tmp_path, worker)
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
    api.submit_plan(directory)  # Remote admitted, source has not received that fact.
    monkeypatch.setattr(Project, "bulk", no_bulk)
    monkeypatch.setattr(Client, "upload", no_upload)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["phase"] == "remote" and row["error"] is None
    assert worker.db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 1
    assert all(node["attempt"] == 1 for node in worker.workflows.status(spec["submission_id"])["nodes"])


@pytest.mark.parametrize("condition", ["quota", "missing_drive"])
def test_new_admission_rechecks_bulk_before_any_upload(tmp_path, worker, project, monkeypatch, condition):
    config, origins = project
    _, directory = freeze(tmp_path, worker)
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
    disk = tmp_path / "bulk-disk"
    if condition == "missing_drive":
        disk.rename(tmp_path / "withdrawn-disk")
    else:
        monkeypatch.setattr(Project, "capacity", blocked_capacity)
    monkeypatch.setattr(Client, "upload", no_upload)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["phase"] == "queued" and row["state"] != "needs_attention"
        assert row["error"].startswith("StorageUnavailable:")
    assert worker.db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 0
    if condition == "missing_drive":
        assert not disk.exists()  # No local shadow storage.


def test_bulk_only_quota_still_blocks_new_admission(tmp_path, worker, project, monkeypatch):
    from research_workflows import project_storage

    config, origins = project
    _, directory = freeze(tmp_path, worker)
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        bulk = queue.project.bulk()
    original = project_storage.live_tree_bytes
    monkeypatch.setattr(project_storage, "live_tree_bytes", lambda path:
        10**12 if path == bulk else original(path))
    monkeypatch.setattr(Client, "upload", no_upload)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["phase"] == "queued" and "bulk evidence capacity" in row["error"]
    assert worker.db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 0


def test_remote_poll_keeps_local_metadata_capacity_guard(tmp_path, worker, project, monkeypatch):
    from research_workflows import project_storage

    config, _ = admitted(tmp_path, worker, project)
    state = Project(config).state
    original = project_storage.live_tree_bytes
    monkeypatch.setattr(project_storage, "live_tree_bytes", lambda path:
        10**12 if path == state else original(path))
    monkeypatch.setattr(Client, "workflow_status", no_upload)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["phase"] == "remote"
        assert "local queue metadata capacity" in row["error"]
        assert row["state"] != "needs_attention"


@pytest.mark.parametrize("at_limit", [True, False])
def test_local_free_space_boundary_still_applies_to_polling(tmp_path, worker, project, monkeypatch, at_limit):
    from research_workflows import project_storage

    config, _ = admitted(tmp_path, worker, project)
    source = Project(config)
    usage = project_storage.shutil.disk_usage

    def observed(path):
        real = usage(path)
        if path == source.root:
            available = (source.storage["local_min_free_mb"] << 20) - (0 if at_limit else 1)
            return type(real)(real.total, real.total - available, available)
        return real

    monkeypatch.setattr(project_storage.shutil, "disk_usage", observed)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["phase"] == "remote"
        if at_limit:
            assert row["error"] is None
        else:
            assert "local research/queue free-space reserve" in row["error"]
            assert row["state"] != "needs_attention"


def test_interrupted_retry_requires_full_capacity_before_resume(tmp_path, worker, project, monkeypatch):
    config, origins = project
    spec, directory = compiled(tmp_path, worker,
        edit=lambda raw: raw["jobs"][0].update(max_attempts=2))
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        assert queue.sync(now=True)[0]["phase"] == "remote"
    worker.workflows.tick()
    job, _, _ = worker._claim()  # A durable claim, no actual process was launched.
    root = worker.root
    worker.close()
    worker.__init__(root, [], backend="trusted-local", workflow_config=configuration(),
                    concurrency=2, min_free_mb=0)
    assert worker.status(job)["state"] == "interrupted"
    assert drive(worker)["state"] == "completed_with_errors"
    original_capacity, request = Project.capacity, Client.request
    resumes = []

    def tracked(self, path, *args, **kwargs):
        if path.endswith("/resume"):
            resumes.append(path)
        return request(self, path, *args, **kwargs)

    monkeypatch.setattr(Project, "capacity", blocked_capacity)
    monkeypatch.setattr(Client, "request", tracked)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["phase"] == "remote" and "synthetic bulk capacity" in row["error"]
    assert resumes == []
    assert next(node for node in worker.workflows.status(spec["submission_id"])["nodes"]
                if node["id"] == "bundle")["attempt"] == 1
    monkeypatch.setattr(Project, "capacity", original_capacity)
    with ProjectQueue(config) as queue:
        assert queue.sync(now=True)[0]["phase"] == "remote"
    assert len(resumes) == 1
    assert drive(worker)["state"] == "completed"
    assert worker.status(job)["state"] == "interrupted"
    assert next(node for node in worker.workflows.status(spec["submission_id"])["nodes"]
                if node["id"] == "bundle")["attempt"] == 2


def test_network_timeout_does_not_require_bulk_or_infer_reexecution(tmp_path, worker, project, monkeypatch):
    config, _ = admitted(tmp_path, worker, project)

    def timeout(*args, **kwargs):
        raise urllib.error.URLError("synthetic network wait")

    monkeypatch.setattr(Project, "bulk", no_bulk)
    monkeypatch.setattr(Client, "workflow_status", timeout)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["phase"] == "remote" and row["state"] != "needs_attention"
        assert row["error"].startswith("URLError:") and row["transport_failures"] == 1
    assert worker.db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 1


def test_known_remote_state_loss_still_fences_admission_without_bulk(tmp_path, worker, project, monkeypatch):
    config, _ = admitted(tmp_path, worker, project)

    def missing(*args, **kwargs):
        raise urllib.error.HTTPError("http://127.0.0.1", 404, "missing", {}, None)

    monkeypatch.setattr(Project, "bulk", no_bulk)
    monkeypatch.setattr(Client, "workflow_status", missing)
    monkeypatch.setattr(Client, "upload", no_upload)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["phase"] == "remote" and row["state"] == "needs_attention"
        assert "do not silently rerun" in row["error"]
    assert worker.db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 1


@pytest.mark.parametrize("field", ["binding", "worker", "workflow", "objects"])
def test_poll_keeps_every_immutable_enqueue_receipt_check(tmp_path, worker, project, monkeypatch, field):
    config, spec = admitted(tmp_path, worker, project)
    with ProjectQueue(config) as queue:
        path = queue.root / "submissions" / spec["submission_id"] / "ENQUEUED.json"
        receipt = load(path)
        receipt[field] = {"changed": True}
        atomic(path, receipt)
    monkeypatch.setattr(Client, "workflow_status", no_upload)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["state"] == "needs_attention"
        assert "source queue differs from its enqueue receipt" in row["error"]


def test_partial_return_capacity_failure_blocks_collection_and_ack(tmp_path, worker, project, monkeypatch):
    config, _ = prepared(tmp_path, worker, project)
    original_capacity, original_collect = Project.capacity, Client.collect
    monkeypatch.setattr(Project, "capacity", blocked_capacity)
    monkeypatch.setattr(Client, "collect", no_collection)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["phase"] == "remote" and row["publications"] == []
        assert "synthetic bulk capacity" in row["error"]
        assert queue.db.execute("SELECT COUNT(*) FROM partial_deliveries").fetchone()[0] == 1
    assert acknowledgements(worker) == 0
    monkeypatch.setattr(Project, "capacity", original_capacity)
    monkeypatch.setattr(Client, "collect", original_collect)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["phase"] == "remote" and len(row["publications"]) == 2
        assert row["error"] is None
    assert acknowledgements(worker) == 0


def test_final_return_capacity_failure_pins_delivery_then_recovers_without_replay(tmp_path, worker, project, monkeypatch):
    config, spec = admitted(tmp_path, worker, project)
    assert drive(worker)["terminal"]
    jobs = worker.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    original_capacity, original_collect = Project.capacity, Client.collect
    monkeypatch.setattr(Project, "capacity", blocked_capacity)
    monkeypatch.setattr(Client, "collect", no_collection)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["phase"] == "collecting" and row["delivery_sha256"]
        assert row["publications"] == [] and "synthetic bulk capacity" in row["error"]
        delivery = row["delivery_sha256"]
    assert acknowledgements(worker) == 0
    monkeypatch.setattr(Project, "capacity", original_capacity)
    monkeypatch.setattr(Client, "collect", original_collect)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["phase"] == "completed" and row["delivery_sha256"] == delivery
        assert len(row["publications"]) == 3
    assert acknowledgements(worker) == 1
    assert worker.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == jobs
    assert all(node["attempt"] == 1 for node in worker.workflows.status(spec["submission_id"])["nodes"])


@pytest.mark.parametrize("stage", ["publishing", "awaiting_ack"])
def test_pending_publication_and_ack_still_require_full_capacity(tmp_path, worker, project, monkeypatch, stage):
    from research_workflows import project_queue

    config, _ = admitted(tmp_path, worker, project)
    assert drive(worker)["terminal"]
    original_publish, original_request = project_queue.publish, Client.request

    def interrupt_publish(*args, **kwargs):
        raise StorageUnavailable("synthetic publication wait")

    def interrupt_ack(self, path, *args, **kwargs):
        if path.endswith("/ack"):
            raise ConnectionResetError("synthetic unacknowledged return")
        return original_request(self, path, *args, **kwargs)

    if stage == "publishing":
        monkeypatch.setattr(project_queue, "publish", interrupt_publish)
    else:
        monkeypatch.setattr(Client, "request", interrupt_ack)
    with ProjectQueue(config) as queue:
        assert queue.sync(now=True)[0]["phase"] == stage
    monkeypatch.setattr(project_queue, "publish", original_publish)
    monkeypatch.setattr(Client, "request", original_request)
    original_capacity = Project.capacity
    monkeypatch.setattr(Project, "capacity", blocked_capacity)
    with ProjectQueue(config) as queue:
        row = queue.sync(now=True)[0]
        assert row["phase"] == stage and "synthetic bulk capacity" in row["error"]
    assert acknowledgements(worker) == 0
    monkeypatch.setattr(Project, "capacity", original_capacity)
    with ProjectQueue(config) as queue:
        assert queue.sync(now=True)[0]["phase"] == "completed"
    assert acknowledgements(worker) == 1
