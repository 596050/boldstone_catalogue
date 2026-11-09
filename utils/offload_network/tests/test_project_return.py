"""Source restarts, real loopback transfers and append-only research publication.

Synthetic subprocess jobs, not a security-sandbox or predictive-performance test.
"""

import errno
import os
import shutil
import subprocess
import sys
import urllib.error
from copy import deepcopy
from pathlib import Path

import pytest

from research_workflows.client import Client, verify_collection
from research_workflows.common import atomic, digest, load, sha
from research_workflows.planner import plan
from research_workflows.project_queue import ProjectQueue
from research_workflows.project_storage import Project, StorageUnavailable
from research_workflows.publication import import_collection, resolve_record
from tests.test_research_workflows import api as _api
from tests.test_research_workflows import compiled, drive
from tests.test_research_workflows import worker as _worker

api, worker = _api, _worker


@pytest.fixture
def project(tmp_path, api):
    root = tmp_path / "project"
    alpha = root / "research/candidates/directional_forecasting/alpha_20260911_v1"
    beta = root / "research/candidates/directional_forecasting/beta_20260911_v1"
    for path in (alpha, beta):
        path.mkdir(parents=True)
        (path / "README.md").write_text("Retain this research history unchanged.\n")
    bulk = tmp_path / "bulk-disk"
    bulk.mkdir()
    config = load(Path(__file__).parents[1] / "research_workflows/project.json")
    config.update(project_root=str(root), evidence={"directory": str(bulk), "relative": "offload"})
    token = tmp_path / "token"
    token.write_text(api.token)
    config["workers"] = {"local": {"url": api.url, "token_file": str(token)}}
    config["storage"].update(min_free_mb=1, local_min_free_mb=1, max_store_mb=128)
    path = root / "project.json"
    atomic(path, config)
    return path, {
        "report": [alpha.relative_to(root).as_posix()],
        "bundle": [alpha.relative_to(root).as_posix(), beta.relative_to(root).as_posix()],
    }


def freeze(tmp_path, worker):
    return compiled(
        tmp_path, worker, edit=lambda raw: raw.update(return_policy={"include_inputs": True})
    )


def test_lost_admission_reply_and_source_restart_return_to_all_origins(
    tmp_path, worker, project, monkeypatch
):
    config, origins = project
    spec, directory = freeze(tmp_path, worker)
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
    directory.rename(tmp_path / "withdrawn-plan")
    request = Client.request
    lost = []

    def drop_reply(self, path, *args, **kwargs):
        result = request(self, path, *args, **kwargs)
        if path == "/v2/workflows" and not lost:
            lost.append(True)
            raise urllib.error.URLError("synthetic lost admission reply")
        return result

    monkeypatch.setattr(Client, "request", drop_reply)
    with ProjectQueue(config) as restarted:
        result = restarted.sync(now=True)[0]
        assert result["phase"] == "queued" and result["transport_failures"] == 1
    assert drive(worker)["state"] == "completed"  # no connected source needed
    with ProjectQueue(config) as restarted:
        result = restarted.sync(now=True)[0]
        assert result["phase"] == "completed"
        assert len(result["publications"]) == 3
        root = restarted.project.bulk()
        assert not list((root / "outbox").glob("*.tar.gz"))
        assert all(not (p / "data").exists() for p in (root / "objects").iterdir() if p.is_dir())
        for relative in result["publications"]:
            record = restarted.project.root / relative
            body = load(record / "RUN_RESULT.json")
            assert body["workflow_sha256"] == digest(spec)
            port = body["node"]["id"] + (
                ".evidence" if body["node"]["id"] == "report" else ".values"
            )
            # bundle.values is remote-only, but the generated consumer input is retained.
            if port not in body["evidence"]["ports"]:
                continue
            resolved = resolve_record(restarted.project, record, port)
            assert resolved.is_dir()
        assert not list(restarted.project.root.rglob("*.tar.gz"))
        assert all(
            path.read_text() == "Retain this research history unchanged.\n"
            for path in restarted.project.root.glob("research/candidates/*/*/README.md")
        )
    assert worker.db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 1
    assert all(n["attempt"] == 1 for n in worker.workflows.status(spec["submission_id"])["nodes"])


