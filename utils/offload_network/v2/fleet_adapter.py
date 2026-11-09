"""Bridge between fleet.py and the v2 sealed-bundle transport.

The legacy ``fleet run --cohort X --host H`` command in fleet.py builds a
PowerShell-encoded ssh wrapper and nohup-spawns it (v1 transport). This
module exposes ``submit_random_windows_via_v2`` — a drop-in for that
call site that instead:

  1. Builds a v2 manifest declaring trading_common + c_emd + uoa_emd_lib
     as code blobs and ``v2/drivers/random_windows.py`` as the entrypoint.
  2. Allocates a job_id from the shared fleet state.json (same registry
     v1 uses, so ``fleet jobs`` and ``fleet collect`` keep working).
  3. Spawns a detached Python child that runs ``v2.submit.submit_one``
     in the background. Returns immediately to the operator. The child
     writes status updates to ~/.fleet/logs/run_<job_id>_<host>_<cohort>.log
     and updates state.json on completion.

Why a detached child rather than synchronous: v2.submit.submit_one blocks
until the remote job finishes (potentially HOURS for a 40-window cohort).
The v1 cmd_run nohup-spawns its wrapper so the operator's terminal
returns immediately; we preserve that contract.
"""
from __future__ import annotations

import json
import os
import pathlib
import shlex
import subprocess
import sys
import textwrap
from datetime import datetime
from typing import Optional

from .defaults import remote_workdir_default
from fleet.paths import fleet_dir


_HERE = pathlib.Path(__file__).resolve().parent       # utils/offload_network/v2/
_ORCH_ROOT = _HERE.parent                              # utils/offload_network/
_REPO_ROOT = _ORCH_ROOT.parent.parent                  # fleet-offload/


def _bundle_state_for_fleet() -> tuple[pathlib.Path, pathlib.Path]:
    """Return (STATE_DIR, LOG_DIR) matching fleet.py / v1.

    Imports lazily so this module is loadable without the fleet/ package
    being on sys.path.
    """
    state_dir = fleet_dir()
    log_dir = state_dir / "logs"
    state_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    return state_dir, log_dir


def _is_bootstrapped_host(cfg: dict) -> bool:
    """Whether a host has the minimum runtime prerequisites to run v2 jobs.

    Modern hosts are tagged with ``has_msys64``; legacy configs still use
    ``has_libemd`` as the bootstrap signal. Prefer the new flag when present.
    """
    if cfg.get("type") == "local":
        return False
    if "has_msys64" in cfg:
        return bool(cfg["has_msys64"])
    return bool(cfg.get("has_libemd"))


