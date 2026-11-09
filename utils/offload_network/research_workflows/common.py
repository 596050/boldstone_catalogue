"""Strict portable names, finite JSON and durable content identities."""

import hashlib
import json
import os
import re
import stat
import uuid
from pathlib import Path

from v2.safe_archive import relative_path

NAME = re.compile(r"[a-z][a-z0-9_-]{0,62}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def load(path, max_bytes=8 << 20):
    path = Path(path)
    if path.stat().st_size > max_bytes:
        raise ValueError("JSON exceeds configured limit")
    return parse(path.read_bytes())


def parse(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result

    return json.loads(
        data,
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")),
    )


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + "." + uuid.uuid4().hex)
    with tmp.open("x", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    sync_directory(path.parent)


def sync_directory(path):
    """Persist rename entries on POSIX; Windows uses its replace/file flush semantics."""
    if os.name == "nt":
        return
    import errno

    descriptor = os.open(path, os.O_RDONLY)
    try:
        try:
            os.fsync(descriptor)
        except OSError as exc:
            if exc.errno not in {errno.EINVAL, errno.ENOTSUP}:
                raise
    finally:
        os.close(descriptor)


def sync_tree(path):
    """Flush already-verified staged regular files before publishing their directory."""
    directories = []
    for parent, _, files in os.walk(path):
        directories.append(parent)
        for filename in files:
            target = Path(parent) / filename
            if target.is_symlink() or not target.is_file():
                raise ValueError("nonregular file in durable object stage")
            with target.open("rb") as stream:
                os.fsync(stream.fileno())
    for directory in reversed(directories):
        sync_directory(directory)


def no_links(path, anchor):
    """Reject link components below an already trusted absolute anchor."""
    path, anchor = Path(path).absolute(), Path(anchor).absolute()
    suffix = path.relative_to(anchor)
    current = anchor
    for part in ("", *suffix.parts):
        current = current / part
        if current.is_symlink():
            raise ValueError("path traverses a symlink: " + str(current))
    return path


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def capture_file(source, destination, *, expected_sha256, max_bytes):
    """Fresh, bounded copy of declared bytes; leave failed captures inspectable."""
    source, destination = Path(source), Path(destination)
    before = source.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
        raise ValueError("capture source is not a bounded regular file")
    value, size = hashlib.sha256(), 0
    with source.open("rb") as incoming, destination.open("xb") as output:
        while True:
            block = incoming.read(min(1 << 20, max_bytes - size + 1))
            if not block:
                break
            size += len(block)
            if size > max_bytes:
                raise ValueError("capture source grew beyond its declared byte budget")
            value.update(block)
            output.write(block)
        output.flush()
        os.fsync(output.fileno())
    after = source.lstat()
    if ((before.st_size, before.st_mtime_ns, before.st_ino) !=
            (after.st_size, after.st_mtime_ns, after.st_ino)
            or size != before.st_size or value.hexdigest() != expected_sha256
            or sha(destination) != expected_sha256):
        raise ValueError("source changed during verified capture")
    return size


def name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError("names must be lowercase portable identifiers (1-63 characters)")
    return value


def hash_id(value):
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise ValueError("expected a lowercase SHA-256 identity")
    return value


def rel(value):
    if not isinstance(value, str):
        raise ValueError("expected a portable relative path")
    relative_path(value)
    # Also reject ambiguous separators and names on Windows controllers.
    if any(part.endswith((" ", ".")) for part in value.split("/")):
        raise ValueError("ambiguous portable path")
    return value


def fields(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError("invalid fields; allowed=" + ",".join(sorted(allowed)))
    return value


def positive(value, maximum, *, integer=True):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected a positive numeric limit")
    if (integer and type(value) is not int) or not 0 < value <= maximum:
        raise ValueError("limit is outside the allowed range")
    return value


def inventory(root, *, max_bytes=1 << 30, max_files=100000):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("expected a regular directory")
    files, seen, total = {}, set(), 0
    for parent, directories, leaves in os.walk(root, followlinks=False):
        for item in sorted(directories + leaves):
            path = Path(parent) / item
            relative = rel(path.relative_to(root).as_posix())
            key = relative.casefold()
            if key in seen:
                raise ValueError("case-colliding paths")
            seen.add(key)
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("only independent regular files/directories are allowed")
            total += info.st_size
            if total > max_bytes or len(files) >= max_files:
                raise ValueError("file tree exceeds its size/count budget")
            value = sha(path)
            after = path.stat()
            if (info.st_size, info.st_mtime_ns, info.st_ino) != (
                after.st_size,
                after.st_mtime_ns,
                after.st_ino,
            ):
                raise ValueError("file changed while hashing: " + relative)
            files[relative] = {"sha256": value, "bytes": info.st_size}
    return files


def verify_tree(root, expected, **limits):
    if not isinstance(expected, dict):
        raise ValueError("file tree differs from its immutable manifest: invalid file table")
    actual = inventory(root, **limits)
    if actual != expected:
        differences = {
            "added": sorted(actual.keys() - expected.keys()),
            "missing": sorted(expected.keys() - actual.keys()),
            "changed": sorted(key for key in actual.keys() & expected.keys()
                              if actual[key] != expected[key]),
        }
        # Keep the original rejection and all byte checks. Name the affected
        # input and a bounded path sample so an auxiliary cache file can be
        # distinguished from changed model/source bytes without another scan.
        detail = {kind: {"count": len(paths), "paths": [p[:160] for p in paths[:5]]}
                  for kind, paths in differences.items() if paths}
        raise ValueError("file tree differs from its immutable manifest: "
                         + str(root) + "; " + canonical(detail))
