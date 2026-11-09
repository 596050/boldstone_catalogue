"""Portable, streaming, regular-files-only archive extraction.

No tar extraction defaults, symlinks, hardlinks, devices, sparse files, path
aliases or overwrites. Destinations must be private to the extracting process.
This module is also sent verbatim to SSH workers before bootstrap execution.
"""

from __future__ import annotations

import contextlib
import pathlib
import re
import shutil
import tarfile


def relative_path(name: str) -> pathlib.PurePosixPath:
    parts = name.split("/")
    if (
        not name
        or name.startswith("/")
        or "\\" in name
        or ":" in name
        or any(p in {"", ".", ".."} or p.rstrip(" .") != p for p in parts)
        or any(ord(c) < 32 for c in name)
        or any(re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?", p) for p in parts)
    ):
        raise ValueError(f"unsafe archive path: {name!r}")
    return pathlib.PurePosixPath(name)


def bounded_members(tar, *, max_bytes, max_members):
    """Validate the same bounded member declarations for sizing and extraction."""
    seen = set()
    total = count = 0
    for member in tar:
        rel = relative_path(member.name.rstrip("/") if member.isdir() else member.name)
        key = str(rel).casefold()
        if key in seen:
            raise ValueError(f"duplicate archive path: {member.name!r}")
        seen.add(key)
        count += 1
        total += member.size
        if count > max_members or total > max_bytes or member.size < 0:
            raise ValueError("archive exceeds extraction limits")
        if not (member.isdir() or member.isreg()) or member.issparse():
            raise ValueError(f"unsafe archive member type: {member.name!r}")
        yield member, rel


def expansion_budget(path, *, max_bytes=100 * (1 << 30), max_members=200_000):
    """Bound declared expansion without writing files or trusting compressed size.

    This is a capacity observation, not verification of file contents. Extraction
    repeats member validation and enforces this observed byte/member ceiling.
    """
    total = count = 0
    with open_archive(path) as tar:
        for member, _ in bounded_members(tar, max_bytes=max_bytes, max_members=max_members):
            total += member.size
            count += 1
    return total, count


def extract_tar(tar, dest, *, max_bytes=100 * (1 << 30), max_members=200_000):
    dest = pathlib.Path(dest).absolute()
    if dest.is_symlink():
        raise ValueError("extraction destination may not be a symlink")
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    for member, rel in bounded_members(tar, max_bytes=max_bytes, max_members=max_members):
        count += 1
        target = dest.joinpath(*rel.parts)
        # Check existing parents too; never follow links even if they point inside.
        for candidate in [target, *target.parents]:
            if candidate == dest:
                break
            if candidate.is_symlink():
                raise ValueError(f"symlink at extraction target: {member.name!r}")
        target.resolve().relative_to(dest)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        source = tar.extractfile(member)
        if source is None:
            raise ValueError(f"unreadable archive member: {member.name!r}")
        with source, target.open("xb") as output:
            shutil.copyfileobj(source, output, length=1 << 20)
        if target.stat().st_size != member.size:
            raise ValueError(f"truncated archive member: {member.name!r}")
        target.chmod(0o700 if member.mode & 0o111 else 0o600)
    return count


@contextlib.contextmanager
def open_archive(path):
    with contextlib.ExitStack() as stack:
        if str(path).endswith(".tar.zst"):
            import zstandard

            raw = stack.enter_context(open(path, "rb"))
            stream = stack.enter_context(zstandard.ZstdDecompressor().stream_reader(raw))
            tar = stack.enter_context(tarfile.open(fileobj=stream, mode="r|"))
        elif str(path).endswith((".tar.gz", ".tgz")):
            tar = stack.enter_context(tarfile.open(path, "r:gz"))
        else:
            raise ValueError(f"unsupported archive format: {path}")
        yield tar
