"""Portable requester CLI with bounded polling and verified result downloads."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.request
from urllib.parse import urlsplit
import uuid

from v2.result import _safe_extract
from .core import ID, TERMINAL


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("refusing redirect with API credentials")


class Client:
    def __init__(self, url, token, *, timeout=30):
        parsed = urlsplit(url)
        if (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or (
                parsed.scheme != "https"
                and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"})
            )
        ):
            raise ValueError("use an HTTPS worker URL, or loopback HTTP for local tests")
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token):
            raise ValueError("invalid API token")
        self.url, self.token, self.timeout = url.rstrip("/"), token, timeout
        self.opener = urllib.request.build_opener(NoRedirect())

    def open(self, path, body=None):
        headers = {"Authorization": "Bearer " + self.token, "X-Offload-Token": self.token}
        data = None
        if body is not None:
            data = json.dumps(body, allow_nan=False).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.url + path, data=data, headers=headers)
        return self.opener.open(request, timeout=self.timeout)

    def request(self, path, body=None):
        with self.open(path, body) as response:
            return json.load(response)

    def submit(self, template, *, job_id=None, args=None, metadata=None):
        return self.request(
            "/v1/jobs",
            {
                "job_id": job_id or "job-" + uuid.uuid4().hex,
                "template": template,
                "args": args or [],
                "metadata": metadata or {},
            },
        )

    def _path(self, job_id):
        if not ID.fullmatch(job_id):
            raise ValueError("invalid job ID")
        return "/v1/jobs/" + job_id

    def wait(self, job_id, *, deadline=3600, interval=0.5):
        until = time.monotonic() + deadline
        while True:
            status = self.request(self._path(job_id))
            if status["state"] in TERMINAL:
                return status
            if time.monotonic() >= until:
                raise TimeoutError(
                    "poll deadline exceeded; job remains queued/running; poll or cancel by ID"
                )
            time.sleep(min(interval, max(0, until - time.monotonic())))

    def download(self, job_id, out, *, max_bytes=1 << 30):
        path = self._path(job_id)
        status = self.request(path)
        expected = (status.get("receipt") or {}).get("result_sha256")
        if not expected:
            raise ValueError("job has no retained result")
        out = Path(out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            retained_archive = out / "received-result.tar.gz"
            if retained_archive.is_file():
                digest = hashlib.sha256()
                with retained_archive.open("rb") as stream:
                    for block in iter(lambda: stream.read(1 << 20), b""):
                        digest.update(block)
                if digest.hexdigest() == expected:
                    self.request(path + "/ack", {"sha256": expected})
                    return out
            raise FileExistsError(f"refusing to overwrite results: {out}")
        # Download and validate BEFORE publishing or acknowledging. On failure,
        # the server keeps the result and the request can be retried safely.
        with tempfile.TemporaryDirectory(prefix=".offload-result-", dir=out.parent) as temp:
            root = Path(temp)
            archive = root / "result.tar.gz"
            digest, size = hashlib.sha256(), 0
            with self.open(path + "/result") as response, archive.open("xb") as stream:
                length = int(response.headers["Content-Length"])
                if length > max_bytes or response.headers.get("X-Content-SHA256") != expected:
                    raise ValueError("result size or identity is invalid")
                while chunk := response.read(1 << 20):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("result exceeds download limit")
                    digest.update(chunk)
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if size != length or digest.hexdigest() != expected:
                raise ValueError("truncated or corrupt result download")
            content = root / "content"
            _safe_extract(archive, content, max_bytes=max_bytes)
            execution = json.loads((content / "status.json").read_text())
            receipt = status["receipt"]
            if (
                execution.get("job_id") != job_id
                or execution.get("phase") != "exited"
                or execution.get("exit_code") != receipt.get("exit_code")
            ):
                raise ValueError("result execution identity mismatch")
            (content / "controller-receipt.json").write_text(json.dumps(status, indent=2))
            if (content / "received-result.tar.gz").exists():
                raise ValueError("result contains a reserved client archive path")
            os.replace(archive, content / "received-result.tar.gz")
            if out.exists():
                raise FileExistsError(out)
            os.replace(content, out)
        self.request(path + "/ack", {"sha256": expected})
        return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("--template", required=True)
    submit.add_argument("--job-id")
    submit.add_argument("args", nargs=argparse.REMAINDER)
    for command in ("status", "wait", "cancel", "result"):
        item = sub.add_parser(command)
        item.add_argument("job_id")
        if command == "wait":
            item.add_argument("--deadline", type=float, default=3600)
        if command == "result":
            item.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    client = Client(args.url, args.token_file.read_text().strip())
    if args.command == "submit":
        tokens = args.args[1:] if args.args[:1] == ["--"] else args.args
        job_id = args.job_id or "job-" + uuid.uuid4().hex
        print(
            f"Job ID: {job_id} (retain this ID if the connection is interrupted)", file=sys.stderr
        )
        result = client.submit(args.template, job_id=job_id, args=tokens)
    elif args.command == "result":
        result = {"directory": str(client.download(args.job_id, args.out))}
    elif args.command == "wait":
        result = client.wait(args.job_id, deadline=args.deadline)
    else:
        path = client._path(args.job_id)
        result = (
            client.request(path + "/cancel", {})
            if args.command == "cancel"
            else client.request(path)
        )
    print(json.dumps(result, indent=2))
    return 1 if isinstance(result, dict) and result.get("state") in TERMINAL - {"succeeded"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
