#!/usr/bin/env python3
"""remote_state_audit.py — comprehensive snapshot of every fleet-offload remote.

For each host in HOSTS, probes via SSH+PowerShell:
  1. fleet-offload* dirs under user's Downloads — size + file count + last-write
  2. cohort dirs (random_windows_*) — classified as ACTIVE / STALE / DONE
     based on `*_chunks/` presence and newest .mat write age:
       ACTIVE  — chunks present, last write < 60 min ago (worker actively writing)
       STALE   — chunks present, last write > 60 min ago (likely dead/orphaned)
       DONE    — no chunks (pipeline finished coalescing into .mat files)
  3. active python.exe process count (rough proxy for pipeline workers)
  4. C: drive free space

Persists the run to ~/.fleet/remote_state_audit.json so the next call can
compute deltas like "+2 mats since last" and detect stalling cohorts whose
last-write age grew between runs.

Output modes:
  default          — pretty-printed text report with emojis + delta callouts
  --json           — machine-readable JSON of full state
  --no-save        — skip writing state file (won't break next diff)

Usage:
  python3 utils/offload_network/remote_state_audit.py
  python3 utils/offload_network/remote_state_audit.py --json > snap.json
  python3 utils/offload_network/remote_state_audit.py --no-save

NOTE: this is the LEGACY pre-orchestrator audit. The
``trading_common/orchestrator/`` package will subsume + extend this
(persistent catalog, lineage queries, recommendation rules). Keep this
script as the working reference of the SSH+PowerShell probe pattern
even after the new structure ships.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from fleet.paths import remote_state_audit_path

# Priority 3 from REFACTOR_PLAN.md (2026-06-05): use the shared
# lib.remote.ps() encoder instead of reimplementing base64-utf16-le SSH
# invocation per script. Eliminates the family of quoting bugs we hit
# repeatedly during the 2026-06-04/05 session.
_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from lib.remote import ps as _ps  # noqa: E402


# ----------------------------------------------------------------------------
# HOST INVENTORY — modify this when the fleet membership changes
# ----------------------------------------------------------------------------
HOSTS: list[dict] = [
    {
        "label":      "kenne",
        "ssh_alias":  "scan-amd64-w11",
        "identity":   "~/.ssh/id_ed25519_kenne",
        "user":       "kenne",
        "downloads":  r"C:\Users\Kenneth\Downloads",
        # cohort_root = workspace + \c_emd\results
        "workspace":  r"C:\Users\Kenneth\Downloads\fleet-offload",
        "cohort_root_relative_to_workspace": r"c_emd\results",
    },
    {
        "label":      "cdec",
        "ssh_alias":  "cdec-24core",
        "identity":   "~/.ssh/id_ed25519_cdec",
        "user":       "kenne",
        "downloads":  r"C:\Users\kenne\Downloads",
        "workspace":  r"C:\Users\kenne\Downloads\fleet-offload",
        "cohort_root_relative_to_workspace": r"c_emd\results",
    },
    {
        "label":      "scan-xeon",
        "ssh_alias":  "scan-xeon",
        "identity":   "~/.ssh/id_ed25519_scan-xeon",
        "user":       "Kenneth",
        "downloads":  r"C:\Users\Kenneth\Downloads",
        # scan-xeon's real workspace is INSIDE the offload-20260601 dir:
        "workspace":  r"C:\Users\Kenneth\Downloads\fleet-offload",
        "cohort_root_relative_to_workspace": r"repo\c_emd\results",
    },
    {
        "label":      "scan-new",
        "ssh_alias":  "100.99.157.53",
        "identity":   "~/.ssh/id_ed25519_scan-new",
        "user":       "kenne",
        "downloads":  r"C:\Users\kenne\Downloads",
        "workspace":  r"C:\Users\kenne\Downloads\fleet-offload",
        "cohort_root_relative_to_workspace": r"c_emd\results",
    },
]

STATE_FILE = remote_state_audit_path()

STALE_THRESHOLD_MIN = 60   # cohort with chunks/ but >60 min since last write = stale


# ----------------------------------------------------------------------------
# Dataclasses
# ----------------------------------------------------------------------------
@dataclass
class CohortStatus:
    name:    str
    chunks:  int
    mats:    int
    age_min: float          # -1 if empty

    @property
    def status(self) -> str:
        if self.chunks == 0:
            return "DONE"
        if self.age_min < 0:
            return "EMPTY"
        if self.age_min > STALE_THRESHOLD_MIN:
            return "STALE"
        return "ACTIVE"

    @property
    def emoji(self) -> str:
        return {"ACTIVE": "🟢", "STALE": "🔴", "DONE": "✓", "EMPTY": "?"}[self.status]


@dataclass
class HostStatus:
    label:        str
    ssh_alias:    str
    dirs:         list = field(default_factory=list)   # [{name, size_bytes, file_count, last_write}]
    cohorts:      list[CohortStatus] = field(default_factory=list)
    proc_count:   int = 0
    disk_free_gb: float = 0.0
    probed_at:    str = ""
    error:        str = ""

    def as_dict(self) -> dict:
        return {
            "label":        self.label,
            "ssh_alias":    self.ssh_alias,
            "dirs":         self.dirs,
            "cohorts":      [asdict(c) for c in self.cohorts],
            "proc_count":   self.proc_count,
            "disk_free_gb": self.disk_free_gb,
            "probed_at":    self.probed_at,
            "error":        self.error,
        }


# ----------------------------------------------------------------------------
# PowerShell probe (UTF-16-LE base64 encoded — avoids SSH quoting hell)
# ----------------------------------------------------------------------------
def build_probe_script(host: dict) -> str:
    downloads   = host["downloads"]
    workspace   = host["workspace"]
    cohort_root = workspace + "\\" + host["cohort_root_relative_to_workspace"]
    return f"""