def test_publication_crash_is_resumed_before_ack_without_overwrite(
    tmp_path, worker, project, monkeypatch
):
    from research_workflows import publication

    config, origins = project
    _, directory = freeze(tmp_path, worker)
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        queue.sync(now=True)
    drive(worker)
    write = publication._write_once
    count = []

    def crash(path, data):
        count.append(path)
        if len(count) == 3:
            raise OSError(errno.ENOSPC, "synthetic full disk during second origin")
        return write(path, data)

    monkeypatch.setattr(publication, "_write_once", crash)
    with ProjectQueue(config) as queue:
        result = queue.sync(now=True)[0]
        assert result["phase"] == "publishing" and result["state"] != "needs_attention"
        records = list(
            queue.project.root.glob("research/candidates/*/*/offload_runs/*/*/*/RUN_RESULT.json")
        )
        assert len(records) == 1
        before = {str(p): sha(p) for p in records}
    assert (
        worker.db.execute(
            "SELECT COUNT(*) FROM workflow_deliveries WHERE acknowledged IS NOT NULL"
        ).fetchone()[0]
        == 0
    )
    monkeypatch.setattr(publication, "_write_once", write)
    with ProjectQueue(config) as queue:
        result = queue.sync(now=True)[0]
        assert result["phase"] == "completed"
        assert all(sha(Path(p)) == value for p, value in before.items())
    assert (
        worker.db.execute(
            "SELECT COUNT(*) FROM workflow_deliveries WHERE acknowledged IS NOT NULL"
        ).fetchone()[0]
        == 1
    )


def test_lost_ack_does_not_recompute_or_duplicate_records(tmp_path, worker, project, monkeypatch):
    config, origins = project
    _, directory = freeze(tmp_path, worker)
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        queue.sync(now=True)
    drive(worker)
    request = Client.request

    def drop_ack(self, path, *args, **kwargs):
        result = request(self, path, *args, **kwargs)
        if path.endswith("/ack"):
            raise ConnectionResetError("synthetic ACK reply lost")
        return result

    monkeypatch.setattr(Client, "request", drop_ack)
    with ProjectQueue(config) as queue:
        result = queue.sync(now=True)[0]
        assert result["phase"] == "awaiting_ack" and len(result["publications"]) == 3
        before = {
            path: sha(queue.project.root / path / "RUN_RESULT.json")
            for path in result["publications"]
        }
    monkeypatch.setattr(Client, "request", request)
    with ProjectQueue(config) as queue:
        result = queue.sync(now=True)[0]
        assert result["phase"] == "completed"
        assert {
            path: sha(queue.project.root / path / "RUN_RESULT.json")
            for path in result["publications"]
        } == before
    assert worker.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 4


def test_worker_restart_retries_only_stopped_interrupted_attempts(tmp_path, worker, project):
    from research_workflows.simulation import configuration

    config, origins = project
    spec, directory = compiled(
        tmp_path,
        worker,
        edit=lambda raw: (
            raw.update(return_policy={"include_inputs": True}),
            raw["jobs"][0].update(max_attempts=2),
        ),
    )
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        queue.sync(now=True)
    worker.workflows.tick()
    job, _, _ = worker._claim()  # Durable running claim; no process has launched.
    root = worker.root
    worker.close()
    # Reopen the same isolated store. Keep the HTTP fixture's object reference.
    worker.__init__(
        root,
        [],
        backend="trusted-local",
        workflow_config=configuration(),
        concurrency=2,
        min_free_mb=0,
    )
    assert worker.status(job)["state"] == "interrupted"
    assert drive(worker)["state"] == "completed_with_errors"
    with ProjectQueue(config) as queue:
        assert queue.sync(now=True)[0]["phase"] == "remote"
    assert drive(worker)["state"] == "completed"
    with ProjectQueue(config) as queue:
        result = queue.sync(now=True)[0]
        assert result["phase"] == "completed"
        record = next(queue.project.root / p for p in result["publications"] if "/bundle/" in p)
        body = load(record / "RUN_RESULT.json")
        assert body["node"]["attempt"] == 2
        assert [a["state"] for a in body["attempt_history"]] == ["interrupted", "succeeded"]
    assert worker.status(job)["state"] == "interrupted"
    assert all(
        n["attempt"] == (2 if n["id"] == "bundle" else 1)
        for n in worker.workflows.status(spec["submission_id"])["nodes"]
    )


