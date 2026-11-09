"""Validate declared output ports after execution; never import returned code."""

import csv
from pathlib import Path

from .common import digest, inventory, load, parse, rel, sha


# Full-history gate and comparison reports can exceed the protocol document
# limit. Keep a separate finite bound for retained native evidence only; input
# declarations, API documents and declared JSON output ports retain their limit.
NATIVE_DOCUMENT_MAX_BYTES = 32 << 20


def _native_document(path):
    return load(path, max_bytes=NATIVE_DOCUMENT_MAX_BYTES)


def validate_ports(root, job, *, max_bytes):
    """Preserve valid partial evidence when a sibling output is invalid."""
    ports = {}
    for name, spec in job["outputs"].items():
        try:
            ports.update(_validate_ports(root, {"outputs": {name: spec}}, max_bytes=max_bytes))
        except (ValueError, OSError, KeyError, TypeError) as exc:
            ports[name] = {"status": "OUTPUT_INVALID", "error": str(exc)}
    return ports


def _validate_ports(root, job, *, max_bytes):
    root = Path(root)
    files = inventory(root, max_bytes=max_bytes, max_files=100000)
    ports = {}
    for name, spec in job["outputs"].items():
        path = root / spec["path"]
        if not path.exists():
            if spec["required"]:
                raise ValueError("required output missing: " + name)
            ports[name] = {"status": "NOT_PRODUCED"}
            continue
        if spec["type"] == "tree":
            if not path.is_dir():
                raise ValueError("expected output directory: " + name)
            selected = {p: value for p, value in files.items() if p.startswith(spec["path"] + "/")}
            if spec["required"] and not selected:
                raise ValueError("required output tree is empty: " + name)
        else:
            if not path.is_file():
                raise ValueError("expected output file: " + name)
            selected = {spec["path"]: files[spec["path"]]}
        if spec["type"] == "json":
            value = load(path)
            if spec.get("schema") and (
                not isinstance(value, dict) or value.get("schema") != spec["schema"]
            ):
                raise ValueError("output schema mismatch: " + name)
        if spec["type"] in {"csv", "jsonl"}:
            count = 0
            with path.open(encoding="utf-8", newline="") as stream:
                if spec["type"] == "csv":
                    rows = csv.reader(stream)
                    if next(rows, None) is None:
                        raise ValueError("CSV output lacks a header")
                    count = sum(1 for _ in rows)
                else:
                    for line in stream:
                        if line.strip():
                            parse(line)
                            count += 1
            if "rows" in spec and spec["rows"] != count:
                raise ValueError("output row-count mismatch: " + name)
        ports[name] = {
            "status": "VERIFIED",
            "path": spec["path"],
            "type": spec["type"],
            "files": selected,
            "bytes": sum(f["bytes"] for f in selected.values()),
        }
    return ports


