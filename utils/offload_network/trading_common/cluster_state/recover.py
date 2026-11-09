"""Recovery handlers — act on alerts detected by ``reconcile``.

Implements Phases 3 of the rollout (safe, read-only-then-state-edit handlers).
Higher-risk handlers (re-run failed targets, restore source dirs, auto-collect
under disk pressure) live behind ``--dry-run`` defaults and opt-in flags.

Every state-changing action in this module:
- writes a ``JobEvent`` with ``actor`` set to its handler name
- respects ``dry_run=True`` by default (callers pass ``dry_run=False`` to apply)
- is idempotent: re-running on the same state is safe
- never deletes data; uses quarantine semantics inherited from data_storage
- respects ``MAX_RETRIES_PER_CLASS`` escalation threshold
"""
from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any

from .ledger import append_event, count_recent_alerts_by_kind
from .reconcile import _ssh_pid_alive
from .schema import Alert, JobEvent, Severity

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_FLEET_PY = _REPO_ROOT / "fleet.py"
_HOSTS_JSON = _REPO_ROOT / "hosts.json"

# Priority 2 from REFACTOR_PLAN.md (2026-06-05): delegate state.json IO to
# fleet/state.py so we share the LOCK_EX with fleet.py + auto_collect_watcher.
# Before this, cluster_state.recover ran its own _load_state/_save_state in
# parallel with fleet.py's IO, racing over the same file.
import sys as _sys
_OFFLOAD_DIR = _REPO_ROOT
if str(_OFFLOAD_DIR) not in _sys.path:
    _sys.path.insert(0, str(_OFFLOAD_DIR))
from fleet import state as _fleet_state  # noqa: E402

# Per-class escalation threshold. After N retries on the same alert kind
# (over a 24h window), STOP attempting recovery and hand off to operator
# via a severity=error alert.
MAX_RETRIES_PER_CLASS = 3
ESCALATION_WINDOW_HOURS = 24


@dataclasses.dataclass
class Recovery:
    """Result of a single recovery action. Caller can audit the field
    set programmatically (e.g. count successes vs escalations)."""
    handler:        str        # e.g. "reclassify_wrapper_state"
    job_id:         int | None = None
    host:           str | None = None
    action_taken:   str = "noop"   # "noop" | "state_edited" | "escalated" | "skipped_due_to_threshold"
    before:         dict[str, Any] = dataclasses.field(default_factory=dict)
    after:          dict[str, Any] = dataclasses.field(default_factory=dict)
    note:           str = ""
    dry_run:        bool = True


def _load_state() -> dict:
    """Shared-lock read via fleet/state.py.

    Round 4 cleanup (2026-06-05): round 2's intended delegation was
    silently overwritten — the function body still did `json.loads(...)`.
    Verified fixed: ``test_clusterstate_uses_shared_load_state`` writes via
    ``fleet.state.save_state`` and reads back through this function.
    """
    state = _fleet_state.load_state()
    state.setdefault("next_job_id", 1)
    return state


def _save_state(state: dict) -> None:
    """Exclusive-lock atomic write via fleet/state.py."""
    _fleet_state.save_state(state)


def _should_escalate(kind: str, job_id: int | None = None) -> bool:
    """Self-repair principle #4 — explicit escalation threshold.

    Per-(kind, job_id) by default — same alert on different jobs are
    different problems. After MAX_RETRIES_PER_CLASS attempts on the
    specific (kind, job_id) in the last ESCALATION_WINDOW_HOURS,
    recovery STOPS retrying and hands off via an error alert.
    """
    return count_recent_alerts_by_kind(
        kind, hours=ESCALATION_WINDOW_HOURS, job_id=job_id,
    ) >= MAX_RETRIES_PER_CLASS