$ErrorActionPreference = 'SilentlyContinue'
$now = Get-Date

# --- 1. fleet-offload* directories in Downloads ---
Get-ChildItem '{downloads}' -Directory -Filter 'fleet-offload*' -ErrorAction SilentlyContinue |
    Sort-Object Name | ForEach-Object {{
    $files = Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue
    $sz = ($files | Measure-Object -Property Length -Sum).Sum
    $n = ($files | Measure-Object).Count
    Write-Output ("DIR|" + $_.Name + "|" + $sz + "|" + $n + "|" + $_.LastWriteTime.ToString('o'))
}}

# --- 2. cohort dirs (random_windows_*) ---
if (Test-Path '{cohort_root}') {{
    Get-ChildItem '{cohort_root}' -Directory -Filter 'random_windows_*' -ErrorAction SilentlyContinue | ForEach-Object {{
        $coh = $_
        $chunks = (Get-ChildItem $coh.FullName -Directory -Filter *_chunks* -ErrorAction SilentlyContinue | Measure-Object).Count
        $mats = (Get-ChildItem $coh.FullName -File -Filter *.mat -ErrorAction SilentlyContinue | Measure-Object).Count
        $newest = Get-ChildItem $coh.FullName -Recurse -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        $age_min = if ($newest) {{ [math]::Round(($now - $newest.LastWriteTime).TotalMinutes, 1) }} else {{ -1 }}
        Write-Output ("COHORT|" + $coh.Name + "|" + $chunks + "|" + $mats + "|" + $age_min)
    }}
}}

# --- 3. python.exe count (pipeline workers) ---
$py = Get-Process python -ErrorAction SilentlyContinue
Write-Output ("PROCS|" + ($py | Measure-Object).Count)

