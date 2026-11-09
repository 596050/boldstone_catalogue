"""Runs inside the isolated job; no control-plane credentials or Docker access."""

import json
import importlib.util
import math
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path


def main():
    work = Path.cwd()
    request = json.loads((work / "blobs/job.json").read_text())
    job, resources = request["job"], request["resources"]
    capsule = work / "blobs/capsule"
    inputs = {key: str(work / "blobs/inputs" / key) for key in job["inputs"]}
    outputs = {key: str(work / spec["path"]) for key, spec in job["outputs"].items()}
    for key in job["outputs"]:
        target = Path(outputs[key])
        target.parent.mkdir(parents=True, exist_ok=True)
    if job.get("portable_inputs"):
        helper = work / "blobs/code/portable.py"
        spec = importlib.util.spec_from_file_location("_offload_portable_inputs", helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for port in job["portable_inputs"]:
            inputs[port] = str(module.materialize(inputs[port], work / "artifacts/inputs" / port))
    pattern = re.compile(r"\{(input|output)\.([a-z][a-z0-9_-]*)\}")

    def expand(text):
        return pattern.sub(lambda m: (inputs if m[1] == "input" else outputs)[m[2]], text)

    args = [expand(text) for text in job["args"]]
    env = os.environ.copy()
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        WORKFLOW_INPUTS_JSON=json.dumps(inputs),
        WORKFLOW_OUTPUTS_JSON=json.dumps(outputs),
        WORKFLOW_JOB_ID=job["id"],
        WORKFLOW_REQUEST_FILE=str(work / "blobs/job.json"),
    )
    for key in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        env[key] = "1"
    cwd = work
    if job["kind"] in {"testing", "testing_stage"}:
        repository = capsule / job["testing"]["repository"]
        entry = repository / "research/testing_stages/testing.py"
        if not entry.is_file():
            raise ValueError("capsule lacks the canonical testing entrypoint")
        cwd = repository
        memory = resources["memory_mb"] / 1024
        args = [
            "escalate",
            # Research resource values are defaults. Keep them before caller
            # arguments so argparse preserves explicit budgets/reservations,
            # including --flag=value. Docker and native cgroup checks retain
            # the actual hard ceilings.
            "--cpu-limit",
            str(max(1, math.floor(resources["cpus"]))),
            "--memory-limit-gb",
            str(memory * 0.9),
            "--worker-memory-gb",
            str(max(0.03125, memory * 0.25)),
            "--threads-per-worker",
            "1",
            "--min-free-gb",
            "0.01",
            *args,
            # Workflow-owned destinations, stage scope and source/cache policy
            # remain mandatory and cannot be replaced by caller arguments.
            "--workflow",
            "research",
            "--data-refresh",
            "pinned",
            "--cache-mode",
            "off",
            "--through",
            job["testing"]["through"],
            "--output",
            str(work / "artifacts/testing"),
        ]
        env["PYTHONPATH"] = str(repository)
        if job["kind"] == "testing_stage":
            if work.as_posix() != "/work":
                raise ValueError("portable testing checkpoints require the Docker /work layout")
            entry = Path(__file__).parent / "stage_runner.py"
            # The runner is also in blobs/code; entrypoint copy is in blobs/.
            if not entry.exists():
                entry = work / "blobs/code/stage_runner.py"
            env["OFFLOAD_STAGE_REQUEST"] = str(work / "blobs/job.json")
    else:
        entry = capsule / job["entrypoint"]
        if not entry.is_file() or entry.is_symlink():
            raise ValueError("capsule entrypoint is unavailable")
        env["PYTHONPATH"] = str(capsule)
    if "python_environment" in job:
        runtime = Path(inputs[job["python_environment"]["input"]])
        helper = work / "blobs/code/environment.py"
        if not helper.is_file():
            raise ValueError("runtime validation helper is absent")
        # -I keeps candidate sitecustomize/.pth code out of the checker until its
        # exact bytes and target platform have been verified by the helper.
        rc = subprocess.call([sys.executable, "-I", "-B", str(helper), str(runtime),
                              outputs["runtime_validation"]], cwd=work, env=env,
                             stdin=subprocess.DEVNULL)
        if rc:
            (work / "WORKFLOW_EXECUTION.json").write_text(json.dumps({
                "schema": "marketmaker.offload_invocation.v1", "node_id": job["id"],
                "workflow_sha256": request["workflow_sha256"], "status": "RUNTIME_VALIDATION_FAILED",
                "native_exit_code": None, "validation_exit_code": rc, "kind": job["kind"],
                "performance_qualification": "NOT_ESTABLISHED"}))
            return rc
        env["PYTHONPATH"] = str(runtime / "site-packages") + os.pathsep + env["PYTHONPATH"]
    command = [sys.executable, "-B", str(entry), *args]
    rc = subprocess.call(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL)
    record = {
        "schema": "marketmaker.offload_invocation.v1",
        "node_id": job["id"],
        "workflow_sha256": request["workflow_sha256"],
        "native_exit_code": rc,
        "kind": job["kind"],
        "performance_qualification": "NOT_ESTABLISHED",
    }
    (work / "WORKFLOW_EXECUTION.json").write_text(json.dumps(record, sort_keys=True))
    return rc


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        Path("WORKFLOW_EXECUTION.json").write_text(
            json.dumps(
                {
                    "schema": "marketmaker.offload_invocation.v1",
                    "status": "ADAPTER_FAILED",
                    "reason": str(error),
                    "traceback": traceback.format_exc(),
                    "performance_qualification": "NOT_ESTABLISHED",
                }
            )
        )
        raise