def reclassify_wrapper_state(job_id: int, dry_run: bool = True) -> Recovery:
    """When a job shows ``status=running`` but its wrapper PID is dead,
    update the state.json entry to reflect reality.

    Two outcomes:

    - if pipeline workers ARE still running on the remote (Task Scheduler
      survived the wrapper death) → status becomes ``wrapper_dead_pipeline_running``
    - if no pipeline workers either → status becomes ``exited``

    This is the safest possible recovery: it's a state-edit only, no data
    is touched. Idempotent — re-running on an already-reclassified job is
    a no-op.
    """
    state = _load_state()
    job_list = state.get("jobs", [])
    matching = [j for j in job_list if j.get("id") == job_id]
    if not matching:
        return Recovery(
            handler="reclassify_wrapper_state",
            job_id=job_id,
            action_taken="noop",
            note=f"no job with id {job_id} in state.json",
            dry_run=dry_run,
        )
    j = matching[0]

    # If already reclassified, no-op
    if j.get("status") not in ("running", "remote_run"):
        return Recovery(
            handler="reclassify_wrapper_state",
            job_id=job_id,
            host=j.get("host"),
            action_taken="noop",
            note=f"already at status={j.get('status')}",
            before={"status": j.get("status")},
            after={"status": j.get("status")},
            dry_run=dry_run,
        )

    host = j.get("host") or "?"
    pid = j.get("wrapper_pid") or 0
    # wrapper_pid is a Mac-side nohup'd PID (fleet.cmd_run launches the
    # wrapper locally; it ssh's to the remote internally). Probe locally
    # regardless of which Windows host the cohort actually runs on.
    if not pid:
        alive: bool | None = False
    else:
        try:
            os.kill(pid, 0)
            alive = True
        except ProcessLookupError:
            alive = False
        except PermissionError:
            # PID exists but is owned by another user — still "alive"
            alive = True
        except OSError:
            alive = None
    if alive is None:
        return Recovery(
            handler="reclassify_wrapper_state",
            job_id=job_id,
            host=host,
            action_taken="escalated",
            note=f"local probe of wrapper pid {pid} failed with OSError; not editing state",
            dry_run=dry_run,
        )
    if alive:
        return Recovery(
            handler="reclassify_wrapper_state",
            job_id=job_id,
            host=host,
            action_taken="noop",
            note=f"wrapper pid {pid} actually alive — no state change needed",
            dry_run=dry_run,
        )

    # Wrapper is dead. Probe for any pipeline-related process (python with
    # random_windows_pipeline in cmd) to decide between
    # 'wrapper_dead_pipeline_running' and 'exited'.
    new_status = "exited"
    if host != "mac":
        cohort = j.get("cohort", "")
        # Search for any python process with this job's out_subdir in its
        # commandline. We use Win32_Process from CIM.
        out_subdir_match = pathlib.Path(j.get("remote_out", "")).name
        try:
            r = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes",
                 host,
                 "powershell.exe", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" "
                 "| Where-Object { $_.CommandLine -match "
                 f"'{out_subdir_match}' }} | Measure-Object | "
                 "Select-Object -ExpandProperty Count"],
                capture_output=True, text=True, timeout=15,
            )
            count_s = (r.stdout or "0").strip().splitlines()[-1].strip()
            try:
                cnt = int(count_s)
            except ValueError:
                cnt = 0
            if cnt > 0:
                new_status = "wrapper_dead_pipeline_running"
        except (subprocess.TimeoutExpired, Exception):
            # Couldn't probe — be conservative; report wrapper dead but pipeline unknown
            new_status = "wrapper_dead_pipeline_unknown"

    before = {"status": j.get("status"), "wrapper_pid": pid}
    after  = {"status": new_status, "wrapper_pid": pid}

    if not dry_run:
        j["status"] = new_status
        _save_state(state)
        # Provenance ledger entry — principle #5
        append_event(JobEvent(
            event="auto_recovery",
            actor="cluster_state.recover.reclassify_wrapper_state",
            job_id=job_id,
            host=host,
            cohort=j.get("cohort"),
            details={"before": before, "after": after,
                     "reason": f"wrapper pid {pid} dead on {host}; "
                               f"pipeline procs check → {new_status}"},
        ))
    return Recovery(
        handler="reclassify_wrapper_state",
        job_id=job_id,
        host=host,
        action_taken="state_edited" if not dry_run else "would_edit_state",
        before=before,
        after=after,
        note=f"wrapper pid {pid} dead → status {before['status']} → {new_status}",
        dry_run=dry_run,
    )


