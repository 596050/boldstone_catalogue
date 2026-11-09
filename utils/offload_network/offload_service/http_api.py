"""Small loopback-only HTTP job API. All endpoints require a bearer token."""

import hmac
import json
import re
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .core import ID, CapacityError, Conflict


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, worker, token):
        if address[0] != "127.0.0.1":
            raise ValueError("bind to 127.0.0.1; use the authenticated tunnel for remote access")
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token):
            raise ValueError("use a random 32-256 character API token")
        self.worker, self.token = worker, token
        self.slots = threading.BoundedSemaphore(32)
        super().__init__(address, Handler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        request.settimeout(15)
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "OffloadWorker/1"

    def log_message(self, *args):
        pass  # never log authorization headers or URL/query tokens

    def reply(self, status, value):
        body = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def body(self, max_bytes=65536):
        sizes = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") or len(sizes) != 1:
            raise ValueError("one Content-Length is required; chunked uploads are unsupported")
        size = int(sizes[0])
        if not 0 < size <= max_bytes:
            raise ValueError(f"body must be 1-{max_bytes} bytes")
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Content-Type must be application/json")
        data = self.rfile.read(size)
        if len(data) != size:
            raise ValueError("truncated request")

        def pairs(items):
            value = {}
            for key, item in items:
                if key in value:
                    raise ValueError("duplicate JSON key")
                value[key] = item
            return value

        return json.loads(
            data,
            object_pairs_hook=pairs,
            parse_constant=lambda x: (_ for _ in ()).throw(ValueError("non-finite JSON")),
        )

    def dispatch(self):
        values = self.headers.get_all("Authorization", [])
        if len(values) != 1 or not hmac.compare_digest(
            values[0].encode("utf-8"), ("Bearer " + self.server.token).encode("utf-8")
        ):
            self.reply(401, {"error": "authorization required"})
            return
        parsed = urlsplit(self.path)
        if parsed.query or parsed.fragment:
            self.reply(400, {"error": "query parameters are not accepted"})
            return
        worker = self.server.worker
        try:
            if hasattr(worker, "workflows"):
                from research_workflows.http_api import dispatch

                if dispatch(self, parsed.path):
                    return
            if parsed.path == "/v1/health" and self.command in {"GET", "HEAD"}:
                self.reply(
                    503 if worker.stop.is_set() else 200,
                    {"ready": not worker.stop.is_set(), "backend": worker.backend},
                )
                return
            if parsed.path == "/v1/templates" and self.command in {"GET", "HEAD"}:
                self.reply(
                    200,
                    {
                        "templates": sorted(
                            k for k in worker.templates if not k.startswith("workflow-")
                        )
                    },
                )
                return
            if parsed.path == "/v1/jobs" and self.command == "POST":
                status, created = worker.submit(self.body())
                self.reply(202 if created else 200, status)
                return
            parts = parsed.path.strip("/").split("/")
            if (
                len(parts) not in {3, 4}
                or parts[:2] != ["v1", "jobs"]
                or not ID.fullmatch(parts[2])
            ):
                self.reply(404, {"error": "unknown endpoint"})
                return
            job_id = parts[2]
            if len(parts) == 3 and self.command in {"GET", "HEAD"}:
                self.reply(200, worker.status(job_id))
            elif len(parts) == 4 and parts[3] == "cancel" and self.command == "POST":
                self.body()
                self.reply(200, worker.cancel(job_id))
            elif len(parts) == 4 and parts[3] == "ack" and self.command == "POST":
                payload = self.body()
                self.reply(200, worker.acknowledge(job_id, payload.get("sha256")))
            elif len(parts) == 4 and parts[3] == "result" and self.command in {"GET", "HEAD"}:
                path, digest = worker.result(job_id)
                with path.open("rb") as stream:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/gzip")
                    self.send_header("Content-Length", str(path.stat().st_size))
                    self.send_header("X-Content-SHA256", digest)
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    if self.command == "GET":
                        shutil.copyfileobj(stream, self.wfile)
            else:
                self.reply(405, {"error": "method not allowed"})
        except KeyError:
            self.reply(404, {"error": "unknown job"})
        except CapacityError as exc:
            self.reply(429, {"error": str(exc)})
        except Conflict as exc:
            self.reply(409, {"error": str(exc)})
        except (ValueError, TypeError, AttributeError) as exc:
            self.reply(400, {"error": str(exc)})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception:
            self.reply(
                500, {"error": "worker operation failed; retained state can be inspected locally"}
            )

    do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = dispatch
