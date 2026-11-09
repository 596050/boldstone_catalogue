"""Observation failures cannot cancel an admitted computation.

These focused controls simulate API faults and owned-process signals. The
separate retained local Docker exercise uses real processes and a TCP disconnect.
"""
import errno
from http.client import IncompleteRead
import io
import json
import ssl
import subprocess
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from research_workflows import client as client_module, local
from research_workflows.client import Client
from research_workflows.common import load

WORKFLOW = "unit-observation"
IDENTITY = "a" * 64
TOKEN = "test_observation_token_" + "x" * 32


def terminal(**changes):
    return {"workflow_id": WORKFLOW, "workflow_sha256": IDENTITY,
            "state": "completed", "terminal": True,
            "nodes": [{"id": "node", "state": "succeeded"}], **changes}


class Clock:
    def __init__(self):
        self.now = 0.

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class ScriptOpener:
    def __init__(self, script):
        self.script, self.calls = list(script), []

    def open(self, request, *, timeout):
        self.calls.append((request.get_method(), request.full_url, timeout))
        value = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(value, BaseException):
            raise value
        return io.BytesIO(value if isinstance(value, bytes) else json.dumps(value).encode())


def scripted(monkeypatch, script):
    clock = Clock()
    monkeypatch.setattr(client_module, "time", clock)
    api = Client("http://127.0.0.1:12345", TOKEN, timeout=30)
    api.opener = ScriptOpener(script)
    return api, clock


@pytest.mark.parametrize("fault", [
    ConnectionResetError("connection reset"), TimeoutError("read timed out"),
    URLError(ConnectionRefusedError(errno.ECONNREFUSED, "connection refused")),
    HTTPError("http://127.0.0.1", 404, "not yet visible", {}, None),
    HTTPError("http://127.0.0.1", 503, "temporarily unavailable", {}, None),
    IncompleteRead(b"{", 20),
])
def test_transient_get_recovers_without_resubmitting_or_cancelling(monkeypatch, fault):
    api, clock = scripted(monkeypatch, [fault, terminal()])
    assert api.wait_workflow(WORKFLOW, deadline=.5, interval=.1) == terminal()
    assert len(api.opener.calls) == 2
    assert all(method == "GET" and url.endswith("/v2/workflows/" + WORKFLOW)
               for method, url, _ in api.opener.calls)
    assert clock.now == .1


def test_repeated_observation_errors_expire_budget_without_cancellation(monkeypatch):
    api, clock = scripted(monkeypatch, [ConnectionResetError("still disconnected")])
    with pytest.raises(TimeoutError, match="not cancelled"):
        api.wait_workflow(WORKFLOW, deadline=.3, interval=.1)
    assert clock.now == pytest.approx(.3)
    assert 2 <= len(api.opener.calls) <= 4
    assert all(call[0] == "GET" for call in api.opener.calls)


def test_one_status_request_cannot_receive_more_than_remaining_socket_budget(monkeypatch):
    api, _ = scripted(monkeypatch, [terminal()])
    api.wait_workflow(WORKFLOW, deadline=.3, interval=.1)
    assert 0 < api.opener.calls[0][2] <= .3
    assert api.timeout == 30  # Per-request override must not mutate the client.


@pytest.mark.parametrize("fault", [
    HTTPError("http://127.0.0.1", 400, "bad request", {}, None),
    HTTPError("http://127.0.0.1", 401, "unauthorized", {}, None),
    HTTPError("http://127.0.0.1", 403, "forbidden", {}, None),
    ssl.SSLCertVerificationError(1, "certificate verification failed"),
    URLError(ssl.SSLCertVerificationError(1, "certificate verification failed")),
    PermissionError(errno.EACCES, "permission denied"), b"malformed json",
])
def test_permanent_errors_are_not_hidden_by_retry(monkeypatch, fault):
    api, clock = scripted(monkeypatch, [fault, terminal()])
    with pytest.raises((OSError, ValueError)):
        api.wait_workflow(WORKFLOW, deadline=.5, interval=.1)
    assert len(api.opener.calls) == 1 and clock.now == 0


