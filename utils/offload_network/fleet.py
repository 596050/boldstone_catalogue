#!/usr/bin/env python3
"""fleet — unified manager for the fleet-offload compute cluster.

Subcommands:
  status               probe all hosts (cores/CPU%/RAM/disk/libemd/running pipelines)
  sync   <host|all>    rsync code+manifest to a host (no data dirs)
  run    --cohort N    launch a pipeline; auto-picks idle host with libemd unless --host
  jobs                 list active jobs across the cluster
  kill   <job-id|all>  stop a job + reap its workers cleanly
  collect <job-id>     rsync results -> external + (optional) delete remote intermediates
  clean  <host> [--age=Nd]   remove old results dirs on a remote host

State lives in ~/.fleet/state.json — one source of truth for jobs we launched.
Existing /tmp/run_*.sh wrappers continue to run as legacy jobs (not managed here).

Conventions:
  - Every Windows host uses ~/Downloads/fleet-offload/ (USERPROFILE-relative).
  - Each cohort runs at <repo>/c_emd/results/random_windows_<cohort>/ on the remote.
  - Watchers rsync to /Volumes/Untitled/offload_data/c_emd/results/random_windows_<cohort>/
    on the Mac and delete the remote intermediates if --collect-mode=move was set.

Examples:
  utils/offload_network/fleet.py status
  utils/offload_network/fleet.py sync kenne
  utils/offload_network/fleet.py run --cohort bonds_dxy_nk
  utils/offload_network/fleet.py run --cohort eminis --host kenne \\
       --pipeline-args "--windows-per-instrument 8 --batches 4 --workers-per-batch 8"
  utils/offload_network/fleet.py jobs
  utils/offload_network/fleet.py collect 7
  utils/offload_network/fleet.py clean kenne --age=7d
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import json
import os
import pathlib
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Optional

from fleet.paths import fleet_dir as _fleet_dir

HERE = pathlib.Path(__file__).resolve().parent
from lib.inventory import hosts_path
HOSTS_JSON = hosts_path()
STATE_DIR = _fleet_dir()
STATE_FILE = STATE_DIR / "state.json"
LOG_DIR = STATE_DIR / "logs"

# Canonical data root on the external drive. Resolves to
# /Volumes/Untitled/offload_data unless FAMOUS_MODEL_DATA_ROOT (or the legacy
# EXTERNAL_DRIVE) overrides it. See TEMP_CURRENT_WORK.md for the target layout.
DATA_ROOT = pathlib.Path(
    os.environ.get("FAMOUS_MODEL_DATA_ROOT")
    or os.environ.get("EXTERNAL_DRIVE")
    or "/Volumes/Untitled/offload_data"
)

# Where cohort outputs land. Three destinations (post-2026-06-05 reorg per
# README_STRUCTURE.md on the external drive):
#
#   research_data (DEFAULT, current): $DATA_ROOT/research_data/c_emd/window_replays/<cohort>/
#     Per README_STRUCTURE.md: "research_data/c_emd/window_replays/: random-window
#     cohorts and holdout replay caches." This is the CURRENT canonical home for
#     random_windows_* outputs. The drive's reorg explicitly warns:
#       "If a process recreates root c_emd/ or live_data/c_emd/results/random_windows,
#        that process is writing to an obsolete layout and should be stopped or
#        redirected before its output is trusted."
#
#   live_data (LEGACY ALIAS, pre-2026-06-05): now redirected to research_data path
#     so older state.json entries referencing --into=live_data still find their
#     destination. Kept as an alias for backward compat with existing tooling.
#
#   external (LEGACY, pre-live_data): $DATA_ROOT/c_emd/results/<cohort>/
#     Outside any canonical tree. Only for collecting older cohorts whose
#     external_dest in ~/.fleet/state.json already points here.
def external_base(into: str = "research_data") -> pathlib.Path:
    if into in ("research_data", "live_data"):
        # Both flag values land in research_data after the 2026-06-05 reorg.
        # 'live_data' kept as a legacy alias so existing state.json entries +
        # downstream callers (auto_collect_watcher, fleet collect --into=live_data)
        # keep working without code changes elsewhere.
        return DATA_ROOT / "research_data" / "c_emd" / "window_replays"
    if into == "external":
        return DATA_ROOT / "c_emd" / "results"
    raise ValueError(f"--into must be 'research_data'|'live_data' (legacy alias) or 'external', got {into!r}")

# Round 4 cleanup (REFACTOR_PLAN.md 2026-06-05): EXTERNAL_BASE removed.
# Grep across the repo found 0 callers — it was a dead back-compat shim.
# If a caller resurfaces, use ``external_base("research_data")`` instead.


# ---------------------------------------------------------------------------
# Inventory + state
# ---------------------------------------------------------------------------

def load_hosts() -> dict[str, dict]:
    return json.loads(HOSTS_JSON.read_text())["hosts"]


def _state_default() -> dict:
    return {"next_job_id": 1, "jobs": []}


# Priority 1 from REFACTOR_PLAN.md (2026-06-05):
# Delegate state.json IO to the locked + schema-validated path in
# utils/offload_network/fleet/state.py. This closes the race
# window between auto_collect_watcher and manual fleet.py invocations
# that produced the unexplained rc=137/143 watcher exits.
#
# fleet/state.py provides:
#   - fcntl LOCK_EX around every read-modify-write
#   - atomic tmp+rename writes
#   - FleetJob/WorkStatus schema validation (opt-in via validate=True)
# Public load_state()/save_state() signatures are preserved here so every
# existing call site in fleet.py automatically gets the lock for free.
#
# 32 tests in utils/offload_network/tests/ pin the behaviour.
# Make the sibling fleet/ package importable. When fleet.py is the entrypoint
# Python loads it as __main__, so `import fleet` resolves to the fleet/
# package (not back to this script) — no name shadowing.
import sys as _sys
_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in _sys.path:
    _sys.path.insert(0, str(_HERE))
from fleet import state as _fleet_state  # noqa: E402


def load_state() -> dict:
    """Shared-lock read of ~/.fleet/state.json. Auto-creates the file with
    _state_default() if missing (legacy behaviour preserved)."""
    if not STATE_FILE.exists():
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        _fleet_state.save_state(_state_default())
    return _fleet_state.load_state()


def save_state(state: dict) -> None:
    """Exclusive-lock atomic write of ~/.fleet/state.json."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _fleet_state.save_state(state)


