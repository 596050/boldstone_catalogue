"""Lossless source-side archive retention and bounded read materialization."""

import errno
import hashlib
import os
import shutil
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .common import (
    atomic,
    digest,
    hash_id,
    load,
    no_links,
    parse,
    rel,
    sha,
    sync_directory,
)
from .objects import extract_object


def marker(identity, manifest):
    return {
        "schema": "marketmaker.offload_archive_only.v1",
        "object_sha256": identity,
        "manifest_sha256": digest(manifest),
    }


def verify_archive(directory, identity, manifest, *, max_bytes, archive_path=None):
    """Check every archived file without expanding thousands of small files on disk."""
    directory = Path(directory)
    archive_path = Path(archive_path) if archive_path is not None else directory / "archive.tar.gz"
    if archive_path.is_symlink() or sha(archive_path) != hash_id(identity):
        raise ValueError("retained compressed archive changed")
    from .deduplicated_objects import SCHEMA as DEDUP_SCHEMA, verify
    if manifest.get('schema') == DEDUP_SCHEMA:
        verify(archive_path, manifest, max_bytes=max_bytes)
        return
    expected, observed, seen, total, header = manifest["files"], {}, set(), 0, False
    with tarfile.open(archive_path, "r|gz") as archive:
        for member in archive:
            relative = rel(member.name.rstrip("/"))
            if relative.casefold() in seen or len(seen) > 100001:
                raise ValueError("duplicate/excessive compressed archive members")
            seen.add(relative.casefold())
            if member.isdir():
                if relative != "data" and not relative.startswith("data/"):
                    raise ValueError("unexpected archive directory")
                continue
            if not member.isfile() or member.issparse():
                raise ValueError("only regular compressed files are allowed")
            stream = archive.extractfile(member)
            if relative == "OBJECT.json":
                if member.size > 8 << 20 or parse(stream.read()) != manifest:
                    raise ValueError("compressed object manifest changed")
                header = True
                continue
            if not relative.startswith("data/") or relative[5:] not in expected:
                raise ValueError("unexpected compressed file")
            key = relative[5:]
            total += member.size
            if total > max_bytes or expected[key]["bytes"] != member.size:
                raise ValueError("compressed object exceeds size manifest/budget")
            value = hashlib.sha256()
            for block in iter(lambda stream=stream: stream.read(1 << 20), b""):
                value.update(block)
            observed[key] = {"bytes": member.size, "sha256": value.hexdigest()}
    if not header or observed != expected:
        raise ValueError("compressed files differ from the immutable manifest")


@contextmanager
def data_view(directory, *, max_bytes):
    """Temporary native-reader view; returned code is never executed here."""
    directory = Path(directory)
    if (directory / "data").is_dir():
        yield directory / "data"
        return
    if not (directory / "ARCHIVE_ONLY.json").is_file():
        raise ValueError("object data is missing without a compressed-retention receipt")
    size = sum(f["bytes"] for f in load(directory / "OBJECT.json")["files"].values())
    with tempfile.TemporaryDirectory(prefix="offload-native-read-") as temporary:
        if shutil.disk_usage(temporary).free < size + (1 << 30):
            raise OSError(
                errno.ENOSPC, "insufficient temporary read space; compressed evidence is retained"
            )
        target = Path(temporary) / "object"
        extract_object(directory / "archive.tar.gz", target, max_bytes=max_bytes)
        yield target / "data"


def compact_object(directory, identity, *, max_bytes):
    """Remove only verified expanded copies; exact archives remain authoritative."""
    from .client import verify_object

    directory = Path(directory).absolute()
    if directory.name != hash_id(identity) or directory.parent.name != "objects":
        raise ValueError("compaction target must be one named object in a shared repository")
    no_links(directory, directory.parent.parent)
    manifest = verify_object(directory, identity, max_bytes=max_bytes)
    verify_archive(directory, identity, manifest, max_bytes=max_bytes)
    atomic(directory / "ARCHIVE_ONLY.json", marker(identity, manifest))
    expanded = no_links(directory / "data", directory)
    # The exact bytes were independently checked against the retained compressed
    # archive. A crash during removal is safe: archive-only readers ignore this
    # explicitly named disposable expansion and the next compaction completes it.
    disposable = no_links(directory / "data.compacting", directory)
    released = expanded.exists() or disposable.exists()
    if expanded.exists():
        if disposable.exists():
            raise ValueError("ambiguous interrupted compaction; retain both copies for inspection")
        os.replace(expanded, disposable)
        sync_directory(directory)
    if disposable.exists():
        shutil.rmtree(disposable)
        sync_directory(directory)
    return {
        "object_sha256": identity,
        "expanded_bytes_released": sum(f["bytes"] for f in manifest["files"].values())
        if released
        else 0,
    }