def test_cancel_then_worker_restart_returns_without_resume_or_duplicate(tmp_path, worker, project):
    from research_workflows.simulation import configuration

    config, origins = project
    spec, directory = compiled(tmp_path, worker,
        edit=lambda raw: raw["jobs"][0].update(max_attempts=2))
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        assert queue.sync(now=True)[0]["phase"] == "remote"
    worker.workflows.tick()
    job, _, _ = worker._claim()
    worker.workflows.cancel(spec["submission_id"])
    root = worker.root
    worker.close()
    worker.__init__(root, [], backend="trusted-local", workflow_config=configuration(),
                    concurrency=2, min_free_mb=0)
    assert worker.status(job)["state"] == "cancelled"
    status = drive(worker)
    assert status["terminal"] and all(n["state"] == "cancelled" for n in status["nodes"])
    before = worker.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    with ProjectQueue(config) as queue:
        result = queue.sync(now=True)[0]
        assert result["phase"] == "completed", result
        assert result["transport_failures"] == 0
        assert len(result["publications"]) == 3
        for relative in result["publications"]:
            body = load(queue.project.root / relative / "RUN_RESULT.json")
            assert body["node"]["state"] == "cancelled"
    assert worker.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == before
    assert all(n["attempt"] <= 1 for n in worker.workflows.status(spec["submission_id"])["nodes"])


def test_interrupted_result_download_resumes_the_retained_byte_range(
    tmp_path, worker, project, monkeypatch
):
    config, origins = project
    _, directory = freeze(tmp_path, worker)
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        queue.sync(now=True)
    drive(worker)
    original = Client.open
    dropped, ranges = [], []

    class BrokenResponse:
        def __init__(self, response):
            self.response, self.reads = response, 0
            self.headers, self.status = response.headers, response.status

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.response.close()

        def read(self, _):
            self.reads += 1
            if self.reads == 1:
                return self.response.read(16)
            raise ConnectionResetError("synthetic mid-download disconnect")

    def broken_open(self, path, *args, **kwargs):
        response = original(self, path, *args, **kwargs)
        if path.endswith("/archive"):
            ranges.append(kwargs.get("headers", {}).get("Range"))
            if not dropped:
                dropped.append(True)
                return BrokenResponse(response)
        return response

    monkeypatch.setattr(Client, "open", broken_open)
    with ProjectQueue(config) as queue:
        assert queue.sync(now=True)[0]["phase"] == "collecting"
        assert [p.stat().st_size for p in (queue.project.bulk() / "objects").glob("*.part")] == [16]
    with ProjectQueue(config) as queue:
        assert queue.sync(now=True)[0]["phase"] == "completed"
    assert "bytes=16-" in ranges


def test_abrupt_source_process_exit_after_admission_recovers_queue(tmp_path, worker, project):
    config, origins = project
    _, directory = freeze(tmp_path, worker)
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
    script = """import os, sys
from research_workflows.client import Client
from research_workflows.project_queue import ProjectQueue
original = Client.request
def request(self, path, *args, **kwargs):
    result = original(self, path, *args, **kwargs)
    if path == '/v2/workflows':
        os._exit(91)
    return result
Client.request = request
queue = ProjectQueue(sys.argv[1])
queue.sync(now=True)
raise SystemExit(92)
"""
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).parents[1]),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    child = subprocess.run([sys.executable, "-c", script, str(config)], env=env, timeout=30)
    assert child.returncode == 91  # No finally blocks, DB close or lock release by Python.
    drive(worker)
    with ProjectQueue(config) as recovered:
        assert recovered.sync(now=True)[0]["phase"] == "completed"
    assert worker.db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 1


def test_remote_input_references_do_not_force_bulk_download_or_delete_source_copy(
    tmp_path, worker, project
):
    config, origins = project
    spec, directory = compiled(tmp_path, worker)
    assert not spec["return_policy"]["include_inputs"]
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        queue.sync(now=True)
    drive(worker)
    with ProjectQueue(config) as queue:
        result = queue.sync(now=True)[0]
        assert result["phase"] == "completed"
        bulk = queue.project.bulk()
        assert list((bulk / "outbox").glob("*.tar.gz"))  # Nonredundant sealed sources retained.
        collection = bulk / "collections" / spec["submission_id"] / result["delivery_sha256"]
        assert not verify_collection(collection)["required_inputs_available_locally"]
        assert not any(k.endswith(".__capsule__") for k in load(collection / "INDEX.json"))


def test_central_attempt_defaults_are_frozen_not_applied_to_existing_plans(
    tmp_path, worker, project
):
    config, _ = project
    spec, _ = freeze(tmp_path, worker)
    spec = deepcopy(spec)
    del spec["jobs"][0]["max_attempts"]
    budget = Project(config).recovery["default_max_attempts"]
    plan(spec, tmp_path / "budget-plan", default_max_attempts=budget)
    frozen = load(tmp_path / "budget-plan/WORKFLOW.json")
    assert frozen["jobs"][0]["max_attempts"] == 2
    assert all(j["max_attempts"] == 1 for j in frozen["jobs"][1:])