def _build_random_windows_manifest(
    *,
    job_id: int,
    cohort: str,
    host_alias: str,
    remote_workdir: str,
    rsync_path: Optional[str],
    pipeline_args: str,
    host_repo: str,
    host_results_root: Optional[str],
    bundle_out_dir: pathlib.Path,
) -> "SealedManifest":  # type: ignore[name-defined]
    """Construct the v2 SealedManifest for a random_windows_pipeline run."""
    # Lazy import — v2.manifest pulls in dataclasses + walks the v2 module;
    # keep the cost out of fleet.py's import path for non-v2 users.
    from v2.manifest import (
        SealedManifest, SealedBlob, HostSpec, ResultSpec,
    )

    driver_src = str(_HERE / "drivers" / "random_windows.py")
    blobs = [
        SealedBlob(
            name="driver",
            local_src=driver_src,
            rel_path="code/random_windows.py",
            is_dir=False,
        ),
        SealedBlob(
            name="trading_common",
            local_src=str(_REPO_ROOT / "trading_common"),
            rel_path="code/trading_common",
            is_dir=True,
        ),
        # c_emd is split into root __init__.py + python/ subdir rather than
        # bundling the whole c_emd/ tree — c_emd/results/ alone is ~15 GB of
        # research outputs that don't need to ship. Same rationale as
        # _standard_code_blobs() below.
        SealedBlob(
            name="c_emd_root_init",
            local_src=str(_REPO_ROOT / "c_emd" / "__init__.py"),
            rel_path="code/c_emd/__init__.py",
            is_dir=False,
        ),
        SealedBlob(
            name="c_emd_python",
            local_src=str(_REPO_ROOT / "c_emd" / "python"),
            rel_path="code/c_emd/python",
            is_dir=True,
        ),
        SealedBlob(
            name="uoa_emd_lib",
            local_src=str(_REPO_ROOT / "Oil_UOA-EMD" / "tests" / "python"),
            rel_path="code/uoa_emd_lib",
            is_dir=True,
        ),
        SealedBlob(
            name="uoa_emd_scripts",
            local_src=str(_REPO_ROOT / "Oil_UOA-EMD" / "tests" / "python"),
            rel_path="code/Oil_UOA-EMD/tests/python",
            is_dir=True,
        ),
    ]

    # Build run_args for the driver. The driver routes --out-root /
    # --summary / --inventory into outputs/ inside the seal workdir;
    # the operator's pipeline-args (eg. "--windows-per-instrument 8")
    # ride along as a single quoted string.
    run_args = [
        "--cohort", cohort,
        "--out-dir", "outputs",
    ]
    if pipeline_args:
        run_args.extend(["--pipeline-args", pipeline_args])
    if host_results_root:
        run_args.extend(["--host-results-root", host_results_root])

    job_id_str = f"v2-rw-{job_id}-{cohort}-{host_alias}"
    # Sanitise job_id for Windows path (no commas, etc.)
    job_id_str = job_id_str.replace(",", "_").replace(" ", "_")

    local_pulled = bundle_out_dir / "pulled" / job_id_str
    manifest = SealedManifest(
        job_id=job_id_str,
        host=HostSpec(
            ssh_alias=host_alias,
            remote_workdir=remote_workdir,
            user=None,
            rsync_path=rsync_path,
            python_executable="python",
        ),
        blobs=blobs,
        entrypoint_rel="code/random_windows.py",
        run_args=run_args,
        env={"PYTHONIOENCODING": "utf-8"},
        result=ResultSpec(
            local_dir=str(local_pulled),
            include_patterns=[
                "outputs/**",
                "report.json",
                "status.json",
                "run.log",
                "bootstrap.log",
            ],
            exclude_patterns=["*.tmp", ".rsync-partial/"],
            archive_format="tar.gz",
            max_size_mb=2048,
        ),
        archive_format="tar.gz",
        metadata={
            "task_type": "random_windows_pipeline_v2",
            "cohort": cohort,
            "host_repo": host_repo,
            "fleet_job_id": job_id,
            "via": "v2",
        },
    )
    return manifest


