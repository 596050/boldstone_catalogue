"""Portable gate checkpoints, executed only inside the canonical Docker layout.

Calls the existing gate modules. It does not implement metrics, comparison or
statistics. State uses a closed JSON type vocabulary, never pickle. Source
receipts are copied byte-for-byte into a new attempt before continuation.
"""

import argparse
import hashlib
import importlib
import inspect
import json
import os
import shutil
import sys
from copy import deepcopy
from pathlib import Path


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            result.update(chunk)
    return result.hexdigest()


def encode(value):
    if isinstance(value, argparse.Namespace):
        return ["namespace", encode(vars(value))]
    if isinstance(value, Path):
        return ["path", str(value)]
    if isinstance(value, dict):
        return ["dict", [[key, encode(item)] for key, item in value.items()]]
    if isinstance(value, (list, tuple)):
        return ["list", [encode(item) for item in value]]
    if value is None or type(value) in (str, int, float, bool):
        return ["scalar", value]
    raise ValueError("unsupported checkpoint state type: " + type(value).__name__)


def decode(value, depth=0):
    if depth > 100 or not isinstance(value, list) or len(value) != 2:
        raise ValueError("invalid checkpoint encoding")
    kind, raw = value
    if kind == "namespace":
        return argparse.Namespace(**decode(raw, depth + 1))
    if kind == "path":
        if not isinstance(raw, str):
            raise ValueError("invalid checkpoint path")
        return Path(raw)
    if kind == "dict":
        result = {}
        for key, item in raw:
            if not isinstance(key, str) or key in result:
                raise ValueError("invalid checkpoint dictionary")
            result[key] = decode(item, depth + 1)
        return result
    if kind == "list":
        return [decode(item, depth + 1) for item in raw]
    if kind == "scalar" and (raw is None or type(raw) in (str, int, float, bool)):
        return raw
    raise ValueError("unsupported checkpoint value")


def read(path):
    if Path(path).stat().st_size > 64 << 20:
        raise ValueError("checkpoint JSON exceeds 64 MiB")

    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate checkpoint JSON key")
            value[key] = item
        return value

    return json.loads(
        Path(path).read_text(),
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite checkpoint JSON")),
    )


def tree(root):
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("checkpoint contains a symlink")
        if path.is_file() and path.name != "RUN.lock":
            result[path.relative_to(root).as_posix()] = sha(path)
    return result


def scientific_identity(request):
    resume = request["job"]["testing"].get("resume_input")
    return digest(
        {
            "capsule": request["capsule"],
            "image_id": request["image_id"],
            "arguments": request["job"]["args"],
            "repository": request["job"]["testing"]["repository"],
            "through": request["job"]["testing"]["through"],
            "resources": request["resources"],
            "inputs": {k: v for k, v in request["inputs"].items() if k != resume},
            "checkpoint_runner": sha(__file__),
            "runner_object": request["runner_object"],
            # Opt-in environment/relocation semantics are part of checkpoint
            # compatibility too. Absent fields preserve legacy identities.
            **{key: request["job"][key] for key in ("python_environment", "portable_inputs")
               if key in request["job"]},
        }
    )


def save_checkpoint(output, state, gate_plan, receipts, request):
    from research.testing_stages.common import atomic_json

    destination = Path("/work/artifacts/checkpoint")
    destination.mkdir(parents=True, exist_ok=False)
    copied = destination / "files"
    shutil.copytree(output, copied, ignore=lambda _, names: [n for n in names if n == "RUN.lock"])
    record = {
        "schema": "marketmaker.testing_checkpoint.v1",
        "layout": "/work",
        "scientific_identity": scientific_identity(request),
        "state": encode(state),
        "gate_plan": gate_plan,
        "receipts": receipts,
        "next_stage": len(receipts),
        "files": tree(copied),
        "performance_qualification": "NOT_ESTABLISHED",
    }
    record["checkpoint_id"] = digest(record)
    atomic_json(destination / "CHECKPOINT.json", record)


