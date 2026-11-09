"""Distinguish real execution from input checks without manufacturing liveness."""

import json
import threading
from types import SimpleNamespace

import pytest

from offload_service import observations
from offload_service.core import Template, Worker
from tests.test_research_workflows import compiled, drive, worker as workflow_worker


@pytest.fixture
def worker(tmp_path):
    code = tmp_path / "code"
    code.mkdir()
    script = code / "main.py"
    script.write_text("from pathlib import Path\nPath('value.txt').write_text('7')\n")
    template = Template("phase-job", script, code_dir=code, timeout_s=15)
    with Worker(tmp_path / "worker", [template], backend="trusted-local", min_free_mb=0) as value:
        yield value


def test_completed_process_is_still_nonterminal_during_input_verification(worker, monkeypatch):
    reached, release = threading.Event(), threading.Event()

    def verify(_):
        reached.set()
        assert release.wait(10)

    monkeypatch.setattr(worker, "verify_extra_inputs", verify)
    worker.submit({"job_id": "phase-observation", "template": "phase-job"})
    thread = threading.Thread(target=worker.process_next)
    thread.start()
    try:
        assert reached.wait(10)
        before = worker.status("phase-observation")
        assert before["state"] == "running"
        phase = before["receipt"]["worker_phase"]
        assert phase["phase"] == "VERIFYING_INPUTS_AFTER_EXECUTION"
        assert phase["observation_kind"] == "PHASE_TRANSITION_NOT_HEARTBEAT"
        assert not before["receipt"].get("result_sha256")
        work = worker.root / "work" / phase["attempt"]
        assert json.loads((work / "status.json").read_text())["exit_code"] == 0
        assert (work / "value.txt").read_text() == "7"
        assert worker.status("phase-observation") == before
    finally:
        release.set()
        thread.join(10)
    assert not thread.is_alive()
    final = worker.status("phase-observation")
    assert final["state"] == "succeeded" and final["receipt"]["result_sha256"]
    phase = final["receipt"]["worker_phase"]
    assert phase["phase"] == "TERMINAL" and phase["terminal_state"] == "succeeded"
    assert [p["phase"] for p in phase["transitions"]] == [
        "PREPARING_INPUTS", "SUPERVISING_EXECUTION", "STOPPING_EXECUTION",
        "VERIFYING_INPUTS_AFTER_EXECUTION", "VERIFYING_RESULT", "TERMINAL",
    ]
    elapsed = [p["elapsed_s"] for p in phase["transitions"]]
    assert elapsed == sorted(elapsed) and elapsed[-1] > 0
    assert json.loads((worker.root / "receipts/phase-observation.json").read_text()) == final["receipt"]


def test_post_execution_integrity_failure_retains_its_phase_and_cannot_be_freshened(worker, monkeypatch):
    def changed(_):
        raise ValueError("controlled changed input")

    monkeypatch.setattr(worker, "verify_extra_inputs", changed)
    worker.submit({"job_id": "phase-failure", "template": "phase-job"})
    result = worker.process_next()
    assert result["state"] == "failed"
    receipt = result["receipt"]
    assert "controlled changed input" in receipt["error"] and not receipt.get("result_sha256")
    history = receipt["worker_phase"]["transitions"]
    assert history[-2]["phase"] == "VERIFYING_INPUTS_AFTER_EXECUTION"
    assert history[-1]["phase"] == "TERMINAL"
    worker._record_phase(result["job_id"], receipt["attempt"], "SUPERVISING_EXECUTION")
    assert worker.status(result["job_id"]) == result


def test_old_attempt_cannot_replace_observation(worker):
    worker.submit({"job_id": "phase-fenced", "template": "phase-job"})
    job, attempt, _ = worker._claim()
    worker._record_phase(job, attempt, "PREPARING_INPUTS")
    with worker.transaction() as db:
        db.execute("UPDATE jobs SET attempt=? WHERE id=?", ("offload-" + "e" * 32, job))
    before = worker.status(job)
    worker._record_phase(job, attempt, "SUPERVISING_EXECUTION")
    worker._finish(job, attempt, "succeeded", {})
    assert worker.status(job) == before


def test_restart_retains_previous_phase_without_combining_clock_intervals(worker):
    worker.submit({"job_id": "phase-restart", "template": "phase-job"})
    job, attempt, _ = worker._claim()
    worker._record_phase(job, attempt, "PREPARING_INPUTS")
    previous = worker.status(job)["receipt"]["worker_phase"]
    templates = list(worker.templates.values())
    worker.close()
    with Worker(worker.root, templates, backend="trusted-local", min_free_mb=0) as resumed:
        result = resumed.status(job)
        assert result["state"] == "interrupted"
        phase = result["receipt"]["worker_phase"]
        assert phase["previous_worker_observation"] == previous
        assert phase["worker_instance"] != previous["worker_instance"]
        assert phase["transitions"] == [{"phase": "TERMINAL", "at": phase["updated_at"], "elapsed_s": 0}]


def test_phase_durations_ignore_wall_clock_jumps_and_repeated_updates(monkeypatch):
    clock = {"wall": 100.0, "tick": 10.0}
    monkeypatch.setattr(observations, "time", SimpleNamespace(
        time=lambda: clock["wall"], monotonic=lambda: clock["tick"]))
    args = {"job_id": "phase-clock", "attempt": "same", "worker_instance": "one"}
    first = observations.transition(None, phase="PREPARING_INPUTS", **args)
    clock.update(wall=-100, tick=12.5)
    assert observations.transition(first, phase="PREPARING_INPUTS", **args) == first
    second = observations.transition(first, phase="SUPERVISING_EXECUTION", **args)
    assert second["transitions"][-1]["elapsed_s"] == 2.5
    assert second["updated_at"] == -100


def test_workflow_status_exposes_retained_phases_without_reverification(tmp_path, workflow_worker, monkeypatch):
    spec, _ = compiled(tmp_path, workflow_worker)
    workflow_worker.workflows.submit(spec)
    result = drive(workflow_worker)
    assert result["state"] == "completed"
    assert all(n["worker_phase"]["phase"] == "TERMINAL" for n in result["nodes"])
    assert all(n["worker_phase"] == n["outputs"]["execution"]["receipt"]["worker_phase"] for n in result["nodes"])

    def forbidden(*_args, **_kwargs):
        raise AssertionError("status must not verify object bytes")

    monkeypatch.setattr(workflow_worker.workflows.objects, "get", forbidden)
    assert workflow_worker.workflows.status(spec["submission_id"]) == result