def submit_random_windows_via_v2(args, hosts) -> int:
    """Drop-in v2 replacement for the random-windows branch of v1 cmd_run.

    Builds the manifest, registers the job in state.json under status
    "running", and nohup-spawns a detached Python child that runs the
    full v2 lifecycle (build → push → run → pull). Returns immediately
    with rc=0 once the spawn succeeds.

    Mirrors v1's args contract: ``args.cohort``, ``args.host``,
    ``args.out_subdir`` (informational only — v2 routes outputs through
    the seal), ``args.into``, ``args.pipeline_args``.
    """
    # Lazy imports so a non-v2 fleet run pays no v2 cost.
    sys.path.insert(0, str(_ORCH_ROOT))  # so 'v2.*' resolves
    # Pull the same load_state/save_state fleet.py uses (the legacy ones,
    # via importlib — see tests/test_parallelism for why ``import fleet``
    # is the package and not the script).
    from fleet import load_state, save_state, external_base  # v2 + v1 both use these

    state_dir, log_dir = _bundle_state_for_fleet()

    cohort = args.cohort
    host = args.host
    if host is None:
        # Inlined picker (was v1.fleet_v1_commands._pick_host before v1 was
        # archived 2026-06-07): pick the highest-capacity bootstrapped host,
        # preferring hosts with ``has_msys64`` (legacy fallback: ``has_libemd``),
        # falling back to the first alphabetically if all are equally busy.
        candidates = sorted(
            (h for h, cfg in hosts.items()
             if _is_bootstrapped_host(cfg)),
            key=lambda h: hosts[h].get("cores", 0), reverse=True,
        )
        host = candidates[0] if candidates else None
        if host is None:
            print(
                "ERROR: no eligible bootstrapped host available "
                "(need has_msys64=true or legacy has_libemd=true).",
                file=sys.stderr,
            )
            return 1
    if host not in hosts:
        print(f"ERROR: host {host!r} not in hosts.json", file=sys.stderr)
        return 1
    hcfg = hosts[host]
    if hcfg.get("type") == "local":
        print(f"ERROR: --via=v2 cannot target the local host ({host}); pick a remote.",
              file=sys.stderr)
        return 1

    pipeline_args = args.pipeline_args or (
        "--window-weeks 8 --windows-per-instrument 8 "
        "--batches 4 --workers-per-batch 8 --seed 42"
    )
    out_subdir = args.out_subdir or f"random_windows_{cohort}"
    into = getattr(args, "into", "live_data")

    state = load_state()
    job_id = state["next_job_id"]
    state["next_job_id"] = job_id + 1

    # Stage area for the seal + pulled result (gitignored by virtue of being
    # under ~/.fleet/v2_bundles/). Each job gets its own subdir so concurrent
    # submits don't fight over the same path.
    bundle_dir = state_dir / "v2_bundles" / f"job_{job_id}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    manifest = _build_random_windows_manifest(
        job_id=job_id,
        cohort=cohort,
        host_alias=hcfg["ssh_alias"],
        remote_workdir=remote_workdir_default(hcfg),
        rsync_path=hcfg.get("rsync_path"),
        pipeline_args=pipeline_args,
        host_repo=hcfg["repo"],
        host_results_root=f'{hcfg["repo"]}/{hcfg.get("results_root", "c_emd/results")}',
        bundle_out_dir=bundle_dir,
    )

    # Persist the manifest so the detached child can pick it up.
    manifest_path = bundle_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2, default=str))

    log_file = log_dir / f"run_{job_id}_{host}_{cohort}.log"
    pid_file = state_dir / f"job_{job_id}.pid"

    # Spawn the detached v2 submit child. It runs `python -m v2 submit
    # <manifest> --out <bundle_dir>` and tee's lifecycle events into log_file.
    # `python3 -u -m v2 submit ...` is exactly what an operator would type,
    # so the behaviour matches the smoke tests.
    cmd = [
        sys.executable, "-u", "-m", "v2", "submit",
        str(manifest_path),
        "--out", str(bundle_dir),
    ]
    # Inherit the operator's environment so any FAMOUS_MODEL_* overrides flow.
    env = os.environ.copy()
    # PYTHONPATH must include the orchestration root so `v2` and `fleet`
    # resolve in the detached child.
    pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(_ORCH_ROOT) + (os.pathsep + pp if pp else "")
    )

    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(log_file, "a", buffering=1)
    log_fh.write(
        f"\n[fleet adapter v2] cohort={cohort} host={host} job_id={job_id} "
        f"started={datetime.now().isoformat(timespec='seconds')}\n"
    )
    log_fh.flush()

    # Detach from this fleet.py invocation so the operator's shell returns.
    # POSIX double-fork via os.setpgrp is what v1 cmd_run does too.
    proc = subprocess.Popen(
        cmd,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=env,
        cwd=str(_ORCH_ROOT),
        preexec_fn=os.setpgrp,
        close_fds=True,
    )
    pid_file.write_text(str(proc.pid))

    job = {
        "id":              job_id,
        "cohort":          cohort,
        "host":            host,
        "remote_out":      f"{manifest.host.remote_workdir}/{manifest.job_id}/outputs",
        "external_dest":   str(external_base(into) / out_subdir) + "/",
        "into":            into,
        "wrapper_pid":     proc.pid,
        "log_file":        str(log_file),
        "started_at":      datetime.now().isoformat(timespec="seconds"),
        "status":          "running",
        "pipeline_args":   pipeline_args,
        "via":             "v2",
        "v2_manifest":     str(manifest_path),
        "v2_bundle_dir":   str(bundle_dir),
        "v2_job_id":       manifest.job_id,
    }
    state["jobs"].append(job)
    save_state(state)

    print(f"[fleet --via=v2] launched job {job_id}")
    print(f"  host       : {host} ({hcfg.get('cores')} cores)")
    print(f"  cohort     : {cohort}")
    print(f"  via        : v2 (sealed bundle, idempotent push/spawn)")
    print(f"  bundle dir : {bundle_dir}")
    print(f"  wrapper PID: {proc.pid}")
    print(f"  log        : {log_file}")
    print(f"  to follow  : tail -f {log_file}")
    print(f"  to collect : {sys.argv[0]} collect {job_id}")
    return 0


# ---------------------------------------------------------------------------
# Generic v2 path — uses v2/drivers/generic.py to run an arbitrary python
# module with passed-through args. New workflows go HERE, not in a new
# driver file. The per-workflow surface is just a small manifest builder.
# ---------------------------------------------------------------------------