def reclassify_running_jobs(dry_run: bool = True, max_jobs: int = 50) -> list[Recovery]:
    """Walk every status=running job; reclassify those whose wrapper PID
    is dead. This is the bulk recovery for the stale-running-state class.

    Cap the number of jobs processed per call (defaults to 50) so a single
    invocation can't hammer many hosts. The next call picks up from where
    the previous left off (no internal state — the loop just walks again).
    """
    state = _load_state()
    results: list[Recovery] = []
    seen = 0
    for j in state.get("jobs", []):
        if j.get("status") not in ("running", "remote_run"):
            continue
        seen += 1
        if seen > max_jobs:
            break
        # Decide if we should attempt at all — escalation threshold (per-job)
        if _should_escalate("wrapper_dead", job_id=j.get("id")):
            results.append(Recovery(
                handler="reclassify_wrapper_state",
                job_id=j.get("id"),
                host=j.get("host"),
                action_taken="skipped_due_to_threshold",
                note=(f"wrapper_dead alerts in last {ESCALATION_WINDOW_HOURS}h "
                      f">= {MAX_RETRIES_PER_CLASS}; not attempting more recoveries"),
                dry_run=dry_run,
            ))
            continue
        r = reclassify_wrapper_state(j["id"], dry_run=dry_run)
        results.append(r)
    return results


def recover_summary(results: list[Recovery]) -> dict:
    """Compact summary of a recovery batch — easy to dump from the CLI."""
    counts: dict[str, int] = {}
    for r in results:
        counts[r.action_taken] = counts.get(r.action_taken, 0) + 1
    return {"total": len(results), "by_action": counts}


# ============================================================================
# Phase 4 — disk_pressure_collect
# ============================================================================

def _data_root() -> pathlib.Path:
    return pathlib.Path(
        os.environ.get("FAMOUS_MODEL_DATA_ROOT")
        or os.environ.get("EXTERNAL_DRIVE")
        or "/Volumes/Untitled/famous_model"
    )


def _load_hosts() -> dict:
    if not _HOSTS_JSON.exists():
        return {}
    return json.loads(_HOSTS_JSON.read_text()).get("hosts", {})


def _remote_ps_helper():
    """Import scripts/offload_orchestration/lib/remote.py once and reuse.

    Uses UTF-16-LE base64-encoded PowerShell over SSH — defeats every
    quoting layer (Mac shell, ssh, cmd.exe, PowerShell parser). Same
    pattern fleet.py uses for _remote_manifest.
    """
    fleet_dir = _REPO_ROOT / "scripts" / "offload_orchestration"
    if str(fleet_dir) not in sys.path:
        sys.path.insert(0, str(fleet_dir))
    from lib import remote as remote_lib  # type: ignore[import-not-found]
    return remote_lib


def _probe_remote_disk_free_gb(host: str) -> float | None:
    """Probe free disk on a remote Windows host (C:). None on failure."""
    hosts = _load_hosts()
    cfg = hosts.get(host)
    if not cfg or cfg.get("type") == "local":
        return None
    try:
        rl = _remote_ps_helper()
        r = rl.ps(cfg["ssh_alias"],
                  "[math]::Round((Get-PSDrive C).Free / 1GB, 1)",
                  timeout=20, capture=True)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            return float(line)
        except ValueError:
            continue
    return None


def _probe_remote_dir_exists(host: str, path: str) -> bool | None:
    """Return True/False/None for remote dir existence (None = probe failed)."""
    hosts = _load_hosts()
    cfg = hosts.get(host)
    if not cfg or cfg.get("type") == "local":
        return None
    # PowerShell single-quote escape: ' -> ''
    safe = path.replace("'", "''")
    try:
        rl = _remote_ps_helper()
        r = rl.ps(cfg["ssh_alias"],
                  f"if (Test-Path '{safe}') {{ 'YES' }} else {{ 'NO' }}",
                  timeout=20, capture=True)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    out = (r.stdout or "").upper()
    if "YES" in out: return True
    if "NO" in out:  return False
    return None


