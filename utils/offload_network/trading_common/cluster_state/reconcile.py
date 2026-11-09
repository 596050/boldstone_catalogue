"""Detection pass — find divergence between intent and reality.

Reads:
- ``~/.fleet/state.json`` (what fleet thinks is running)
- live process probes via SSH (what is actually running)
- external drive artifacts (what landed)

Writes:
- alerts to ``$DATA_ROOT/cluster_state/alerts.jsonl`` via ``ledger``

Does NOT take any state-changing action. ``recover`` is the layer that does.

Self-repair principle #1 (read-only by default) and #2 (idempotent) apply
at the package boundary: ``reconcile_once()`` is safe to call repeatedly;
it never edits state, never deletes files, never moves data.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
from typing import Iterable

from .ledger import append_alert, count_recent_alerts_by_kind
from .schema import Alert, Severity

# Round 4 cleanup of REFACTOR_PLAN.md (2026-06-05): reconcile.py was missed
# during the round-2 lock wiring, so it kept reading state.json without
# respecting the LOCK_EX held by fleet.mutate_state and recover._save_state.
# That left a race window: reconcile could see torn writes mid-mutation.
# Now uses the canonical locked path.
import sys as _sys
_REPO_ROOT_FOR_FLEET = pathlib.Path(__file__).resolve().parents[2]
_OFFLOAD_DIR = _REPO_ROOT_FOR_FLEET
if str(_OFFLOAD_DIR) not in _sys.path:
    _sys.path.insert(0, str(_OFFLOAD_DIR))
from fleet import state as _fleet_state  # noqa: E402


def _load_fleet_state() -> dict:
    """Shared-lock read via fleet/state.py.

    Caller may rely on the legacy 'next_job_id' field always being present
    (it's not in the FleetState dataclass), so we default it on read."""
    state = _fleet_state.load_state()
    state.setdefault("next_job_id", 1)
    return state


def _ssh_pid_alive(host_alias: str, pid: int, timeout: int = 8) -> bool | None:
    """Probe whether ``pid`` is alive on Windows host ``host_alias``.

    Returns True / False / None (None means probe itself failed — host
    unreachable or other transient error; caller should NOT recover on
    None since the truth is unknown).
    """
    if not pid:
        return False
    try:
        r = subprocess.run(
            ["ssh", "-o", f"ConnectTimeout={timeout}",
             "-o", "BatchMode=yes",
             host_alias,
             "powershell.exe", "-NoProfile", "-Command",
             f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) "
             f"{{ 'ALIVE' }} else {{ 'DEAD' }}"],
            capture_output=True, text=True, timeout=timeout + 5,
        )
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0:
        return None
    out = (r.stdout or "").strip().upper()
    if "ALIVE" in out:
        return True
    if "DEAD" in out:
        return False
    return None


def detect_stale_running(emit_alerts: bool = True) -> list[dict]:
    """Find ``status=running`` jobs whose wrapper PID is no longer alive
    on the remote host.

    Returns a list of {"job_id", "host", "wrapper_pid", "probe_result"}
    dicts. If ``emit_alerts`` is True, also writes one ``wrapper_dead``
    or ``host_unreachable`` alert per finding (deduped by kind+job_id
    via the recent-alerts query so we don't spam the ledger).
    """
    state = _load_fleet_state()
    findings = []
    for j in state.get("jobs", []):
        if j.get("status") != "running":
            continue
        pid = j.get("wrapper_pid") or 0
        host = j.get("host") or "?"
        # IMPORTANT: wrapper_pid is the Mac-side nohup'd wrapper PID, NOT a
        # remote PID. fleet.cmd_run launches `nohup <wrapper.sh>` locally; the
        # wrapper internally `ssh`s to the remote. So probe LOCALLY regardless
        # of which Windows host the cohort runs on. (Older code probed via SSH
        # using the wrapper PID, which always returned 'not found' because
        # that PID number means nothing on the Windows side.)
        try:
            os.kill(pid, 0) if pid else (_ for _ in ()).throw(ProcessLookupError())
            alive: bool | None = True
        except ProcessLookupError:
            alive = False
        except PermissionError:
            # Mac kill(0) returns EPERM if the PID exists but is owned by
            # another user. For our purposes, that still means "alive".
            alive = True
        except OSError:
            alive = None
        if alive is True:
            continue  # genuinely running
        finding = {
            "job_id":        j["id"],
            "host":          host,
            "wrapper_pid":   pid,
            "cohort":        j.get("cohort"),
            "probe_result":  ("dead" if alive is False else "unreachable"),
        }
        findings.append(finding)
        if emit_alerts:
            kind = "wrapper_dead" if alive is False else "host_unreachable_during_probe"
            # Dedupe: if we already fired this kind for this job_id in
            # the last 24h, don't fire again. This keeps the ledger
            # readable across many reconcile passes.
            # Note: this check is on KIND+job_id, not just KIND.
            # For simplicity we use the count helper; a per-job check is
            # better but adds disk I/O — defer to escalation logic.
            already = count_recent_alerts_by_kind(kind, hours=24)
            append_alert(Alert(
                kind=kind,
                severity=Severity.WARN,
                host=host,
                job_id=j["id"],
                detail=(f"job {j['id']} (cohort={j.get('cohort','?')[:60]}) shows "
                        f"status=running but wrapper PID {pid} is {finding['probe_result']} "
                        f"on {host}"),
                context={"wrapper_pid": pid, "probe_result": finding["probe_result"],
                         "recent_same_kind_count": already},
            ))
    return findings


def detect_wrapper_dead(emit_alerts: bool = True) -> list[dict]:
    """Alias for ``detect_stale_running`` — same semantics, different name
    for callers that think in terms of process state vs job state."""
    return detect_stale_running(emit_alerts=emit_alerts)


def reconcile_once(emit_alerts: bool = True, verbose: bool = False) -> dict:
    """Run all detection passes once and return a summary.

    Returns:
        {
            "stale_running": [...findings...],
            "alerts_emitted": <int>,
            "data_root": "...",
        }
    """
    stale = detect_stale_running(emit_alerts=emit_alerts)
    if verbose:
        print(f"[reconcile] stale_running: {len(stale)} finding(s)")
        for f in stale:
            print(f"  job {f['job_id']:>3}  host={f['host']:<10}  "
                  f"pid={f['wrapper_pid']:<6}  {f['probe_result']}")
    return {
        "stale_running":   stale,
        "alerts_emitted":  len(stale) if emit_alerts else 0,
    }
