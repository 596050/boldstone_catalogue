"""Build, verify, and extract sealed bundle archives.

A sealed archive layout:
  manifest.json          ← canonical, with all blob shas filled in
  bootstrap.cmd          ← Windows entry script (generated)
  runner.py              ← v2 runner copied in at build time
  blobs/<rel_path>       ← each declared blob, placed at its rel_path

The manifest's seal_sha256 is the hash of the FINAL archive file.
build_seal stamps it on the in-memory manifest but the archive itself
is sealed (immutable) — re-hashing after that point would mismatch.

Compression choice:
  tar.zst — if `zstandard` module installed (best ratio / fast decode)
  tar.gz  — fallback (stdlib only)

Cache blobs (already-compressed .mat etc.) get tarred without secondary
compression: we set store-only for blobs flagged as `is_dir=False` with
size > 100 MB. The archive's outer compression still applies.
"""
from __future__ import annotations

import hashlib
import io
import json
import pathlib
import shutil
import tarfile
import tempfile
from typing import Optional

from .manifest import (
    SealError, SealedManifest, SealedBlob, sha256_of_file, sha256_of_dir,
    is_skip_path,
)


_BOOTSTRAP_CMD = r"""@echo off
REM Auto-generated bootstrap for sealed job {job_id}
REM
REM Output routing on Windows + DETACHED_PROCESS:
REM   - cmd.exe's own echo lines (start/end markers) go to bootstrap.log
REM     via cmd-level redirect on each line. This works under DETACHED.
REM   - Python's stdout/stderr can NOT be reliably redirected by cmd.exe
REM     under DETACHED — python sees stdout.isatty()=True and writes
REM     vanish even with `>` or block redirects. So the python runner
REM     opens run.log itself and dup2's onto fd 1/2 (see runner.py).
REM   - The two files are kept separate so there is no file-sharing
REM     conflict between cmd.exe's redirect handle and python's
REM     own append-open of the same file.
setlocal
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
set PYTHONUTF8=1
set SEAL_JOB_ID={job_id}
set SEAL_WORKDIR=%~dp0
cd /d "%SEAL_WORKDIR%"
echo [bootstrap] starting runner at %TIME% >> "%SEAL_WORKDIR%bootstrap.log" 2>&1
"{python}" -u "%SEAL_WORKDIR%runner.py" "%SEAL_WORKDIR%manifest.json"
set RUNNER_RC=%ERRORLEVEL%
echo [bootstrap] runner exited rc=%RUNNER_RC% at %TIME% >> "%SEAL_WORKDIR%bootstrap.log" 2>&1
exit /b %RUNNER_RC%
"""

_BOOTSTRAP_SH = r"""#!/bin/sh
# Auto-generated POSIX bootstrap for sealed job {job_id}
set -u
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1
export PYTHONUTF8=1
export SEAL_JOB_ID='{job_id}'
SEAL_WORKDIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export SEAL_WORKDIR
cd "$SEAL_WORKDIR" || exit 74
printf '[bootstrap] starting runner at %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> bootstrap.log
'{python}' -u "$SEAL_WORKDIR/runner.py" "$SEAL_WORKDIR/manifest.json"
RUNNER_RC=$?
printf '[bootstrap] runner exited rc=%s at %s\n' "$RUNNER_RC" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> bootstrap.log
exit "$RUNNER_RC"
"""


def _stamp_blob_hashes(manifest: SealedManifest) -> None:
    """Compute sha256 + size for every blob whose hash is unset."""
    for b in manifest.blobs:
        if b.sha256:
            continue
        p = pathlib.Path(b.local_src)
        if not p.exists():
            raise SealError(f"blob {b.name!r}: local_src {p} missing")
        if b.is_dir:
            if not p.is_dir():
                raise SealError(f"blob {b.name!r}: is_dir=True but {p} is not a dir")
            b.sha256 = sha256_of_dir(p)
            b.size_bytes = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        else:
            if not p.is_file():
                raise SealError(f"blob {b.name!r}: is_dir=False but {p} is not a file")
            b.sha256 = sha256_of_file(p)
            b.size_bytes = p.stat().st_size


def _arcname_for(manifest: SealedManifest, rel: str) -> str:
    """Path inside the tar — always relative, forward-slash."""
    return rel.replace("\\", "/").lstrip("/")


def _open_writer(out_path: pathlib.Path, archive_format: str):
    """Return (file-handle, tarfile-mode). Caller closes both."""
    if archive_format == "tar.zst":
        try:
            import zstandard as zstd  # type: ignore
        except ImportError as e:
            raise SealError(
                f"archive_format=tar.zst requires the `zstandard` package; "
                f"fall back to tar.gz. ImportError: {e}"
            )
        # zstd compresses the tar stream; we treat tar as plain mode "w|"
        # and wrap the writer manually.
        raw = out_path.open("wb")
        cctx = zstd.ZstdCompressor(level=6, threads=-1)
        compressor = cctx.stream_writer(raw)
        tar = tarfile.open(fileobj=compressor, mode="w|")
        return tar, [compressor, raw]
    elif archive_format == "tar.gz":
        tar = tarfile.open(str(out_path), mode="w:gz", compresslevel=6)
        return tar, [tar]
    else:
        raise SealError(f"unknown archive_format {archive_format!r}")