def test_observation_error_hook_retains_fault_and_expected_identity(monkeypatch):
    api, _ = scripted(monkeypatch, [ConnectionResetError("retained reset"), terminal()])
    errors = []
    assert api.wait_workflow(WORKFLOW, deadline=.5, interval=.1,
                             expected_sha256=IDENTITY, observation_hook=errors.append)["terminal"]
    assert len(errors) == 1
    assert errors[0]["error_type"] == "ConnectionResetError"
    assert errors[0]["error"] == "retained reset"
    assert errors[0]["workflow_id"] == WORKFLOW


@pytest.mark.parametrize("changed", [
    {"workflow_id": "other-workflow"}, {"workflow_sha256": "b" * 64},
    {"terminal": "true"}, {"terminal": True, "state": "running"},
])
def test_inconsistent_terminal_identity_is_not_accepted(monkeypatch, changed):
    api, _ = scripted(monkeypatch, [terminal(**changed)])
    with pytest.raises(ValueError):
        api.wait_workflow(WORKFLOW, deadline=.5, expected_sha256=IDENTITY)
    assert len(api.opener.calls) == 1


@pytest.fixture
def owned(monkeypatch, tmp_path):
    plan = tmp_path / "plan"
    plan.mkdir()
    (plan / "WORKFLOW.json").write_text(json.dumps(
        {"submission_id": WORKFLOW, "jobs": [{"runtime": "python"}]}))
    (plan / "PLAN_RECEIPT.json").write_text(json.dumps({"workflow_sha256": IDENTITY}))
    state = {"signals": [], "submit_error": None, "observe_error": None,
             "collect_error": None, "status": terminal(), "popen_options": None,
             "phase_receipts": {}}

    def capture_phase(boundary):
        state["phase_receipts"][boundary] = load(state["output"] / "LOCAL_RUN.json")

    class Process:
        pid, returncode = 43210, None

        def poll(self):
            return self.returncode

        def terminate(self):
            state["signals"].append("terminate")
            self.returncode = -15

        def kill(self):
            state["signals"].append("kill")
            self.returncode = -9

        def wait(self, timeout=None):
            return self.returncode

    process = Process()

    def start(*args, **kwargs):
        state["popen_options"] = kwargs
        kwargs["stdout"].write(b"Worker ready at http://127.0.0.1:12345; backend=docker\n")
        kwargs["stdout"].flush()
        return process

    def submit(*args, **kwargs):
        capture_phase("submit")
        if state["submit_error"]:
            raise state["submit_error"]
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    class API:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            return {"backend": "docker"}

        def wait_workflow(self, *args, **kwargs):
            capture_phase("observe")
            if state["observe_error"]:
                raise state["observe_error"]
            return state["status"]

        def collect(self, *args, partial=False, **kwargs):
            if not partial:
                capture_phase("collect")
            if state["collect_error"]:
                raise state["collect_error"]
            return {"final": not partial}

    monkeypatch.setattr(local.subprocess, "Popen", start)
    monkeypatch.setattr(local.subprocess, "run", submit)
    monkeypatch.setattr(local, "Client", API)
    monkeypatch.setattr(local, "verify_collection", lambda *a, **k: {"final": True})
    state.update(plan=plan, output=tmp_path / "owned", process=process)
    return state


def run_owned(state, **kwargs):
    return local.run(state["plan"], state["output"], image="unit-image",
                     disconnected_seconds=0, **kwargs)


@pytest.mark.parametrize("error", [ConnectionResetError("lost reply"),
    TimeoutError("observer deadline"), KeyboardInterrupt("observer interrupted")])
def test_uncertain_observation_never_signals_owned_worker(owned, error):
    owned["observe_error"] = error
    with pytest.raises(type(error)):
        run_owned(owned)
    assert owned["signals"] == []
    assert owned["process"].poll() is None
    record = load(owned["output"] / "LOCAL_RUN.json")
    assert record["worker_stopped"] is False
    assert record["worker_preserved"] is True
    assert record["workflow_id"] == WORKFLOW