# New: context-manager for read-modify-write under exclusive lock.
# Existing call sites that follow "state = load_state(); ...; save_state(state)"
# can incrementally migrate to:    with mutate_state() as state: ...
mutate_state = _fleet_state.mutate_state


def alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


# ---------------------------------------------------------------------------
# Status (re-uses cluster_status logic — calls it inline)
# ---------------------------------------------------------------------------

def cmd_status(args, hosts):
    # Delegate to the consolidated cluster_status.py (same dir as fleet.py).
    cluster = HERE / "cluster_status.py"
    if not cluster.exists():
        # back-compat: also check the old scripts/ location
        repo = pathlib.Path(hosts["mac"]["repo"])
        cluster = repo / "scripts" / "cluster_status.py"
        if not cluster.exists():
            print(f"ERROR: cluster_status.py not found at {cluster}", file=sys.stderr)
            return 1
    return subprocess.run([sys.executable, str(cluster)]).returncode


# ---------------------------------------------------------------------------
# Sync code to a host
# ---------------------------------------------------------------------------

# What we sync to every remote (code + manifest only — never data dirs).
SYNC_PATHS = [
    "c_emd/Makefile",
    "c_emd/Makefile.win",
    "c_emd/include/",
    "c_emd/src/",
    "c_emd/tests/",
    "c_emd/python/",
    "c_emd/__init__.py",
    # Option D: ship cluster_state to remotes so future remote-side handlers
    # (host_state probes, disk-pressure alerts) can run locally on each host.
    # Functionally inert until a remote-side entry point is added; for now
    # Mac-side cluster_state probes remotes via SSH and recovery happens
    # centrally.
    "trading_common/cluster_state/",
    "trading_common/__init__.py",
    "Oil_UOA-EMD/tests/python/",
    "Oil_UOA-EMD/tests/cache_generation_manifest.csv",
    "scripts/",
]
SYNC_EXCLUDES = [
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    ".DS_Store",
]
# v1 transport (rsync-code-push + ssh-launch + nohup) was archived on
# 2026-06-07 to archive/v1_2026-06-07.tar.gz. Workflows now run exclusively
# via the v2 sealed-bundle path (v2/ + v2/fleet_adapter.py). The previously
# v1-only subcommands (sync, collect, manifest, recover) have been removed
# from this CLI — see git log + the archive tarball for historical reference.