def _remote_rm_rf(host: str, path: str) -> bool:
    """Recursively remove a remote dir via PowerShell-over-SSH. Returns True on
    success. This is the disk-reclamation primitive that replaces the legacy
    ``fleet collect --delete-remote`` subcommand (removed when v1 was archived);
    deleting the remote output dir is what that subcommand ultimately did."""
    hosts = _load_hosts()
    cfg = hosts.get(host)
    if not cfg or cfg.get("type") == "local" or not path:
        return False
    safe = path.replace("'", "''")
    try:
        rl = _remote_ps_helper()
        r = rl.ps(cfg["ssh_alias"],
                  f"Remove-Item -Recurse -Force -LiteralPath '{safe}' -ErrorAction Stop; 'OK'",
                  timeout=120, capture=True)
    except Exception:
        return False
    return r.returncode == 0


def disk_pressure_collect(host: str,
                          dry_run: bool = True,
                          free_threshold_gb: float = 30.0) -> Recovery:
    """When ``host`` is under ``free_threshold_gb`` GB free AND ≥1
    ``status=collected`` job still has its remote dir, run
    ``fleet collect --verify-only --delete-remote`` on the oldest such job
    to reclaim the disk.

    Caps at one cohort per invocation; subsequent invocations pick up the
    next oldest. Idempotent: when no collected-with-remote jobs remain or
    disk is above threshold, returns a noop.
    """
    free_gb = _probe_remote_disk_free_gb(host)
    if free_gb is None:
        return Recovery(handler="disk_pressure_collect", host=host,
                        action_taken="escalated",
                        note=f"could not probe disk free on {host}",
                        dry_run=dry_run)
    if free_gb >= free_threshold_gb:
        return Recovery(handler="disk_pressure_collect", host=host,
                        action_taken="noop",
                        note=f"free disk {free_gb} GB ≥ threshold {free_threshold_gb}",
                        dry_run=dry_run)

    if _should_escalate("disk_pressure", job_id=None):
        return Recovery(handler="disk_pressure_collect", host=host,
                        action_taken="skipped_due_to_threshold",
                        note=f"disk_pressure alerts in last {ESCALATION_WINDOW_HOURS}h "
                             f">= {MAX_RETRIES_PER_CLASS}; STOP",
                        dry_run=dry_run)

    state = _load_state()
    candidates = []
    for j in state.get("jobs", []):
        if j.get("host") != host: continue
        if j.get("status") != "collected": continue
        if not j.get("remote_out"): continue
        ex = _probe_remote_dir_exists(host, j["remote_out"])
        if ex is True:
            candidates.append(j)
    if not candidates:
        return Recovery(handler="disk_pressure_collect", host=host,
                        action_taken="noop",
                        note=f"no collected jobs with remote dirs still present (disk {free_gb} GB)",
                        dry_run=dry_run)

    candidates.sort(key=lambda j: j.get("started_at", ""))
    oldest = candidates[0]

    if dry_run:
        return Recovery(handler="disk_pressure_collect", job_id=oldest["id"], host=host,
                        action_taken="would_recover",
                        note=(f"free disk {free_gb} GB < {free_threshold_gb}; would remove "
                              f"oldest collected job {oldest['id']} remote_out {oldest['remote_out']!r}"),
                        before={"free_gb": free_gb, "remote_out": oldest["remote_out"]},
                        dry_run=True)

    # dry_run=False: actually reclaim the disk by removing the oldest collected
    # job's remote output dir. (Previously this body was misplaced as dead code
    # after chunks_cleanup_recover and called the removed `fleet collect`
    # subcommand, so the real path returned None.)
    removed = _remote_rm_rf(host, oldest["remote_out"])
    if removed:
        append_event(JobEvent(
            event="auto_recovery",
            actor="cluster_state.recover.disk_pressure_collect",
            job_id=oldest["id"],
            host=host,
            cohort=oldest.get("cohort"),
            details={"reason": f"host {host} free disk {free_gb} GB < {free_threshold_gb}; "
                               f"removed oldest collected job's remote dir",
                     "free_gb_before": free_gb,
                     "remote_out": oldest["remote_out"]},
        ))
    return Recovery(handler="disk_pressure_collect", job_id=oldest["id"], host=host,
                    action_taken=("state_edited" if removed else "escalated"),
                    note=(f"removed remote_out {oldest['remote_out']!r}: ok={removed} "
                          f"(free was {free_gb} GB < {free_threshold_gb})"),
                    before={"free_gb": free_gb, "remote_out": oldest["remote_out"]},
                    dry_run=False)


