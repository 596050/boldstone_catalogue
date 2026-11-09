"""v2 driver: random_windows_pipeline.

Bundled INSIDE a v2 seal. Translates the seal's runtime environment so
``c_emd.python.random_windows_pipeline.main()`` can run as if it had
been launched by the v1 ``fleet run`` ssh-and-nohup path.

Layout inside the seal workdir at runtime:
  blobs/code/random_windows.py    ← this file (entrypoint)
  blobs/code/trading_common/      ← bundled package (sealed copy)
  blobs/code/c_emd/               ← bundled c_emd python package
  blobs/code/uoa_emd_lib/         ← bundled uoa_emd_lib package
  outputs/                        ← pipeline writes here; v2 collects after

libemd.dll IS shipped as a code blob (~160 KB) in every v2 seal at
``blobs/native/libemd.dll`` (stateless-host architecture, 2026-06-07).
We prefer the seal-bundled copy; the host-repo fallback exists only for
backward compat with hosts that still have a pre-built libemd checkout.

External data (ig_trading caches at FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT)
is NOT shipped either — caches live on the remote host's external drive
and are referenced via the env var inherited from the runner.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import runpy
import shlex
import sys
import time
import traceback


_HOST_REPO_CANDIDATES = [
    pathlib.Path(r"C:\Users\Kenneth\Downloads\fleet-offload"),
    pathlib.Path(r"C:\Users\kenne\Downloads\fleet-offload"),
    pathlib.Path(r"C:\Users\Kenneth\Downloads\fleet-offload"),
]


def main() -> int:
    p = argparse.ArgumentParser(
        description="v2 driver wrapping c_emd.python.random_windows_pipeline",
    )
    p.add_argument("--cohort", required=True,
                   help="instruments-list shortcut (e.g. new10, bonds_dxy_nk, eminis)")
    p.add_argument("--out-dir", required=True,
                   help="outputs/ dir inside the seal workdir; pipeline writes here")
    p.add_argument("--pipeline-args", default="",
                   help="extra arg-string appended to random_windows_pipeline")
    p.add_argument("--host-results-root", default=None,
                   help="value to set as FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT (where the host "
                        "stores ig_trading caches). If unset, inherit any existing value.")
    args = p.parse_args()

    workdir = pathlib.Path.cwd()
    bundled_code = workdir / "blobs" / "code"
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Routes the pipeline's --out-root + --summary + --inventory into
    # outputs/, so v2 picks them up in the result archive.
    out_root = out_dir.resolve()
    summary_path = out_root / "summary.json"
    inventory_path = out_root / "picks_inventory.json"

    # Bundled code goes on sys.path FIRST so the seal version of
    # trading_common / c_emd / uoa_emd_lib wins over anything on the host.
    for p_ in (bundled_code / "uoa_emd_lib", bundled_code):
        s = str(p_)
        if s not in sys.path:
            sys.path.insert(0, s)

    # libemd.dll: prefer seal-bundled copy; fall back to host repo.
    seal_libemd_dir = bundled_code.parent / "native"
    libemd_dir: pathlib.Path | None = None
    if (seal_libemd_dir / "libemd.dll").is_file():
        libemd_dir = seal_libemd_dir
        print(f"[driver_v2_rw] libemd from SEAL: {seal_libemd_dir}", flush=True)
    else:
        for cand in _HOST_REPO_CANDIDATES:
            host_libemd_dir = cand / "c_emd" / "build"
            if (host_libemd_dir / "libemd.dll").is_file():
                libemd_dir = host_libemd_dir
                print(f"[driver_v2_rw] libemd from HOST: {host_libemd_dir}", flush=True)
                break

    # MSYS64 UCRT64 runtime: libemd's transitive deps (libgcc/libstdc++/
    # libwinpthread/libgfortran/libgomp/libhdf5) live here.
    msys64_ucrt = None
    for cand in (r"C:\msys64\ucrt64\bin",
                 r"C:\Users\Kenneth\msys64\ucrt64\bin",
                 r"C:\Users\kenne\msys64\ucrt64\bin"):
        if pathlib.Path(cand).is_dir():
            msys64_ucrt = cand
            break

    additions = []
    if libemd_dir is not None:
        additions.append(str(libemd_dir))
    if msys64_ucrt is not None:
        additions.append(msys64_ucrt)
    if additions:
        os.environ["PATH"] = os.pathsep.join(additions) + os.pathsep + os.environ.get("PATH", "")
        print(f"[driver_v2_rw] PATH prepended: {additions}", flush=True)

    # Append host repo to sys.path so any *unbundled* c_emd sub-modules
    # (e.g. tests) resolve from the host installation (backward compat).
    host_repo = None
    for cand in _HOST_REPO_CANDIDATES:
        if cand.is_dir():
            sys.path.append(str(cand))
            host_repo = cand
            break

    if libemd_dir is None:
        print("[driver_v2_rw] WARN: libemd.dll not found in seal or host; "
              "ctypes calls may fail", flush=True)
    if msys64_ucrt is None:
        print("[driver_v2_rw] WARN: msys64\\ucrt64\\bin not found; "
              "libemd's runtime deps may fail to load", flush=True)

    # FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT: random_windows_pipeline reads the
    # ig_trading caches from this root. Default to the host repo's results
    # tree (matches what v1 cmd_run sets); operator can override with the
    # --host-results-root flag.
    if args.host_results_root:
        os.environ["FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT"] = args.host_results_root
        print(f"[driver_v2_rw] FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT="
              f"{args.host_results_root}", flush=True)
    elif "FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT" not in os.environ and host_repo is not None:
        os.environ["FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT"] = str(host_repo / "c_emd" / "results")
        print(f"[driver_v2_rw] defaulted FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT="
              f"{os.environ['FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT']}", flush=True)

    try:
        extra = shlex.split(args.pipeline_args) if args.pipeline_args else []
    except ValueError as exc:
        print(f"[driver_v2_rw] FATAL: could not parse --pipeline-args: {exc}", flush=True)
        return 2

    sys.argv = [
        "random_windows_pipeline.py",
        "--instruments-list", args.cohort,
        "--out-root", str(out_root),
        "--summary", str(summary_path),
        "--inventory", str(inventory_path),
        *extra,
    ]
    print(f"[driver_v2_rw] cohort={args.cohort} out_root={out_root}", flush=True)
    print(f"[driver_v2_rw] invoking random_windows_pipeline …", flush=True)

    t0 = time.monotonic()
    try:
        runpy.run_module(
            "c_emd.python.random_windows_pipeline",
            run_name="__main__",
        )
        rc = 0
    except SystemExit as se:
        rc = se.code if isinstance(se.code, int) else (1 if se.code else 0)
    except Exception as e:
        rc = 3
        print(f"[driver_v2_rw] pipeline raised {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
    elapsed = time.monotonic() - t0

    # Pull lightweight signals out of the produced summary so the v2
    # report.json is informative without re-reading the whole tree.
    report = {
        "rc": rc,
        "cohort": args.cohort,
        "elapsed_s": round(elapsed, 1),
        "elapsed_clock": "time.monotonic",
        "out_root": str(out_root),
        "summary_path": str(summary_path),
        "summary_exists": summary_path.exists(),
        "inventory_exists": inventory_path.exists(),
    }
    if summary_path.exists():
        try:
            content = json.loads(summary_path.read_text())
            if isinstance(content, dict):
                # Whatever the pipeline produces — windows/instrument count etc.
                # Don't hardcode keys; just promote a few common ones if present.
                for k in ("instruments", "windows_total", "batches", "ok"):
                    if k in content:
                        report[k] = content[k]
        except Exception as exc:
            report["summary_parse_err"] = str(exc)
    (out_root / "report.json").write_text(json.dumps(report, indent=2))
    print(f"[driver_v2_rw] done rc={rc} elapsed={elapsed:.1f}s", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