def materialize(project, directory, relative=None):
    """Return a verified source-local read copy; no bulk expansion on the data drive."""
    from lib.file_lock import file_lock

    from .client import verify_object
    from .project_storage import StorageUnavailable

    directory = Path(directory)
    identity = directory.name
    limit = project.storage["max_collection_mb"] << 20
    manifest = verify_object(directory, identity, max_bytes=limit)
    wanted = rel(relative) if relative is not None else None
    files = {
        k: v
        for k, v in manifest["files"].items()
        if wanted is None or k == wanted or k.startswith(wanted + "/")
    }
    if not files:
        raise ValueError("requested file/directory is absent from the immutable object")
    cache = no_links(project.state / "read-cache" / hash_id(identity), project.root)
    target = cache / wanted if wanted is not None else cache
    with file_lock(project.state / "read-cache.lock", timeout=0):
        missing = {}
        for key, value in files.items():
            path = no_links(cache / key, project.root)
            if path.exists():
                if path.stat().st_size != value["bytes"] or sha(path) != value["sha256"]:
                    raise ValueError("materialized read copy changed")
            else:
                missing[key] = value
        size = sum(value["bytes"] for value in missing.values())
        from lib.live_files import live_tree_bytes

        if live_tree_bytes(project.state) + size > project.storage[
            "max_local_state_mb"
        ] << 20 or shutil.disk_usage(project.root).free < size + (
            project.storage["local_min_free_mb"] << 20
        ):
            raise StorageUnavailable(
                "bounded local read cache is full; retained archives remain intact"
            )
        if missing:
            cache.mkdir(parents=True, exist_ok=True)
            from .deduplicated_objects import SCHEMA as DEDUP_SCHEMA, materialize as dedup_materialize
            if manifest['schema'] == DEDUP_SCHEMA:
                # Use a private staging tree so interruption cannot leave an
                # apparently valid cached file at an original path.
                with tempfile.TemporaryDirectory(prefix='.materialize-', dir=project.state) as temp:
                    stage = Path(temp) / 'data'
                    dedup_materialize(directory / 'archive.tar.gz', stage, manifest,
                                      files=missing, max_bytes=limit)
                    for key in missing:
                        path = no_links(cache / key, project.root)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(stage / key, path)
                        sync_directory(path.parent)
                atomic(cache.parent / ('.' + identity + '.json'), {'object_sha256': identity})
                return target
            with tarfile.open(directory / "archive.tar.gz", "r|gz") as archive:
                for member in archive:
                    key = member.name[5:] if member.name.startswith("data/") else None
                    if key not in missing:
                        continue
                    path = no_links(cache / key, project.root)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    part = no_links(
                        path.with_name("." + path.name + ".materializing"), project.root
                    )
                    with archive.extractfile(member) as incoming, part.open("wb") as output:
                        shutil.copyfileobj(incoming, output, 1 << 20)
                        output.flush()
                        os.fsync(output.fileno())
                    if sha(part) != files[key]["sha256"]:
                        raise ValueError("materialized file identity differs from its archive")
                    os.replace(part, path)
                    sync_directory(path.parent)
            atomic(cache.parent / ("." + identity + ".json"), {"object_sha256": identity})
        return target


def compact_collection(project, collection):
    from .client import collection_objects, verify_collection

    limit = project.storage["max_collection_mb"] << 20
    repository = project.bulk()
    no_links(Path(collection).absolute(), repository)
    receipt = verify_collection(collection, max_bytes=limit)
    root, _ = collection_objects(collection)
    if root != repository / "objects":
        raise ValueError("only shared source-owned collections may be compacted")
    released = [
        compact_object(root / ident, ident, max_bytes=limit)
        for ident in receipt["collected_objects"]
    ]
    verify_collection(collection, max_bytes=limit)
    return released
