"""Owned loopback worker process for real local Docker offload exercises.

No simulator and no public tunnel. Inputs are uploaded through the normal API,
jobs run in Docker, and returned evidence is verified by the normal collector.
Retain the complete directory; there is no implicit artifact deletion.
"""

import os
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .client import Client, checked_workflow_status, verify_collection
from .common import atomic, load, name, positive


def admission_timeout(deadline, max_object_mb):
    """HTTP timeout for plan upload/commit. The 30s client default cannot hash multi-GiB objects."""
    needed = 120.0 + float(max_object_mb)
    return min(float(deadline), max(300.0, needed))


def store_limits(max_object_mb):
    """Archive plus extracted tree must both fit; 4 GiB cannot hold a full-minute object."""
    needed = max(int(max_object_mb) * 2, 4096)
    return {"worker_max_store_mb": max(8192, needed), "workflow_max_store_mb": needed}


def run(
    plan,
    directory,
    *,
    image,
    runtime="python",
    deadline=900,
    concurrency=2,
    disconnected_seconds=1,
    admitted_hook=None,
    runtime_resources=None,
    min_free_mb=256,
    max_object_mb=256,
    max_return_mb=1024,
    input_transport="bind",
):
    plan, directory = Path(plan).resolve(), Path(directory).resolve()
    positive(deadline, 86400, integer=False)
    positive(concurrency, 8)
    if not 0 <= disconnected_seconds <= 60:
        raise ValueError("local disconnected interval must be 0-60 seconds")
    name(runtime)
    resources = {
        "cpus": 1,
        "memory_mb": 1024,
        "pids": 128,
        "timeout_s": 300,
        "max_work_mb": 512,
        "max_output_mb": 128,
        "max_input_mb": 256,
    }
    if runtime_resources is not None:
        if not isinstance(runtime_resources, dict) or set(runtime_resources) - set(resources):
            raise ValueError("runtime_resources must contain only declared numeric resource limits")
        resources.update(runtime_resources)
    for key, value in resources.items():
        positive(value, 10485760, integer=key not in ("cpus", "timeout_s"))
    positive(min_free_mb, 10485760)
    positive(max_object_mb, 1048576)
    positive(max_return_mb, 1048576)
    if input_transport not in ("bind", "docker-volume"):
        raise ValueError("input_transport must be bind or docker-volume")
    for key in ("cpus", "memory_mb", "pids", "max_work_mb"):
        positive(resources[key] * concurrency, 10485760, integer=key != "cpus")
    requested_runtimes = {job["runtime"] for job in load(plan / "WORKFLOW.json")["jobs"]}
    unavailable = requested_runtimes - {runtime}
    if unavailable:
        raise ValueError(
            "local worker runtime " + runtime + " cannot run requested runtimes: "
            + ", ".join(sorted(unavailable))
            + "; select the matching runtime or use a configured multi-runtime worker"
        )
    directory.mkdir(parents=True, exist_ok=False)
    token_file = directory / "access-token"
    with os.fdopen(os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        stream.write(secrets.token_urlsafe(32))
    stores = store_limits(max_object_mb)
    config = {
        "root": "state",
        "token_file": "access-token",
        "port": 0,
        "concurrency": concurrency,
        "max_pending": 128,
        "min_free_mb": min_free_mb,
        "max_store_mb": stores["worker_max_store_mb"],
        "templates": {},
        "workflows": {
            "enabled": True,
            "input_transport": input_transport,
            "runtimes": {runtime: {"image": image, **resources}},
            "capacity": {
                k: resources[k] * concurrency for k in ("cpus", "memory_mb", "pids", "max_work_mb")
            },
            "max_object_mb": max_object_mb,
            "max_store_mb": stores["workflow_max_store_mb"],
            "min_free_mb": min_free_mb,
        },
    }
    atomic(directory / "worker.json", config)
    # Explicit controller package location supports an editable checkout as well
    # as an installed wheel. These host variables are not passed into job images.
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic()
    record = {
        "schema": "marketmaker.local_offload_run.v1",
        "backend": "docker",
        "input_transport": input_transport,
        "plan": str(plan),
        "max_return_mb": max_return_mb,
        "requester_exit_after_submission": True,
        "disconnected_seconds": disconnected_seconds,
        "status": "STARTING",
        "automatic_delete": False,
        "performance_qualification": "NOT_ESTABLISHED",
    }
    process, client = None, None
    submission_attempted, terminal_observed = False, False

    def checkpoint(status=None):
        # These are controller phase observations, not queue heartbeats or
        # scientific verdicts. Persist recovery coordinates before a potentially
        # long upload, and never call submission or terminal exit collection.
        observed = datetime.now(timezone.utc).isoformat()
        elapsed = round(time.monotonic() - started, 3)
        if status is not None:
            record["status"] = status
            record.setdefault("phase_history", []).append(
                {"status": status, "at_utc": observed, "elapsed_seconds": elapsed}
            )
        record.update(updated_at_utc=observed, elapsed_seconds=elapsed,
                      submission_attempted=submission_attempted,
                      terminal_observed=terminal_observed)
        atomic(directory / "LOCAL_RUN.json", record)

    try:
        checkpoint("STARTING")
        with (directory / "worker.log").open("xb") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "offload_service",
                    "serve",
                    "--config",
                    str(directory / "worker.json"),
                ],
                cwd=directory,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=os.name == "posix",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
        record["worker_pid"] = process.pid
        until = started + min(deadline, 90)
        while True:
            text = (directory / "worker.log").read_text(errors="replace")
            ready = re.search(r"Worker ready at (http://127\.0\.0\.1:\d+);", text)
            if ready:
                break
            if process.poll() is not None or time.monotonic() >= until:
                raise RuntimeError("local Docker worker did not become ready; inspect worker.log")
            time.sleep(0.1)
        url = ready[1]
        record["url"] = url
        request_timeout = admission_timeout(deadline, max_object_mb)
        record["request_timeout_seconds"] = request_timeout
        workflow = name(load(plan / "WORKFLOW.json")["submission_id"])
        workflow_sha256 = load(plan / "PLAN_RECEIPT.json")["workflow_sha256"]
        record.update(workflow_id=workflow, workflow_sha256=workflow_sha256,
                      worker_config=str(directory / "worker.json"), token_file=str(token_file))
        # A requester can lose its acknowledgement after a successful admission.
        # From this point, observation failure must not stop the owned worker.
        submission_attempted = True
        checkpoint("SUBMITTING_INPUTS_AND_WORKFLOW")
        # A separate requester exits after admission, before the queue completes.
        submitted = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "research_workflows",
                "submit",
                "--plan",
                str(plan),
                "--url",
                url,
                "--token-file",
                str(token_file),
                "--request-timeout",
                str(request_timeout),
            ],
            cwd=directory,
            env=env,
            text=True,
            capture_output=True,
            timeout=max(1, deadline - (time.monotonic() - started)),
        )
        (directory / "submission.stdout").write_text(submitted.stdout)
        (directory / "submission.stderr").write_text(submitted.stderr)
        if submitted.returncode:
            raise RuntimeError("local submission failed; inspect submission.stderr")
        record["requester_exit_code"] = submitted.returncode
        checkpoint("SUBMISSION_ACKNOWLEDGED")
        if admitted_hook:
            admitted_hook()
        time.sleep(disconnected_seconds)
        # A new client reconnects; the worker never needs original source paths.
        client = Client(url, token_file.read_text(), timeout=request_timeout)
        record["capabilities"] = client.request("/v2/capabilities")

        def observation_error(event):
            record["observation_error_count"] = record.get("observation_error_count", 0) + 1
            record["recent_observation_errors"] = (record.get("recent_observation_errors", []) + [event])[-20:]
            checkpoint()
            if process.poll() is not None:
                raise RuntimeError("owned worker exited during observation; execution outcome remains unconfirmed")

        checkpoint("OBSERVING_WORKFLOW")
        status = client.wait_workflow(
            workflow, deadline=max(1, deadline - (time.monotonic() - started)),
            expected_sha256=workflow_sha256, observation_hook=observation_error,
        )
        checked_workflow_status(status, workflow, workflow_sha256, require_terminal=True)
        terminal_observed = True
        atomic(directory / "FINAL_STATUS.json", status)
        checkpoint("TERMINAL_OBSERVED")
        checkpoint("COLLECTING")
        record["collection"] = client.collect(
            workflow, directory / "returned", max_bytes=max_return_mb << 20
        )
        assert (
            verify_collection(directory / "returned", max_bytes=max_return_mb << 20) == record["collection"]
        )
        record["returned"] = str(directory / "returned")
        checkpoint("COLLECTED_AND_VERIFIED")
    except BaseException as error:
        record.update(status="ERROR", error=str(error), error_type=type(error).__name__)
        checkpoint("ERROR")
        if client and record.get("workflow_id"):
            try:
                record["partial_collection"] = client.collect(
                    record["workflow_id"], directory / "partial", partial=True, max_bytes=max_return_mb << 20
                )
            except (OSError, ValueError, RuntimeError, KeyError) as partial_error:
                record["partial_collection_error"] = str(partial_error)
        raise
    finally:
        if process:
            record["worker_preserved"] = False
            if process.poll() is None and (not submission_attempted or terminal_observed):
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                    record["forced_worker_stop"] = True
            elif process.poll() is None:
                record.update(worker_preserved=True, status="OBSERVATION_INCOMPLETE_WORKER_PRESERVED",
                    recovery="Poll the retained URL and exact workflow identity using the retained token file. Do not resubmit or stop an unconfirmed execution.")
            record["worker_exit_code"] = process.returncode
            record["worker_stopped"] = process.poll() is not None
        checkpoint()
    return record
