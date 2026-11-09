"""Cross-platform worker and optional Cloudflare tunnel launcher."""

import argparse
import json
import os
import secrets
import signal
import subprocess
import sys
import threading
from pathlib import Path

from .core import Template, Worker
from .http_api import Server


def initialize(directory, image):
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "code").mkdir()
    (directory / "data").mkdir()
    (directory / "code" / "job.py").write_text(
        "import json, pathlib, sys\n"
        "values = json.loads(pathlib.Path('blobs/data/values.json').read_text())\n"
        "pathlib.Path('result.json').write_text(json.dumps({'sum': sum(values), 'args': sys.argv[1:]}))\n"
    )
    (directory / "data" / "values.json").write_text("[2, 3, 5]\n")
    token = directory / "access-token"
    fd = os.open(token, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(secrets.token_urlsafe(32) + "\n")
    config = {
        "root": "state",
        "token_file": "access-token",
        "port": 8765,
        "concurrency": 1,
        "max_pending": 100,
        "templates": {
            "demo-sum": {
                "entrypoint": "code/job.py",
                "code_dir": "code",
                "data": [{"path": "data/values.json", "rel_path": "data/values.json"}],
                "image": image,
                "timeout_s": 300,
            }
        },
    }
    (directory / "worker.json").write_text(json.dumps(config, indent=2))
    (directory / ".gitignore").write_text("access-token\nstate/\n")
    return directory / "worker.json"


def load_config(path):
    path = path.resolve()
    raw = json.loads(path.read_text())
    allowed = {
        "root",
        "token_file",
        "port",
        "concurrency",
        "max_pending",
        "min_free_mb",
        "max_store_mb",
        "templates",
        "workflows",
    }
    if set(raw) - allowed:
        raise ValueError(f"unknown worker configuration: {set(raw) - allowed}")
    templates = [
        Template.load(name, value, path.parent) for name, value in raw["templates"].items()
    ]
    if not templates and not raw.get("workflows", {}).get("enabled"):
        raise ValueError("configure at least one template")
    return raw, templates, path.parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--dir", type=Path, required=True)
    init.add_argument("--image", default="python:3.12-slim")
    serve = sub.add_parser("serve")
    serve.add_argument("--config", type=Path, required=True)
    serve.add_argument(
        "--trusted-local", action="store_true", help="NO sandbox; trusted code/testing only"
    )
    serve.add_argument(
        "--tunnel", action="store_true", help="publish the authenticated worker using Cloudflare"
    )
    serve.add_argument("--tunnel-args", nargs=argparse.REMAINDER, default=[])
    args = parser.parse_args(argv)
    if args.command == "init":
        print(initialize(args.dir, args.image))
        return 0
    if args.trusted_local and args.tunnel:
        parser.error("trusted-local execution may not be exposed by this tunnel launcher")
    raw, templates, base = load_config(args.config)
    token_file = (base / raw["token_file"]).resolve()
    token = token_file.read_text().strip()
    stop = threading.Event()
    tunnel = None
    worker_class = Worker
    workflow_options = {}
    if raw.get("workflows", {}).get("enabled"):
        from research_workflows.worker import WorkflowWorker

        worker_class = WorkflowWorker
        workflow_options["workflow_config"] = raw["workflows"]
    with worker_class(
        base / raw["root"],
        templates,
        backend="trusted-local" if args.trusted_local else "docker",
        **workflow_options,
        **{
            k: raw[k]
            for k in ("concurrency", "max_pending", "min_free_mb", "max_store_mb")
            if k in raw
        },
    ) as worker:
        server = Server(("127.0.0.1", raw.get("port", 8765)), worker, token)
        worker.start()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        previous = {}
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, lambda *_: stop.set())
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            print(
                f"Worker ready at {url}; backend={worker.backend}; token file={token_file}",
                flush=True,
            )
            if args.tunnel:
                # Gateway consumes X-Offload-Token, API independently verifies
                # Authorization. The client supplies both with this shared token.
                command = [
                    sys.executable,
                    "-m",
                    "external_machine_connect.cloudflare.connect",
                    *args.tunnel_args,
                    "--url",
                    url,
                    "--auth-header",
                    "X-Offload-Token",
                    "--token-file",
                    str(token_file),
                ]
                tunnel_env = os.environ.copy()
                tunnel_env.pop("OFFLOAD_ACCESS_TOKEN", None)
                tunnel = subprocess.Popen(command, env=tunnel_env)
            while not stop.wait(0.2):
                if worker.stop.is_set():
                    raise RuntimeError("worker stopped after an execution-boundary failure")
                if tunnel and tunnel.poll() is not None:
                    raise RuntimeError(f"tunnel stopped with exit code {tunnel.returncode}")
        finally:
            if tunnel and tunnel.poll() is None:
                tunnel.terminate()
                try:
                    tunnel.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    tunnel.kill()
                    tunnel.wait(timeout=5)
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