def restore_checkpoint(source, output, request):
    record = read(source / "CHECKPOINT.json")
    original = {k: v for k, v in record.items() if k != "checkpoint_id"}
    if (
        record.get("schema") != "marketmaker.testing_checkpoint.v1"
        or record.get("layout") != "/work"
        or digest(original) != record.get("checkpoint_id")
        or record.get("scientific_identity") != scientific_identity(request)
    ):
        raise ValueError("checkpoint identity/layout/code/runtime/inputs changed")
    if tree(source / "files") != record["files"]:
        raise ValueError("checkpoint file identities changed")
    if list(output.iterdir()):
        raise ValueError("checkpoint continuation requires an empty attempt output")
    shutil.copytree(source / "files", output, dirs_exist_ok=True)
    # The Docker-volume transport seals inputs as 0444/0555. copytree retains
    # those modes, but this new attempt must be able to lock and append gates.
    # Normalize only the verified, private copy; never modify sealed inputs.
    output.chmod(0o700)
    for directory, dirs, files in os.walk(output):
        for name in dirs:
            (Path(directory) / name).chmod(0o700)
        for name in files:
            (Path(directory) / name).chmod(0o600)
    if tree(output) != record["files"]:
        raise ValueError("checkpoint copy differs from its sealed input")
    gate_plan = record["gate_plan"]
    if (
        digest({k: v for k, v in gate_plan.items() if k != "gate_plan_id"})
        != gate_plan["gate_plan_id"]
    ):
        raise ValueError("checkpoint gate plan changed")
    from research.testing_stages.runtime.escalation import STAGES, directory

    previous = None
    receipts = record["receipts"]
    if record["next_stage"] != len(receipts) or not receipts:
        raise ValueError("invalid checkpoint continuation boundary")
    for index, receipt in enumerate(receipts):
        path = output / directory(index) / "GATE.json"
        gate = read(path)
        if (
            receipt["stage"] != STAGES[index]
            or receipt["status"] != "PASS"
            or gate["status"] != "PASS"
            or sha(path) != receipt["sha256"]
            or gate["previous_receipt_sha256"] != previous
            or gate["gate_plan_id"] != gate_plan["gate_plan_id"]
        ):
            raise ValueError("checkpoint skips or changes a preceding gate")
        previous = receipt["sha256"]
    state = decode(record["state"])
    if read(output / "PLAN.json") != state["plan"] or read(output / "GATE_PLAN.json") != gate_plan:
        raise ValueError("checkpoint state and native plan disagree")
    return state, gate_plan, receipts


def initialize(args, output):
    from research.testing_stages import experiment, profiles
    from research.testing_stages.common import HERE, atomic_json
    from research.testing_stages.runtime.escalation import STAGES, directory

    evaluation = deepcopy(args)
    evaluation.command, evaluation.verify = "test", True
    stop = STAGES.index(args.through)
    evaluation._defer_statistics = stop >= 7
    if args.workflow == "deployment" and stop == 9 and (not args.forward_config or not args.statistics_config):
        raise ValueError("deployment stage 09 requires prebound forward and statistical designs")
    if args.purpose == "inspect" and stop > 2:
        raise ValueError("inspection ends at models")
    requested = list(profiles.resolve(evaluation)["checks"])
    if stop >= 7 and "statistics" not in requested:
        requested.append("statistics")
    check_stage = {
        "causality": 3,
        "independent_verification": 5,
        "statistics": 7,
        "stress": 7,
        "native_execution": 8,
        "prospective": 9,
        "simulation_execution": 8,
        "forward_holdout": 9,
    }
    if any(check_stage.get(key, 7) > stop for key in requested):
        raise ValueError("requested checks extend beyond the final endpoint")
    evaluation.checks = []
    if evaluation.purpose == "stress":
        evaluation.purpose = "evaluate"
    state = {"requested_checks": requested, "evaluation_args": evaluation}
    state["plan"] = experiment.plan(evaluation)
    bindings = {
        str(path.resolve()): sha(path)
        for base in [HERE / "runtime", *HERE.glob("stage_[0-9][0-9]_*")]
        for path in base.glob("*.py")
    }
    bindings.update(
        {
            str(HERE / n): sha(HERE / n)
            for n in ("testing.py", "common.py", "__init__.py", "legacy_imports.py")
        }
    )
    gate_plan = {
        "schema": "marketmaker.progressive_gate_plan.v1",
        "through": args.through,
        "stages": [directory(i) for i in range(stop + 1)],
        "plan_id": state["plan"]["plan_id"],
        "framework_bindings": bindings,
        "requested_checks": requested,
        "requested_purpose": args.purpose,
        "performance_qualification": "NOT_ESTABLISHED",
    }
    gate_plan["gate_plan_id"] = digest(gate_plan)
    atomic_json(output / "PLAN.json", state["plan"])
    atomic_json(output / "RESOURCE_PLAN.json", state["plan"]["profile"]["resources"])
    atomic_json(output / "GATE_PLAN.json", gate_plan)
    return state, gate_plan, []