def test_missing_bulk_drive_and_quota_pause_without_local_shadow(
    tmp_path, worker, project, monkeypatch
):
    from research_workflows import project_storage

    config, origins = project
    _, directory = freeze(tmp_path, worker)
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
    disk = tmp_path / "bulk-disk"
    disk.rename(tmp_path / "withdrawn-disk")
    with ProjectQueue(config) as queue:
        result = queue.sync(now=True)[0]
        assert result["phase"] == "queued" and result["state"] != "needs_attention"
        assert not disk.exists()
    (tmp_path / "withdrawn-disk").rename(disk)
    live = project_storage.live_tree_bytes
    monkeypatch.setattr(project_storage, "live_tree_bytes", lambda _: 10**12)
    with ProjectQueue(config) as queue:
        assert "capacity" in queue.sync(now=True)[0]["error"]
    assert worker.db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 0
    monkeypatch.setattr(project_storage, "live_tree_bytes", live)
    with ProjectQueue(config) as queue:
        assert queue.sync(now=True)[0]["phase"] == "remote"


def test_remote_state_loss_never_silently_reassigns_or_reruns(
    tmp_path, worker, project, monkeypatch
):
    config, origins = project
    _, directory = freeze(tmp_path, worker)
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        queue.sync(now=True)
    monkeypatch.setattr(
        Client,
        "workflow_status",
        lambda *a: (_ for _ in ()).throw(
            urllib.error.HTTPError("http://127.0.0.1", 404, "missing", {}, None)
        ),
    )
    with ProjectQueue(config) as queue:
        result = queue.sync(now=True)[0]
        assert result["state"] == "needs_attention"
        assert "do not silently rerun" in result["error"]
        assert queue.sync(now=True) == queue.status()
    assert worker.db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 1


def test_shared_objects_reused_across_batches_and_negative_results_kept(tmp_path, worker, project):
    config, origins = project
    spec, directory = freeze(tmp_path, worker)
    # Add a required missing output: semantic failure remains a research result.
    spec["jobs"][-1]["outputs"]["absent"] = {
        "path": "artifacts/absent.json",
        "type": "json",
        "required": True,
    }
    original = tmp_path / "negative-plan"
    plan(spec, original)
    shutil.copytree(directory / "objects", original / "objects", dirs_exist_ok=True)
    with ProjectQueue(config) as queue:
        queue.enqueue(original, "local", origins)
        queue.sync(now=True)
    assert drive(worker)["state"] == "completed_with_errors"
    with ProjectQueue(config) as queue:
        first = queue.sync(now=True)[0]
        assert first["phase"] == "completed"
        root = queue.project.bulk()
        cache_before = {p.name for p in (root / "objects").iterdir() if p.is_dir()}
        report = next(queue.project.root / p for p in first["publications"] if "/report/" in p)
        assert load(report / "RUN_RESULT.json")["node"]["state"] == "failed"
        assert load(report / "RUN_RESULT.json")["attempt_history"]
    spec["submission_id"] = "second-batch"
    plan(spec, tmp_path / "second-plan")  # reference returned source objects, no repackaging
    with ProjectQueue(config) as queue:
        queue.enqueue(tmp_path / "second-plan", "local", origins)
        queue.sync(now=True)
    drive(worker, "second-batch")
    with ProjectQueue(config) as queue:
        second = queue.sync(now=True)[1]
        assert second["phase"] == "completed"
        assert cache_before <= {p.name for p in (root / "objects").iterdir() if p.is_dir()}
        assert not list((root / "collections").rglob("archive.tar.gz"))
        assert (
            len(list(queue.project.root.glob("research/candidates/*/*/offload_runs/*/report/*")))
            == 2
        )


@pytest.mark.parametrize(
    "bad",
    [
        "../outside",
        "research",
        "research/testing_stages",
        "research/candidates/directional_forecasting",
        "research/candidates/x/../outside",
    ],
)
def test_unsafe_origin_paths_are_rejected(project, bad):
    config, _ = project
    with pytest.raises((ValueError, StorageUnavailable)):
        Project(config).origin(bad)


def test_origin_symlink_and_submission_rebinding_are_rejected(tmp_path, worker, project):
    config, origins = project
    spec, directory = freeze(tmp_path, worker)
    with ProjectQueue(config) as queue:
        queue.enqueue(directory, "local", origins)
        changed = deepcopy(origins)
        changed["report"] = list(origins["bundle"])
        with pytest.raises(ValueError, match="another origin"):
            queue.enqueue(directory, "local", changed)
        folder = queue.project.root / origins["report"][0]
        folder.rename(folder.with_name("withdrawn"))
        folder.symlink_to(folder.with_name("withdrawn"), target_is_directory=True)
        with pytest.raises(ValueError, match="symlink"):
            queue.project.binding(spec, origins)


