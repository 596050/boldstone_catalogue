"""Large native evidence keeps receipt and artifact checks and a finite bound."""
from pathlib import Path

import pytest

from research_workflows.common import atomic, digest, load, sha
from research_workflows.output_manifest import NATIVE_DOCUMENT_MAX_BYTES, native_summary, validate_ports
from research_workflows.spec import STAGES


def evidence(root, *, large=None, size=9 << 20):
    def padded(name, value):
        if name == large:
            value["retained_detail"] = "x" * size
        return value

    prefix = "/work/artifacts/testing"
    plan = padded("plan", {"jobs": [{"job_id": "one", "description": {"id": "fixture"}}]})
    plan["plan_id"] = digest(plan)
    atomic(root / "PLAN.json", plan)
    gate_plan = padded("gate_plan", {"plan_id": plan["plan_id"], "through": "replay"})
    gate_plan["gate_plan_id"] = digest(gate_plan)
    atomic(root / "GATE_PLAN.json", gate_plan)
    previous, receipts = None, []
    for index, stage in enumerate(STAGES[:STAGES.index("replay") + 1]):
        relative = f"stage_{index:02d}_{stage}/GATE.json"
        gate = {"stage": stage, "status": "PASS", "previous_receipt_sha256": previous,
                "gate_plan_id": gate_plan["gate_plan_id"]}
        atomic(root / relative, padded("gate" if stage == "replay" else stage, gate))
        previous = sha(root / relative)
        receipts.append({"stage": stage, "status": "PASS", "path": prefix + "/" + relative,
                         "sha256": previous})
    relative = "stage_04_replay/evaluation/one"
    worker_root = root / relative
    worker_root.mkdir(parents=True)
    (worker_root / "ledger.txt").write_text("retained ledger\n")
    outcome = {"status": "EVALUATED", "directory": prefix + "/" + relative,
               "evaluation": {"result": "fixture"},
               "artifacts": {"ledger.txt": sha(worker_root / "ledger.txt")}}
    atomic(worker_root / "WORKER.json", padded("worker", dict(outcome)))
    atomic(worker_root / "REQUEST.json", padded("request", {"description": {"id": "fixture"}}))
    relative_result = "stage_04_replay/evaluation/RESULT.json"
    atomic(root / relative_result, padded("replay", {
        "plan": {"path": prefix + "/PLAN.json", "sha256": sha(root / "PLAN.json")},
        "plan_id": plan["plan_id"], "models": {"one": outcome}}))
    atomic(root / "RESULT.json", padded("result", {
        "workflow": "research", "performance_qualification": "NOT_ESTABLISHED",
        "status": "REQUESTED_GATES_PASSED", "through": "replay", "not_run": [],
        "stopped_at": None, "receipts": receipts,
        "evaluation_result": prefix + "/" + relative_result, "statistical_verdict": "FAILED"}))
    return {"kind": "testing", "testing": {"through": "replay"}}, worker_root


@pytest.mark.parametrize("document", ["plan", "gate_plan", "gate", "replay", "worker", "request", "result"])
def test_large_native_documents_preserve_complete_receipt_validation(tmp_path, document):
    job, _ = evidence(tmp_path, large=document)
    summary = native_summary(None, job, native_directory=tmp_path)
    assert summary["verification"] == "NATIVE_PLANS_RECEIPTS_AND_ARTIFACT_REFERENCES"
    assert summary["statistical_verdict"] == "FAILED"
    assert summary["performance_qualification"] == "NOT_ESTABLISHED"


def test_large_native_report_still_rejects_changed_artifacts(tmp_path):
    job, worker = evidence(tmp_path, large="replay")
    (worker / "ledger.txt").write_text("changed\n")
    with pytest.raises(ValueError, match="ledger/artifact changed"):
        native_summary(None, job, native_directory=tmp_path)


def test_large_native_report_still_rejects_changed_gate_receipt(tmp_path):
    job, _ = evidence(tmp_path, large="gate")
    path = tmp_path / "stage_04_replay/GATE.json"
    with path.open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="receipt chain is invalid"):
        native_summary(None, job, native_directory=tmp_path)


def test_native_report_limit_is_finite(tmp_path):
    job, _ = evidence(tmp_path, large="result", size=NATIVE_DOCUMENT_MAX_BYTES)
    with pytest.raises(ValueError, match="JSON exceeds configured limit"):
        native_summary(None, job, native_directory=tmp_path)


def test_protocol_and_declared_json_output_limit_remains_unchanged(tmp_path):
    path = tmp_path / "artifacts/result.json"
    atomic(path, {"detail": "x" * (9 << 20)})
    with pytest.raises(ValueError, match="JSON exceeds configured limit"):
        load(path)
    job = {"outputs": {"result": {"type": "json", "path": "artifacts/result.json", "required": True}}}
    assert validate_ports(tmp_path, job, max_bytes=16 << 20)["result"]["status"] == "OUTPUT_INVALID"
