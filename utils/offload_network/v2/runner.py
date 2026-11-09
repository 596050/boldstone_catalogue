"""v2 sealed-bundle runner — runs INSIDE the extracted seal on the remote.

Lifecycle:
  1. Read manifest.json from cwd (the extracted seal root).
  2. Verify every blob's sha256 against the on-disk file (Phase-1 sealing
     guarantees the seal archive was hash-checked end-to-end before
     extraction, but a quick local re-hash catches disk corruption).
  3. Write status.json {phase: starting, ...}.
  4. Set up env: prepend extra_pythonpath, layer manifest.env over
     os.environ, switch cwd to the seal root.
  5. Exec the entrypoint via runpy.
  6. On exit, pack the result archive per ResultSpec.
  7. Write final status.json {phase: exited, exit_code, result_archive}.

Errors during steps 1-4 land in status.json as phase=failed with
exception info. Errors in the entrypoint itself are captured by the
runpy wrapper and surfaced as non-zero exit_code.

This file is COPIED INTO each seal at build time. Do NOT import from
v2.manifest here — the seal needs to be self-contained when running
on a remote that may not have the v2 package on PYTHONPATH.
"""
from __future__ import annotations

import fnmatch
import hashlib
import io
import json
import os
import pathlib
import runpy
import sys
import tarfile
import time
import traceback
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_of_file(path: pathlib.Path, *, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _is_skip(rel: str) -> bool:
    """Mirror of v2.manifest.is_skip_path so runner is self-contained."""
    if rel.endswith(".pyc") or rel.endswith(".pyo"):
        return True
    parts = rel.split("/")
    for p in ("__pycache__", ".pytest_cache", ".rsync-partial"):
        if p in parts:
            return True
    if any(p.startswith(".DS_Store") for p in parts):
        return True
    return False


def _sha256_of_dir(path: pathlib.Path) -> str:
    rels = []
    for f in path.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(path).as_posix()
        if _is_skip(rel):
            continue
        rels.append((rel, f.stat().st_size, _sha256_of_file(f)))
    # Sort by rel-path string (NOT Path object — pathlib does
    # case-normalisation on Windows which makes sorted(rglob) non-portable).
    rels.sort(key=lambda t: t[0])
    entries = [f"{rel}\t{sz}\t{h}" for (rel, sz, h) in rels]
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()


def _write_status(status_path: pathlib.Path, payload: dict) -> None:
    """Atomic write of status.json — use a temp + os.replace to avoid
    readers seeing a partial file."""
    tmp = status_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    os.replace(tmp, status_path)


def _verify_blobs(workdir: pathlib.Path, manifest: dict) -> None:
    """Re-hash each blob on disk against the manifest. Raises on mismatch."""
    for b in manifest.get("blobs", []):
        rel = b["rel_path"]
        p = workdir / "blobs" / rel
        if b.get("is_dir"):
            if not p.is_dir():
                raise RuntimeError(f"blob {b['name']!r}: dir {p} missing after extract")
            computed = _sha256_of_dir(p)
        else:
            if not p.is_file():
                raise RuntimeError(f"blob {b['name']!r}: file {p} missing after extract")
            computed = _sha256_of_file(p)
        expected = b["sha256"]
        if computed != expected:
            raise RuntimeError(
                f"blob {b['name']!r}: sha mismatch — manifest {expected} vs disk {computed}"
            )


def _matches_any(path: str, patterns: list[str]) -> bool:
    """fnmatch with ** support (collapsed: ** = .* across path separators)."""
    norm = path.replace("\\", "/")
    for pat in patterns:
        p = pat.replace("\\", "/")
        if "**" in p:
            # crude ** handling: split on **, all halves must appear in order
            parts = p.split("**")
            i = 0
            ok = True
            for part in parts:
                if not part:
                    continue
                j = norm.find(part, i)
                if j < 0:
                    ok = False
                    break
                i = j + len(part)
            if ok:
                return True
        elif fnmatch.fnmatch(norm, p):
            return True
        # Also match basename-only against the pattern (for "*.json" vs "subdir/x.json")
        elif fnmatch.fnmatch(os.path.basename(norm), p):
            return True
    return False


def _collect_result_files(workdir: pathlib.Path, result_spec: dict) -> list[pathlib.Path]:
    """Walk workdir and pick files matching include minus exclude.

    Result-spec patterns are interpreted relative to workdir.
    """
    include = result_spec.get("include_patterns", [])
    exclude = result_spec.get("exclude_patterns", [])
    picked: list[pathlib.Path] = []
    for root, dirs, files in os.walk(workdir):
        # Skip the input blobs/ tree
        rel_root = pathlib.Path(root).relative_to(workdir)
        if rel_root.parts and rel_root.parts[0] in ("blobs",):
            dirs[:] = []
            continue
        for fn in files:
            fp = pathlib.Path(root) / fn
            if fp.is_symlink() or not fp.is_file():
                raise RuntimeError(f"result contains a non-regular file: {fp}")
            rel = fp.relative_to(workdir).as_posix()
            if not _matches_any(rel, include):
                continue
            if _matches_any(rel, exclude):
                continue
            picked.append(fp)
    status = workdir / "status.json"
    if status.is_file() and status not in picked:
        picked.append(status)
    return picked


def _pack_result(
    workdir: pathlib.Path,
    result_spec: dict,
    job_id: str,
) -> tuple[pathlib.Path, dict]:
    """Tar the picked result files. Returns (archive_path, summary)."""
    files = _collect_result_files(workdir, result_spec)
    total_bytes = sum(f.stat().st_size for f in files)
    max_mb = int(result_spec.get("max_size_mb", 1024))
    if total_bytes > max_mb * (1 << 20):
        raise RuntimeError(
            f"result content {total_bytes / 1e6:.1f} MB exceeds max_size_mb={max_mb} MB"
        )

    fmt = result_spec.get("archive_format", "tar.gz")
    arc_path = workdir / f"{job_id}.result.{fmt}"
    if fmt == "tar.gz":
        tar = tarfile.open(str(arc_path), "w:gz", compresslevel=6)
    elif fmt == "tar.zst":
        try:
            import zstandard as zstd  # type: ignore
        except ImportError:
            # Remote may not have zstandard; fall back to gz transparently.
            fmt = "tar.gz"
            arc_path = workdir / f"{job_id}.result.tar.gz"
            tar = tarfile.open(str(arc_path), "w:gz", compresslevel=6)
        else:
            raw = open(arc_path, "wb")
            cctx = zstd.ZstdCompressor(level=6, threads=-1)
            compressor = cctx.stream_writer(raw)
            tar = tarfile.open(fileobj=compressor, mode="w|")
    else:
        raise RuntimeError(f"unknown archive_format {fmt!r}")

    try:
        for fp in files:
            arc = fp.relative_to(workdir).as_posix()
            tar.add(str(fp), arcname=arc)
    finally:
        tar.close()
        if fmt == "tar.zst":
            compressor.close()
            raw.close()

    summary = {
        "format": fmt,
        "n_files": len(files),
        "bytes": arc_path.stat().st_size,
        "content_bytes": total_bytes,
    }
    return arc_path, summary


def _redirect_stdio_to_runlog(workdir: pathlib.Path) -> None:
    """Reopen sys.stdout/stderr against a real file in workdir.

    Background: on Windows under DETACHED_PROCESS, the child python sees
    sys.stdout.isatty() == True even when cmd.exe redirects stdout. The
    "console" is fake — writes vanish. We bypass this by opening run.log
    ourselves at the python level (which works) and pointing sys.stdout
    / sys.stderr at it. All subsequent prints (from this runner AND from
    the driver entrypoint via runpy) land in run.log.

    Bootstrap.cmd appends its own marker lines to run.log via cmd-level
    redirect; we open in append mode here so we don't clobber those.
    """
    log_path = workdir / "run.log"
    try:
        f = open(log_path, "a", buffering=1, encoding="utf-8", errors="replace")
    except Exception:
        return  # best-effort — don't crash the runner if log can't open
    # Replace fd-1 / fd-2 wholesale so child processes inherit too.
    try:
        os.dup2(f.fileno(), 1)
        os.dup2(f.fileno(), 2)
    except Exception:
        pass
    # Replace sys.stdout/sys.stderr so Python's TextIOWrapper buffers don't
    # bypass the new fd.
    sys.stdout = f
    sys.stderr = f
    print(f"[runner] stdio redirected to {log_path} at {_now()}", flush=True)


def main(manifest_path: str) -> int:
    workdir = pathlib.Path(manifest_path).resolve().parent
    status_path = workdir / "status.json"
    started_at = _now()

    # FIRST thing — re-route stdio to run.log. Anything that errors before
    # this is invisible; everything after is captured.
    _redirect_stdio_to_runlog(workdir)

    # Phase 0: load manifest
    try:
        manifest = json.loads(pathlib.Path(manifest_path).read_text())
    except Exception as e:
        _write_status(status_path, {
            "phase": "failed", "stage": "load_manifest",
            "error": f"{type(e).__name__}: {e}",
            "started_at": started_at, "finished_at": _now(),
        })
        return 70

    job_id = manifest.get("job_id", "unknown")
    _write_status(status_path, {
        "phase": "starting", "job_id": job_id,
        "started_at": started_at, "manifest_loaded": True,
    })

    # Phase 1: verify blobs (catches partial extracts / disk corruption)
    try:
        _verify_blobs(workdir, manifest)
    except Exception as e:
        _write_status(status_path, {
            "phase": "failed", "stage": "verify_blobs",
            "error": f"{type(e).__name__}: {e}",
            "started_at": started_at, "finished_at": _now(),
        })
        return 71

    # Phase 2: set up env
    extra_pp = manifest.get("extra_pythonpath", []) or []
    pp_parts = [str((workdir / p).resolve()) for p in extra_pp]
    if pp_parts:
        os.environ["PYTHONPATH"] = os.pathsep.join(pp_parts + [os.environ.get("PYTHONPATH", "")]).rstrip(os.pathsep)
        sys.path[:0] = pp_parts
    for k, v in (manifest.get("env") or {}).items():
        os.environ[str(k)] = str(v)

    entry_rel = manifest["entrypoint_rel"]
    entry_disk = workdir / "blobs" / entry_rel
    entry_disk.resolve().relative_to(workdir / "blobs")
    if not entry_disk.is_file():
        _write_status(status_path, {
            "phase": "failed", "stage": "resolve_entrypoint",
            "error": f"entrypoint {entry_disk} not found",
            "started_at": started_at, "finished_at": _now(),
        })
        return 72

    # Phase 3: run
    run_args = list(manifest.get("run_args", []))
    os.chdir(workdir)
    sys.path.insert(0, str(entry_disk.parent))
    saved_argv = sys.argv[:]
    sys.argv = [str(entry_disk)] + run_args
    exit_code = 0
    run_started = _now()
    _write_status(status_path, {
        "phase": "running", "job_id": job_id,
        "started_at": started_at, "run_started_at": run_started,
        "entrypoint": str(entry_disk),
        "argv": sys.argv,
    })

    t0 = time.monotonic()
    try:
        runpy.run_path(str(entry_disk), run_name="__main__")
    except SystemExit as se:
        exit_code = int(se.code) if isinstance(se.code, int) else (1 if se.code else 0)
    except Exception as e:
        exit_code = 73
        # Surface the traceback into run.log via stdout (which the
        # bootstrap.cmd redirects to run.log).
        sys.stderr.write(f"[runner] entrypoint raised {type(e).__name__}: {e}\n")
        traceback.print_exc()
    finally:
        sys.argv = saved_argv
    elapsed = time.monotonic() - t0
    run_finished = _now()
    # This authoritative execution record is inside the returned archive. The
    # outer status adds archive identity only after compression has finished.
    _write_status(status_path, {
        "phase": "exited", "job_id": job_id, "exit_code": exit_code,
        "started_at": started_at, "run_started_at": run_started,
        "run_finished_at": run_finished, "finished_at": _now(),
        "elapsed_s": round(elapsed, 1),
        "elapsed_clock": "time.monotonic",
    })
    sys.stdout.flush()
    sys.stderr.flush()

    # Phase 4: pack result
    result_summary: dict = {}
    result_archive: str = ""
    pack_error: str = ""
    try:
        arc_path, result_summary = _pack_result(workdir, manifest["result"], job_id)
        result_archive = str(arc_path)
    except Exception as e:
        pack_error = f"{type(e).__name__}: {e}"
        sys.stderr.write(f"[runner] result pack failed: {pack_error}\n")
        traceback.print_exc()

    # Phase 5: final status
    final = {
        "phase": "exited" if not pack_error else "exited_pack_failed",
        "job_id": job_id,
        "exit_code": exit_code,
        "elapsed_s": round(elapsed, 1),
        "elapsed_clock": "time.monotonic",
        "started_at": started_at,
        "run_started_at": run_started,
        "run_finished_at": run_finished,
        "finished_at": _now(),
        "result_archive": result_archive,
        "result_summary": result_summary,
    }
    if pack_error:
        final["pack_error"] = pack_error
    else:
        final["result_sha256"] = _sha256_of_file(arc_path)
    _write_status(status_path, final)
    return exit_code or (74 if pack_error else 0)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: runner.py <manifest_path>", file=sys.stderr)
        sys.exit(64)
    sys.exit(main(sys.argv[1]))
