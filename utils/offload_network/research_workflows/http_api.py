"""Authenticated extension routes; invoked only after the base API auth check."""

import re

from offload_service.core import Conflict

from .common import fields, hash_id, name
from .objects import CHUNK


def dispatch(handler, path):
    coordinator = handler.server.worker.workflows
    method = handler.command
    pieces = path.strip("/").split("/")
    if not pieces or pieces[0] != "v2":
        return False
    if path == "/v2/capabilities" and method in {"GET", "HEAD"}:
        handler.reply(200, coordinator.capabilities())
        return True
    if path == "/v2/queue" and method in {"GET", "HEAD"}:
        from .queue_view import snapshot

        handler.reply(200, snapshot(handler.server.worker))
        return True
    if pieces[:2] == ["v2", "objects"] and len(pieces) >= 3:
        ident = hash_id(pieces[2])
        store = coordinator.objects
        if len(pieces) == 3 and method in {"GET", "HEAD"}:
            handler.reply(200, store.status(ident))
        elif len(pieces) == 4 and pieces[3] == "begin" and method == "POST":
            body = handler.body()
            fields(body, {"bytes"}, {"bytes"})
            handler.reply(200, store.begin(ident, body["bytes"]))
        elif len(pieces) == 4 and pieces[3] == "commit" and method == "POST":
            fields(handler.body(), set())
            handler.reply(200, store.commit(ident))
        elif len(pieces) == 5 and pieces[3] == "chunks" and method == "PUT":
            sizes = handler.headers.get_all("Content-Length", [])
            if handler.headers.get("Transfer-Encoding") or len(sizes) != 1:
                raise ValueError("one Content-Length is required")
            size = int(sizes[0])
            if not 0 < size <= CHUNK or not pieces[4].isdigit():
                raise ValueError("invalid chunk length/offset")
            if handler.headers.get_content_type() != "application/octet-stream":
                raise ValueError("binary chunks require application/octet-stream")
            data = handler.rfile.read(size)
            if len(data) != size:
                raise ValueError("truncated upload")
            handler.reply(200, store.append(ident, int(pieces[4]), data))
        elif len(pieces) == 4 and pieces[3] == "archive" and method in {"GET", "HEAD"}:
            root, _ = store.get(ident)
            archive = root / "archive.tar.gz"
            size, start, end = archive.stat().st_size, 0, archive.stat().st_size - 1
            if handler.headers.get("If-Match") not in {None, ident, '"' + ident + '"'}:
                raise Conflict("download identity precondition failed")
            ranges = handler.headers.get_all("Range", [])
            if ranges:
                match = re.fullmatch(r"bytes=(\d+)-(\d*)", ranges[0])
                if len(ranges) != 1 or not match:
                    raise ValueError("one bounded byte range is supported")
                start = int(match[1])
                end = int(match[2]) if match[2] else end
                if not 0 <= start <= end < size:
                    handler.reply(416, {"error": "range outside immutable object"})
                    return True
            with archive.open("rb") as stream:
                handler.send_response(206 if ranges else 200)
                handler.send_header("Content-Type", "application/gzip")
                handler.send_header("Content-Length", str(end - start + 1))
                handler.send_header("X-Content-SHA256", ident)
                handler.send_header("ETag", '"' + ident + '"')
                handler.send_header("Accept-Ranges", "bytes")
                handler.send_header("Cache-Control", "no-store")
                if ranges:
                    handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                handler.end_headers()
                if method != "HEAD":
                    stream.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        block = stream.read(min(CHUNK, remaining))
                        if not block:
                            raise ValueError("stored object truncated")
                        handler.wfile.write(block)
                        remaining -= len(block)
        else:
            handler.reply(405, {"error": "unsupported object operation"})
        return True
    if path == "/v2/workflows" and method == "POST":
        status, created = coordinator.submit(handler.body(max_bytes=1 << 20))
        handler.reply(202 if created else 200, status)
        return True
    if path == "/v2/validate" and method == "POST":
        handler.reply(200, coordinator.preflight(handler.body(max_bytes=1 << 20))[2])
        return True
    if pieces[:2] == ["v2", "workflows"] and len(pieces) in {3, 4}:
        workflow = name(pieces[2])
        if len(pieces) == 3 and method in {"GET", "HEAD"}:
            handler.reply(200, coordinator.status(workflow))
        elif len(pieces) == 4 and pieces[3] == "delivery" and method in {"GET", "HEAD"}:
            handler.reply(200, coordinator.delivery(workflow))
        elif len(pieces) == 4 and pieces[3] == "snapshot" and method in {"GET", "HEAD"}:
            handler.reply(200, coordinator.delivery(workflow, partial=True))
        elif len(pieces) == 4 and pieces[3] == "revocation" and method in {"GET", "HEAD"}:
            handler.reply(200, coordinator.revocation(workflow))
        elif len(pieces) == 4 and method == "POST" and pieces[3] in {"cancel", "resume", "ack", "revoke"}:
            body = handler.body()
            if pieces[3] == "ack":
                fields(body, {"delivery_sha256"}, {"delivery_sha256"})
                result = coordinator.acknowledge(workflow, body["delivery_sha256"])
            elif pieces[3] == "revoke":
                fields(body, {"workflow_sha256"}, {"workflow_sha256"})
                result = coordinator.revoke(workflow, body["workflow_sha256"])
            else:
                fields(body, set())
                result = getattr(coordinator, pieces[3])(workflow)
            handler.reply(200, result)
        else:
            handler.reply(405, {"error": "unsupported workflow operation"})
        return True
    handler.reply(404, {"error": "unknown workflow endpoint"})
    return True