def _stage_dir_blobs(manifest: SealedManifest, staging_root: pathlib.Path) -> dict:
    """Snapshot every dir-blob to ``staging_root`` so hash and tar see the
    same point-in-time content.

    Returns a mapping {blob.name -> staging_path}. Single files are staged too:
    their source can change between separate hash and archive reads.

    Why this exists: trading_common (and other code-bundle dirs) may
    contain live-mutating state files written by other processes
    (research_validation/*.json registry, for example). If hash-compute
    and tar-pack each read the file at different times, the two diverge
    and the runner's verify-blobs step fails. Snapshotting freezes the
    view so the two stages agree.
    """
    import shutil
    staged = {}
    def _ignore(_dir, names):
        return [n for n in names if is_skip_path(n)]
    for b in manifest.blobs:
        src = pathlib.Path(b.local_src)
        if src.is_symlink() or (src.is_dir() and any(p.is_symlink() for p in src.rglob("*"))):
            raise SealError(f"blob {b.name!r}: symlink sources are not allowed")
        dst = staging_root / b.name
        if not b.is_dir:
            if not src.is_file():
                raise SealError(f"blob {b.name!r}: file {src} missing")
            shutil.copyfile(src, dst)
            staged[b.name] = dst
            continue
        if not src.is_dir():
            raise SealError(f"blob {b.name!r}: is_dir=True but {src} is not a dir")
        dst = staging_root / b.name
        # copy_function=shutil.copy preserves content; copy2 would copy
        # mtime which is unnecessary (we hash content, not metadata).
        shutil.copytree(
            str(src), str(dst),
            ignore=_ignore, dirs_exist_ok=False, copy_function=shutil.copy,
        )
        staged[b.name] = dst
    return staged


def build_seal(
    manifest: SealedManifest,
    *,
    out_dir: pathlib.Path | str,
    runner_py_src: Optional[pathlib.Path | str] = None,
) -> pathlib.Path:
    """Build the sealed archive for ``manifest`` and return its path.

    Side effects:
      - Stamps sha256 + size on every blob (if missing) by reading content.
      - Generates bootstrap.cmd and embeds it.
      - Embeds runner.py (defaults to the one shipped next to seal.py).
      - Embeds canonical manifest.json (with hashes filled in).
      - Updates ``manifest.seal_sha256`` / ``seal_path_local`` /
        ``seal_size_bytes`` / ``status = SEALED``.
    """
    import shutil, tempfile
    from .manifest import SealStatus  # local import to avoid cycle in __init__

    manifest.validate()

    # Snapshot dir blobs to a staging area so hash + tar read the same
    # frozen view. Caller's local_src is preserved in the manifest for
    # traceability; we transparently swap in the staging path while we
    # hash and pack, then restore the original after.
    staging_root = pathlib.Path(tempfile.mkdtemp(prefix="v2_stage_"))
    original_srcs: dict[str, str] = {}
    try:
        staged = _stage_dir_blobs(manifest, staging_root)
        for b in manifest.blobs:
            if b.name in staged:
                original_srcs[b.name] = b.local_src
                b.local_src = str(staged[b.name])
        _stamp_blob_hashes(manifest)
        return _build_seal_inner(manifest, out_dir, runner_py_src)
    finally:
        # Restore caller-supplied paths in the manifest object
        for b in manifest.blobs:
            if b.name in original_srcs:
                b.local_src = original_srcs[b.name]
        shutil.rmtree(staging_root, ignore_errors=True)