# ---------------------------------------------------------------------------
# Run a pipeline on a host
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Jobs list
# ---------------------------------------------------------------------------

def cmd_jobs(args, hosts):
    state = load_state()
    rows = []
    for j in state["jobs"]:
        pid = j.get("wrapper_pid")
        live = alive(pid)
        status = j["status"]
        if status == "running" and not live:
            # Previously: SSH-probed the remote host's pipeline process count
            # via v1's _remote_pipeline_process_count to disambiguate
            # "running" / "exited" / "remote_run" / "unknown". That helper
            # was archived with v1 on 2026-06-07. Now: a "running" entry
            # whose Mac wrapper is dead is reported as "orphaned" so the
            # operator can decide; v2 jobs update their own status via the
            # v2 submit lifecycle and don't hit this branch.
            status = "orphaned"
        started = j.get("started_at")
        if not started and j.get("adopted_at"):
            started = "adopted@" + datetime.fromtimestamp(j["adopted_at"]).isoformat(timespec="seconds")
        rows.append((j["id"], j["host"], j["cohort"], status, pid if pid else "-", started or "-"))
    if not rows:
        print("no jobs registered. ('fleet run' to launch one)")
        return 0
    print(f"{'ID':>3}  {'HOST':<10}  {'COHORT':<24}  {'STATUS':<10}  {'PID':>7}  {'STARTED'}")
    for r in sorted(rows):
        print(f"{r[0]:>3}  {r[1]:<10}  {r[2]:<24}  {r[3]:<10}  {r[4]:>7}  {r[5]}")
    return 0


# ---------------------------------------------------------------------------
# Kill
# ---------------------------------------------------------------------------

def cmd_kill(args, hosts):
    state = load_state()
    target = args.job_id
    n = 0
    for j in state["jobs"]:
        if target != "all" and str(j["id"]) != str(target):
            continue
        if j["status"] != "running":
            continue
        pid = j.get("wrapper_pid")
        if not pid:
            print(f"  job {j['id']} ({j['host']}/{j['cohort']}): no local wrapper PID; not marking killed")
            continue
        if alive(pid):
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except (PermissionError, ProcessLookupError):
                pass
            print(f"  job {j['id']} ({j['host']}/{j['cohort']}): SIGTERM -> {pid}")
        j["status"] = "killed"
        n += 1
    save_state(state)
    print(f"killed {n} job(s).")
    return 0


# ---------------------------------------------------------------------------
# Collect (rsync results -> external; optionally delete remote)
# ---------------------------------------------------------------------------

# rsync exit codes that are usually worth retrying. 12 = protocol data error
# (typically network blip), 23 = partial xfer (often a transient SSH issue
# mid-stream), 30 = data send/receive timeout, 255 = ssh-layer failure.
# Kept here (and duplicated verbatim in v1/fleet_v1_commands.py) because
# tests/test_v1_constants_parity locks the two together.
RSYNC_TRANSIENT_RCS = {12, 23, 30, 255}
# _RSYNC_BINARY / _RSYNC_HELP_TEXT caches moved to v1/fleet_v1_commands.py
# with the _resolve_rsync_binary() / _rsync_help_text() helpers they back.


_LEGACY_PATH_PREFIXES = [
    # Pre-2026-06-04 destination tree. external_base("live_data") and
    # external_base("research_data") both now resolve to
    # research_data/c_emd/window_replays/, so anything still stored under
    # the old live_data/c_emd/results/random_windows/ path is stale —
    # rewriting at use-time prevents the "I was watching the wrong dir"
    # bug seen 2026-06-05 with jobs 48 & 49.
    (
        "/Volumes/Untitled/offload_data/live_data/c_emd/results/random_windows/",
        "/Volumes/Untitled/offload_data/research_data/c_emd/window_replays/",
    ),
]


# `cmd_manifest` (remote-vs-local manifest diff) was removed when v1 was
# archived (2026-06-07). It depended on v1's _local_manifest /
# _remote_manifest / _diff_manifests rsync helpers, which only made sense
# when results lived on the remote between submit and `fleet collect`.
# v2 ships results back as part of the submit lifecycle, so the
# manifest-diff use case is gone.