def finish(output, state, gate_plan, receipts, blocked, *, checkpointed):
    from research.testing_stages.common import atomic_json
    from research.testing_stages.runtime.escalation import STAGES
    from research.testing_stages.runtime.run_summary import markdown, summarize

    through = gate_plan["through"]
    if state.get("result_path") and not state.get("statistical_evidence"):
        from research.testing_stages.stage_07_statistics.command import evaluate

        state["statistical_evidence"] = evaluate(
            state["result_path"], state["plan"]["statistics_config"], output / "statistics",
            execution=state["plan"]["profile"].get("resources"),
        )
        path = output / "statistics/STATISTICS.json"
        state["statistical_reference"] = {"path": str(path), "sha256": sha(path)}
    result = {
        "schema": "marketmaker.progressive_gate_result.v1",
        "workflow": "research",
        "status": "STOPPED_AT_GATE"
        if blocked
        else ("CHECKPOINTED" if checkpointed else "REQUESTED_GATES_PASSED"),
        "through": through,
        "stopped_at": blocked,
        "receipts": receipts,
        "not_run": list(STAGES[len(receipts) : STAGES.index(through) + 1]),
        "evaluation_result": str(state["result_path"]) if state.get("result_path") else None,
        "statistical_verdict": state.get("statistical_evidence", {}).get("statistical_verdict"),
        "statistics": state.get("statistical_reference"),
        "forward_result": str(output / "stage_09_prospective/FORWARD_RESULT.json")
        if state.get("forward_evidence")
        else None,
        "forward_statistical_verdict": state.get("forward_evidence", {}).get("statistical_verdict"),
        "performance_qualification": "NOT_ESTABLISHED",
        "boundary": "Existing native gates; checkpoint completion is not final workflow or performance acceptance.",
    }
    extra = {"plan": state.get("plan")} if "plan" in inspect.signature(summarize).parameters else {}
    summary = summarize(result, state.get("result"), state.get("statistical_evidence"), **extra)
    result["summary"] = summary
    atomic_json(output / "RESULT.json", result, replace=True)
    atomic_json(output / "SUMMARY.json", summary, replace=True)
    lines = [markdown(summary), "", result["boundary"], "", "| Stage | Status |", "| --- | --- |"]
    lines += [f"| {r['stage']} | {r['status']} |" for r in receipts]
    lines += [f"| {n} | NOT_RUN |" for n in result["not_run"]]
    if state.get("result_path"):
        for filename in ("METRICS_COMPARISON.md", "METRICS_COMPARISON.csv", "metrics.csv"):
            source = Path(state["result_path"]).parent / filename
            if source.is_file():
                shutil.copyfile(source, output / filename)
    if state.get("statistical_evidence"):
        from research.testing_stages.stage_07_statistics import reporting

        lines += ["", reporting.markdown(state["statistical_evidence"])]
        # A resumed attempt may contain the preceding checkpoint's report.
        # Replace only its derived table, preserving all immutable gate receipts.
        comparison_path = output / "comparison.next.csv"
        reporting.write_csv(comparison_path, [state["statistical_evidence"]])
        comparison_path.replace(output / "comparison.csv")
        reporting.annotate_metrics(output, state["plan"], state["statistical_evidence"])
    if state.get("forward_evidence"):
        lines += ["", (output / "stage_09_prospective/RESULT.md").read_text()]
    (output / "RESULT.md").write_text("\n".join(lines) + "\n")
    model_tables = Path.cwd() / "research/testing_stages/stage_05_metrics/model_tables.py"
    if model_tables.exists():
        from research.testing_stages.stage_05_metrics.model_tables import write

        write(
            output,
            state["plan"],
            state.get("result"),
            state.get("statistical_evidence"),
            gates=result,
            announce=False,
        )
    return result