def test_existing_collection_import_preserves_delivery_and_is_idempotent(
    tmp_path, api, worker, project
):
    config, origins = project
    spec, directory = freeze(tmp_path, worker)
    api.submit_plan(directory)
    drive(worker)
    old = tmp_path / "old-result"
    before = api.collect(spec["submission_id"], old)
    project = Project(config)
    result = import_collection(project, old, origins)
    assert result["jobs_executed"] == 0
    assert verify_collection(result["collection"]) == before
    assert import_collection(project, old, origins) == result
    record = project.root / result["publications"][0]
    (record / "RESULT.md").write_text("Changed historical record")
    with pytest.raises(ValueError, match="differs"):
        import_collection(project, old, origins)


def test_compressed_file_readback_and_corruption_fail_closed(tmp_path, api, worker, project):
    config, origins = project
    spec, directory = freeze(tmp_path, worker)
    api.submit_plan(directory)
    drive(worker)
    old = tmp_path / "old-result"
    api.collect(spec["submission_id"], old)
    instance = Project(config)
    result = import_collection(instance, old, origins)
    record = next(instance.root / p for p in result["publications"] if "/report/" in p)
    returned = resolve_record(instance, record, "report.evidence", "metrics.csv")
    before = old / load(old / "INDEX.json")["report.evidence"] / "metrics.csv"
    assert returned.read_bytes() == before.read_bytes()
    assert returned.is_relative_to(instance.state / "read-cache")
    alias = tmp_path / "os-prefix-alias"
    alias.symlink_to(instance.root.parent, target_is_directory=True)
    aliased_record = alias / instance.root.name / record.relative_to(instance.root)
    assert resolve_record(instance, aliased_record, "report.evidence", "metrics.csv") == returned
    manifest = load(Path(result["collection"]) / "DELIVERY.json")["manifest"]
    obj = instance.bulk() / "objects" / manifest["objects"]["report.evidence"]
    assert not (obj / "data").exists()
    assert not (returned.parent / "ledger.bin").exists()
    with (obj / "archive.tar.gz").open("ab") as stream:
        stream.write(b"corruption")
    with pytest.raises(ValueError, match="archive changed"):
        resolve_record(instance, record, "report.evidence", "metrics.csv")


def test_crash_during_compaction_keeps_exact_archive_and_resumes_cleanup(
    tmp_path, api, worker, project
):
    from research_workflows.client import verify_object
    from research_workflows.compressed import compact_object, marker

    config, _ = project
    spec, directory = freeze(tmp_path, worker)
    api.submit_plan(directory)
    drive(worker)
    old = tmp_path / "old-result"
    receipt = api.collect(spec["submission_id"], old)
    ident = receipt["collected_objects"][0]
    instance = Project(config)
    target = instance.bulk() / "objects" / ident
    shutil.copytree(old / "objects" / ident, target)
    manifest = verify_object(target, ident)
    atomic(target / "ARCHIVE_ONLY.json", marker(ident, manifest))
    (target / "data").rename(target / "data.compacting")
    first = next((target / "data.compacting").rglob("*"))
    if first.is_file():
        first.unlink()
    assert compact_object(target, ident, max_bytes=1 << 30)["object_sha256"] == ident
    assert not (target / "data.compacting").exists()
    assert sha(target / "archive.tar.gz") == ident
    assert verify_object(target, ident) == manifest


def test_local_materialization_cache_limit_does_not_remove_evidence(
    tmp_path, api, worker, project, monkeypatch
):
    import lib.live_files

    config, origins = project
    spec, directory = freeze(tmp_path, worker)
    api.submit_plan(directory)
    drive(worker)
    old = tmp_path / "old-result"
    api.collect(spec["submission_id"], old)
    instance = Project(config)
    result = import_collection(instance, old, origins)
    record = next(instance.root / p for p in result["publications"] if "/report/" in p)
    monkeypatch.setattr(lib.live_files, "live_tree_bytes", lambda _: 10**12)
    with pytest.raises(StorageUnavailable, match="cache is full"):
        resolve_record(instance, record, "report.evidence", "metrics.csv")
    assert verify_collection(result["collection"])["delivery_sha256"] == result["delivery_sha256"]