def _build_seal_inner(
    manifest: "SealedManifest",
    out_dir,
    runner_py_src,
) -> pathlib.Path:
    """The pre-staging tar-packaging core. Called from build_seal() once
    blob.local_src points at the staging snapshot.
    """
    from .manifest import SealStatus

    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = manifest.archive_format
    out_path = out_dir / f"{manifest.job_id}.{ext}"

    # Resolve runner.py source
    runner_src = (
        pathlib.Path(runner_py_src) if runner_py_src
        else pathlib.Path(__file__).parent / "runner.py"
    )
    if not runner_src.is_file():
        raise SealError(f"runner.py source not found at {runner_src}")

    # Build canonical manifest JSON (with hashes filled in)
    canonical = manifest.to_dict()
    canonical_bytes = json.dumps(canonical, indent=2, sort_keys=False, default=str).encode("utf-8")

    bootstrap_text = _BOOTSTRAP_CMD.format(
        job_id=manifest.job_id,
        python=manifest.host.python_executable or "python",
    )
    bootstrap_sh = _BOOTSTRAP_SH.format(
        job_id=manifest.job_id,
        python=(manifest.host.python_executable or "python3").replace("'", "'\"'\"'"),
    )

    tar, handles = _open_writer(out_path, ext)
    try:
        def _add_bytes(name: str, data: bytes) -> None:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))

        _add_bytes("manifest.json", canonical_bytes)
        _add_bytes("bootstrap.cmd", bootstrap_text.encode("utf-8"))
        info = tarfile.TarInfo(name="bootstrap.sh")
        data = bootstrap_sh.encode("utf-8")
        info.size = len(data)
        info.mode = 0o755
        tar.addfile(info, io.BytesIO(data))
        tar.add(str(runner_src), arcname="runner.py")

        for b in manifest.blobs:
            arc = "blobs/" + _arcname_for(manifest, b.rel_path)
            src = pathlib.Path(b.local_src)
            if b.is_dir:
                # Filter out __pycache__ etc. so the on-tape contents
                # match what sha256_of_dir hashed.
                src_root = src.resolve()

                def _filter(ti, _root=src_root):
                    # ti.name is the arcname; convert back to source-relative
                    # by stripping the leading "blobs/<rel_path>/" prefix.
                    prefix = "blobs/" + _arcname_for(manifest, b.rel_path).rstrip("/") + "/"
                    name = ti.name
                    if name.startswith(prefix):
                        rel = name[len(prefix):]
                    else:
                        rel = name
                    return None if is_skip_path(rel) else ti

                tar.add(str(src), arcname=arc, recursive=True, filter=_filter)
            else:
                tar.add(str(src), arcname=arc)
    finally:
        tar.close()
        for h in handles:
            try:
                h.close()
            except Exception:
                pass

    seal_sha = sha256_of_file(out_path)
    manifest.seal_sha256 = seal_sha
    manifest.seal_path_local = str(out_path)
    manifest.seal_size_bytes = out_path.stat().st_size
    manifest.status = SealStatus.SEALED
    return out_path


def verify_seal(seal_path: pathlib.Path | str, *, expected_sha256: Optional[str] = None) -> SealedManifest:
    """Read manifest.json from inside the seal and verify integrity.

    If ``expected_sha256`` is provided, it must match the seal file hash.
    Inside the seal, every blob's sha256 is verified against its archived
    bytes. Raises SealError on any mismatch.
    """
    seal_path = pathlib.Path(seal_path)
    if expected_sha256 is not None:
        actual = sha256_of_file(seal_path)
        if actual != expected_sha256:
            raise SealError(
                f"seal sha mismatch: expected {expected_sha256}, actual {actual}"
            )

    manifest = _read_manifest_from_seal(seal_path)
    manifest.validate()
    # Streaming extraction also validates EVERY member, including bootstrap files.
    with tempfile.TemporaryDirectory(prefix="seal-verify-") as temp:
        root = pathlib.Path(temp)
        with _open_reader(seal_path, manifest.archive_format) as tar:
            _safe_extract_tar(tar, root)
        for blob in manifest.blobs:
            path = root / "blobs" / blob.rel_path
            computed = sha256_of_dir(path) if blob.is_dir else sha256_of_file(path)
            if computed != blob.sha256:
                raise SealError(f"blob {blob.name!r}: sha mismatch")

    return manifest


def extract_seal(seal_path: pathlib.Path | str, out_dir: pathlib.Path | str) -> SealedManifest:
    """Extract a seal into ``out_dir``. Returns the manifest read from inside.

    Verification is NOT performed here — call verify_seal separately if
    integrity guarantees are required (verify_seal currently re-walks the
    archive, which extract_seal would do anyway; we keep them split so
    extract can be fast-path for trusted seals).
    """
    seal_path = pathlib.Path(seal_path)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = _read_manifest_from_seal(seal_path)
    with _open_reader(seal_path, manifest.archive_format) as tar:
        _safe_extract_tar(tar, out_dir)
    return manifest


# ---------- internals ------------------------------------------------------

def _open_reader(seal_path: pathlib.Path, archive_format: str):
    from .safe_archive import open_archive
    return open_archive(seal_path)


def _read_manifest_from_seal(seal_path: pathlib.Path) -> SealedManifest:
    """Pull just manifest.json out of the seal without full extraction."""
    # We have to sniff the format from the file extension since the
    # manifest tells us, but we need the manifest to know the format...
    # Sniff by extension.
    s = str(seal_path)
    if s.endswith(".tar.zst"):
        fmt = "tar.zst"
    elif s.endswith(".tar.gz") or s.endswith(".tgz"):
        fmt = "tar.gz"
    else:
        raise SealError(f"cannot infer archive format from path {seal_path}")
    with _open_reader(seal_path, fmt) as tar:
        for m in tar:
            if m.name == "manifest.json" and m.isfile():
                f = tar.extractfile(m)
                if f is None:
                    raise SealError("manifest.json present but not readable")
                return SealedManifest.from_json(f.read().decode("utf-8"))
    raise SealError(f"manifest.json not found in {seal_path}")


def _safe_extract_tar(tar: tarfile.TarFile, dest: pathlib.Path) -> None:
    from .safe_archive import extract_tar
    try:
        extract_tar(tar, dest)
    except (ValueError, OSError) as exc:
        raise SealError(str(exc)) from exc
