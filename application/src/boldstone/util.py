from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .errors import IntegrityError


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def new_id(prefix):
    return f"{prefix}-{uuid4().hex}"


def check_no_symlinks(path):
    path = Path(path).expanduser()
    if not path.is_absolute():
        raise IntegrityError("Managed local paths must be absolute")
    if ".." in path.parts:
        raise IntegrityError("Managed local paths may not contain '..'")
    for component in (path, *path.parents):
        if component.is_symlink():
            raise IntegrityError("Symlink in a managed local path", details={"path": str(path)})
    return path


def private_directory(path):
    path = check_no_symlinks(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir():
        raise IntegrityError("Managed directory is not a directory")
    os.chmod(path, 0o700)
    return path


def atomic_write(path, data, *, exclusive=True):
    """Commit bytes without following destination symlinks or replacing evidence."""
    path = check_no_symlinks(path)
    private_directory(path.parent)
    fd, temporary = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data.encode() if isinstance(data, str) else data)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.link(temporary, path)  # Atomic no-clobber promotion, same filesystem.
        else:
            os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path


def json_write(path, data, *, exclusive=True):
    return atomic_write(
        path, json.dumps(data, indent=2, ensure_ascii=False) + "\n", exclusive=exclusive
    )


SECRET_KEYS = {
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "set-cookie",
    "app_secret",
    "client_secret",
    "code_verifier",
    "authorization_code",
    "download_url",
    "temporary_link",
}


def redact(value):
    if isinstance(value, dict):
        return {
            str(k): ("[REDACTED]" if str(k).lower() in SECRET_KEYS else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


def within_path(path, root):
    """Both inputs are native, server-normalized namespace paths."""
    return isinstance(path, str) and (path == root or path.startswith(root.rstrip("/") + "/"))


def parent_path(path):
    return path.rsplit("/", 1)[0] or ""


def native_reference(value):
    if not isinstance(value, str) or value.startswith("ns:") or "//" in value:
        raise IntegrityError("Historical connector paths are not native Dropbox references")
    if not (value.startswith("id:") or value.startswith("/") or value == ""):
        raise IntegrityError("Expected a native Dropbox stable ID or API-relative path")
    return value
