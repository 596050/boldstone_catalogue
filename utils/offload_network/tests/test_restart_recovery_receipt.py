"""Restart reconciliation must retain why an execution claim was unresolved."""

import json

import pytest

from offload_service.core import Template, Worker


@pytest.fixture
def unresolved(tmp_path):
    script = tmp_path / "never_run.py"
    script.write_text("raise AssertionError('recovery must not execute the job')\n")
    template = Template("recovery-fixture", script, max_input_mb=1, max_work_mb=8)
    with Worker(tmp_path / "worker", [template], backend="trusted-local", min_free_mb=0) as worker:
        # Admit and seal normally; only Docker observations are substituted.
        worker.backend = "docker"
        worker.images[template.name] = "sha256:" + "a" * 64
        worker.submit({"job_id": "interrupted-fixture", "template": template.name})
        job, attempt, payload = worker._claim()
        previous = {
            "error": "TimeoutError: job exceeded 14400 seconds",
            "termination_error": "could not stop previous job container; recovery blocked",
            "backend": "docker",
            "seal_sha256": payload["seal_sha256"],
            "image_id": payload["image_id"],
        }
        # Arrange the durable state left by _execute's failed cleanup branch.
        with worker.transaction() as db:
            db.execute("UPDATE jobs SET receipt=? WHERE id=?", (json.dumps(previous), job))
        yield worker, job, attempt, previous


@pytest.mark.parametrize("cancelled", [False, True])
def test_restart_retains_original_execution_error_after_confirmed_cleanup(unresolved, monkeypatch, cancelled):
    worker, job, attempt, previous = unresolved
    if cancelled:
        worker.cancel(job)
    removed = []

    def confirmed_cleanup(name):
        assert worker.status(job)["state"] == "running"
        assert worker.status(job)["receipt"] == previous
        removed.append(name)

    monkeypatch.setattr(worker, "_remove_container", confirmed_cleanup)
    worker._recover()
    after = worker.status(job)
    assert after["state"] == ("cancelled" if cancelled else "interrupted")
    assert removed == [attempt]
    assert after["receipt"]["restart_recovery"] == {
        "previous_state": "running", "previous_receipt": previous, "new_execution": False,
    }
    assert after["receipt"]["attempt"] == attempt
    assert after["receipt"].get("result_sha256") is None
    assert worker._claim() is None
    # A second reconciliation must not change a terminal receipt or retry it.
    worker._recover()
    assert worker.status(job) == after
    retained = json.loads((worker.root / "receipts" / (job + ".json")).read_text())
    assert retained == after["receipt"]


def test_unconfirmed_restart_cleanup_retains_nonterminal_claim_and_original_receipt(unresolved, monkeypatch):
    worker, job, _, previous = unresolved
    before = worker.status(job)

    def unavailable(_):
        raise RuntimeError("controlled Docker observation unavailable")

    monkeypatch.setattr(worker, "_remove_container", unavailable)
    with pytest.raises(RuntimeError, match="controlled Docker observation unavailable"):
        worker._recover()
    assert worker.status(job) == before
    assert worker.status(job)["receipt"] == previous
    assert not (worker.root / "receipts" / (job + ".json")).exists()


def test_clean_restart_records_no_invented_execution_cause(tmp_path):
    script = tmp_path / "never_run.py"
    script.write_text("raise AssertionError('recovery must not execute the job')\n")
    template = Template("clean-fixture", script, max_input_mb=1, max_work_mb=8)
    with Worker(tmp_path / "worker", [template], backend="trusted-local", min_free_mb=0) as worker:
        worker.submit({"job_id": "clean-restart", "template": template.name})
        worker._claim()
        worker._recover()
        after = worker.status("clean-restart")
        assert after["state"] == "interrupted"
        assert after["receipt"]["restart_recovery"] == {
            "previous_state": "running", "previous_receipt": {}, "new_execution": False,
        }
        assert worker._claim() is None
