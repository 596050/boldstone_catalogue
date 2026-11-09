"""v2 driver: cache_stage.

Ships an EXISTING EMD cache .mat to a remote host without rebuilding it.
For instruments whose cache is already built locally and only needs to
be available on the remote workdir so the downstream replay job's
``remote_refs`` rsync can pick it up.

Why: rebuilding caches for amazon/microsoft/es (etc.) is expensive and
wasteful when we already have a known-good .mat on disk. The
``cache_stage`` expects the .mat to be pre-staged on the remote host
outside the sealed tarball, and this driver places it under
``outputs/cache/<INST_ID>_live_emd_cache.mat`` — the exact path the
``replay`` template's ``remote_refs.remote_path`` expects.

Usage (run inside the seal workdir via generic.py):
  cache_stage.py --src-cache <remote-prestaged-path> --instrument-id <id> --out-dir <dir>

Invariants:
  - The source path must already exist on the remote host.
  - The destination filename is FIXED: ``<INST_ID>_live_emd_cache.mat``.
    The replay template's remote_path hard-codes this name; if we ever
    parameterise it, update both sides.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sys
import time


def _sha256_of(path: pathlib.Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(
        description="Stage an existing EMD cache .mat into outputs/cache/"
    )
    p.add_argument("--src-cache", required=True,
                   help="Path to the bundled .mat (relative to seal workdir)")
    p.add_argument("--instrument-id", required=True,
                   help="Instrument id used in the destination filename")
    p.add_argument("--out-dir", default="outputs/cache",
                   help="Destination dir (relative to workdir; default outputs/cache)")
    args = p.parse_args()

    workdir = pathlib.Path.cwd()
    src = pathlib.Path(args.src_cache)
    if not src.is_absolute():
        src = (workdir / src).resolve()
    if not src.is_file():
        print(f"[cache_stage] FATAL: src cache not found: {src}", flush=True)
        return 2

    out_dir = pathlib.Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = (workdir / out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    dst_name = f"{args.instrument_id}_live_emd_cache.mat"
    dst = out_dir / dst_name

    t0 = time.monotonic()
    # Use copy2 so mtime is preserved (helps if downstream replay logs
    # the cache mtime for provenance).
    shutil.copy2(src, dst)
    copy_elapsed = time.monotonic() - t0

    # Sha-verify the round-trip so a silent corruption fails loudly.
    src_sha = _sha256_of(src)
    dst_sha = _sha256_of(dst)
    if src_sha != dst_sha:
        print(f"[cache_stage] FATAL: sha mismatch after copy: "
              f"src={src_sha[:12]} dst={dst_sha[:12]}", flush=True)
        return 3

    # Drop a tiny report.json alongside outputs so v2's result-pull
    # includes it (the standard ResultSpec catches outputs/** + report.json).
    report = {
        "rc": 0,
        "instrument_id": args.instrument_id,
        "src": str(src),
        "dst": str(dst),
        "size_bytes": dst.stat().st_size,
        "sha256": src_sha,
        "copy_elapsed_s": round(copy_elapsed, 2),
        "copy_elapsed_clock": "time.monotonic",
    }
    report_path = workdir / "outputs" / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))
    # Also write at workdir root, since the v2 ResultSpec includes
    # both "outputs/**" and "report.json" at the top level.
    (workdir / "report.json").write_text(json.dumps(report, indent=2))

    print(f"[cache_stage] staged {args.instrument_id} "
          f"{report['size_bytes']/1e6:.1f}MB in {copy_elapsed:.1f}s → {dst}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