_LIBEMD_WIN_DLL = _REPO_ROOT / "c_emd" / "build" / "windows" / "libemd.dll"
# Native v2 EMD cache-chunk exe (engine=exe). Bundled like libemd.dll so any
# seal can run `generate_cache_chunk.py --engine exe`. _default_exe_path() in
# generate_cache_chunk.py resolves it at code/c_emd/build/windows/.
_EMD_CACHE_GEN_EXE = _REPO_ROOT / "c_emd" / "build" / "windows" / "emd_cache_gen.exe"


def _standard_code_blobs():
    """Returns the standard list of code-blob SealedBlobs every v2 manifest
    bundles: trading_common + c_emd python module + uoa_emd_lib + the
    Windows libemd.dll binary.

    Why c_emd is split into 2 blobs (root __init__.py + python/ subdir):
    c_emd/results/ alone is ~15 GB of research outputs that don't need to
    ship — the python code only needs c_emd.__init__ + c_emd.python.* to
    satisfy `from c_emd.python.X import Y`. This shrinks the seal from
    ~15 GB to ~3 MB.

    Why libemd.dll ships in EVERY seal (added 2026-06-07):
    ctypes-loaded native binary, ~160 KB. Shipping it makes remote hosts
    "stateless" — they need only SSH + rsync + python + msys64 UCRT64
    runtime; NO fleet-offload checkout, NO setup_windows_host.ps1, NO
    libemd build step. New hosts onboard in minutes, not hours. The
    runtime DLLs (libgcc_s, libstdc++, libwinpthread, libgfortran,
    libgomp, libhdf5) are NOT bundled — we assume the target's
    C:\\msys64\\ucrt64\\bin is on PATH (set by the drivers).

    Lazy import so non-v2 callers don't pay the cost.
    """
    from v2.manifest import SealedBlob
    blobs = [
        SealedBlob(
            name="trading_common",
            local_src=str(_REPO_ROOT / "trading_common"),
            rel_path="code/trading_common",
            is_dir=True,
        ),
        SealedBlob(
            name="c_emd_root_init",
            local_src=str(_REPO_ROOT / "c_emd" / "__init__.py"),
            rel_path="code/c_emd/__init__.py",
            is_dir=False,
        ),
        SealedBlob(
            name="c_emd_python",
            local_src=str(_REPO_ROOT / "c_emd" / "python"),
            rel_path="code/c_emd/python",
            is_dir=True,
        ),
        SealedBlob(
            name="uoa_emd_lib",
            local_src=str(_REPO_ROOT / "Oil_UOA-EMD" / "tests" / "python"),
            rel_path="code/uoa_emd_lib",
            is_dir=True,
        ),
    ]
    if _LIBEMD_WIN_DLL.is_file():
        blobs.append(SealedBlob(
            name="libemd_dll",
            local_src=str(_LIBEMD_WIN_DLL),
            rel_path="native/libemd.dll",
            is_dir=False,
        ))
        blobs.append(SealedBlob(
            name="libemd_dll_c_emd_build",
            local_src=str(_LIBEMD_WIN_DLL),
            rel_path="code/c_emd/build/libemd.dll",
            is_dir=False,
        ))
    if _EMD_CACHE_GEN_EXE.is_file():
        blobs.append(SealedBlob(
            name="emd_cache_gen_exe",
            local_src=str(_EMD_CACHE_GEN_EXE),
            rel_path="code/c_emd/build/windows/emd_cache_gen.exe",
            is_dir=False,
        ))
    return blobs


