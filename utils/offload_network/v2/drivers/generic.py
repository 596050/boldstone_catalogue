"""Generic v2 driver — runs an arbitrary python module (or script) inside
a sealed bundle.

The previous driver pattern was: one ``v2/drivers/<workflow>.py`` per
distinct entry-point. That doesn't scale — the only thing those drivers
differed in was the module name + the arg-translation. Everything else
(sys.path setup, libemd discovery, host-repo append, output routing) was
identical boilerplate.

This generic driver does the boilerplate once. Each workflow becomes a
manifest builder in ``v2/fleet_adapter.py`` that hands the module name +
arg list to this driver via run_args. New workflows = one new function
in fleet_adapter.py, no new driver file.

Layout inside the seal workdir at runtime (unchanged from per-workflow
drivers):
  blobs/code/generic.py        ← this file (entrypoint)
  blobs/code/trading_common/   ← bundled package (sealed copy)
  blobs/code/c_emd/            ← bundled c_emd package
  blobs/code/uoa_emd_lib/      ← bundled uoa_emd_lib
  outputs/                     ← workflow writes here; v2 collects after

The runner sets cwd to the seal workdir before invoking this driver, so
relative paths like ``outputs/`` resolve correctly.

Args this driver accepts:
  --module M              Python module to run (e.g. trading_common.strategy_testing.emd_cache_replay)
  --script S              OR a script path (resolved against blobs/code/)
  --pass-arg A            Arg to forward to the module/script (repeatable)
  --pass-args-shlex S     OR a single shlex-quoted string of args (mutually
                          exclusive with --pass-arg; convenient for the
                          fleet-adapter side which has the args as one string)
  --host-results-root R   Sets $FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT for
                          workflows that read ig_trading caches from there
  --out-dir D             Optional output dir to mkdir before running
                          (default: outputs/ in the seal workdir)
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


def _setup_sys_path(bundled_code: pathlib.Path) -> pathlib.Path | None:
    """Put bundled code on sys.path first, then resolve libemd.dll +
    msys64 UCRT64 runtime onto PATH.

    libemd resolution (added 2026-06-07 — stateless-host architecture):
      1. Prefer seal-bundled ``blobs/native/libemd.dll`` if present
         (every v2 seal now ships its own; new hosts need NOTHING
         pre-installed besides SSH+rsync+python+msys64).
      2. Fall back to host-installed checkout
         (``$HOST_REPO/c_emd/build/libemd.dll``) for backward compat.

    msys64 UCRT64 runtime DLLs (libgcc/libstdc++/libwinpthread/libgfortran/
    libgomp/libhdf5) are NOT bundled in the seal — they're large and
    standard. We add ``C:\\msys64\\ucrt64\\bin`` to PATH and rely on
    msys64 being present on the target (true on every cluster host
    today; the host_bootstrap kit installs it).
    """
    # Bundled wins: prepend uoa_emd_lib then the code root.
    for p in (bundled_code / "uoa_emd_lib", bundled_code):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)

    # 1. Find libemd: seal first, then host repo
    seal_libemd_dir = bundled_code.parent / "native"
    libemd_dir: pathlib.Path | None = None
    if (seal_libemd_dir / "libemd.dll").is_file():
        libemd_dir = seal_libemd_dir
        print(f"[driver_v2_generic] libemd from SEAL: {seal_libemd_dir}", flush=True)
    else:
        for cand in _HOST_REPO_CANDIDATES:
            host_libemd_dir = cand / "c_emd" / "build"
            if (host_libemd_dir / "libemd.dll").is_file():
                libemd_dir = host_libemd_dir
                print(f"[driver_v2_generic] libemd from HOST: {host_libemd_dir}", flush=True)
                break

    # 2. Locate msys64 UCRT64 (runtime for libemd's deps)
    msys64_ucrt = None
    for cand in (r"C:\msys64\ucrt64\bin",
                 r"C:\Users\Kenneth\msys64\ucrt64\bin",
                 r"C:\Users\kenne\msys64\ucrt64\bin"):
        if pathlib.Path(cand).is_dir():
            msys64_ucrt = cand
            break

    # 3. PATH prepend
    additions = []
    if libemd_dir is not None:
        additions.append(str(libemd_dir))
    if msys64_ucrt is not None:
        additions.append(msys64_ucrt)
    if additions:
        os.environ["PATH"] = os.pathsep.join(additions) + os.pathsep + os.environ.get("PATH", "")
        print(f"[driver_v2_generic] PATH prepended: {additions}", flush=True)

    # 4. Host repo on sys.path (for any non-bundled host code)
    host_repo = None
    for cand in _HOST_REPO_CANDIDATES:
        if cand.is_dir():
            sys.path.append(str(cand))  # APPEND so bundled code still wins
            host_repo = cand
            break

    if libemd_dir is None:
        print("[driver_v2_generic] WARN: libemd.dll not found in seal or host; "
              "ctypes calls may fail", flush=True)
    if msys64_ucrt is None:
        print("[driver_v2_generic] WARN: msys64\\ucrt64\\bin not found; "
              "libemd's runtime deps may fail to load", flush=True)
    return host_repo


def _resolve_pass_args(args: argparse.Namespace) -> list[str]:
    """Return the arg list to hand to the wrapped module/script."""
    if args.pass_arg and args.pass_args_shlex:
        raise SystemExit("[driver_v2_generic] --pass-arg and --pass-args-shlex "
                         "are mutually exclusive")
    if args.pass_args_shlex:
        return shlex.split(args.pass_args_shlex)
    return list(args.pass_arg or [])


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run an arbitrary python module/script inside a v2 sealed bundle",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--module", help="Python module to run with `python -m <module>` semantics")
    g.add_argument("--script", help="Python script path (relative to blobs/code/) to run")
    p.add_argument("--pass-arg", action="append", default=[],
                   help="Arg to forward to the wrapped module/script (repeatable)")
    p.add_argument("--pass-args-shlex", default="",
                   help="Alternative to --pass-arg: a single shlex-quoted arg string")
    p.add_argument("--host-results-root", default=None,
                   help="Sets $FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT on the remote")
    p.add_argument("--out-dir", default="outputs",
                   help="Output dir to create before running (default: outputs/)")
    args = p.parse_args()

    workdir = pathlib.Path.cwd()
    bundled_code = workdir / "blobs" / "code"
    out_dir = (workdir / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    host_repo = _setup_sys_path(bundled_code)

    # FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT — ig_trading workflows read caches
    # from this root. Default to the host repo's results tree (matches
    # v1 cmd_run); operator can override via --host-results-root.
    if args.host_results_root:
        os.environ["FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT"] = args.host_results_root
        print(f"[driver_v2_generic] FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT="
              f"{args.host_results_root}", flush=True)
    elif "FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT" not in os.environ and host_repo is not None:
        os.environ["FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT"] = str(host_repo / "c_emd" / "results")
        print(f"[driver_v2_generic] defaulted FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT="
              f"{os.environ['FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT']}", flush=True)

    try:
        pass_args = _resolve_pass_args(args)
    except SystemExit as exc:
        print(str(exc), flush=True)
        return 2

    # Build the argv the wrapped module/script will see.
    if args.module:
        sys.argv = [f"{args.module}.py", *pass_args]
        target_repr = f"module {args.module}"
    else:
        script_path = bundled_code / args.script
        if not script_path.is_file():
            print(f"[driver_v2_generic] FATAL: --script {script_path} not found",
                  flush=True)
            return 2
        sys.argv = [str(script_path), *pass_args]
        target_repr = f"script {script_path}"

    print(f"[driver_v2_generic] invoking {target_repr} with {len(pass_args)} arg(s)",
          flush=True)
    print(f"[driver_v2_generic] cwd={workdir} out_dir={out_dir}", flush=True)

    t0 = time.monotonic()
    try:
        if args.module:
            runpy.run_module(args.module, run_name="__main__")
        else:
            runpy.run_path(str(script_path), run_name="__main__")
        rc = 0
    except SystemExit as se:
        rc = se.code if isinstance(se.code, int) else (1 if se.code else 0)
    except Exception as e:
        rc = 3
        print(f"[driver_v2_generic] {target_repr} raised {type(e).__name__}: {e}",
              flush=True)
        traceback.print_exc()
    elapsed = time.monotonic() - t0

    # Always write a report.json so v2's result archive has a structured summary.
    report = {
        "rc": rc,
        "target": target_repr,
        "module": args.module,
        "script": args.script,
        "pass_args_count": len(pass_args),
        "elapsed_s": round(elapsed, 1),
        "elapsed_clock": "time.monotonic",
        "out_dir": str(out_dir),
        "host_results_root": os.environ.get("FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT"),
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))
    print(f"[driver_v2_generic] done rc={rc} elapsed={elapsed:.1f}s", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