def test_lost_submission_acknowledgement_never_signals_owned_worker(owned):
    owned["submit_error"] = subprocess.TimeoutExpired("requester", 3)
    with pytest.raises(subprocess.TimeoutExpired):
        run_owned(owned)
    assert owned["signals"] == []
    assert load(owned["output"] / "LOCAL_RUN.json")["worker_preserved"] is True
    before_reply = owned["phase_receipts"]["submit"]
    assert before_reply["status"] == "SUBMITTING_INPUTS_AND_WORKFLOW"
    assert before_reply["submission_attempted"] and not before_reply["terminal_observed"]
    assert before_reply["workflow_sha256"] == IDENTITY
    assert before_reply["url"] == "http://127.0.0.1:12345"
    assert before_reply["worker_pid"] == owned["process"].pid
    assert "requester_exit_code" not in before_reply
    assert "SUBMISSION_ACKNOWLEDGED" not in {
        row["status"] for row in load(owned["output"] / "LOCAL_RUN.json")["phase_history"]}


@pytest.mark.parametrize("changed", [{"workflow_sha256": "b" * 64},
                                      {"terminal": False, "state": "running"}])
def test_unverified_terminal_result_cannot_authorize_worker_stop(owned, changed):
    owned["status"] = terminal(**changed)
    with pytest.raises(ValueError):
        run_owned(owned)
    assert owned["signals"] == []


def test_confirmed_terminal_result_still_stops_owned_worker(owned):
    result = run_owned(owned)
    assert owned["signals"] == ["terminate"]
    assert result["worker_stopped"] and result["status"] == "COLLECTED_AND_VERIFIED"


def test_durable_phases_distinguish_submission_observation_and_verified_collection(owned):
    result = run_owned(owned)
    waiting = owned["phase_receipts"]["observe"]
    collecting = owned["phase_receipts"]["collect"]
    assert waiting["status"] == "OBSERVING_WORKFLOW"
    assert waiting["requester_exit_code"] == 0 and not waiting["terminal_observed"]
    assert collecting["status"] == "COLLECTING" and collecting["terminal_observed"]
    assert "collection" not in collecting and "returned" not in collecting
    history = result["phase_history"]
    phases = [row["status"] for row in history]
    assert phases.index("SUBMITTING_INPUTS_AND_WORKFLOW") < phases.index("SUBMISSION_ACKNOWLEDGED")
    assert phases.index("TERMINAL_OBSERVED") < phases.index("COLLECTING") < phases.index("COLLECTED_AND_VERIFIED")
    assert all(row["at_utc"] for row in history)
    assert [row["elapsed_seconds"] for row in history] == sorted(row["elapsed_seconds"] for row in history)
    assert load(owned["output"] / "LOCAL_RUN.json") == result


def test_collection_verification_failure_never_publishes_a_verified_phase(owned, monkeypatch):
    def corrupt_return(*args, **kwargs):
        raise ValueError("file digest changed after collection")
    monkeypatch.setattr(local, "verify_collection", corrupt_return)
    with pytest.raises(ValueError, match="file digest changed"):
        run_owned(owned)
    record = load(owned["output"] / "LOCAL_RUN.json")
    assert record["status"] == "ERROR" and record["terminal_observed"]
    assert "COLLECTED_AND_VERIFIED" not in {row["status"] for row in record["phase_history"]}
    assert "returned" not in record


def test_terminal_collection_failure_retains_evidence_and_allows_worker_stop(owned):
    owned["collect_error"] = ValueError("invalid returned archive")
    with pytest.raises(ValueError, match="invalid returned archive"):
        run_owned(owned)
    assert owned["signals"] == ["terminate"]
    assert (owned["output"] / "FINAL_STATUS.json").is_file()
    assert load(owned["output"] / "LOCAL_RUN.json")["status"] == "ERROR"


def test_failure_before_submission_still_stops_empty_owned_worker(owned):
    (owned["plan"] / "PLAN_RECEIPT.json").unlink()
    with pytest.raises(FileNotFoundError):
        run_owned(owned)
    assert owned["signals"] == ["terminate"]


def test_dead_worker_is_recorded_without_signalling_a_new_process(owned):
    owned["process"].returncode = -9
    owned["observe_error"] = ConnectionResetError("already exited")
    with pytest.raises(ConnectionResetError):
        run_owned(owned)
    assert owned["signals"] == []
    assert load(owned["output"] / "LOCAL_RUN.json")["worker_stopped"] is True