def _build_generic_manifest(
    *,
    job_id: int,
    workflow: str,            # short tag for job_id / metadata (eg. "emd-cache-replay")
    module: str,              # python -m target (eg. "trading_common.strategy_testing.emd_cache_replay")
    pass_args: list[str],     # forwarded to the wrapped module
    host_alias: str,
    remote_workdir: str,
    rsync_path: Optional[str],
    host_repo: str,
    host_results_root: Optional[str],
    extra_blobs: list,
    bundle_out_dir: pathlib.Path,
    result_max_size_mb: int = 2048,
    host_platform: str = "windows",
    host_python: Optional[str] = None,
) -> "SealedManifest":  # type: ignore[name-defined]
    """Construct a v2 manifest that uses v2/drivers/generic.py to run an
    arbitrary python module.

    The fleet-adapter side controls every workflow-specific detail (module
    name, output paths inside outputs/, host-results-root env, extra blobs
    like caches) — the driver just executes what it's told.
    """
    from v2.manifest import (
        SealedManifest, SealedBlob, HostSpec, ResultSpec,
    )

    driver_src = str(_HERE / "drivers" / "generic.py")
    blobs = [
        SealedBlob(
            name="driver",
            local_src=driver_src,
            rel_path="code/generic.py",
            is_dir=False,
        ),
        *_standard_code_blobs(),
        *extra_blobs,
    ]

    run_args = ["--module", module]
    if pass_args:
        # Use --pass-args-shlex so a single arg can contain spaces / quoting.
        import shlex as _shlex
        run_args += ["--pass-args-shlex", _shlex.join(pass_args)]
    if host_results_root:
        run_args += ["--host-results-root", host_results_root]

    safe_workflow = workflow.replace("/", "-").replace(" ", "_")
    job_id_str = f"v2-{safe_workflow}-{job_id}-{host_alias}"

    return SealedManifest(
        job_id=job_id_str,
        host=HostSpec(
            ssh_alias=host_alias,
            remote_workdir=remote_workdir,
            platform=host_platform,
            user=None,
            rsync_path=rsync_path,
            python_executable=(
                host_python
                or ("python3" if host_platform in {"linux", "macos"} else "python")
            ),
        ),
        blobs=blobs,
        entrypoint_rel="code/generic.py",
        run_args=run_args,
        env={"PYTHONIOENCODING": "utf-8"},
        result=ResultSpec(
            local_dir=str(bundle_out_dir / "pulled" / job_id_str),
            include_patterns=[
                "outputs/**",
                "report.json",
                "status.json",
                "run.log",
                "bootstrap.log",
            ],
            exclude_patterns=["*.tmp", ".rsync-partial/"],
            archive_format="tar.gz",
            max_size_mb=result_max_size_mb,
        ),
        archive_format="tar.gz",
        metadata={
            "task_type": f"{workflow}_v2",
            "module": module,
            "host_repo": host_repo,
            "fleet_job_id": job_id,
            "via": "v2",
        },
    )


def _build_emd_cache_replay_manifest(
    *,
    job_id: int,
    instrument: str,
    cache_path: str,             # absolute local path to the .mat cache
    cadence_rows: int,
    extra_args: list[str],       # additional --foo bar args for emd_cache_replay
    host_alias: str,
    remote_workdir: str,
    rsync_path: Optional[str],
    host_repo: str,
    bundle_out_dir: pathlib.Path,
) -> "SealedManifest":  # type: ignore[name-defined]
    """Manifest for one ``trading_common.strategy_testing.emd_cache_replay``
    run (the workflow validated by the microsoft 30m smoke test).

    The .mat cache (often >2 GB) is shipped as an extra blob so the seal
    is self-contained — same pattern that produced byte-for-byte parity
    with v1 on cdec.
    """
    from v2.manifest import SealedBlob

    name = f"{instrument}_v2_{job_id}"
    cache_blob = SealedBlob(
        name="cache",
        local_src=cache_path,
        rel_path="data/cache.mat",
        is_dir=False,
    )

    # The driver passes our args verbatim to emd_cache_replay. We point
    # --emit-artifacts-dir and --out under outputs/ so v2 collects them.
    pass_args = [
        "--name", name,
        "--instrument", instrument,
        # cache.mat path INSIDE the seal — driver resolves relative to cwd
        # which is the workdir root, so "blobs/data/cache.mat" is correct.
        "--cache", "blobs/data/cache.mat",
        "--cadence-rows", str(cadence_rows),
        "--emit-artifacts-dir", f"outputs/artifacts/{name}",
        "--out", f"outputs/{name}.json",
        *extra_args,
    ]

    return _build_generic_manifest(
        job_id=job_id,
        workflow=f"emd-cache-replay-{instrument}",
        module="trading_common.strategy_testing.emd_cache_replay",
        pass_args=pass_args,
        host_alias=host_alias,
        remote_workdir=remote_workdir,
        rsync_path=rsync_path,
        host_repo=host_repo,
        host_results_root=None,    # emd_cache_replay reads the cache we shipped
        extra_blobs=[cache_blob],
        bundle_out_dir=bundle_out_dir,
        result_max_size_mb=4096,   # 30m replays produce ~890 artifact files
    )