# ============================================================================
# Phase 4.5 — chunks_cleanup_recover (cheaper disk relief than full collect)
# ============================================================================
# When a host is under disk pressure but no collect candidate exists (e.g., all
# collected jobs already had their remote dirs deleted), the *_chunks/ scratch
# dirs inside status=exited cohorts are safe to delete and typically free
# 5-15 GB without any network transfer cost. This handler wraps
# scripts/offload_orchestration/clean_kenne_chunks.py and emits a JobEvent so
# the alert ledger reflects the action.

_CLEAN_KENNE_CHUNKS = _REPO_ROOT / "scripts" / "offload_orchestration" / "clean_kenne_chunks.py"


def chunks_cleanup_recover(host: str,
                           dry_run: bool = True,
                           free_threshold_gb: float = 30.0) -> Recovery:
    """Run the chunks-cleanup script on ``host`` when disk is under
    threshold. The script itself is multi-layer safe (skips status=running
    cohorts; chunks are excluded from rsync, regeneratable from source).

    Currently only `kenne` is supported (the script is kenne-specific). For
    other hosts, returns noop with a note.
    """
    if host != "kenne":
        return Recovery(handler="chunks_cleanup_recover", host=host,
                        action_taken="noop",
                        note=f"chunks-cleanup script is kenne-specific; "
                             f"host '{host}' not yet supported",
                        dry_run=dry_run)
    if not _CLEAN_KENNE_CHUNKS.exists():
        return Recovery(handler="chunks_cleanup_recover", host=host,
                        action_taken="escalated",
                        note=f"clean_kenne_chunks.py not found at {_CLEAN_KENNE_CHUNKS}",
                        dry_run=dry_run)

    free_gb = _probe_remote_disk_free_gb(host)
    if free_gb is None:
        return Recovery(handler="chunks_cleanup_recover", host=host,
                        action_taken="escalated",
                        note=f"could not probe disk free on {host}",
                        dry_run=dry_run)
    if free_gb >= free_threshold_gb:
        return Recovery(handler="chunks_cleanup_recover", host=host,
                        action_taken="noop",
                        note=f"free disk {free_gb} GB ≥ threshold {free_threshold_gb}",
                        dry_run=dry_run)

    cmd = [sys.executable, str(_CLEAN_KENNE_CHUNKS)] + (["--apply"] if not dry_run else [])
    if dry_run:
        return Recovery(handler="chunks_cleanup_recover", host=host,
                        action_taken="would_recover",
                        note=(f"free disk {free_gb} GB < {free_threshold_gb}; "
                              f"would run `{' '.join(cmd)}`"),
                        before={"free_gb": free_gb},
                        dry_run=True)

    res = subprocess.run(cmd, cwd=_REPO_ROOT, capture_output=True, text=True)
    # The cleanup script prints "TOTAL: freed X.XX GB across N chunk dir(s)" near the end
    freed_match = re.search(r"TOTAL:\s+freed\s+([\d.]+)\s+GB\s+across\s+(\d+)", res.stdout)
    freed_gb = float(freed_match.group(1)) if freed_match else 0.0
    n_dirs   = int(freed_match.group(2)) if freed_match else 0

    if res.returncode == 0 and freed_gb > 0:
        append_event(JobEvent(
            event="auto_recovery",
            actor="cluster_state.recover.chunks_cleanup_recover",
            job_id=None, host=host, cohort=None,
            details={"reason": f"host {host} free disk {free_gb} GB < {free_threshold_gb}; "
                               f"freed {freed_gb} GB by deleting {n_dirs} chunk dirs",
                     "free_gb_before": free_gb, "freed_gb": freed_gb,
                     "n_dirs": n_dirs},
        ))

    return Recovery(handler="chunks_cleanup_recover", host=host,
                    action_taken=("state_edited" if (res.returncode == 0 and freed_gb > 0) else "escalated"),
                    note=(f"clean_kenne_chunks.py rc={res.returncode} "
                          f"freed={freed_gb} GB across {n_dirs} dirs"),
                    dry_run=False)