# ---------------------------------------------------------------------------
# Rollup per-batch summary JSONs into a master summary.json on the remote.
#
# Why this exists: the parallel-batches change (random_windows_pipeline.py's
# _spawn_parallel_batches) writes per-batch summary_batch{N}.json and only
# aggregates them into summary.json at the END from the parent process. If
# the wrapper dies but batches keep running (which happens often when SSH
# ControlMaster reaps the parent), the per-batch files exist but no master
# summary.json is ever written. cmd_collect refuses to collect a cohort
# without a complete-looking summary; this command rebuilds it on demand.
# ---------------------------------------------------------------------------

def cmd_rollup_summary(args, hosts):
    """Rebuild summary.json from per-batch summary_batch*.json on the remote.

    Idempotent: re-running on a cohort that already has a master summary.json
    overwrites it with the latest per-batch aggregation. Safe to run any
    number of times.
    """
    state = load_state()
    matching = [j for j in state["jobs"] if str(j["id"]) == str(args.job_id)]
    if not matching:
        print(f"no job with id {args.job_id}", file=sys.stderr)
        return 1
    j = matching[0]
    hcfg = hosts[j["host"]]
    if hcfg["type"] == "local":
        print("rollup-summary not yet supported for local jobs", file=sys.stderr)
        return 1

    remote_out = j["remote_out"]
    # PowerShell single-quote escape
    safe = remote_out.replace("'", "''")
    script = (
        "$ErrorActionPreference = 'SilentlyContinue'\n"
        f"$d = '{safe}'\n"
        "if (-not (Test-Path $d)) { Write-Output 'NO_DIR'; exit 1 }\n"
        "$batches = Get-ChildItem $d -Filter 'summary_batch*.json' -File\n"
        "if (-not $batches) { Write-Output 'NO_BATCHES'; exit 2 }\n"
        "$all = New-Object System.Collections.ArrayList\n"
        "foreach ($f in $batches) {\n"
        "    try {\n"
        "        $b = Get-Content $f.FullName -Raw | ConvertFrom-Json\n"
        "        if ($b -is [System.Collections.IEnumerable] -and -not ($b -is [string])) {\n"
        "            foreach ($r in $b) { [void]$all.Add($r) }\n"
        "        } else { [void]$all.Add($b) }\n"
        "    } catch {}\n"
        "}\n"
        "$out = Join-Path $d 'summary.json'\n"
        "$all | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $out -Encoding UTF8\n"
        "\"WROTE $($all.Count) results to summary.json\"\n"
    )
    HERE = pathlib.Path(__file__).resolve().parent
    sys.path.insert(0, str(HERE))
    from lib import remote as remote_lib  # noqa
    try:
        r = remote_lib.ps(hcfg["ssh_alias"], script, timeout=120, capture=True)
    except subprocess.TimeoutExpired:
        print(f"rollup-summary timed out on {j['host']}", file=sys.stderr)
        return 1
    out = (r.stdout or "").strip()
    if r.returncode != 0 or "NO_DIR" in out:
        print(f"  remote_out missing on {j['host']}: {remote_out}", file=sys.stderr)
        return 1
    if "NO_BATCHES" in out:
        print(f"  no summary_batch*.json files in {remote_out} -- nothing to rollup",
              file=sys.stderr)
        return 2
    # Last line should be "WROTE N results to summary.json"
    print(f"[rollup job {j['id']}] {out.splitlines()[-1] if out else '(no output)'}")
    return 0


# ---------------------------------------------------------------------------
# Clean old results on a host
# ---------------------------------------------------------------------------