# --- 4. Disk free on C: ---
$d = Get-PSDrive C
Write-Output ("DISK|" + [math]::Round($d.Free / 1GB, 2))
"""


def probe_host(host: dict, ssh_timeout: int = 300) -> HostStatus:
    """SSH to one host via shared lib.remote.ps() and return its HostStatus."""
    script = build_probe_script(host)
    probed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        r = _ps(
            host["ssh_alias"], script,
            timeout=ssh_timeout,
            identity=host["identity"], user=host["user"],
            connect_timeout=20, no_control_master=True,
            text=False,                       # CLIXML progress can be non-utf8
            silence_progress=False,           # script does its own ErrorActionPreference
        )
        stdout = r.stdout.decode("utf-8", errors="replace")
    except Exception as e:
        return HostStatus(
            label=host["label"], ssh_alias=host["ssh_alias"],
            probed_at=probed_at,
            error="timeout after %ds" % ssh_timeout if "Timeout" in type(e).__name__ else str(e),
        )

    status = HostStatus(label=host["label"], ssh_alias=host["ssh_alias"], probed_at=probed_at)
    for line in stdout.strip().splitlines():
        parts = line.split("|")
        try:
            if parts[0] == "DIR" and len(parts) == 5:
                status.dirs.append({
                    "name":       parts[1],
                    "size_bytes": int(parts[2] or 0),
                    "file_count": int(parts[3] or 0),
                    "last_write": parts[4],
                })
            elif parts[0] == "COHORT" and len(parts) == 5:
                status.cohorts.append(CohortStatus(
                    name=parts[1], chunks=int(parts[2]),
                    mats=int(parts[3]), age_min=float(parts[4]),
                ))
            elif parts[0] == "PROCS" and len(parts) == 2:
                status.proc_count = int(parts[1])
            elif parts[0] == "DISK" and len(parts) == 2:
                status.disk_free_gb = float(parts[1])
        except Exception:
            continue
    return status


# ----------------------------------------------------------------------------
# Persistence (so next run can diff)
# ----------------------------------------------------------------------------
def load_previous() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_current(states: list[HostStatus]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(
        {s.label: s.as_dict() for s in states},
        indent=2, default=str,
    ))


# ----------------------------------------------------------------------------
# Render (human-readable with delta callouts + risk surfacing)
# ----------------------------------------------------------------------------
def _delta_int(prev, curr) -> str:
    if prev is None:
        return ""
    d = curr - prev
    if d == 0:
        return "(unchanged)"
    return f"(was {prev}, {'+' if d > 0 else ''}{d})"


def _delta_gb(prev_bytes, curr_bytes) -> str:
    if prev_bytes is None:
        return ""
    d_gb = (curr_bytes - prev_bytes) / 1e9
    if abs(d_gb) < 0.01:
        return "(unchanged)"
    return f"({'+' if d_gb > 0 else ''}{d_gb:.2f} GB since last)"


def render(states: list[HostStatus], prev: dict) -> list[str]:
    """Returns list of risk strings (for callers + final summary section)."""
    risks: list[str] = []
    for s in states:
        prev_s = prev.get(s.label, {})

        if s.error:
            print(f"\n🔴 {s.label} ({s.ssh_alias}) — UNREACHABLE: {s.error}\n")
            risks.append(f"{s.label}: probe failed — {s.error}")
            continue

        # Top-level emoji from cohort statuses
        statuses = {c.status for c in s.cohorts}
        if "STALE" in statuses:
            top_emoji = "⚠️ "
        elif "ACTIVE" in statuses:
            top_emoji = "🟢"
        elif not s.cohorts and s.proc_count == 0:
            top_emoji = "💤"
        else:
            top_emoji = "🟢"
        print(f"\n{top_emoji} {s.label} ({s.ssh_alias})")
        print()

        # fleet-offload* dirs
        for d in s.dirs:
            prev_d = next((pd for pd in prev_s.get("dirs", []) if pd["name"] == d["name"]), None)
            prev_sz = prev_d["size_bytes"] if prev_d else None
            delta = _delta_gb(prev_sz, d["size_bytes"])
            print(f"  {d['name']:35s}  {d['size_bytes']/1e9:>7.2f} GB / {d['file_count']:>5} files  {delta}")

        # Cohorts
        if s.cohorts:
            print()
            for c in s.cohorts:
                prev_c = next((pc for pc in prev_s.get("cohorts", []) if pc["name"] == c.name), None)
                mat_delta = ""
                stall_note = ""
                if prev_c:
                    m_diff = c.mats - prev_c["mats"]
                    if m_diff > 0:
                        mat_delta = f" (+{m_diff} since last)"
                    elif m_diff == 0 and c.status == "ACTIVE":
                        age_grow = c.age_min - prev_c["age_min"]
                        if age_grow > 10:
                            stall_note = f" — was {prev_c['age_min']:.1f} min, now {c.age_min:.1f} min — SLOWING"
                            risks.append(f"{s.label}/{c.name}: 0 mat progress, write-age grew {prev_c['age_min']:.0f}→{c.age_min:.0f} min — slowing")
                if c.status == "STALE":
                    risks.append(f"{s.label}/{c.name}: STALE — {c.chunks} chunks, {c.mats} mats, last write {c.age_min/60:.1f}h ago")

                age_str = (f"write {c.age_min:.1f} min ago" if c.age_min < 60
                           else f"write {c.age_min/60:.1f} h ago")
                print(f"  {c.emoji} {c.status:6s}  {c.chunks:>2} chunks  {c.mats:>3} mats   "
                      f"{c.name:55s}   {age_str}{mat_delta}{stall_note}")

        # Process count + disk
        prev_procs = prev_s.get("proc_count")
        prev_disk  = prev_s.get("disk_free_gb")
        print()
        print(f"  processes:  {s.proc_count} python.exe  {_delta_int(prev_procs, s.proc_count)}")
        if prev_disk is not None:
            disk_delta = f"(was {prev_disk:.2f} GB, {'+' if (s.disk_free_gb - prev_disk) > 0 else ''}{s.disk_free_gb - prev_disk:.2f} GB)"
        else:
            disk_delta = ""
        print(f"  disk:       {s.disk_free_gb:.2f} GB free  {disk_delta}")

    # Risk summary
    print()
    if risks:
        print("\n=== RISKS / WATCH-POINTS ===")
        for r in risks:
            print(f"  ⚠️  {r}")
    else:
        print("\n=== NO RISKS — all cohorts healthy ===")
    print()
    return risks


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true",
                    help="emit JSON instead of human-readable report")
    ap.add_argument("--no-save", action="store_true",
                    help="don't persist this run to disk (next call won't diff against it)")
    ap.add_argument("--hosts", nargs="+",
                    help="probe only these host labels (default: all in HOSTS)")
    ap.add_argument("--ssh-timeout", type=int, default=300)
    args = ap.parse_args()

    targets = HOSTS
    if args.hosts:
        targets = [h for h in HOSTS if h["label"] in args.hosts]
        if not targets:
            print(f"no matching hosts in {[h['label'] for h in HOSTS]}", file=sys.stderr)
            return 1

    print(f"Probing {len(targets)} remote(s) in parallel...", file=sys.stderr)
    states: list[HostStatus] = []
    with ThreadPoolExecutor(max_workers=len(targets)) as ex:
        futures = [ex.submit(probe_host, h, args.ssh_timeout) for h in targets]
        for f in futures:
            states.append(f.result())

    if args.json:
        print(json.dumps({s.label: s.as_dict() for s in states},
                         indent=2, default=str))
    else:
        prev = load_previous()
        render(states, prev)

    if not args.no_save:
        save_current(states)
    return 0


if __name__ == "__main__":
    sys.exit(main())
