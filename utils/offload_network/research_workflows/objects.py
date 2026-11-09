"""Deterministic sealed directories and resumable, bounded worker-local objects.

No uploaded code is imported here. Objects become visible only after complete
archive and file-manifest verification. Dataset registration is a one-time local
snapshot, never a mutable path supplied by an HTTP caller.
"""

import gzip
import io
import os
import shutil
import tarfile
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

from lib.live_files import live_tree_bytes
from offload_service.core import CapacityError, Conflict
from v2.safe_archive import extract_tar

from .common import (
    atomic,
    canonical,
    digest,
    fields,
    hash_id,
    inventory,
    load,
    name,
    no_links,
    positive,
    parse,
    rel,
    sha,
    sync_directory,
    sync_tree,
    verify_tree,
)
from .archive_copy import copy as copy_archive

SCHEMA = "marketmaker.offload_object.v1"
from .deduplicated_objects import SCHEMA as DEDUP_SCHEMA
SUPPORTED_SCHEMAS = {SCHEMA, DEDUP_SCHEMA}
CHUNK = 4 << 20


def _archive_metadata(archive, *, max_bytes):
    """Bind a small commit's reservation to its bounded manifest, not the
    largest dataset this worker is allowed to accept.

    The deterministic object format puts OBJECT.json first. Its declaration is
    not trusted as proof of contents: extraction is capped at this same budget
    and verify_tree subsequently checks every byte, size, hash and member.
    """
    with tarfile.open(archive, mode="r|gz") as stream:
        first = stream.next()
        if first is not None:
            rel(first.name.rstrip("/") if first.isdir() else first.name)
            if first.size < 0 or first.size > max_bytes:
                raise ValueError("archive exceeds extraction limits")
            if not first.isreg() or first.issparse():
                raise ValueError("unsafe object archive member type")
        if (first is None or first.name != "OBJECT.json" or not first.isreg()
                or first.issparse() or not 0 < first.size <= min(max_bytes, 8 << 20)):
            raise ValueError("object archive must start with bounded regular OBJECT.json")
        member = stream.extractfile(first)
        if member is None:
            raise ValueError("unreadable object manifest")
        with member:
            encoded = member.read((8 << 20) + 1)
        if len(encoded) != first.size:
            raise ValueError("truncated object manifest")
        manifest = parse(encoded)
    fields(manifest, {"schema", "files"}, {"schema", "files"})
    files = manifest["files"]
    if manifest["schema"] not in SUPPORTED_SCHEMAS or not isinstance(files, dict) or not 1 <= len(files) <= 100000:
        raise ValueError("invalid object schema or file count")
    total, names = first.size, set()
    for path, reference in files.items():
        key = rel(path).casefold()
        if key in names:
            raise ValueError("case-colliding object manifest paths")
        names.add(key)
        fields(reference, {"bytes", "sha256"}, {"bytes", "sha256"})
        hash_id(reference["sha256"])
        size = reference["bytes"]
        if type(size) is not int or size < 0:
            raise ValueError("object file size must be a nonnegative integer")
        total += size
        if total > max_bytes:
            raise ValueError("object exceeds its configured expansion limit")
    if any('/'.join(path.split('/')[:i]) in names
           for path in names for i in range(1, len(path.split('/')))):
        raise ValueError('object manifest file/directory collision')
    return manifest, total, len(files) + 1


def object_expansion_budget(archive, *, max_bytes):
    """Return strictly bounded expanded bytes and member count from the header."""
    _, total, members = _archive_metadata(archive, max_bytes=max_bytes)
    return total, members


def extract_object(archive, destination, *, max_bytes, max_members=100001):
    """Object format is always gzip, including resumable .part transfers."""
    manifest, _, members = _archive_metadata(archive, max_bytes=max_bytes)
    if manifest['schema'] == DEDUP_SCHEMA:
        from .deduplicated_objects import materialize
        destination = Path(destination)
        materialize(archive, destination / 'data', manifest,
                    max_bytes=max_bytes, max_members=min(max_members, members))
        atomic(destination / 'OBJECT.json', manifest)
        return members
    with tarfile.open(archive, mode="r|gz") as stream:
        return extract_tar(stream, destination, max_bytes=max_bytes, max_members=max_members)


