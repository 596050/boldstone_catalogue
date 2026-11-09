"""Synthetic loopback workflow, including disconnected-source execution and cleanup."""

import secrets
import tempfile
import threading
import time
from pathlib import Path

from offload_service.http_api import Server

from .client import Client, verify_collection
from .common import atomic, load
from .planner import plan
from .worker import WorkflowWorker

PROGRAM = """import json, pathlib, sys
mode = sys.argv[1]
left = json.loads(pathlib.Path(sys.argv[2]).read_text())['values']
if mode == 'copy':
    pathlib.Path(sys.argv[3]).write_text(json.dumps({'schema':'synthetic.values.v1','values':left},sort_keys=True))
elif mode == 'report':
    right = json.loads(pathlib.Path(sys.argv[3]).read_text())['values']
    output = pathlib.Path(sys.argv[4]); output.mkdir(exist_ok=True)
    (output/'result.json').write_text(json.dumps({'schema':'synthetic.report.v1','left':sum(left),'right':sum(right),'equal':left==right}))
    (output/'metrics.csv').write_text('metric,value\\nsum,'+str(sum(left))+'\\n')
    (output/'REPORT.md').write_text('Synthetic pipeline check; no trading performance claim.\\n')
    (output/'ledger.bin').write_bytes(bytes(left))
else:
    raise RuntimeError('unknown synthetic mode')
"""


def configuration(image="python:3.12-slim"):
    return {
        "enabled": True,
        "runtimes": {
            "python": {
                "image": image,
                "cpus": 1,
                "memory_mb": 512,
                "pids": 128,
                "timeout_s": 30,
                "max_work_mb": 128,
                "max_output_mb": 32,
            }
        },
        "capacity": {"cpus": 2, "memory_mb": 1024, "pids": 256, "max_work_mb": 256},
        "max_object_mb": 64,
        "max_store_mb": 512,
        "min_free_mb": 16,
    }


def fixture(root):
    root = Path(root)
    code, data = root / "code", root / "data"
    code.mkdir()
    data.mkdir()
    (code / "job.py").write_text(PROGRAM)
    atomic(data / "values.json", {"schema": "synthetic.values.v1", "values": [2, 3, 5]})
    return code, data


def workflow(code, data, remote_ref, submission_id="synthetic-offload"):
    def copy_job(key, inputs, deps=()):
        return {
            "id": key,
            "kind": "producer",
            "runtime": "python",
            "capsule": {"source": str(code)},
            "entrypoint": "job.py",
            "args": ["copy", "{input.values}/values.json", "{output.values}"],
            "inputs": {"values": inputs},
            "depends_on": list(deps),
            "outputs": {
                "values": {
                    "path": "artifacts/values.json",
                    "type": "json",
                    "schema": "synthetic.values.v1",
                    "delivery": "remote",
                }
            },
        }

    return {
        "schema": "marketmaker.research_offload_workflow.v1",
        "submission_id": submission_id,
        "workflow": "research",
        "jobs": [
            copy_job("bundle", {"mode": "bundle", "source": str(data)}),
            copy_job("remote", {"mode": "dataset_ref", **remote_ref}),
            copy_job(
                "generated",
                {"mode": "artifact_ref", "job": "bundle", "output": "values"},
                ["bundle"],
            ),
            {
                "id": "report",
                "kind": "producer",
                "runtime": "python",
                "capsule": {"source": str(code)},
                "entrypoint": "job.py",
                "args": [
                    "report",
                    "{input.left}/values.json",
                    "{input.right}/values.json",
                    "{output.evidence}",
                ],
                "inputs": {
                    "left": {"mode": "artifact_ref", "job": "generated", "output": "values"},
                    "right": {"mode": "artifact_ref", "job": "remote", "output": "values"},
                },
                "depends_on": ["generated", "remote"],
                "outputs": {
                    "evidence": {"path": "artifacts/evidence", "type": "tree"},
                    "summary": {
                        "path": "artifacts/evidence/result.json",
                        "type": "json",
                        "schema": "synthetic.report.v1",
                    },
                },
            },
        ],
    }


def run(*, docker=False):
    backend = "docker" if docker else "trusted-local"
    temporary_path = None
    with tempfile.TemporaryDirectory(prefix="research-offload-simulation-") as temporary:
        root = Path(temporary)
        temporary_path = str(root)
        code, data = fixture(root)
        token = secrets.token_urlsafe(32)
        with WorkflowWorker(
            root / "worker",
            [],
            backend=backend,
            workflow_config=configuration(),
            concurrency=2,
            min_free_mb=0,
            max_store_mb=1024,
        ) as worker:
            remote = worker.workflows.objects.register_dataset(
                "synthetic-values", "version-one", data
            )
            compiled = root / "compiled"
            plan(workflow(code, data, remote), compiled)
            server = Server(("127.0.0.1", 0), worker, token)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}"
                client = Client(url, token)
                first = client.submit_plan(compiled)
                duplicate = client.submit_plan(compiled)
                assert first == duplicate
                del client  # no requester process is needed to schedule dependencies
                (data / "values.json").write_text('{"values":[999]}')
                (code / "job.py").write_text("raise RuntimeError('changed source must not run')\n")
                worker.start()
                deadline = time.monotonic() + 90
                while not worker.workflows.status(first["workflow_id"])["terminal"]:
                    if worker.stop.is_set():
                        raise RuntimeError("workflow worker stopped unexpectedly")
                    if time.monotonic() > deadline:
                        raise TimeoutError("synthetic workflow timed out")
                    time.sleep(0.1)
                client = Client(url, token)
                status = client.workflow_status(first["workflow_id"])
                assert status["state"] == "completed", status
                receipt = client.collect(first["workflow_id"], root / "returned")
                verify_collection(root / "returned")
                client.collect(first["workflow_id"], root / "returned")
                index = load(root / "returned/INDEX.json")
                evidence = root / "returned" / index["report.evidence"]
                result = load(evidence / "result.json")
                assert result == {
                    "schema": "synthetic.report.v1",
                    "left": 10,
                    "right": 10,
                    "equal": True,
                }
                assert (evidence / "ledger.bin").read_bytes() == bytes([2, 3, 5])
                assert (evidence / "metrics.csv").is_file() and (evidence / "REPORT.md").is_file()
                report = {
                    "status": "PASS",
                    "backend": backend,
                    "os_isolation_tested": docker,
                    "input_modes": ["bundle", "dataset_ref", "artifact_ref"],
                    "nodes_completed": len(status["nodes"]),
                    "source_disconnected": True,
                    "source_mutation_did_not_change_admitted_inputs": True,
                    "duplicate_submission_did_not_duplicate_jobs": True,
                    "binary_csv_markdown_json_returned": True,
                    "repeat_collection_verified": True,
                    "ack_did_not_delete_remote_outputs": True,
                    "delivery_sha256": receipt["delivery_sha256"],
                    "performance_qualification": "NOT_ESTABLISHED",
                }
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
    report["temporary_state_removed"] = not Path(temporary_path).exists()
    report["worker_and_http_threads_stopped"] = not thread.is_alive() and worker.closed
    return report