# ============================================================================
# Phase 5 — recollect_delta
# ============================================================================

def recollect_delta(job_id: int, dry_run: bool = True) -> Recovery:
    """When a previous collect verify-failed (mismatch detected), re-trigger
    fleet collect to delta-rsync the missing/short files.

    fleet's rsync uses --partial + --append-verify so a re-run is naturally
    incremental: only files that are missing on local OR shorter than remote
    transfer. Idempotent — running on a job that already matches is a noop.
    """
    state = _load_state()
    job = next((j for j in state.get("jobs", []) if j.get("id") == job_id), None)
    if not job:
        return Recovery(handler="recollect_delta", job_id=job_id,
                        action_taken="noop", note=f"no job {job_id}", dry_run=dry_run)

    # Use fleet.py manifest --diff to detect mismatch.
    # Exit code 2 = mismatch (per fleet.py cmd_manifest); 0 = match.
    try:
        proc = subprocess.run(
            [sys.executable, str(_FLEET_PY),
             "manifest", str(job_id), "--diff"],
            cwd=_REPO_ROOT, capture_output=True, text=True, timeout=180,
        )
    except subprocess.TimeoutExpired:
        return Recovery(handler="recollect_delta", job_id=job_id, host=job.get("host"),
                        action_taken="escalated",
                        note="manifest --diff timed out; cannot decide", dry_run=dry_run)

    if proc.returncode == 0:
        return Recovery(handler="recollect_delta", job_id=job_id, host=job.get("host"),
                        action_taken="noop",
                        note="manifest diff shows no mismatch — nothing to recollect",
                        dry_run=dry_run)

    if _should_escalate("verify_mismatch", job_id=job_id):
        return Recovery(handler="recollect_delta", job_id=job_id, host=job.get("host"),
                        action_taken="skipped_due_to_threshold",
                        note=f"verify_mismatch alerts for job {job_id} in last "
                             f"{ESCALATION_WINDOW_HOURS}h >= {MAX_RETRIES_PER_CLASS}",
                        dry_run=dry_run)

    if dry_run:
        return Recovery(handler="recollect_delta", job_id=job_id, host=job.get("host"),
                        action_taken="would_recover",
                        note=f"manifest --diff rc={proc.returncode}; would run "
                             f"`fleet collect {job_id}` (resumes from .rsync-partial)",
                        dry_run=True)

    rc = subprocess.run([
        sys.executable, str(_FLEET_PY),
        "collect", str(job_id),
    ], cwd=_REPO_ROOT).returncode

    if rc == 0:
        append_event(JobEvent(
            event="auto_recovery",
            actor="cluster_state.recover.recollect_delta",
            job_id=job_id,
            host=job.get("host"),
            cohort=job.get("cohort"),
            details={"reason": "manifest --diff showed mismatch; re-collected delta",
                     "manifest_diff_rc": proc.returncode},
        ))
    return Recovery(handler="recollect_delta", job_id=job_id, host=job.get("host"),
                    action_taken=("state_edited" if rc == 0 else "escalated"),
                    note=f"fleet collect rc={rc}",
                    dry_run=False)


# ============================================================================
# Phase 6 — restore_source_dir
# ============================================================================

# Where to look for canonical source data on the external drive, in priority
# order. First hit wins. Sources beyond these need an operator decision.
_SOURCE_SEARCH_ORDER = (
    "live_data/iqfeed_data",   # data_storage canonical layout
    "uoa_emd_archive",         # post-2026-06-03 backups (my session)
    "AA2_IQKollect",           # legacy top-level mirror
    "LiveTrading",             # legacy top-level mirror
    "",                         # fallback: top-level lookup at $DATA_ROOT
)


