"""Exact workflow revocations must survive slow admission and worker restart."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import threading
from urllib.error import HTTPError

import pytest

from offload_service.core import Conflict
from research_workflows.client import Client
from research_workflows.simulation import configuration
from research_workflows.spec import identity
from research_workflows.worker import WorkflowWorker
from tests.test_research_workflows import (
    TOKEN, api as api_fixture, compiled, drive, worker as worker_fixture,
)

worker = worker_fixture
api = api_fixture


@pytest.mark.parametrize("phase", ["objects", "capacity"])
def test_revoke_during_uncommitted_admission_prevents_late_commit(tmp_path, worker, api, monkeypatch, phase):
    spec, _ = compiled(tmp_path, worker)
    entered, release, revoked = threading.Event(), threading.Event(), threading.Event()
    preflight_done = threading.Event()
    original_get = worker.workflows.objects.get
    original_capacity = worker.workflows.objects.capacity
    original_preflight = worker.workflows.preflight

    def hold():
        if not entered.is_set():
            entered.set()
            assert release.wait(10), "admission fixture not released"

    def get(key):
        if phase == "objects":
            hold()
        return original_get(key)

    def preflight(raw):
        result = original_preflight(raw)
        preflight_done.set()
        return result

    def capacity(additional=0):
        if phase == "capacity" and preflight_done.is_set():
            hold()
        return original_capacity(additional)

    def revoke():
        result = api.revoke_workflow(spec["submission_id"], identity(spec))
        revoked.set()
        return result

    monkeypatch.setattr(worker.workflows.objects, "get", get)
    monkeypatch.setattr(worker.workflows.objects, "capacity", capacity)
    monkeypatch.setattr(worker.workflows, "preflight", preflight)
    with ThreadPoolExecutor(max_workers=2) as pool:
        admission = pool.submit(api.request, "/v2/workflows", spec)
        try:
            assert entered.wait(5)
            with pytest.raises(HTTPError) as missing:
                api.workflow_status(spec["submission_id"])
            assert missing.value.code == 404
            cancellation = pool.submit(revoke)
            assert revoked.wait(2), "revocation blocked behind slow uncommitted admission"
            assert cancellation.result(timeout=5)["workflow"] is None
        finally:
            release.set()
        with pytest.raises(HTTPError) as stopped:
            admission.result(timeout=10)
        assert stopped.value.code == 409
    assert api.workflow_revocation(spec["submission_id"])["workflow_sha256"] == identity(spec)
    worker.workflows.tick()
    assert worker.db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 0
    assert worker.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    other = deepcopy(spec)
    other["submission_id"] = "independent-after-revocation"
    assert worker.workflows.submit(other)[1]
    assert drive(worker, other["submission_id"])["state"] == "completed"


def test_revocation_survives_worker_restart_and_rejects_before_preflight(tmp_path, monkeypatch):
    config = configuration()
    with WorkflowWorker(tmp_path / "worker", [], backend="trusted-local", workflow_config=config, min_free_mb=0) as first:
        spec, _ = compiled(tmp_path, first)
        receipt = first.workflows.revoke(spec["submission_id"], identity(spec))["revocation"]
    with WorkflowWorker(tmp_path / "worker", [], backend="trusted-local", workflow_config=config, min_free_mb=0) as second:
        assert second.workflows.revocation(spec["submission_id"]) == receipt

        def forbidden(_):
            pytest.fail("revoked workflow reached source verification")

        monkeypatch.setattr(second.workflows, "preflight", forbidden)
        with pytest.raises(Conflict, match="admission has been revoked"):
            second.workflows.submit(spec)
        changed = deepcopy(spec)
        changed["jobs"][0]["args"].append("changed")
        with pytest.raises(Conflict, match="different workflow"):
            second.workflows.submit(changed)
        assert second.workflows.revoke(spec["submission_id"], identity(spec))["revocation"] == receipt
        assert second.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_wrong_identity_does_not_cancel_admitted_work(tmp_path, worker, api):
    spec, _ = compiled(tmp_path, worker)
    worker.workflows.submit(spec)
    wrong = "0" * 64
    assert wrong != identity(spec)
    with pytest.raises(HTTPError) as rejected:
        api.revoke_workflow(spec["submission_id"], wrong)
    assert rejected.value.code == 409
    assert worker.db.execute("SELECT COUNT(*) FROM workflow_revocations").fetchone()[0] == 0
    assert drive(worker)["state"] == "completed"


def test_lost_revoke_response_can_be_read_back_and_repeated(tmp_path, worker, api):
    spec, _ = compiled(tmp_path, worker)
    first = api.revoke_workflow(spec["submission_id"], identity(spec))
    assert api.workflow_revocation(spec["submission_id"]) == first["revocation"]
    assert api.revoke_workflow(spec["submission_id"], identity(spec)) == first
    with pytest.raises(HTTPError) as rejected:
        api.revoke_workflow(spec["submission_id"], "0" * 64)
    assert rejected.value.code == 409
    assert api.workflow_revocation(spec["submission_id"]) == first["revocation"]
    assert first["revocation"]["execution_stopped"] == "NOT_ESTABLISHED_BY_REVOCATION"


@pytest.mark.parametrize("body", [{}, {"workflow_sha256": "invalid"},
    {"workflow_sha256": None}, {"workflow_sha256": "0" * 64, "extra": True}])
def test_bad_revocation_body_creates_no_record(worker, api, body):
    with pytest.raises(HTTPError) as rejected:
        api.request("/v2/workflows/unsubmitted/revoke", body)
    assert rejected.value.code == 400
    assert worker.db.execute("SELECT COUNT(*) FROM workflow_revocations").fetchone()[0] == 0


def test_revocation_requires_authentication(worker, api):
    wrong = Client(api.url, "x" * 43)
    with pytest.raises(HTTPError) as rejected:
        wrong.revoke_workflow("unsubmitted", "0" * 64)
    assert rejected.value.code == 401
    assert worker.db.execute("SELECT COUNT(*) FROM workflow_revocations").fetchone()[0] == 0


@pytest.mark.parametrize("completed", [False, True])
def test_revoke_matching_admitted_work_retains_history(tmp_path, worker, api, completed):
    spec, _ = compiled(tmp_path, worker)
    worker.workflows.submit(spec)
    if completed:
        before = drive(worker)
        delivery = worker.workflows.delivery(spec["submission_id"])
    else:
        worker.workflows.tick()
    result = api.revoke_workflow(spec["submission_id"], identity(spec))
    assert result["workflow"] is not None
    worker.workflows.tick()
    status = worker.workflows.status(spec["submission_id"])
    if completed:
        assert status == before
        assert worker.workflows.delivery(spec["submission_id"]) == delivery
    else:
        assert status["terminal"] and all(n["state"] == "cancelled" for n in status["nodes"])
        assert worker.db.execute("SELECT COUNT(*) FROM jobs WHERE attempt IS NOT NULL").fetchone()[0] == 0
    with pytest.raises(Conflict, match="revoked"):
        worker.workflows.submit(spec)


def test_cli_can_revoke_and_read_back_exact_identity(tmp_path, worker, api, capsys):
    from research_workflows.cli import main

    spec, _ = compiled(tmp_path, worker)
    token = tmp_path / "synthetic-token"
    token.write_text(TOKEN)
    common = ["--url", api.url, "--token-file", str(token), "--workflow", spec["submission_id"]]
    assert main(["revoke", *common, "--workflow-sha256", identity(spec)]) == 0
    receipt = json.loads(capsys.readouterr().out)["revocation"]
    assert main(["revocation", *common]) == 0
    assert json.loads(capsys.readouterr().out) == receipt


def test_ordinary_unknown_cancel_does_not_claim_revocation(worker, api):
    with pytest.raises(HTTPError) as missing:
        api.request("/v2/workflows/unsubmitted/cancel", {})
    assert missing.value.code == 404
    assert worker.db.execute("SELECT COUNT(*) FROM workflow_revocations").fetchone()[0] == 0
    assert api.request("/v2/capabilities")["durable_admission_revocation"] is True