def main():
    from research.testing_stages import experiment_support as support
    from research.testing_stages.common import atomic_json, lock
    from research.testing_stages.runtime.escalation import STAGES, directory, parser

    args = parser().parse_args(sys.argv[1:])
    if args.workflow != "research" or args.data_refresh != "pinned" or args.cache_mode != "off":
        raise ValueError(
            "checkpoint execution requires isolated pinned research inputs with cache off"
        )
    request = read(os.environ["OFFLOAD_STAGE_REQUEST"])
    testing = request["job"]["testing"]
    output = Path("/work/artifacts/testing")
    output.mkdir(parents=True, exist_ok=True)
    stop = STAGES.index(testing["stop_after"])
    resume = testing.get("resume_input")
    # Restore into a new directory before acquiring a new owned lock.
    if resume:
        state, gate_plan, receipts = restore_checkpoint(
            Path("/work/blobs/inputs") / resume, output, request
        )
    else:
        if list(output.iterdir()):
            raise ValueError("stage execution needs a fresh output directory")
        state, gate_plan, receipts = initialize(args, output)
    if stop < len(receipts):
        raise ValueError("checkpoint continuation must advance to a later stage")
    blocked = None
    with lock(output):
        for index in range(len(receipts), stop + 1):
            folder = output / directory(index)
            folder.mkdir()
            try:
                support.unchanged(gate_plan["framework_bindings"])
                module = importlib.import_module(
                    "research.testing_stages." + directory(index) + ".gate"
                )
                row = module.run(state, folder)
                if not isinstance(row, dict) or row.get("status") not in {
                    "PASS",
                    "FAILED",
                    "NOT_EVALUABLE",
                    "NOT_IMPLEMENTED",
                    "NOT_MEASURED",
                }:
                    raise ValueError("invalid native gate result")
                support.unchanged(gate_plan["framework_bindings"])
            except Exception as exc:
                row = {"status": "FAILED", "reason": str(exc), "type": type(exc).__name__}
            row.update(
                stage=STAGES[index],
                gate_plan_id=gate_plan["gate_plan_id"],
                previous_receipt_sha256=receipts[-1]["sha256"] if receipts else None,
                performance_qualification="NOT_ESTABLISHED",
            )
            atomic_json(folder / "GATE.json", row)
            receipts.append(
                {
                    "stage": STAGES[index],
                    "status": row["status"],
                    "path": str(folder / "GATE.json"),
                    "sha256": sha(folder / "GATE.json"),
                }
            )
            if row["status"] != "PASS":
                blocked = STAGES[index]
                break
        checkpointed = not blocked and stop < STAGES.index(testing["through"])
        finish(output, state, gate_plan, receipts, blocked, checkpointed=checkpointed)
        if checkpointed:
            save_checkpoint(output, state, gate_plan, receipts, request)
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
