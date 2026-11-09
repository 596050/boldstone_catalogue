"""Retention failure/restore tests; OS and Docker ownership probes are simulated.

The separate generic lifecycle Docker test exercises the real ownership checks.
These tests never select existing user jobs or evidence.
"""

import os
import shutil
import sqlite3
from pathlib import Path

import pytest

from lib.file_lock import file_lock
from research_workflows import retention
from research_workflows.common import atomic, inventory, load, sha
from research_workflows.objects import extract_object, pack


@pytest.fixture
def local(tmp_path, monkeypatch):
    directory = tmp_path / "local"
    root = directory / "state"
    work = root / "work/offload-unit"
    work.mkdir(parents=True)
    (work / "payload").write_bytes(b"immutable evidence\n" * 500)
    (root / "unrelated").write_bytes(b"keep")
    atomic(directory / "worker.json", {"root": "state"})
    collection = {"final": True, "scope": "simulated verifier for fault injection"}
    atomic(directory / "LOCAL_RUN.json", {"schema": "marketmaker.local_offload_run.v1", "backend": "docker",
           "status": "COLLECTED_AND_VERIFIED", "worker_stopped": True, "worker_exit_code": 0,
           "worker_pid": os.getpid(), "returned": str(directory / "returned"),
           "collection": collection, "workflow_id": "generic"})
    with sqlite3.connect(root / "jobs.sqlite3") as db:
        db.executescript("CREATE TABLE jobs(id TEXT,state TEXT,attempt TEXT);"
                         "CREATE TABLE workflow_nodes(workflow TEXT,id TEXT,state TEXT);"
                         "CREATE TABLE workflow_attempts(workflow TEXT,job_id TEXT);")
        db.execute("INSERT INTO jobs VALUES ('job', 'succeeded', 'offload-unit')")
        db.execute("INSERT INTO workflow_nodes VALUES ('generic', 'node', 'succeeded')")
        db.execute("INSERT INTO workflow_attempts VALUES ('generic', 'job')")
    monkeypatch.setattr(retention, "process_alive", lambda pid: False)
    monkeypatch.setattr(retention, "container_mounts", lambda: [])
    monkeypatch.setattr(retention, "verify_collection", lambda *a, **k: collection)
    request = {"schema": retention.SCHEMA, "local_run": str(directory / "LOCAL_RUN.json"),
               "work_attempts": [work.name], "objects": [], "max_bytes": 2 << 20, "min_free_bytes": 0}
    return request, work, tmp_path / "retained"


def test_inspect_then_lossless_archive_restore_and_idempotent_receipts(local):
    request, work, retained = local
    expected = inventory(work)
    assert retention.retain(request)["status"] == "INSPECTED_NOT_EXECUTED"
    assert work.is_dir() and not retained.exists()
    completed = retention.retain(request, retained, execute=True)
    before = {path.name: (sha(path), path.stat().st_mtime_ns) for path in retained.glob("*.json")}
    assert not work.exists() and (work.parents[1] / "unrelated").read_bytes() == b"keep"
    result = retention.restore(retained, work.name, retained.parent / "restored", max_bytes=2 << 20)
    assert inventory(result["directory"]) == expected
    assert retention.retain(request, retained, execute=True) == completed
    assert before == {path.name: (sha(path), path.stat().st_mtime_ns) for path in retained.glob("*.json")}


@pytest.mark.parametrize("reason", ["pid", "mount", "nonterminal", "ownership", "lock", "collection"])
def test_active_or_unverified_local_work_is_never_removed(local, monkeypatch, reason):
    request, work, retained = local
    if reason == "pid":
        monkeypatch.setattr(retention, "process_alive", lambda pid: True)
    elif reason == "mount":
        monkeypatch.setattr(retention, "container_mounts", lambda: [{"id": "held", "sources": [str(work)]}])
    elif reason in {"nonterminal", "ownership"}:
        with sqlite3.connect(work.parents[1] / "jobs.sqlite3") as db:
            db.execute("UPDATE jobs SET state='running'" if reason == "nonterminal"
                       else "INSERT INTO jobs VALUES ('unrelated', 'succeeded', 'offload-other')")
    elif reason == "collection":
        monkeypatch.setattr(retention, "verify_collection", lambda *a, **k: {"final": True, "changed": True})
    if reason == "lock":
        with file_lock(work.parents[1] / "worker.lock", timeout=0):
            with pytest.raises(TimeoutError):
                retention.retain(request, retained, execute=True)
    else:
        with pytest.raises(ValueError):
            retention.retain(request, retained, execute=True)
    assert work.is_dir() and not retained.exists()