def _build_ig_trading_manifest(
    *,
    job_id: int,
    submodule: str,              # e.g. "offload_replay_status" — appended to c_emd.python.ig_trading.
    extra_args: list[str],
    host_alias: str,
    remote_workdir: str,
    rsync_path: Optional[str],
    host_repo: str,
    bundle_out_dir: pathlib.Path,
) -> "SealedManifest":  # type: ignore[name-defined]
    """Manifest for any ``c_emd.python.ig_trading.<submodule>`` run.

    Covers offload_replay_status, replay_coverage_status,
    current_best_pipeline_inventory, holdout_compare_kurt_range_vs_btl,
    cache_replay_aggregate_evidence,
    pre_registered_feature_required_composite_audit, etc.

    These workflows read the host's existing cache tree (via
    FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT) and write status/inventory JSON.
    No extra blobs needed — code-only seal.
    """
    module = f"c_emd.python.ig_trading.{submodule}"
    host_results_root = f'{host_repo}/c_emd/results'
    return _build_generic_manifest(
        job_id=job_id,
        workflow=f"ig-trading-{submodule}",
        module=module,
        pass_args=extra_args,
        host_alias=host_alias,
        remote_workdir=remote_workdir,
        rsync_path=rsync_path,
        host_repo=host_repo,
        host_results_root=host_results_root,
        extra_blobs=[],
        bundle_out_dir=bundle_out_dir,
        result_max_size_mb=512,    # status/inventory outputs are small
    )


# ---------------------------------------------------------------------------
# Spawning + state.json registration — shared between all workflow
# submit_*_via_v2 entry points so they all integrate uniformly with
# fleet jobs / fleet collect / fleet kill.
# ---------------------------------------------------------------------------

def _spawn_v2_submit_and_register(
    *,
    manifest: "SealedManifest",
    cohort_label: str,
    host: str,
    hcfg: dict,
    into: str,
    pipeline_args: str,
    out_subdir: str,
    bundle_dir: pathlib.Path,
) -> int:
    """Common tail of every submit_*_via_v2 function: write the manifest,
    spawn the detached `python -m v2 submit ...` child, append the job to
    state.json, print operator summary, return 0.

    Pulled out as a helper so adding a new workflow doesn't duplicate the
    spawn+state-record logic (~80 lines per workflow otherwise).
    """
    sys.path.insert(0, str(_ORCH_ROOT))
    from fleet import load_state, save_state, external_base
    state_dir, log_dir = _bundle_state_for_fleet()

    state = load_state()
    job_id = state["next_job_id"]
    state["next_job_id"] = job_id + 1

    manifest_path = bundle_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), indent=2, default=str)
    )

    log_file = log_dir / f"run_{job_id}_{host}_{cohort_label}.log"
    pid_file = state_dir / f"job_{job_id}.pid"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-u", "-m", "v2", "submit",
        str(manifest_path),
        "--out", str(bundle_dir),
    ]
    env = os.environ.copy()
    pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(_ORCH_ROOT) + (os.pathsep + pp if pp else "")

    log_fh = open(log_file, "a", buffering=1)
    log_fh.write(
        f"\n[fleet adapter v2] cohort={cohort_label} host={host} "
        f"job_id={job_id} started={datetime.now().isoformat(timespec='seconds')}\n"
    )
    log_fh.flush()
    proc = subprocess.Popen(
        cmd,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=env,
        cwd=str(_ORCH_ROOT),
        preexec_fn=os.setpgrp,
        close_fds=True,
    )
    pid_file.write_text(str(proc.pid))

    job = {
        "id":              job_id,
        "cohort":          cohort_label,
        "host":            host,
        "remote_out":      f"{manifest.host.remote_workdir}/{manifest.job_id}/outputs",
        "external_dest":   str(external_base(into) / out_subdir) + "/",
        "into":            into,
        "wrapper_pid":     proc.pid,
        "log_file":        str(log_file),
        "started_at":      datetime.now().isoformat(timespec="seconds"),
        "status":          "running",
        "pipeline_args":   pipeline_args,
        "via":             "v2",
        "v2_manifest":     str(manifest_path),
        "v2_bundle_dir":   str(bundle_dir),
        "v2_job_id":       manifest.job_id,
    }
    state["jobs"].append(job)
    save_state(state)

    print(f"[fleet --via=v2] launched job {job_id}")
    print(f"  host       : {host} ({hcfg.get('cores')} cores)")
    print(f"  cohort     : {cohort_label}")
    print(f"  module     : {manifest.metadata.get('module', '?')}")
    print(f"  bundle dir : {bundle_dir}")
    print(f"  wrapper PID: {proc.pid}")
    print(f"  log        : {log_file}")
    print(f"  to follow  : tail -f {log_file}")
    print(f"  to collect : {sys.argv[0]} collect {job_id}")
    return 0


