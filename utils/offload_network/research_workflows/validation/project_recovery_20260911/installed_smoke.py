"""Installed-wheel CLI roundtrip; synthetic loopback worker, automatic temp cleanup."""

import argparse
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

import research_workflows
from offload_service.http_api import Server
from research_workflows.common import atomic, load, sha
from research_workflows.simulation import configuration
from research_workflows.worker import WorkflowWorker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    assert importlib.metadata.version("fleet-offload-orchestration") == "0.6.0"
    assert "site-packages" in research_workflows.__file__
    with zipfile.ZipFile(args.wheel) as wheel:
        checked = []
        for member in wheel.namelist():
            if member.startswith("research_workflows/") and member.endswith((".py", ".json", ".md")):
                assert wheel.read(member) == (args.source / member).read_bytes(), member
                checked.append(member)
        assert "research_workflows/project.json" in checked
    commands = []
    env = {**os.environ, "PYTHONPATH": "", "PYTHONDONTWRITEBYTECODE": "1"}

    def cli(root, *argv):
        result = subprocess.run([sys.executable, "-B", "-m", "research_workflows", *map(str, argv)],
                                cwd=root, env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, (argv, result.stderr)
        commands.append(argv[0])
        return json.loads(result.stdout)

    with tempfile.TemporaryDirectory(prefix="offload-installed-recovery-") as temporary:
        root = Path(temporary)
        candidate = root / "research/candidates/example/installed_20260911_v1"
        candidate.mkdir(parents=True)
        (candidate / "README.md").write_text("Unchanged research record.\n")
        code, data, disk = root / "code", root / "data", root / "disk"
        for path in (code, data, disk):
            path.mkdir()
        (code / "copy.py").write_text("import pathlib,sys\npathlib.Path(sys.argv[2]).write_bytes(pathlib.Path(sys.argv[1]).read_bytes())\n")
        atomic(data / "values.json", {"values": [2, 3, 5]})
        request = {"schema": "marketmaker.research_offload_workflow.v1", "submission_id": "installed-recovery",
                   "jobs": [], "return_policy": {"include_inputs": True}}
        for key in ("prepare", "measure"):
            request["jobs"].append({"id": key, "kind": "producer", "runtime": "python",
                "capsule": {"source": str(code)}, "entrypoint": "copy.py",
                "args": ["{input.values}/values.json", "{output.result}"],
                "depends_on": ["prepare"] if key == "measure" else [],
                "inputs": {"values": {"mode": "bundle", "source": str(data)} if key == "prepare" else
                           {"mode": "artifact_ref", "job": "prepare", "output": "result"}},
                "outputs": {"result": {"type": "json", "path": "artifacts/values.json"}}})
        atomic(root / "REQUEST.json", request)
        atomic(root / "ORIGINS.json", {"measure": [candidate.relative_to(root).as_posix()]})
        token = "s" * 43
        (root / "token").write_text(token)
        with WorkflowWorker(root / "worker", [], workflow_config=configuration(), backend="trusted-local",
                            min_free_mb=0, concurrency=2) as worker:
            server = Server(("127.0.0.1", 0), worker, token)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                config = load(Path(research_workflows.__file__).with_name("project.json"))
                config.update(project_root=str(root), evidence={"directory": str(disk), "relative": "offload"},
                              workers={"local": {"url": f"http://127.0.0.1:{server.server_port}", "token_file": "token"}})
                config["storage"].update(local_min_free_mb=1, min_free_mb=1)
                atomic(root / "project.json", config)
                cli(root, "plan", "--request", root / "REQUEST.json", "--out", root / "plan",
                    "--project-config", root / "project.json")
                assert all(j["max_attempts"] == 2 for j in load(root / "plan/WORKFLOW.json")["jobs"])
                cli(root, "enqueue", "--config", root / "project.json", "--plan", root / "plan",
                    "--worker", "local", "--origins", root / "ORIGINS.json")
                worker.start()
                until = time.monotonic() + 60
                while True:
                    state = cli(root, "sync", "--config", root / "project.json", "--now")[0]
                    if state["phase"] == "completed":
                        break
                    assert state["state"] != "needs_attention", state
                    assert time.monotonic() < until, state
                    time.sleep(0.1)
                record = root / state["publications"][0]
                resolved = cli(root, "origin", "--config", root / "project.json", "--record", record,
                               "--port", "measure.result", "--relative", "values.json")
                assert load(resolved["path"]) == {"values": [2, 3, 5]}
                assert (candidate / "README.md").read_text() == "Unchanged research record.\n"
                assert cli(root, "queue", "--config", root / "project.json")[0]["phase"] == "completed"
                cli(root, "init-worker", "--dir", root / "new-worker")
                assert load(root / "new-worker/worker.json")["max_pending"] >= 128
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                assert not thread.is_alive()
    result = {"status": "PASS", "version": "0.6.0", "backend": "trusted-local",
              "source_assets_verified": len(checked), "commands": commands,
              "worker_and_server_stopped": True, "temporary_root_removed": not Path(temporary).exists(),
              "wheel_sha256": sha(args.wheel), "research_record_preserved": True}
    atomic(args.report, result)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