def pack(source, destination, *, max_bytes=1 << 30, max_files=100000, deduplicate=False):
    """Freeze a directory without importing it; deterministic gzip/tar bytes."""
    source, destination = Path(source), Path(destination)
    files = inventory(source, max_bytes=max_bytes, max_files=max_files)
    if not files:
        raise ValueError("cannot package an empty input")
    # A returned v2 object's archive identity may be bound by a portable
    # checkpoint. Preserve the exact sealed representation after independently
    # verifying both its archive and expanded tree; re-encoding it as v1 would
    # change that identity despite unchanged logical input bytes.
    retained = source.parent / 'archive.tar.gz'
    header = source.parent / 'OBJECT.json'
    if source.name == 'data' and header.is_file() and retained.is_file():
        if header.is_symlink() or retained.is_symlink():
            raise ValueError('retained object metadata and archive must be regular files')
        original = load(header)
        if original == {'schema': DEDUP_SCHEMA, 'files': files}:
            from .deduplicated_objects import verify
            verify(retained, original, max_bytes=max_bytes, max_members=max_files + 1)
            identity = sha(retained)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with retained.open('rb') as incoming, destination.open('xb') as outgoing:
                shutil.copyfileobj(incoming, outgoing, CHUNK)
                outgoing.flush(); os.fsync(outgoing.fileno())
            if sha(destination) != identity or sha(retained) != identity:
                raise ValueError('retained object changed during identity-preserving copy')
            verify_tree(source, files, max_bytes=max_bytes, max_files=max_files)
            return {'object_sha256': identity, 'archive_bytes': destination.stat().st_size,
                    'content_manifest': original}
    manifest = {"schema": DEDUP_SCHEMA if deduplicate else SCHEMA, "files": files}
    if len(canonical(manifest).encode()) > 8 << 20:
        raise ValueError("object file manifest exceeds 8 MiB")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|") as archive:
                encoded = (canonical(manifest) + "\n").encode()
                member = tarfile.TarInfo("OBJECT.json")
                member.size, member.mode = len(encoded), 0o644
                archive.addfile(member, io.BytesIO(encoded))
                if deduplicate:
                    from .deduplicated_objects import write_members
                    write_members(archive, source, manifest)
                for relative, ref in ([] if deduplicate else sorted(files.items())):
                    member = tarfile.TarInfo("data/" + relative)
                    member.size, member.mode = ref["bytes"], 0o644
                    with (source / relative).open("rb") as stream:
                        archive.addfile(member, stream)
        raw.flush()
        os.fsync(raw.fileno())
    verify_tree(source, files, max_bytes=max_bytes, max_files=max_files)
    return {
        "object_sha256": sha(destination),
        "archive_bytes": destination.stat().st_size,
        "content_manifest": manifest,
    }


