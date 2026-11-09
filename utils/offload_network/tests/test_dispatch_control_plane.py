"""Slow verified dispatch must not disable durable cancellation/admission."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading

import pytest

from tests.test_research_workflows import worker as worker_fixture, compiled, drive

worker = worker_fixture


@pytest.mark.parametrize("changed", [False, True])
def test_cancel_during_slow_dispatch_is_prompt_and_never_launches(tmp_path, worker, monkeypatch, changed):
    spec, _ = compiled(tmp_path, worker)
    worker.workflows.submit(spec)
    entered, release, cancelled = threading.Event(), threading.Event(), threading.Event()
    original, calls = worker.workflows.objects.get, []

    def delayed(identity):
        if not entered.is_set():
            entered.set()
            assert release.wait(10), "dispatch fixture not released"
            if changed:
                raise ValueError("controlled source mutation while verifying")
        calls.append(identity)
        return original(identity)

    def cancel():
        value = worker.workflows.cancel(spec["submission_id"])
        cancelled.set()
        return value

    monkeypatch.setattr(worker.workflows.objects, "get", delayed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        dispatch = pool.submit(worker.workflows.tick)
        try:
            assert entered.wait(5)
            cancellation = pool.submit(cancel)
            assert cancelled.wait(2), "cancellation blocked behind slow verified dispatch"
        finally:
            release.set()
        dispatch.result(timeout=10)
        assert cancellation.result(timeout=10)["terminal"]
    result = worker.workflows.status(spec["submission_id"])
    assert all(row["state"] == "cancelled" and row["job_id"] is None for row in result["nodes"])
    assert worker.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    if not changed:
        assert calls  # The runner object still received full verification.


def test_new_admission_and_partial_delivery_survive_slow_dispatch(tmp_path, worker, monkeypatch):
    spec, _ = compiled(tmp_path, worker)
    worker.workflows.submit(spec)
    other = deepcopy(spec); other["submission_id"] = "independent-admission"
    entered, release, admitted = threading.Event(), threading.Event(), threading.Event()
    original = worker.workflows.objects.get
    owner = []

    def delayed(identity):
        if owner and threading.get_ident() == owner[0] and not entered.is_set():
            entered.set()
            assert release.wait(10), "dispatch fixture not released"
        return original(identity)

    def tick():
        owner.append(threading.get_ident())
        worker.workflows.tick()

    def admit():
        result = worker.workflows.submit(other)
        delivery = worker.workflows.delivery(spec["submission_id"], partial=True)
        admitted.set()
        return result, delivery

    monkeypatch.setattr(worker.workflows.objects, "get", delayed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        dispatch = pool.submit(tick)
        try:
            assert entered.wait(5)
            admission = pool.submit(admit)
            assert admitted.wait(2), "admission/delivery blocked behind unrelated dispatch"
        finally:
            release.set()
        dispatch.result(timeout=10)
        result, delivery = admission.result(timeout=10)
    assert result[1] and not delivery["manifest"]["final"]
    assert drive(worker, spec["submission_id"])["state"] == "completed"
    assert drive(worker, other["submission_id"])["state"] == "completed"


def test_cancel_intended_id_not_yet_committed_to_job_queue(tmp_path, worker):
    spec, _ = compiled(tmp_path, worker)
    worker.workflows.submit(spec)
    with worker.transaction() as db:
        db.execute("UPDATE workflow_nodes SET state='dispatching',job_id='wf-never-submitted' "
                   "WHERE workflow=? AND id=?", (spec["submission_id"], spec["jobs"][0]["id"]))
    status = worker.workflows.cancel(spec["submission_id"])
    assert status["terminal"] and all(n["state"] == "cancelled" for n in status["nodes"])
    worker.workflows.tick()
    assert worker.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_dispatch_size_lookup_does_not_replace_before_execution_verification(tmp_path, worker, monkeypatch):
    spec, _ = compiled(tmp_path, worker)
    worker.workflows.submit(spec)
    store = worker.workflows.objects
    identity = spec["jobs"][0]["inputs"]["values"]["object_sha256"]
    original, calls = store.get, []

    def checked(key):
        calls.append(key)
        return original(key)

    monkeypatch.setattr(store, "get", checked)
    worker.workflows.tick()
    assert identity not in calls  # Provisional budget need not rehash bulk data.
    (store.directory(identity)/"data/values.json").write_text("corrupted after admission")
    assert store.declared_size(identity) > 0  # Explicitly not a verification API.
    with pytest.raises(ValueError):
        store.get(identity)
    worker.process_next()
    assert identity in calls
    worker.workflows.tick()
    status = worker.workflows.status(spec["submission_id"])
    first = next(n for n in status["nodes"] if n["id"] == spec["jobs"][0]["id"])
    assert first["state"] == "failed"


def test_admission_capacity_scan_does_not_block_other_workflow_snapshot(tmp_path, worker, monkeypatch):
    spec, _ = compiled(tmp_path, worker)
    worker.workflows.submit(spec)
    other = deepcopy(spec)
    other["submission_id"] = "slow-capacity-admission"
    entered, release, returned = threading.Event(), threading.Event(), threading.Event()
    preflight_done = threading.Event()
    original_preflight = worker.workflows.preflight
    original_capacity = worker.workflows.objects.capacity

    def preflight(raw):
        value = original_preflight(raw)
        preflight_done.set()
        return value

    def capacity(additional=0):
        if preflight_done.is_set() and not entered.is_set():
            entered.set()
            assert release.wait(10), "capacity fixture not released"
        return original_capacity(additional)

    def snapshot():
        value = worker.workflows.delivery(spec["submission_id"], partial=True)
        returned.set()
        return value

    monkeypatch.setattr(worker.workflows, "preflight", preflight)
    monkeypatch.setattr(worker.workflows.objects, "capacity", capacity)
    with ThreadPoolExecutor(max_workers=2) as pool:
        admission = pool.submit(worker.workflows.submit, other)
        try:
            assert entered.wait(5)
            collection = pool.submit(snapshot)
            assert returned.wait(2), "snapshot blocked behind admission's live storage scan"
        finally:
            release.set()
        assert admission.result(timeout=10)[1]
        assert not collection.result(timeout=10)["manifest"]["final"]


@pytest.mark.parametrize("phase", ["capacity", "prepare", "prepare_failure", "before_submit"])
def test_cancel_and_snapshot_during_worker_admission_never_launch(tmp_path, worker, monkeypatch, phase):
    from offload_service import core

    spec, _ = compiled(tmp_path, worker)
    worker.workflows.submit(spec)
    entered, release, cancelled = threading.Event(), threading.Event(), threading.Event()
    owner = core if phase == "capacity" else worker
    attribute = {"capacity": "live_tree_bytes", "prepare": "_prepare", "prepare_failure": "_prepare", "before_submit": "submit"}[phase]
    original = getattr(owner, attribute)

    def delayed(*args, **kwargs):
        if not entered.is_set():
            entered.set()
            assert release.wait(10), "worker admission fixture not released"
            if phase == "prepare_failure":
                raise ValueError("controlled source failure after durable cancellation")
        return original(*args, **kwargs)

    def cancel_and_snapshot():
        worker.workflows.cancel(spec["submission_id"])
        value = worker.workflows.delivery(spec["submission_id"], partial=True)
        cancelled.set()
        return value

    monkeypatch.setattr(owner, attribute, delayed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        dispatch = pool.submit(worker.workflows.tick)
        try:
            assert entered.wait(5)
            cancellation = pool.submit(cancel_and_snapshot)
            assert cancelled.wait(2), "control plane blocked behind worker admission"
        finally:
            release.set()
        dispatch.result(timeout=10)
        cancellation.result(timeout=10)
    result = drive(worker, spec["submission_id"])
    assert result["terminal"] and all(n["state"] == "cancelled" for n in result["nodes"])
    assert worker.db.execute("SELECT COUNT(*) FROM jobs WHERE attempt IS NOT NULL").fetchone()[0] == 0
    assert worker.db.execute("SELECT COUNT(*) FROM jobs WHERE state!='cancelled'").fetchone()[0] == 0


def test_dependency_change_during_preparation_is_fenced_before_claim(tmp_path, worker, monkeypatch):
    spec, _ = compiled(tmp_path, worker)
    worker.workflows.submit(spec)
    worker.workflows.tick()
    worker.process_next()  # The bundle producer genuinely finishes.
    worker.workflows._tick_node(spec["submission_id"], "bundle")
    generated = next(n for n in worker.workflows.status(spec["submission_id"])["nodes"] if n["id"] == "generated")
    assert generated["state"] == "waiting"
    original = worker._prepare
    changed = []

    def changed_parent(job_id, template, args, metadata):
        payload = original(job_id, template, args, metadata)
        child = worker.db.execute("SELECT id FROM workflow_nodes WHERE workflow=? AND job_id=?", (spec["submission_id"], job_id)).fetchone()
        if child and child[0] == "generated":
            with worker.transaction() as db:
                db.execute("UPDATE workflow_nodes SET attempt=attempt+1 WHERE workflow=? AND id='bundle'", (spec["submission_id"],))
            changed.append(job_id)
        return payload

    monkeypatch.setattr(worker, "_prepare", changed_parent)
    worker.workflows._tick_node(spec["submission_id"], "generated")
    assert len(changed) == 1
    result = worker.status(changed[0])
    assert result["state"] == "cancelled" and result["receipt"]["attempt"] is None
    assert "fence changed" in result["receipt"]["error"]
    assert result["cancel_requested"]
