"""Exercise the installed CLI with Docker and synthetic data only.

Default: loopback HTTP. --live explicitly opens a temporary public tunnel.
--edge-ip is a test-client-only DNS override; HTTPS hostname verification stays on.
"""

import argparse
import http.client
import ipaddress
import json
from pathlib import Path
import queue
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

from .cli import initialize
from .client import Client, NoRedirect


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--edge-ip")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.edge_ip:
        ipaddress.ip_address(args.edge_ip)
        if not args.live:
            parser.error("--edge-ip only applies to --live HTTPS testing")
    with tempfile.TemporaryDirectory(prefix="offload-smoke-") as temp:
        root = Path(temp)
        config = initialize(root / "worker", "python:3.12-slim")
        settings = json.loads(config.read_text())
        settings["port"] = 0
        config.write_text(json.dumps(settings))
        command = [sys.executable, "-m", "offload_service", "serve", "--config", str(config)]
        if args.live:
            command += ["--tunnel", "--tunnel-args", "--protocol", "http2", "--once"]
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )
        messages = queue.Queue()
        logs = []

        def reader():
            for line in process.stdout:
                messages.put(line)

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + (150 if args.live else 30)
            url = None
            connected = not args.live
            while not (url and connected):
                if time.monotonic() > deadline or process.poll() is not None:
                    raise RuntimeError("worker/tunnel did not become ready: " + "".join(logs[-8:]))
                try:
                    line = messages.get(timeout=0.2)
                except queue.Empty:
                    continue
                logs.append(line)
                if args.live:
                    match = re.search(r"PUBLIC_URL=(https://[^\s]+)", line)
                    connected |= "Tunnel connected." in line
                else:
                    match = re.search(r"Worker ready at (http://[^;\s]+)", line)
                if match:
                    url = match.group(1)
            token = (config.parent / "access-token").read_text().strip()
            client = Client(url, token)
            if args.edge_ip:

                class EdgeConnection(http.client.HTTPSConnection):
                    def __init__(self, *positional, **kwargs):
                        super().__init__(*positional, **kwargs)
                        self._create_connection = lambda address, timeout, source: (
                            socket.create_connection((args.edge_ip, address[1]), timeout, source)
                        )

                class EdgeHandler(urllib.request.HTTPSHandler):
                    def https_open(self, request):
                        return self.do_open(EdgeConnection, request, context=self._context)

                client.opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({}), NoRedirect(), EdgeHandler()
                )
            # Registration can precede edge routing/DNS propagation. Retry only
            # transport/5xx errors; an unauthenticated 2xx is always a failure.
            propagation_deadline = time.monotonic() + 60
            propagation_retries = 0
            while True:
                try:
                    client.opener.open(url + "/v1/health", timeout=10)
                    raise AssertionError("unauthenticated request was not rejected")
                except urllib.error.HTTPError as exc:
                    if exc.code == 401:
                        break
                    if exc.code < 500 or time.monotonic() >= propagation_deadline:
                        raise
                except (urllib.error.URLError, TimeoutError):
                    if time.monotonic() >= propagation_deadline:
                        raise
                propagation_retries += 1
                time.sleep(2)
            wrong = urllib.request.Request(url + "/v1/health", headers={
                "Authorization": "Bearer incorrect", "X-Offload-Token": "incorrect"})
            try:
                client.opener.open(wrong, timeout=10)
                raise AssertionError("incorrect token was accepted")
            except urllib.error.HTTPError as exc:
                assert exc.code == 401
            accepted = client.submit("demo-sum", job_id="smoke-job", args=["hello"])
            again = client.submit("demo-sum", job_id="smoke-job", args=["hello"])
            assert accepted["sequence"] == again["sequence"]
            status = client.wait("smoke-job", deadline=45)
            assert status["state"] == "succeeded", status
            result = client.download("smoke-job", root / "result")
            observed = json.loads((result / "result.json").read_text())
            assert observed == {"sum": 10, "args": ["hello"]}, observed
            terminal = client.request("/v1/jobs/smoke-job")
            assert terminal["acknowledged_sha256"] == terminal["receipt"]["result_sha256"]
            report = {
                "ok": True,
                "transport": "public_https" if args.live else "loopback_http",
                "url": url,
                "dns_override": args.edge_ip,
                "native_controller": sys.platform,
                "backend": "docker",
                "image_id": status["image_id"],
                "seal_sha256": status["seal_sha256"],
                "receipt": terminal["receipt"],
                "unauthenticated_status": 401,
                "idempotent_submission": True,
                "acknowledged": True,
                "edge_propagation_retries": propagation_retries,
                "result": observed,
            }
            if args.out:
                args.out.write_text(json.dumps(report, indent=2))
            print(json.dumps(report, indent=2))
        except Exception as exc:
            if args.out:
                args.out.write_text(
                    json.dumps(
                        {
                            "ok": False,
                            "transport": "public_https" if args.live else "loopback_http",
                            "url": url,
                            "dns_override": args.edge_ip,
                            "error": f"{type(exc).__name__}: {exc}",
                        },
                        indent=2,
                    )
                )
            raise
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=90)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
