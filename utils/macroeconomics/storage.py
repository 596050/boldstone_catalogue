"""Verified Toshiba-only storage and inspectable, resumable HTTP acquisition."""

from __future__ import annotations

import fcntl
import gzip
import hashlib
import json
import os
import subprocess
import tempfile
import time
import urllib.parse
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from utils.data_paths import ensure_external_storage, resolve_source_location


def utc():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def guard(root, *, force=False, reserve=20 * 1024**3):
    storage = ensure_external_storage(force=force)
    mount = storage["mount_point"]
    expected = resolve_source_location("macroeconomic_releases")
    if Path(root) != expected or not os.path.ismount(mount):
        raise OSError("Wrong archive or absent Toshiba; no local fallback permitted")
    current = mount
    for part in expected.relative_to(mount).parts:
        current /= part
        if current.is_symlink():
            raise OSError("Symlink in economic archive path")
    existing = expected if expected.exists() else expected.parent
    if existing.stat().st_dev != mount.stat().st_dev:
        raise OSError("Archive is not on verified Toshiba")
    stat = os.statvfs(mount)
    if stat.f_bavail * stat.f_frsize < reserve:
        raise OSError("SPACE_RESERVE: preserving 20 GiB for the shared drive")
    return storage


def local_path(root, relative):
    rel = Path(relative)
    if rel.is_absolute() or any(p in (".", "..") for p in rel.parts):
        raise ValueError("unsafe relative output path")
    current = Path(root)
    for part in rel.parts:
        current /= part
        if current.is_symlink():
            raise OSError("symlink in output path")
    return current


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".part")
    with temp.open("xb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


@contextmanager
def lock(path):
    with Path(path).open("a+b") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            stream.seek(0)
            stream.truncate()
            stream.write(
                canonical(
                    {
                        "pid": os.getpid(),
                        "owner": "utils.macroeconomics",
                        "since": utc(),
                    }
                )
            )
            stream.flush()
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def verify_http(root, receipt):
    path = local_path(root, receipt["raw_file"])
    if sha(path) != receipt["raw_sha256"]:
        raise ValueError("HTTP response compressed hash mismatch")
    hasher = hashlib.sha256()
    size = 0
    with gzip.open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
            size += len(block)
    if hasher.hexdigest() != receipt["body_sha256"] or size != receipt["body_bytes"]:
        raise ValueError("HTTP response original bytes mismatch")
    return "HASH_AND_GZIP_PASS"


@contextmanager
def download_temporary(parent):
    """Keep interrupted downloads; discard only duplicated, retained temp bytes."""
    directory = Path(tempfile.mkdtemp(prefix="http-", dir=parent))
    yield directory
    # This section is deliberately not in finally: exceptions retain everything.
    for name in ("body", "headers"):
        path = directory / name
        if path.exists():
            path.unlink()
    directory.rmdir()


class Fetcher:
    """One request at a time; existing exact requests are reverified, not replaced."""

    def __init__(self, root, snapshot, check=None):
        self.root = Path(root)
        self.snapshot = snapshot
        self.check = check or (lambda: guard(self.root))
        self.next_request = 0.0

    def fetch(
        self, url, folder, label, form=None, *, timeout=60, max_bytes=128 * 1024**2
    ):
        self.check()
        if urllib.parse.urlsplit(url).scheme != "https":
            raise ValueError("Only HTTPS public sources are permitted")
        # No credentials are supplied to these public download forms.
        request_spec = {
            "url": url,
            "method": "POST" if form else "GET",
            "form": form,
            "transport": "curl",
        }
        request_id = hashlib.sha256(canonical(request_spec)).hexdigest()[:20]
        target = local_path(self.root, f"{folder}/{self.snapshot}")
        target.mkdir(parents=True, exist_ok=True)
        stem = f"{label}__{request_id}"
        receipt_path = target / (stem + ".receipt.json")
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            verify_http(self.root, receipt)
            return receipt
        # Never collide with an interrupted attempt's retained bytes.
        raw_path = target / (stem + "__" + uuid.uuid4().hex[:10] + ".raw.gz")
        receipt = {
            "schema": "economic_releases.http.v1",
            "snapshot": self.snapshot,
            "request_id": request_id,
            "request": request_spec,
            "started_at_utc": utc(),
            "raw_file": str(raw_path.relative_to(self.root)),
            "receipt_file": str(receipt_path.relative_to(self.root)),
            "status": "FAILED",
            "http_status": None,
            "error": None,
        }
        delay = self.next_request - time.monotonic()
        if delay > 0:
            time.sleep(min(delay, 2))
        hasher = hashlib.sha256()
        size = 0
        # Native curl can reach these public sources on this machine, whereas
        # the Python URL opener timed out. No browser impersonation or login.
        # Temporary response files stay on Toshiba and are removed only after
        # their original body has been preserved in the archive's gzip file.
        with download_temporary(target) as temp:
            body_path, headers_path = temp / "body", temp / "headers"
            command = [
                "curl",
                "--silent",
                "--show-error",
                "--location",
                "--proto",
                "=https",
                "--proto-redir",
                "=https",
                "--connect-timeout",
                "15",
                "--max-time",
                str(timeout),
                "--max-filesize",
                str(max_bytes),
                "--header",
                "Accept-Encoding: identity",
                "--dump-header",
                str(headers_path),
                "--output",
                str(body_path),
                "--write-out",
                "%{http_code}\\n%{url_effective}",
            ]
            if form:
                command.extend(["--data", urllib.parse.urlencode(form, doseq=True)])
            command.append(url)
            proc = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                while proc.poll() is None:
                    self.check()
                    time.sleep(0.25)
                output_meta, stderr = proc.communicate()
                lines = output_meta.decode(errors="replace").splitlines()
                receipt["http_status"] = (
                    int(lines[0]) if lines and lines[0].isdigit() else None
                )
                receipt["final_url"] = lines[1] if len(lines) > 1 else url
                receipt["curl_exit_code"] = proc.returncode
                receipt["error"] = stderr.decode(errors="replace").strip() or None
                receipt["status"] = (
                    "DOWNLOADED"
                    if proc.returncode == 0 and receipt["http_status"] == 200
                    else "HTTP_ERROR"
                    if receipt["http_status"] and receipt["http_status"] >= 400
                    else "FAILED"
                )
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
            if headers_path.exists():
                receipt["response_headers"] = [
                    line
                    for line in headers_path.read_text(errors="replace").splitlines()
                    if line.lower().startswith(
                        (
                            "http/",
                            "content-type:",
                            "content-length:",
                            "content-disposition:",
                            "last-modified:",
                            "etag:",
                            "date:",
                        )
                    )
                ]
            with raw_path.open("xb") as output:
                with gzip.GzipFile(
                    fileobj=output, mode="wb", filename="", mtime=0
                ) as zipped:
                    if body_path.exists():
                        with body_path.open("rb") as source:
                            for block in iter(lambda: source.read(128 * 1024), b""):
                                self.check()
                                zipped.write(block)
                                hasher.update(block)
                                size += len(block)
                output.flush()
                os.fsync(output.fileno())
        self.next_request = time.monotonic() + 0.3
        self.check()
        receipt.update(
            completed_at_utc=utc(),
            body_bytes=size,
            body_sha256=hasher.hexdigest(),
            raw_sha256=sha(raw_path),
        )
        receipt["verification"] = verify_http(self.root, receipt)
        atomic_json(receipt_path, receipt)
        return receipt

    def body(self, receipt):
        if receipt["status"] != "DOWNLOADED":
            raise ValueError(
                f"Source acquisition failed: HTTP {receipt['http_status']}; {receipt['error']}"
            )
        with gzip.open(local_path(self.root, receipt["raw_file"]), "rb") as stream:
            return stream.read()
