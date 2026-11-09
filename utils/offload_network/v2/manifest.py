"""v2 sealed-bundle manifest.

A SealedManifest describes a single self-contained job. Unlike v1's
JobManifest, every input is content-addressed: each blob has a sha256
plus a path relative to the bundle root. The bundle is reproducible
from the manifest alone (given the blob contents).

Schema is JSON-friendly and forward-compatible. Adding new optional
fields is safe; remote runners ignore unknown keys.
"""
from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
import pathlib
import re
import uuid
from datetime import datetime, timezone
from typing import Optional


class SealError(Exception):
    """Raised for any v2-manifest or seal integrity error."""


_ID_RE = re.compile(r"^[A-Za-z0-9._-]{4,80}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ARCHIVE_FORMATS = ("tar.zst", "tar.gz")


class SealStatus(str, enum.Enum):
    PENDING     = "pending"      # manifest exists; bundle not built
    SEALED      = "sealed"       # local archive built
    PUSHED      = "pushed"       # archive on remote
    EXTRACTED   = "extracted"    # runner extracted archive
    RUNNING     = "running"      # entrypoint executing
    PACKED      = "packed"       # result archive built remote-side
    PULLED      = "pulled"       # result archive on local
    DONE        = "done"         # success path complete
    FAILED      = "failed"       # any unrecoverable error


@dataclasses.dataclass
class SealedBlob:
    """One file or directory entry in the sealed archive.

    All blobs are addressed by sha256 of their on-disk content (file:
    direct hash; directory: hash of a sorted manifest of recursive
    contents, used by content-addressed dedup in Phase 3 — but for
    Phase 1 we just hash files directly).
    """
    name:        str                          # logical role, e.g. "cache", "driver"
    local_src:   str                          # absolute path on submitter
    rel_path:    str                          # path within sealed archive (e.g. "data/cache.mat")
    sha256:      Optional[str] = None         # set by build_seal
    size_bytes:  Optional[int] = None
    is_dir:      bool = False                 # if true, local_src is a dir and rel_path is dir-rooted

    def validate(self) -> None:
        from .safe_archive import relative_path
        if not self.name:
            raise SealError("SealedBlob.name required")
        if not self.local_src:
            raise SealError(f"SealedBlob {self.name!r}: local_src required")
        if not self.rel_path:
            raise SealError(f"SealedBlob {self.name!r}: rel_path required")
        try:
            relative_path(self.rel_path)
            relative_path(self.name)
        except ValueError:
            raise SealError(
                f"SealedBlob {self.name!r}: rel_path {self.rel_path!r} must be relative, no parent refs"
            )
        if self.sha256 is not None and not _SHA_RE.match(self.sha256):
            raise SealError(
                f"SealedBlob {self.name!r}: bad sha256 {self.sha256!r}"
            )


@dataclasses.dataclass
class ResultSpec:
    """Describes what gets packed + pulled back as the result.

    The runner walks the remote workdir at exit, includes anything
    matching ``include_patterns`` minus ``exclude_patterns``, tars it
    into a result archive, and the submitter pulls + extracts it to
    ``local_dir``.
    """
    local_dir:        str                                   # where to extract result on submitter
    include_patterns: list = dataclasses.field(
        default_factory=lambda: ["result.json", "report.json", "status.json", "run.log",
                                  "*.json", "*.log", "artifacts/**"]
    )
    exclude_patterns: list = dataclasses.field(
        default_factory=lambda: ["*.tmp", "*_chunks/", ".rsync-partial/"]
    )
    archive_format:   str = "tar.gz"                        # "tar.zst" or "tar.gz"
    max_size_mb:      int = 1024                            # safety cap: runner refuses to pack a giant result

    def validate(self) -> None:
        if not self.local_dir:
            raise SealError("ResultSpec.local_dir required")
        if self.archive_format not in _ARCHIVE_FORMATS:
            raise SealError(
                f"ResultSpec.archive_format must be one of {_ARCHIVE_FORMATS}, got {self.archive_format!r}"
            )


@dataclasses.dataclass
class HostSpec:
    """Where the job runs."""
    ssh_alias:        str                                   # passed to ssh as host arg
    remote_workdir:   str                                   # base dir under which seal extracts
    platform:         str = "windows"                       # windows, linux, or macos
    user:             Optional[str] = None
    rsync_path:       Optional[str] = None                  # remote rsync binary if non-default
    python_executable: Optional[str] = None                 # "python" by default

    def validate(self) -> None:
        if not self.ssh_alias:
            raise SealError("HostSpec.ssh_alias required")
        if not self.remote_workdir:
            raise SealError("HostSpec.remote_workdir required")
        if self.platform not in {"windows", "linux", "macos"}:
            raise SealError(
                f"HostSpec.platform must be windows, linux, or macos; got {self.platform!r}"
            )


@dataclasses.dataclass
class SealedManifest:
    """A complete v2 job description.

    The entrypoint is one blob with role="entrypoint" + run_args. The
    runner invokes it as: ``python <entrypoint_path> <run_args>`` with
    cwd set to the workdir root.
    """
    job_id:           str = ""
    version:          str = "2.0"
    task_type:        str = "generic"
    metadata:         dict = dataclasses.field(default_factory=dict)

    host:             HostSpec = dataclasses.field(default_factory=lambda: HostSpec(ssh_alias="", remote_workdir=""))
    blobs:            list[SealedBlob] = dataclasses.field(default_factory=list)

    entrypoint_rel:   str = ""                              # rel_path of the entrypoint blob in the archive
    run_args:         list = dataclasses.field(default_factory=list)
    env:              dict = dataclasses.field(default_factory=dict)  # extra env vars for the runner
    extra_pythonpath: list = dataclasses.field(default_factory=list)  # prepended to PYTHONPATH (rel paths in archive)

    result:           ResultSpec = dataclasses.field(default_factory=lambda: ResultSpec(local_dir=""))

    archive_format:   str = "tar.gz"                        # "tar.zst" (zstd) or "tar.gz" (fallback)
    seal_sha256:      Optional[str] = None                  # of the built archive
    seal_path_local:  Optional[str] = None
    seal_size_bytes:  Optional[int] = None
    status:           SealStatus = SealStatus.PENDING
    last_error:       Optional[str] = None
    created_at:       str = ""

    def __post_init__(self) -> None:
        if not self.job_id:
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
            self.job_id = f"job-{stamp}-{uuid.uuid4().hex[:6]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def validate(self) -> None:
        if not _ID_RE.match(self.job_id):
            raise SealError(f"bad job_id {self.job_id!r}, must match {_ID_RE.pattern}")
        if self.archive_format not in _ARCHIVE_FORMATS:
            raise SealError(f"bad archive_format {self.archive_format!r}, must be one of {_ARCHIVE_FORMATS}")
        self.host.validate()
        for b in self.blobs:
            b.validate()
        if len({b.name for b in self.blobs}) != len(self.blobs):
            raise SealError("blob names must be unique")
        paths = [b.rel_path.casefold() for b in self.blobs]
        if any(a == b or a.startswith(b + "/") or b.startswith(a + "/")
               for i, a in enumerate(paths) for b in paths[i + 1:]):
            raise SealError("blob paths must not overlap")
        if not self.entrypoint_rel:
            raise SealError("entrypoint_rel required")
        # entrypoint must correspond to a declared blob
        rel_paths = {b.rel_path for b in self.blobs}
        if self.entrypoint_rel not in rel_paths:
            raise SealError(
                f"entrypoint_rel {self.entrypoint_rel!r} not in declared blobs ({sorted(rel_paths)})"
            )
        self.result.validate()
        if not isinstance(self.run_args, list):
            raise SealError("run_args must be a list")

    # --- serialisation -----------------------------------------------------
    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        # Preserve byte/schema compatibility for existing Windows manifests.
        # POSIX manifests carry the explicit discriminator.
        if d.get("host", {}).get("platform") == "windows":
            d["host"].pop("platform", None)
        d["status"] = self.status.value
        return d

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, d: dict) -> "SealedManifest":
        host_d   = d.get("host") or {}
        result_d = d.get("result") or {}
        return cls(
            job_id=d.get("job_id", ""),
            version=d.get("version", "2.0"),
            task_type=d.get("task_type", "generic"),
            metadata=dict(d.get("metadata") or {}),
            host=HostSpec(**host_d),
            blobs=[SealedBlob(**b) for b in d.get("blobs", [])],
            entrypoint_rel=d.get("entrypoint_rel", ""),
            run_args=list(d.get("run_args") or []),
            env=dict(d.get("env") or {}),
            extra_pythonpath=list(d.get("extra_pythonpath") or []),
            result=ResultSpec(**result_d),
            archive_format=d.get("archive_format", "tar.gz"),
            seal_sha256=d.get("seal_sha256"),
            seal_path_local=d.get("seal_path_local"),
            seal_size_bytes=d.get("seal_size_bytes"),
            status=SealStatus(d.get("status", "pending")),
            last_error=d.get("last_error"),
            created_at=d.get("created_at", ""),
        )

    @classmethod
    def from_json(cls, s: str) -> "SealedManifest":
        return cls.from_dict(json.loads(s))

    @classmethod
    def from_path(cls, p: pathlib.Path | str) -> "SealedManifest":
        return cls.from_json(pathlib.Path(p).read_text())

    def canonical_hash(self) -> str:
        """Hash of the manifest excluding mutable runtime fields. Used to
        detect drift between submitter-side and remote-side copies."""
        d = self.to_dict()
        for k in ("seal_sha256", "seal_path_local", "seal_size_bytes",
                   "status", "last_error"):
            d.pop(k, None)
        s = json.dumps(d, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_of_file(path: pathlib.Path | str, *, chunk: int = 1 << 20) -> str:
    """Stream-hash a regular file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            buf = f.read(chunk)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def is_skip_path(rel_posix: str) -> bool:
    """Files we never bundle and never include in a dir hash.

    Excludes Python compilation byproducts (which can be created /
    modified between the hash-compute and the tar-add windows) and
    other ephemera that don't affect program correctness."""
    if rel_posix.endswith(".pyc") or rel_posix.endswith(".pyo"):
        return True
    parts = rel_posix.split("/")
    if "__pycache__" in parts:
        return True
    if ".pytest_cache" in parts:
        return True
    if ".rsync-partial" in parts:
        return True
    if any(p.startswith(".DS_Store") for p in parts):
        return True
    return False


def sha256_of_dir(path: pathlib.Path | str) -> str:
    """Hash of a directory's content: sha256 over sorted ``<rel>\t<size>\t<sha>\n`` lines.

    Files matched by ``is_skip_path`` are excluded from the hash and
    must also be excluded by the tar-add step (seal.py uses the same
    helper so the two stay in sync).
    """
    p = pathlib.Path(path)
    if not p.is_dir():
        raise SealError(f"sha256_of_dir: {p} not a dir")
    # Collect rel paths first, then sort by rel-path string. pathlib.Path
    # __lt__ does case-normalisation on Windows, which breaks cross-platform
    # determinism — sort by the (lowercase-of-)POSIX rel path instead.
    rels = []
    for f in p.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(p).as_posix()
        if is_skip_path(rel):
            continue
        rels.append((rel, f.stat().st_size, sha256_of_file(f)))
    rels.sort(key=lambda t: t[0])
    entries = [f"{rel}\t{sz}\t{h}" for (rel, sz, h) in rels]
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