def test_corrupt_archive_cannot_authorize_deletion_or_restore(local, monkeypatch):
    request, work, retained = local
    original = retention.inactive
    calls = []
    def stop_before_delete(*args):
        calls.append(1)
        if len(calls) == 2:
            raise ValueError("synthetic interruption after verified archive")
        return original(*args)
    monkeypatch.setattr(retention, "inactive", stop_before_delete)
    with pytest.raises(ValueError, match="synthetic"):
        retention.retain(request, retained, execute=True)
    monkeypatch.setattr(retention, "inactive", original)
    archive = retained / "archives/offload-unit.tar.gz"
    archive.write_bytes(archive.read_bytes() + b"tamper")
    for call in (lambda: retention.retain(request, retained, execute=True),
                 lambda: retention.restore(retained, work.name, retained.parent / "restored", max_bytes=2 << 20)):
        with pytest.raises(ValueError, match="archive changed"):
            call()
    assert work.is_dir()


def test_interrupted_retirement_resumes_from_exact_archive(local, monkeypatch):
    request, work, retained = local
    remove = retention.shutil.rmtree
    def stop(path, *args, **kwargs):
        if str(path).endswith(".retiring"):
            raise OSError("synthetic retirement interruption")
        return remove(path, *args, **kwargs)
    monkeypatch.setattr(retention.shutil, "rmtree", stop)
    with pytest.raises(OSError, match="synthetic"):
        retention.retain(request, retained, execute=True)
    parked = work.with_name(work.name + ".retiring")
    assert parked.exists() and not work.exists()
    monkeypatch.setattr(retention.shutil, "rmtree", remove)
    assert retention.retain(request, retained, execute=True)["status"] == "COMPLETED"
    assert not parked.exists()


def test_restore_proof_tamper_and_nonfresh_destination_fail_closed(local, monkeypatch):
    request, work, retained = local
    retained.mkdir()
    with pytest.raises(ValueError, match="fresh"):
        retention.retain(request, retained, execute=True)
    retained = retained.parent / "fresh-retained"
    original = retention.inactive
    calls = []
    def interrupt(*args):
        calls.append(1)
        if len(calls) == 2:
            raise ValueError("stop")
        return original(*args)
    monkeypatch.setattr(retention, "inactive", interrupt)
    with pytest.raises(ValueError, match="stop"):
        retention.retain(request, retained, execute=True)
    monkeypatch.setattr(retention, "inactive", original)
    atomic(retained / "offload-unit.RESTORE_VERIFIED.json", {})
    with pytest.raises(ValueError, match="restore verification receipt"):
        retention.retain(request, retained, execute=True)
    assert work.exists()


def test_explicit_object_compaction_keeps_verifiable_archive(local):
    request, work, retained = local
    archive = retained.parent / "object.tar.gz"
    reference = pack(work, archive, max_bytes=request["max_bytes"])
    identity = reference["object_sha256"]
    target = work.parents[1] / "workflows/objects" / identity
    target.parent.mkdir(parents=True)
    extract_object(archive, target, max_bytes=request["max_bytes"])
    shutil.copyfile(archive, target / "archive.tar.gz")
    request.update(work_attempts=[], objects=[identity])
    result = retention.retain(request, retained, execute=True)
    assert result["compacted_objects"][0]["expanded_bytes_released"] > 0
    assert not (target / "data").exists() and (target / "archive.tar.gz").exists()
    assert work.exists()
    assert retention.retain(request, retained, execute=True) == result


def test_completed_request_cannot_remove_recreated_workspace(local):
    request, work, retained = local
    retention.retain(request, retained, execute=True)
    work.mkdir()
    (work / "new-user-file").write_text("preserve")
    with pytest.raises(ValueError, match="reappeared"):
        retention.retain(request, retained, execute=True)
    assert (work / "new-user-file").read_text() == "preserve"


@pytest.mark.parametrize("query_failure", [False, True])
def test_inactive_inspection_closes_readonly_database_before_return(local, monkeypatch, query_failure):
    request, work, _ = local
    if query_failure:
        db = sqlite3.connect(work.parents[1] / "jobs.sqlite3")
        try:
            db.execute("DROP TABLE workflow_nodes")
            db.commit()
        finally:
            db.close()
    connect = sqlite3.connect
    opened = []
    def tracked(*args, **kwargs):
        connection = connect(*args, **kwargs)
        opened.append(connection)  # Keep it alive to rule out deferred GC cleanup.
        return connection
    monkeypatch.setattr(retention.sqlite3, "connect", tracked)
    receipt, directory, root = retention.validate(request)
    try:
        if query_failure:
            with pytest.raises(sqlite3.OperationalError, match="no such table"):
                retention.inactive(request, receipt, directory, root)
        else:
            retention.inactive(request, receipt, directory, root)
        assert len(opened) == 1
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            opened[0].execute("SELECT 1")
    finally:
        for connection in opened:
            connection.close()