def native_summary(root, job, *, native_directory=None):
    if job["kind"] not in {"testing", "testing_stage"}:
        return None
    directory = (
        Path(native_directory) if native_directory is not None else Path(root) / "artifacts/testing"
    )
    value = _native_document(directory / "RESULT.json")
    if (
        value.get("workflow") != "research"
        or value.get("performance_qualification") != "NOT_ESTABLISHED"
    ):
        raise ValueError("invalid native research scope")
    allowed = {"REQUESTED_GATES_PASSED", "STOPPED_AT_GATE", "CHECKPOINTED"}
    if value.get("status") not in allowed:
        raise ValueError("unsupported native gate status")
    # The native validator still owns metric correctness. Here verify receipt closure.
    previous = None
    from .spec import STAGES

    receipts = value.get("receipts", [])
    through = job["testing"]["through"]
    if value.get("through") != through or not receipts or len(receipts) > STAGES.index(through) + 1:
        raise ValueError("native gate endpoint/receipts do not match the request")
    if value["status"] == "REQUESTED_GATES_PASSED" and len(receipts) != STAGES.index(through) + 1:
        raise ValueError("native result omits a required gate")
    if value["status"] == "CHECKPOINTED":
        if (
            job["kind"] != "testing_stage"
            or len(receipts) != STAGES.index(job["testing"]["stop_after"]) + 1
            or job["testing"]["stop_after"] == through
        ):
            raise ValueError("checkpoint claims an incorrect gate boundary")
    if value.get("not_run") != list(STAGES[len(receipts) : STAGES.index(through) + 1]):
        raise ValueError("native missing-stage inventory is inconsistent")
    expected_stop = receipts[-1]["stage"] if value["status"] == "STOPPED_AT_GATE" else None
    if value.get("stopped_at") != expected_stop:
        raise ValueError("native stopped gate does not match its receipts")
    gate_plan = (
        _native_document(directory / "GATE_PLAN.json") if (directory / "GATE_PLAN.json").is_file() else None
    )
    plan = _native_document(directory / "PLAN.json") if (directory / "PLAN.json").is_file() else None
    if gate_plan is not None:
        if (
            digest({k: v for k, v in gate_plan.items() if k != "gate_plan_id"})
            != gate_plan["gate_plan_id"]
            or gate_plan["through"] != through
            or not plan
            or gate_plan["plan_id"] != plan["plan_id"]
            or digest({k: v for k, v in plan.items() if k != "plan_id"}) != plan["plan_id"]
        ):
            raise ValueError("native plans do not match their identities")
    elif value["status"] != "STOPPED_AT_GATE" or expected_stop != "contracts":
        raise ValueError("native gate plan is missing")
    for index, receipt in enumerate(receipts):
        if index >= len(STAGES) or receipt["stage"] != STAGES[index]:
            raise ValueError("native gates are reordered")
        folder = f"stage_{index:02d}_" + receipt["stage"]
        path = directory / folder / "GATE.json"
        gate = _native_document(path)
        if sha(path) != receipt["sha256"] or gate.get("previous_receipt_sha256") != previous:
            raise ValueError("native gate receipt chain is invalid")
        if value["status"] != "STOPPED_AT_GATE" and gate.get("status") != "PASS":
            raise ValueError("native success claims a failed gate")
        if gate.get("stage") != receipt["stage"] or gate.get("status") != receipt["status"]:
            raise ValueError("native receipt does not match its gate")
        if gate_plan and gate.get("gate_plan_id") != gate_plan["gate_plan_id"]:
            raise ValueError("native gate belongs to a different plan")
        if index < len(receipts) - 1 and gate["status"] != "PASS":
            raise ValueError("native execution advanced past a nonpassing gate")
        if (
            value["status"] == "STOPPED_AT_GATE"
            and index == len(receipts) - 1
            and gate["status"] == "PASS"
        ):
            raise ValueError("native stopped result has no nonpassing gate")
        previous = receipt["sha256"]
    prefix = receipts[0]["path"].removesuffix("/stage_00_contracts/GATE.json")
    if prefix == receipts[0]["path"]:
        raise ValueError("native output layout is not portable")

    def resolve(path):
        if not isinstance(path, str) or not path.startswith(prefix + "/"):
            raise ValueError("native result references an undeclared output directory")
        return directory / rel(path[len(prefix) + 1 :])

    def verify_artifact(path, expected):
        from .native_artifacts import verify

        work_mb = job.get("resources", {}).get("max_work_mb")
        verify(path, expected, root=directory, prefix=prefix,
               max_decoded_bytes=work_mb << 20 if type(work_mb) is int else None)

    if value.get("evaluation_result"):
        replay = _native_document(resolve(value["evaluation_result"]))
        plan_ref = replay["plan"]
        if (
            sha(resolve(plan_ref["path"])) != plan_ref["sha256"]
            or _native_document(resolve(plan_ref["path"])) != plan
            or replay["plan_id"] != plan["plan_id"]
        ):
            raise ValueError("returned replay differs from its native plan")
        planned = {j["job_id"]: j for j in plan["jobs"]}
        if set(replay["models"]) != set(planned):
            raise ValueError("returned replay omitted or added candidate/benchmark/seed jobs")
        for key, outcome in replay["models"].items():
            if "directory" not in outcome:
                if outcome.get("status") == "EVALUATED":
                    raise ValueError("completed model has no retained worker evidence")
                continue
            worker_root = resolve(outcome["directory"] + "/WORKER.json").parent
            worker = _native_document(worker_root / "WORKER.json")
            request = _native_document(worker_root / "REQUEST.json")
            if (
                worker.get("evaluation") != outcome.get("evaluation")
                or request["description"] != planned[key]["description"]
            ):
                raise ValueError("returned model evidence differs from the requested model/seed")
            if outcome.get("artifacts") != worker.get("artifacts"):
                raise ValueError("returned model artifact inventory differs from its worker")
            for relative, expected in outcome.get("artifacts", {}).items():
                verify_artifact(worker_root / rel(relative), expected)

        # Check all reference-shaped records in result evidence, never input/code
        # references outside this output prefix and never execute returned code.
        def references(item):
            if isinstance(item, dict):
                if (
                    isinstance(item.get("path"), str)
                    and item["path"].startswith(prefix + "/")
                    and "sha256" in item
                ):
                    verify_artifact(resolve(item["path"]), item["sha256"])
                for child in item.values():
                    references(child)
            elif isinstance(item, list):
                for child in item:
                    references(child)

        references(replay)
    return {
        "native_output_prefix": prefix,
        "verification": "NATIVE_PLANS_RECEIPTS_AND_ARTIFACT_REFERENCES",
        **{
            key: value.get(key)
            for key in (
                "status",
                "through",
                "stopped_at",
                "not_run",
                "statistical_verdict",
                "forward_statistical_verdict",
                "performance_qualification",
                "summary",
            )
        },
    }
