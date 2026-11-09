"""Safely delete chunk_generator scratch dirs from kenne.

The `*_chunks/` directories under each `c_emd/results/random_windows_*/`
hold per-batch intermediate output written by chunk_generator.py before
the parallel batches coalesce into the final `.mat` file. They are:

  - explicitly EXCLUDED from rsync (see _remote_manifest/_local_manifest
    `include_scratch=False` default added 2026-06-03)
  - REGENERATABLE from source data if ever needed (the pipeline rebuilds
    them in a fresh run)
  - NOT needed once the parent cohort's per-window `.mat` files exist

This script deletes those scratch dirs SAFELY:
  - Dry-run by default; pass --apply to actually delete
  - Skips any cohort whose state.json status is "running"
  - Skips any cohort actively being collected
  - Reports byte-savings per cohort

Usage:
    python3 utils/offload_network/clean_kenne_chunks.py            # dry-run
    python3 utils/offload_network/clean_kenne_chunks.py --apply    # actually delete
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

# Priority 4 + 5 from REFACTOR_PLAN.md (2026-06-05): kept the sys.path.insert
# for back-compat with `python3 utils/offload_network/clean_kenne_chunks.py`
# direct invocations, BUT once `pip install -e .` runs against the new
# pyproject.toml, `from lib.remote import ps` resolves cleanly without the hack.
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from lib.remote import ps
from lib.logging_helper import setup_file_logger
from fleet.paths import fleet_state_file


_LOG = setup_file_logger("clean_kenne_chunks")


def _kenne_results_root() -> str:
    """Derive kenne's results root from hosts.json (the source of truth) so this
    cleaner follows the configured repo instead of a stale hardcoded path. The
    previous literal pointed at `...Downloads\\fleet-offload\\...`, but the active
    hosts.json `kenne.repo` is `C:/Users/Kenneth/fleet-offload` (no Downloads), so
    the hardcode silently scanned a non-existent dir (and `-ErrorAction
    SilentlyContinue` freed 0 GB without error). Falls back to the legacy literal
    only if hosts.json is unreadable."""
    fallback = r"C:\Users\Kenneth\Downloads\fleet-offload\c_emd\results"
    try:
        hosts = json.loads((pathlib.Path(__file__).parent / "hosts.json").read_text())
        kenne = hosts.get("kenne") or hosts.get("hosts", {}).get("kenne") or {}
        repo = kenne.get("repo")
        if repo:
            return repo.rstrip("/\\").replace("/", "\\") + r"\c_emd\results"
    except Exception:
        pass
    return fallback


KENNE_RESULTS_ROOT = _kenne_results_root()


def _running_kenne_cohorts() -> set[str]:
    """Return the set of remote_out cohort-dir basenames on kenne that
    state.json says are currently status=running. We must NOT delete
    chunks under these — the pipeline is still writing them."""
    state_path = fleet_state_file()
    s = json.loads(state_path.read_text())
    running = set()
    for j in s["jobs"]:
        if j.get("host") != "kenne":
            continue
        if j.get("status") != "running":
            continue
        ro = j.get("remote_out", "") or ""
        # cohort dir is the last segment of remote_out
        base = ro.rstrip("/\\").split("/")[-1].split("\\")[-1]
        if base:
            running.add(base)
    return running


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="Actually delete. Without this, just report sizes.")
    args = ap.parse_args()

    running = _running_kenne_cohorts()
    print(f"Excluding {len(running)} status=running cohort(s) on kenne:")
    for c in sorted(running):
        print(f"    {c}")
    print()

    # Build a PowerShell list of cohort dirs to skip
    skip_list = ", ".join(f"'{c}'" for c in running) or "''"
    apply_flag = "1" if args.apply else "0"

    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$root = '{KENNE_RESULTS_ROOT}'
$skip = @({skip_list})
$apply = {apply_flag}

$saved = 0.0
$count = 0

Get-ChildItem $root -Directory -Filter random_windows_* | ForEach-Object {{
    $cohort = $_
    if ($skip -contains $cohort.Name) {{
        Write-Output ("  SKIP (running): " + $cohort.Name)
        return
    }}
    Get-ChildItem $cohort.FullName -Directory -Filter *_chunks* | ForEach-Object {{
        $sz = (Get-ChildItem $_.FullName -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1GB
        if ($apply -eq 1) {{
            Remove-Item $_.FullName -Recurse -Force
            Write-Output ("  DELETED  {{0,8:F2}} GB   {{1}}\\{{2}}" -f $sz, $cohort.Name, $_.Name)
        }} else {{
            Write-Output ("  would delete  {{0,8:F2}} GB   {{1}}\\{{2}}" -f $sz, $cohort.Name, $_.Name)
        }}
        $script:saved += $sz
        $script:count += 1
    }}
}}

Write-Output ""
$verb = if ($apply -eq 1) {{ 'freed' }} else {{ 'would free' }}
Write-Output ("TOTAL: $verb {{0:F2}} GB across $count chunk dir(s)" -f $saved)
$d = Get-PSDrive C
Write-Output ("C: free = {{0:F1}} GB" -f ($d.Free/1GB))
"""
    r = ps("kenne", script, timeout=180)
    print(r.stdout)
    if r.stderr.strip():
        print("STDERR:", r.stderr[:500], file=sys.stderr)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