def submit_emd_cache_replay_via_v2(args, hosts) -> int:
    """v2 entry-point for `trading_common.strategy_testing.emd_cache_replay`.

    Expected ``args`` namespace:
      instrument, cache, cadence_rows (or cadence-rows), host, into,
      extra_args (list of strings, eg. ['--trade-cost=-0.000125']).
    """
    host = args.host
    if host is None or host not in hosts:
        print(f"ERROR: --host required (got {host!r})", file=sys.stderr)
        return 1
    hcfg = hosts[host]
    if hcfg.get("type") == "local":
        print(f"ERROR: --via=v2 cannot target the local host ({host}); pick a remote.",
              file=sys.stderr)
        return 1

    state_dir, _ = _bundle_state_for_fleet()
    # Read next_job_id without consuming it; the shared spawner will increment.
    sys.path.insert(0, str(_ORCH_ROOT))
    from fleet import load_state
    peeked_job_id = load_state()["next_job_id"]
    bundle_dir = state_dir / "v2_bundles" / f"job_{peeked_job_id}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    cadence_rows = getattr(args, "cadence_rows", None) or getattr(args, "cadence-rows", 30)
    manifest = _build_emd_cache_replay_manifest(
        job_id=peeked_job_id,
        instrument=args.instrument,
        cache_path=args.cache,
        cadence_rows=int(cadence_rows),
        extra_args=list(getattr(args, "extra_args", []) or []),
        host_alias=hcfg["ssh_alias"],
        remote_workdir=remote_workdir_default(hcfg),
        rsync_path=hcfg.get("rsync_path"),
        host_repo=hcfg["repo"],
        bundle_out_dir=bundle_dir,
    )

    return _spawn_v2_submit_and_register(
        manifest=manifest,
        cohort_label=f"emd_cache_replay_{args.instrument}",
        host=host,
        hcfg=hcfg,
        into=getattr(args, "into", "live_data"),
        pipeline_args="emd_cache_replay",
        out_subdir=f"emd_cache_replay_{args.instrument}",
        bundle_dir=bundle_dir,
    )


def submit_ig_trading_via_v2(args, hosts) -> int:
    """v2 entry-point for any ``c_emd.python.ig_trading.<submodule>`` run.

    Expected ``args`` namespace:
      ig_module (submodule name, eg. 'offload_replay_status'),
      ig_args (list of strings forwarded to the module),
      host, into.
    """
    host = args.host
    if host is None or host not in hosts:
        print(f"ERROR: --host required (got {host!r})", file=sys.stderr)
        return 1
    hcfg = hosts[host]
    if hcfg.get("type") == "local":
        print(f"ERROR: --via=v2 cannot target the local host ({host}); pick a remote.",
              file=sys.stderr)
        return 1

    state_dir, _ = _bundle_state_for_fleet()
    sys.path.insert(0, str(_ORCH_ROOT))
    from fleet import load_state
    peeked_job_id = load_state()["next_job_id"]
    bundle_dir = state_dir / "v2_bundles" / f"job_{peeked_job_id}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    manifest = _build_ig_trading_manifest(
        job_id=peeked_job_id,
        submodule=args.ig_module,
        extra_args=list(getattr(args, "ig_args", []) or []),
        host_alias=hcfg["ssh_alias"],
        remote_workdir=remote_workdir_default(hcfg),
        rsync_path=hcfg.get("rsync_path"),
        host_repo=hcfg["repo"],
        bundle_out_dir=bundle_dir,
    )

    return _spawn_v2_submit_and_register(
        manifest=manifest,
        cohort_label=f"ig_trading_{args.ig_module}",
        host=host,
        hcfg=hcfg,
        into=getattr(args, "into", "live_data"),
        pipeline_args=f"ig_trading.{args.ig_module}",
        out_subdir=f"ig_trading_{args.ig_module}",
        bundle_dir=bundle_dir,
    )