def cmd_clean(args, hosts):
    h = args.host
    if h not in hosts or hosts[h]["type"] == "local":
        print(f"clean is only for remote hosts.  unknown: {h}", file=sys.stderr)
        return 1
    days = int((args.age or "7d").rstrip("d"))
    hcfg = hosts[h]
    results = f'{hcfg["repo"]}/{hcfg.get("results_root", "c_emd/results")}'
    # Safety: refuse to recurse-delete a too-shallow root — a misconfigured
    # repo/results_root must never let `fleet clean --yes` wipe a drive or home dir.
    _segs = [s for s in results.replace("\\", "/").split("/") if s and s not in (".", "..")]
    if len(_segs) < 3 or results.rstrip("/\\").endswith(":"):
        print(f"clean refusing unsafe shallow results root: {results!r}", file=sys.stderr)
        return 1
    # List dirs older than `days` days
    ps = (
        f'$cutoff = (Get-Date).AddDays(-{days});'
        f'Get-ChildItem -Path "{results}" -Directory -ErrorAction SilentlyContinue '
        f'| Where-Object {{ $_.LastWriteTime -lt $cutoff }} '
        f'| Select-Object Name,@{{N="LastWriteTime";E={{$_.LastWriteTime}}}},'
        f'@{{N="SizeMB";E={{[math]::Round((Get-ChildItem $_.FullName -Recurse | Measure-Object Length -Sum).Sum/1MB,0)}}}}'
        f'| Format-Table -AutoSize'
    )
    r = subprocess.run(["ssh", hcfg["ssh_alias"], "powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True)
    print(r.stdout)
    if not args.yes:
        print(f"(dry run; pass --yes to actually delete)")
        return 0
    # Actually delete
    ps2 = (
        f'$cutoff = (Get-Date).AddDays(-{days});'
        f'Get-ChildItem -Path "{results}" -Directory -ErrorAction SilentlyContinue '
        f'| Where-Object {{ $_.LastWriteTime -lt $cutoff }} '
        f'| ForEach-Object {{ Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue; Write-Host "  rm $($_.Name)" }}'
    )
    subprocess.run(["ssh", hcfg["ssh_alias"], "powershell", "-NoProfile", "-Command", ps2])
    return 0


# ---------------------------------------------------------------------------
# recover / hdd-status subcommands — for HDD failure recovery
# ---------------------------------------------------------------------------

def cmd_hdd_status(args, hosts):
    """Print HDD readiness — mount, write probe, free space, label.

    Use BEFORE starting a big collect to confirm the disk is ready.
    Use AFTER an interruption to verify the disk is back."""
    sys.path.insert(0, str(HERE))
    from lib import hdd_health  # noqa: E402
    r = hdd_health.probe_hdd(force=True)
    if r["ok"]:
        print(f"[hdd] OK  mount={r['mount']}  free={r['free_gb']} GB  "
              f"label={r['label']!r}  uuid={r['uuid']!r}")
    else:
        print(f"[hdd] FAIL  mount={r['mount']}  errors:", file=sys.stderr)
        for e in r["errors"]:
            print(f"  - {e}", file=sys.stderr)
    return 0 if r["ok"] else 1


def cmd_ops(args, hosts):
    """List operation journal entries — current state, recent finished,
    and per-op_type breakdown. Use to audit what the system did / is doing.

    Filters:
        --type <op_type>   only show entries with this op_type
        --state <state>    only show entries in this state
        --all              include terminal-state entries (default: only non-terminal)
    """
    sys.path.insert(0, str(HERE))
    from lib import op_journal as oj  # noqa: E402
    if getattr(args, "all", False):
        entries = oj.list_all()
    else:
        entries = oj.list_incomplete()
    if getattr(args, "type", None):
        entries = [e for e in entries if e.op_type == args.type]
    if getattr(args, "state", None):
        entries = [e for e in entries if e.state == args.state]
    if not entries:
        print("[ops] no entries match")
        return 0
    # Group + render
    print(f"[ops] {len(entries)} entries")
    print(f"  {'op_id':<28s} {'type':<14s} {'state':<11s} {'age':<7s} {'host':<10s} {'job':<8s} note")
    for e in entries:
        # Age in human terms
        try:
            t0 = time.mktime(time.strptime(e.started_at[:19], "%Y-%m-%dT%H:%M:%S"))
            age_s = time.time() - t0
            if age_s < 60: age = f"{int(age_s)}s"
            elif age_s < 3600: age = f"{int(age_s/60)}m"
            elif age_s < 86400: age = f"{int(age_s/3600)}h"
            else: age = f"{int(age_s/86400)}d"
        except Exception:
            age = "?"
        note = e.last_error[:50] if e.last_error else ""
        if not note and e.attempts:
            note = (e.attempts[-1].get("note") or "")[:50]
        print(f"  {e.op_id:<28s} {e.op_type:<14s} {e.state:<11s} {age:<7s} "
              f"{(e.host or '-'):<10s} {(e.job_id or '-'):<8s} {note}")
    return 0


# `cmd_recover` was removed when v1 was archived (2026-06-07). It scanned
# ~/.fleet/op_journal/ for incomplete rsync-collect operations and re-ran
# them via cmd_collect — a flow that only existed in the v1 transport.
# v2 submits pull results as part of their own lifecycle; if a v2 submit
# fails, the operator re-runs it directly (idempotency in the v2 push +
# extract + spawn layers means a re-submit costs ~seconds, not minutes).


# ---------------------------------------------------------------------------
# network-discover subcommand
# ---------------------------------------------------------------------------

def cmd_network_discover(args, hosts):
    """Probe each host for a direct same-LAN address; cache results.

    Once cached, future `fleet sync` / `fleet collect` automatically prefer
    the LAN address over the overlay tunnel (Tailscale today). The cache
    has a 1h TTL — pass --force to bypass it.

    The probe is two-stage per host:
      1. Find a candidate IP (e.g. Tailscale's "direct" peer endpoint)
      2. Verify the candidate responds with an SSH banner on port 22

    Hosts with no LAN route (purely remote, e.g. scan-xeon over public
    Internet) get a None entry, which the rest of fleet then treats as
    "stay on the overlay".
    """
    sys.path.insert(0, str(HERE))
    from lib import network as netlib  # noqa: E402

    requested = args.hosts or [
        name for name, h in hosts.items()
        if h.get("type") != "local"
    ]
    print(f"[network-discover] probing {len(requested)} host(s) (force={args.force}) ...")
    addrs = netlib.discover_lan_addresses(requested, force=args.force)
    have_lan = sum(1 for v in addrs.values() if v)
    print(f"[network-discover] cache updated at {netlib.CACHE_PATH}")
    print(f"[network-discover] {have_lan}/{len(addrs)} host(s) have a verified same-LAN route\n")
    for alias in sorted(addrs):
        ip = addrs[alias]
        if ip:
            print(f"  {alias:>12s}  →  LAN  {ip}")
        else:
            print(f"  {alias:>12s}  →  overlay only (no direct LAN reachable)")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sp = p.add_subparsers(dest="cmd", required=True)

    sp.add_parser("status",   help="probe all hosts")

    # `sync` subcommand removed when v1 was archived (2026-06-07). v2 ships
    # code IN the seal each submit, so there's no remote repo to pre-seed.

    p_disc = sp.add_parser("network-discover",
                            help="probe all hosts for direct LAN addresses; "
                                 "cache results so future SSH/rsync prefers them")
    p_disc.add_argument("--force", action="store_true",
                         help="ignore cache TTL and re-probe every host")
    p_disc.add_argument("hosts", nargs="*",
                         help="hosts to probe (default: every non-local host in hosts.json)")

    p_run = sp.add_parser("run", help="launch a pipeline cohort on a host")
    p_run.add_argument("--cohort", required=True,
                        help="instruments-list shortcut (e.g. bonds_dxy_nk, ig_friendly, eminis)")
    p_run.add_argument("--host", default=None,
                        help="explicit host (omit to auto-pick the idlest libemd host)")
    p_run.add_argument("--out-subdir", default=None,
                        help="results subdir name (default: random_windows_<cohort>)")
    p_run.add_argument("--into", choices=["live_data", "external"], default="live_data",
                        help="Where on the external drive collected results will land. "
                             "Default 'live_data' lands them under "
                             "$DATA_ROOT/live_data/c_emd/results/random_windows/<cohort>/ "
                             "(the data_storage canonical tree). Use 'external' for legacy "
                             "$DATA_ROOT/c_emd/results/<cohort>/.")
    p_run.add_argument("--pipeline-args", default=None,
                        help="extra args appended to random_windows_pipeline (default: 8 windows / 4 batches / 8 workers / seed 42)")
    # --via flag removed: v2 is now the only transport. v1 was archived
    # on 2026-06-07 (see archive/v1_2026-06-07.tar.gz).

    # Generic job type — runs an arbitrary python module on a remote host
    # via v2/drivers/generic.py. Use this for ad-hoc one-off remote runs
    # (smoke tests, single-instrument reruns, probes). For repeatable
    # multi-job work prefer `v2 batch submit` with a spec.json.
    p_generic = sp.add_parser("generic",
        help="run an arbitrary python module on a remote host (one-shot)")
    p_generic.add_argument("--module", required=True,
        help="dotted python module to run, eg trading_common.tools.smoke")
    p_generic.add_argument("--host", default=None,
        help="explicit host (omit to auto-pick the most-cored libemd host)")
    p_generic.add_argument("--workflow", default=None,
        help="short tag for job_id + metadata (default: --module's leaf)")
    p_generic.add_argument("--into", choices=["live_data", "external"], default="live_data",
        help="where pulled results land on the external HDD (default live_data)")
    p_generic.add_argument("--blob", action="append", default=[],
        help="ship extra file/dir into the seal: src=as_path; repeatable. "
             "src may be absolute or relative to repo root; as_path is the "
             "rel_path inside the seal's blobs/ tree (driver sees it at "
             "workdir/blobs/<as_path>).")
    p_generic.add_argument("--env", action="append", default=[],
        help="layer KEY=VAL onto the seal's process env; repeatable")
    p_generic.add_argument("--host-results-root", default=None,
        help="value for FAMOUS_MODEL_EXTERNAL_RESULTS_ROOT inside the seal "
             "(default: <host_repo>/c_emd/results)")
    p_generic.add_argument("pass_args", nargs=argparse.REMAINDER,
        help="all args after `--` are forwarded verbatim to the wrapped module")

    sp.add_parser("jobs", help="list active + recent jobs")

    sp.add_parser("hdd-status", help="probe the external HDD's readiness "
                                       "(mounted/writable/free/label)")

    # `recover` subcommand removed when v1 was archived (2026-06-07). It
    # resumed v1 rsync-collect operations from ~/.fleet/op_journal/; v2
    # submits are self-recovering via the idempotent push/extract/spawn
    # layers (operator re-runs the same `fleet run` and it picks up).

    p_ops = sp.add_parser("ops",
                            help="list operation journal entries (status of "
                                 "submits, collects, syncs, monitor cycles)")
    p_ops.add_argument("--all", action="store_true",
                         help="include terminal (done/failed) entries; default is "
                              "non-terminal only")
    p_ops.add_argument("--type", help="filter to ops with this op_type "
                                          "(collect|submit|sync|monitor_loop|...)")
    p_ops.add_argument("--state",
                         help="filter to ops in this state "
                              "(planned|copying|verifying|publishing|done|failed|interrupted)")

    p_kill = sp.add_parser("kill", help="terminate a job by id (or 'all')")
    p_kill.add_argument("job_id")

    # `collect` + `manifest` subcommands removed when v1 was archived
    # (2026-06-07). v2 pulls results as part of its submit lifecycle —
    # they land under ~/.fleet/v2_bundles/<job>/pulled/ automatically.

    p_roll = sp.add_parser("rollup-summary",
        help="Rebuild summary.json from per-batch summary_batch*.json on the "
             "remote (used when wrapper died before final aggregation).")
    p_roll.add_argument("job_id")

    p_clean = sp.add_parser("clean", help="remove old result dirs on a remote host")
    p_clean.add_argument("host")
    p_clean.add_argument("--age", default="7d", help="default 7d")
    p_clean.add_argument("--yes", action="store_true",
                          help="actually delete (default: dry-run preview)")

    args = p.parse_args()
    hosts = load_hosts()

    # `fleet run` goes directly to the v2 sealed-bundle adapter. v1's
    # ssh-and-nohup path was archived on 2026-06-07.
    def _run_v2(args, hosts):
        from v2.fleet_adapter import submit_random_windows_via_v2
        return submit_random_windows_via_v2(args, hosts)

    def _generic_v2(args, hosts):
        from v2.fleet_adapter import submit_generic_via_v2
        # argparse.REMAINDER preserves the leading "--" separator; strip it
        # so the wrapped module's argparse doesn't see a spurious "--".
        if args.pass_args and args.pass_args[0] == "--":
            args.pass_args = args.pass_args[1:]
        return submit_generic_via_v2(args, hosts)

    handlers = {
        "status":           cmd_status,
        "run":              _run_v2,
        "generic":          _generic_v2,
        "jobs":             cmd_jobs,
        "kill":             cmd_kill,
        "rollup-summary":   cmd_rollup_summary,
        "clean":            cmd_clean,
        "network-discover": cmd_network_discover,
        "hdd-status":       cmd_hdd_status,
        "ops":              cmd_ops,
    }
    return handlers[args.cmd](args, hosts)


if __name__ == "__main__":
    sys.exit(main())