class ObjectStore:
    def __init__(self, root, *, max_object_mb=1024, max_store_mb=10240, min_free_mb=128):
        self.root = Path(root)
        self.max_bytes = positive(max_object_mb, 1048576) * (1 << 20)
        self.max_store = positive(max_store_mb, 10485760) * (1 << 20)
        self.reserve = positive(min_free_mb, 1048576) * (1 << 20)
        self.guard = threading.RLock()
        self.verification_guard = threading.Lock()
        self.verification_locks = {}
        for part in ("objects", "uploads", "datasets"):
            (self.root / part).mkdir(parents=True, exist_ok=True, mode=0o700)

    def capacity(self, additional=0):
        used = live_tree_bytes(self.root)
        if (
            used + additional > self.max_store
            or shutil.disk_usage(self.root).free < self.reserve + additional
        ):
            raise CapacityError("workflow object storage budget exhausted")

    def directory(self, identity):
        return self.root / "objects" / hash_id(identity)

    def _declared_manifest(self, identity):
        root = no_links(self.directory(identity), self.root)
        if not (root / "COMMITTED.json").is_file():
            raise KeyError(identity)
        committed = load(no_links(root / "COMMITTED.json", self.root))
        manifest = load(no_links(root / "OBJECT.json", self.root))
        archive = no_links(root / "archive.tar.gz", self.root)
        if (
            committed != {"object_sha256": identity, "manifest": manifest}
            or manifest.get("schema") not in SUPPORTED_SCHEMAS
            or _archive_metadata(archive, max_bytes=self.max_bytes)[0] != manifest
        ):
            raise ValueError("invalid object commit")
        return root, manifest

    def declared_size(self, identity):
        """Provisional input-budget accounting only; NOT verification of bytes.

        Admission, all execution boundaries and object downloads still use get.
        A changed tree/archive may pass this size lookup, but cannot pass get.
        Do not use this method to authorize execution or content reuse.
        """
        _, manifest = self._declared_manifest(identity)
        return sum(reference["bytes"] for reference in manifest["files"].values())

    @contextmanager
    def _verification(self, identity):
        hash_id(identity)
        # Avoid overlapping bulk reads of the same object without holding the
        # metadata/upload lock. Different objects retain parallel verification.
        with self.verification_guard:
            entry = self.verification_locks.setdefault(identity, [threading.Lock(), 0])
            entry[1] += 1
        try:
            with entry[0]:
                yield
        finally:
            with self.verification_guard:
                entry[1] -= 1
                if not entry[1]:
                    del self.verification_locks[identity]

    def get(self, identity):
        with self._verification(identity):
            # Every caller rehashes all bytes after it acquires the lock. A
            # previous verification is never reused across a trust boundary.
            root, manifest = self._declared_manifest(identity)
            data = no_links(root / "data", self.root)
            if not data.exists():
                self._restore_archived(identity, root, manifest)
            verify_tree(root / "data", manifest["files"], max_bytes=self.max_bytes)
            # The archive is also the authenticated, immutable download object.
            if sha(root / "archive.tar.gz") != identity:
                raise ValueError("stored archive changed")
            return root, manifest

    def _restore_archived(self, identity, root, manifest):
        """Restore only explicitly retained missing expansions, under get's lock.

        Commit, archive identity and every extracted byte remain mandatory. A
        corrupt existing tree, absent retention marker, or interrupted compaction
        is an error. Keep the original archive and retention receipt unchanged.
        """
        from .compressed import marker

        with self.guard:
            retained = no_links(root / "ARCHIVE_ONLY.json", self.root)
            if not retained.is_file() or load(retained) != marker(identity, manifest):
                raise ValueError("missing object data lacks a valid archive-retention receipt")
            if no_links(root / "data.compacting", self.root).exists():
                raise ValueError("interrupted object compaction requires inspection")
            archive = no_links(root / "archive.tar.gz", self.root)
            if sha(archive) != identity:
                raise ValueError("stored archive changed")
            expanded, members = object_expansion_budget(archive, max_bytes=self.max_bytes)
            # Serialize reservation and materialization with other store writes.
            # The archive already occupies the store; reserve only its expansion.
            self.capacity(expanded + 4096)
            with tempfile.TemporaryDirectory(prefix=".restore-", dir=self.root / "uploads") as temp:
                stage = Path(temp) / "object"
                extract_object(archive, stage, max_bytes=expanded, max_members=members)
                if ({p.name for p in stage.iterdir()} != {"OBJECT.json", "data"}
                        or load(stage / "OBJECT.json") != manifest):
                    raise ValueError("restored object manifest changed")
                verify_tree(stage / "data", manifest["files"], max_bytes=self.max_bytes)
                if sha(archive) != identity:
                    raise ValueError("stored archive changed during restoration")
                sync_tree(stage / "data")
                destination = no_links(root / "data", self.root)
                if destination.exists():
                    raise Conflict("object expansion appeared during restoration")
                os.replace(stage / "data", destination)
                sync_directory(root)
                atomic(root / "RESTORED.json", {
                    "schema": "marketmaker.offload_object_restoration.v1",
                    "object_sha256": identity,
                    "manifest_sha256": digest(manifest),
                    "expanded_bytes": sum(ref["bytes"] for ref in manifest["files"].values()),
                    "archive_and_retention_receipt_unchanged": True,
                })

    def status(self, identity):
        with self.guard:
            root = self.directory(identity)
            if (root / "COMMITTED.json").exists():
                # Presence/commit metadata is not execution authorization.
                # begin() and GET /v2/objects of an already-committed identity
                # must not re-hash the tree under the store lock; get() still
                # verifies every file before admission or download of bytes.
                root, manifest = self._declared_manifest(identity)
                return {
                    "object_sha256": identity,
                    "state": "committed",
                    "bytes": (root / "archive.tar.gz").stat().st_size,
                    "manifest": manifest,
                }
            meta = self.root / "uploads" / (identity + ".json")
            if not meta.exists():
                raise KeyError(identity)
            value = load(meta)
            part = meta.with_suffix(".part")
            return {**value, "state": "uploading", "offset": part.stat().st_size}

    def begin(self, identity, size):
        hash_id(identity)
        positive(size, self.max_bytes)
        with self.guard:
            meta = no_links(self.root / "uploads" / (identity + ".json"), self.root)
            part = no_links(meta.with_suffix(".part"), self.root)
            try:
                old = self.status(identity)
            except KeyError:
                old = None
            if old:
                if old["bytes"] != size:
                    raise Conflict("object upload size conflicts with previous request")
                if old["state"] == "committed":
                    self._finish_upload(identity, old["bytes"])
                return old
            self.capacity(size * 3)
            if part.exists():
                # A crash before the begin receipt can leave only this empty
                # file. Nonempty unbound bytes are ambiguous: retain and reject.
                if not part.is_file() or part.stat().st_size:
                    raise Conflict("unbound nonempty upload requires inspection")
            else:
                with part.open("xb") as stream:
                    stream.flush()
                    os.fsync(stream.fileno())
            atomic(meta, {"object_sha256": identity, "bytes": size})
            return self.status(identity)

    def _finish_upload(self, identity, size):
        """Finish only a verified commit's redundant upload cleanup, idempotently."""
        meta = no_links(self.root / "uploads" / (identity + ".json"), self.root)
        part = no_links(meta.with_suffix(".part"), self.root)
        if meta.exists() and load(meta) != {"object_sha256": identity, "bytes": size}:
            raise ValueError("committed upload metadata changed; retaining staging")
        if part.exists():
            if not part.is_file() or part.stat().st_size != size or sha(part) != identity:
                raise ValueError("committed upload staging changed; retaining bytes")
            part.unlink()
            sync_directory(part.parent)
        if meta.exists():
            meta.unlink()
            sync_directory(meta.parent)

    def append(self, identity, offset, data):
        hash_id(identity)
        if type(offset) is not int or offset < 0 or not 0 < len(data) <= CHUNK:
            raise ValueError("invalid upload offset/chunk")
        with self.guard:
            state = self.status(identity)
            if state["state"] == "committed":
                raise Conflict("object is already committed")
            part = self.root / "uploads" / (identity + ".part")
            if offset + len(data) > state["bytes"]:
                raise ValueError("chunk exceeds declared upload length")
            if offset < state["offset"]:
                with part.open("rb") as stream:
                    stream.seek(offset)
                    if stream.read(len(data)) != data:
                        raise Conflict("repeated chunk has different bytes")
                return state
            if offset != state["offset"]:
                raise Conflict("upload offset does not match retained prefix")
            self.capacity(len(data))
            with part.open("ab") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            return self.status(identity)

    def commit(self, identity):
        hash_id(identity)
        with self.guard:
            state = self.status(identity)
            if state["state"] == "committed":
                self._finish_upload(identity, state["bytes"])
                return state
            part = self.root / "uploads" / (identity + ".part")
            if part.stat().st_size != state["bytes"] or sha(part) != identity:
                raise ValueError("incomplete or corrupt uploaded object")
            expanded, members = object_expansion_budget(part, max_bytes=self.max_bytes)
            self.capacity(expanded + state["bytes"])
            with tempfile.TemporaryDirectory(prefix=".verify-", dir=self.root / "uploads") as temp:
                stage = Path(temp) / "object"
                extract_object(part, stage, max_bytes=expanded, max_members=members)
                if {p.name for p in stage.iterdir()} != {"OBJECT.json", "data"}:
                    raise ValueError("object archive must contain only OBJECT.json and data/")
                manifest = load(stage / "OBJECT.json")
                fields(manifest, {"schema", "files"}, {"schema", "files"})
                if manifest["schema"] not in SUPPORTED_SCHEMAS or not manifest["files"]:
                    raise ValueError("invalid object schema")
                verify_tree(stage / "data", manifest["files"], max_bytes=self.max_bytes)
                copy_archive(part, stage / "archive.tar.gz")
                if sha(stage / "archive.tar.gz") != identity:
                    raise ValueError("object copy verification failed")
                atomic(stage / "COMMITTED.json", {"object_sha256": identity, "manifest": manifest})
                destination = self.directory(identity)
                if destination.exists():
                    raise Conflict("uncommitted object directory already exists")
                sync_tree(stage)
                os.replace(stage, destination)
                sync_directory(destination.parent)
            state = self.status(identity)
            self._finish_upload(identity, state["bytes"])
            return state

    def ingest(self, directory, *, deduplicate=False):
        with (
            self.guard,
            tempfile.TemporaryDirectory(prefix=".ingest-", dir=self.root / "uploads") as temp,
        ):
            archive = Path(temp) / "object.tar.gz"
            ref = pack(directory, archive, max_bytes=self.max_bytes, deduplicate=deduplicate)
            ident = ref["object_sha256"]
            status = self.begin(ident, archive.stat().st_size)
            if status["state"] != "committed":
                with archive.open("rb") as stream:
                    stream.seek(status["offset"])
                    offset = status["offset"]
                    for chunk in iter(lambda: stream.read(CHUNK), b""):
                        self.append(ident, offset, chunk)
                        offset += len(chunk)
                self.commit(ident)
            return ident

    def register_dataset(self, dataset_id, version, directory, *, expected_object=None):
        name(dataset_id)
        name(version)
        # Existing versions cannot be remapped. Take one immutable local snapshot.
        with self.guard:
            destination = self.root / "datasets" / dataset_id / (version + ".json")
            identity = self.ingest(directory)
            if expected_object is not None and identity != hash_id(expected_object):
                raise ValueError("dataset snapshot does not match expected identity")
            record = {"dataset_id": dataset_id, "version": version, "object_sha256": identity}
            if destination.exists() and load(destination) != record:
                raise Conflict("dataset version already has different bytes")
            atomic(destination, record)
            return record

    def dataset_identity(self, dataset_id, version, expected):
        """Validate the version binding, NOT the dataset's current data bytes."""
        name(dataset_id)
        name(version)
        hash_id(expected)
        path = no_links(self.root / "datasets" / dataset_id / (version + ".json"), self.root)
        if not path.is_file():
            raise KeyError("registered dataset unavailable")
        record = load(path)
        if record != {"dataset_id": dataset_id, "version": version, "object_sha256": expected}:
            raise ValueError("registered dataset identity mismatch")
        return expected

    def dataset(self, dataset_id, version, expected):
        return self.get(self.dataset_identity(dataset_id, version, expected))