def submit_generic_via_v2(args, hosts) -> int:
    """v2 entry-point for running an arbitrary python module/script via the
    generic driver — no per-workflow manifest builder needed.

    Use this for ad-hoc remote work that isn't worth writing a v2 batch
    spec for: one-off probes, smoke tests, manual reruns of a single
    instrument. For repeatable multi-job work prefer ``v2 batch submit``
    with a spec.json.

    Expected ``args`` namespace:
      module (str, dotted)            — eg. "trading_common.tools.smoke_test"
      pass_args (list[str])           — forwarded verbatim to the module
      workflow (str, optional)        — short tag for job_id + metadata
                                        (default: derived from --module)
      host (str, optional)            — explicit host alias; auto-picks if None
      into ("live_data"|"external")   — pull-destination tier
      blob (list[str], optional)      — repeatable ``src=as_path`` pairs to
                                        ship extra files alongside the seal
      env (list[str], optional)       — repeatable ``KEY=VAL`` pairs added
                                        to the spawned process env
      host_results_root (str, optional) — value for FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT
                                          (default: <host_repo>/c_emd/results)
    """
    from v2.manifest import SealedBlob

    host = args.host
    if host is None:
        # Same picker as submit_random_windows_via_v2: most-cored bootstrapped host.
        candidates = sorted(
            (h for h, cfg in hosts.items()
             if _is_bootstrapped_host(cfg)),
            key=lambda h: hosts[h].get("cores", 0), reverse=True,
        )
        host = candidates[0] if candidates else None
        if host is None:
            print(
                "ERROR: no eligible bootstrapped host available "
                "(need has_msys64=true or legacy has_libemd=true).",
                file=sys.stderr,
            )
            return 1
    if host not in hosts:
        print(f"ERROR: host {host!r} not in hosts.json", file=sys.stderr)
        return 1
    hcfg = hosts[host]
    if hcfg.get("type") == "local":
        print(f"ERROR: --via=v2 cannot target the local host ({host}); pick a remote.",
              file=sys.stderr)
        return 1

    # Parse --blob entries (repeatable: src=as_path). Each becomes an extra
    # SealedBlob shipped alongside the standard code blobs. Resolution:
    #   - src may be absolute or relative-to-repo-root
    #   - as_path is the rel_path inside the seal (driver sees it at
    #     workdir/blobs/<as_path>)
    extra_blobs: list = []
    for i, entry in enumerate(getattr(args, "blob", None) or []):
        if "=" not in entry:
            print(f"ERROR: --blob expects src=as_path, got {entry!r}", file=sys.stderr)
            return 1
        src, as_path = entry.split("=", 1)
        src_p = pathlib.Path(src)
        if not src_p.is_absolute():
            src_p = _REPO_ROOT / src
        if not src_p.exists():
            print(f"ERROR: --blob src not found: {src_p}", file=sys.stderr)
            return 1
        extra_blobs.append(SealedBlob(
            name=f"extra_{i}_{src_p.name}",
            local_src=str(src_p),
            rel_path=as_path,
            is_dir=src_p.is_dir(),
        ))

    # Workflow tag: short, file-safe. Default to module's leaf if not given.
    workflow = getattr(args, "workflow", None) or args.module.rsplit(".", 1)[-1]

    state_dir, _ = _bundle_state_for_fleet()
    sys.path.insert(0, str(_ORCH_ROOT))
    from fleet import load_state
    peeked_job_id = load_state()["next_job_id"]
    bundle_dir = state_dir / "v2_bundles" / f"job_{peeked_job_id}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    host_results_root = getattr(args, "host_results_root", None) or (
        f'{hcfg["repo"]}/{hcfg.get("results_root", "c_emd/results")}'
    )

    manifest = _build_generic_manifest(
        job_id=peeked_job_id,
        workflow=workflow,
        module=args.module,
        pass_args=list(getattr(args, "pass_args", []) or []),
        host_alias=hcfg["ssh_alias"],
        remote_workdir=remote_workdir_default(hcfg),
        rsync_path=hcfg.get("rsync_path"),
        host_repo=hcfg["repo"],
        host_results_root=host_results_root,
        extra_blobs=extra_blobs,
        bundle_out_dir=bundle_dir,
        host_platform=hcfg.get("platform", "windows"),
        host_python=hcfg.get("python_executable"),
    )

    # Operator-supplied env (KEY=VAL list) is layered on top of the
    # manifest's default env. Useful for one-off PYTHONHASHSEED, log
    # level overrides, etc., without editing the adapter.
    for kv in getattr(args, "env", None) or []:
        if "=" not in kv:
            print(f"ERROR: --env expects KEY=VAL, got {kv!r}", file=sys.stderr)
            return 1
        k, v = kv.split("=", 1)
        manifest.env[k] = v

    return _spawn_v2_submit_and_register(
        manifest=manifest,
        cohort_label=f"generic_{workflow}",
        host=host,
        hcfg=hcfg,
        into=getattr(args, "into", "live_data"),
        pipeline_args=args.module,
        out_subdir=f"generic_{workflow}",
        bundle_dir=bundle_dir,
    )