def restore_source_dir(dir_name: str,
                       host: str,
                       dry_run: bool = True) -> Recovery:
    """Restore a missing source dir on ``host`` from canonical store on
    the external drive. This is a HIGH-impact recovery — it writes to the
    remote's repo dir. Opt-in only; never called by reconcile's auto loop
    without explicit ``--auto-restore``.

    Search order on external (first hit wins):
        $DATA_ROOT/live_data/iqfeed_data/<dir_name>/
        $DATA_ROOT/uoa_emd_archive/<dir_name>/
        $DATA_ROOT/AA2_IQKollect/<dir_name>/  (when dir_name is a file in there)
        $DATA_ROOT/LiveTrading/<dir_name>/
        $DATA_ROOT/<dir_name>/
    """
    data_root = _data_root()

    source: pathlib.Path | None = None
    for base in _SOURCE_SEARCH_ORDER:
        candidate = (data_root / base / dir_name) if base else (data_root / dir_name)
        if candidate.exists() and candidate.is_dir():
            source = candidate
            break

    if source is None:
        return Recovery(
            handler="restore_source_dir", host=host,
            action_taken="escalated",
            note=(f"{dir_name!r} not found in canonical store; searched "
                  f"{', '.join(_SOURCE_SEARCH_ORDER)}; manual recovery needed"),
            dry_run=dry_run,
        )

    hosts = _load_hosts()
    cfg = hosts.get(host)
    if not cfg or cfg.get("type") == "local":
        return Recovery(
            handler="restore_source_dir", host=host,
            action_taken="escalated",
            note=f"host {host!r} unknown in hosts.json (or marked local)",
            dry_run=dry_run,
        )

    repo = cfg.get("repo", "")
    if not repo:
        return Recovery(
            handler="restore_source_dir", host=host,
            action_taken="escalated",
            note=f"host {host!r} has no repo path in hosts.json",
            dry_run=dry_run,
        )

    # Windows path C:/Users/.. → MSYS /c/Users/.. for the remote rsync.
    msys_repo = re.sub(r"^([A-Za-z]):", lambda m: "/" + m.group(1).lower(), repo)
    dest = f"{cfg['ssh_alias']}:{msys_repo}/{dir_name}/"

    if dry_run:
        return Recovery(
            handler="restore_source_dir", host=host,
            action_taken="would_recover",
            note=f"would rsync {source}/ → {dest}",
            before={"source": str(source), "dest": dest, "size_bytes": _dir_size(source)},
            dry_run=True,
        )

    cmd = ["rsync", "-az", "--no-perms", "--no-owner", "--no-group",
           "--omit-dir-times", "--partial"]
    if cfg.get("rsync_path"):
        cmd += ["--rsync-path", cfg["rsync_path"]]
    cmd += [str(source) + "/", dest]
    rc = subprocess.run(cmd).returncode

    if rc == 0:
        # Post-restore verification: probe at least one file's presence
        verify_ok = False
        try:
            inner = next((p for p in source.rglob("*") if p.is_file()), None)
            if inner is not None:
                rel = inner.relative_to(source).as_posix()
                verify_ok = bool(_probe_remote_dir_exists(host, f"{repo}/{dir_name}/{rel}"))
        except StopIteration:
            verify_ok = True  # empty dir; nothing to verify
        action = "state_edited" if verify_ok else "escalated"
        append_event(JobEvent(
            event="auto_recovery",
            actor="cluster_state.recover.restore_source_dir",
            host=host,
            details={"reason": f"restored source dir {dir_name!r} from {source}",
                     "source": str(source),
                     "dest": dest,
                     "rsync_rc": rc,
                     "post_verify_ok": verify_ok},
        ))
        return Recovery(handler="restore_source_dir", host=host,
                        action_taken=action,
                        note=f"rsync rc=0; post-verify={'ok' if verify_ok else 'FAIL'}",
                        dry_run=False)
    return Recovery(handler="restore_source_dir", host=host,
                    action_taken="escalated",
                    note=f"rsync rc={rc} — restore failed",
                    dry_run=False)


def _dir_size(path: pathlib.Path) -> int:
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
    except OSError:
        pass
    return total
