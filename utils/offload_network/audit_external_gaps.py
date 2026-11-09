#!/usr/bin/env python3
"""audit_external_gaps.py — promoted from /tmp/gap_analysis_external.py.

P3 promotion from the 2026-06-05 scripts audit. Finds every fleet-offload
data piece on every remote that is NOT mirrored on the external HDD.
Categorises as:
  - PIPELINE OUTPUTS (random_windows_<cohort>/ with .mat files)
  - SOURCE DATA      (AA2_IQKollect, *_UOA-EMD, iqfeed_data, LiveTrading)
  - RESEARCH ARTIFACTS (ig_trading/cache_replay, adaptive_strategy, etc.)

Uses the post-2026-06-05 external layout:
  research_data/c_emd/window_replays/   ← cohort outputs go here now
  archive/                              ← migrated workspace snapshots
  uoa_emd_archive/ + archive/research/local_uoa_emd/  ← source data mirror

Usage:
  python3 audit_external_gaps.py            # human-readable report
  python3 audit_external_gaps.py --json     # machine-readable
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor

# Priority 3 from REFACTOR_PLAN.md (2026-06-05): use shared lib.remote.ps
# instead of reimplementing the SSH+UTF-16-LE-base64 encoding inline.
_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from lib.remote import ps as _ps  # noqa: E402


# Host probe map — keep in sync with remote_state_audit.py
HOSTS = [
    ("scan-amd64-w11", "~/.ssh/id_ed25519_kenne",     "kenne",   r"C:\Users\Kenneth\Downloads", "kenne"),
    ("cdec-24core",    "~/.ssh/id_ed25519_cdec",      "kenne",   r"C:\Users\kenne\Downloads",   "cdec"),
    ("scan-xeon",      "~/.ssh/id_ed25519_scan-xeon", "Kenneth", r"C:\Users\Kenneth\Downloads", "scan-xeon"),
    ("100.99.157.53",  "~/.ssh/id_ed25519_scan-new",  "kenne",   r"C:\Users\kenne\Downloads",   "scan-new"),
]


def probe_host(ssh_alias: str, identity: str, user: str, downloads: str, label: str):
    """SSH+PowerShell probe of one host for cohort/source/ig artefacts."""
    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$downloads = '{downloads}'

# A) Pipeline outputs (random_windows_* with .mat files)
Write-Output '--- PIPELINE OUTPUTS ---'
$bases = @($downloads, "$downloads\\offload")
foreach ($base in $bases) {{
    if (-not (Test-Path $base)) {{ continue }}
    Get-ChildItem $base -Directory -Filter 'fleet-offload*' -ErrorAction SilentlyContinue | ForEach-Object {{
        $top = $_
        @((Join-Path $top.FullName 'c_emd\\results'),
          (Join-Path $top.FullName 'repo\\c_emd\\results')) | ForEach-Object {{
            $r = $_
            if (-not (Test-Path $r)) {{ return }}
            Get-ChildItem $r -Directory -ErrorAction SilentlyContinue | ForEach-Object {{
                $coh = $_
                $mats = Get-ChildItem $coh.FullName -File -Filter *.mat -ErrorAction SilentlyContinue
                if ($mats.Count -gt 0) {{
                    $sz = ($mats | Measure-Object -Property Length -Sum).Sum
                    Write-Output "COHORT|$($top.Name)|$($coh.Name)|$($mats.Count)|$sz"
                }}
            }}
        }}
    }}
}}

# B) Source data dirs
Write-Output '--- SOURCE DATA ---'
$canon = "$downloads\\fleet-offload"
if (Test-Path $canon) {{
    $src_patterns = @('AA2_IQKollect','*_UOA-EMD','iqfeed_data','LiveTrading')
    foreach ($pat in $src_patterns) {{
        Get-ChildItem $canon -Directory -Filter $pat -ErrorAction SilentlyContinue | ForEach-Object {{
            $sz = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
            $n = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
            Write-Output "SOURCE|$($_.Name)|$n|$sz"
        }}
    }}
}}

# C) IG_trading research artifacts
Write-Output '--- IG_TRADING + CACHE_REPLAY ---'
$ig_path = "$canon\\c_emd\\results\\ig_trading"
if (Test-Path $ig_path) {{
    Get-ChildItem $ig_path -Directory -ErrorAction SilentlyContinue | ForEach-Object {{
        $sz = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        $n = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
        Write-Output "IG|$($_.Name)|$n|$sz"
    }}
}}
"""
    try:
        r = _ps(
            ssh_alias, script,
            timeout=300, identity=identity, user=user,
            connect_timeout=15, no_control_master=True,
            silence_progress=False,        # script does its own ErrorActionPreference
        )
        return label, r.stdout, r.stderr
    except Exception as e:
        return label, "", str(e)


def build_external_inventory(ext_root: pathlib.Path):
    """Build sets of cohort names, source dirs, ig_trading dirs on external."""
    cohorts: set[str] = set()
    for p in [ext_root / "research_data" / "c_emd" / "window_replays",
              ext_root / "research_data" / "c_emd" / "window_replays" / "from_legacy_c_emd",
              ext_root / "research_data" / "c_emd" / "window_replays" / "from_live_data",
              ext_root / "live_data" / "c_emd" / "results" / "random_windows"]:
        if p.exists():
            cohorts.update(d.name for d in p.iterdir() if d.is_dir())

    sources: set[str] = set()
    for top in ("AA2_IQKollect", "iqfeed_data", "LiveTrading"):
        if (ext_root / top).exists():
            sources.add(top)
    for sub in ("uoa_emd_archive", "archive/research/local_uoa_emd"):
        p = ext_root / sub
        if p.exists():
            sources.update(d.name for d in p.iterdir() if d.is_dir())

    ig: set[str] = set()
    for p in [ext_root / "live_data" / "c_emd" / "results" / "ig_trading",
              ext_root / "research_data" / "c_emd" / "results" / "ig_trading"]:
        if p.exists():
            ig.update(d.name for d in p.iterdir() if d.is_dir())

    return cohorts, sources, ig


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--ext-root",
                    default="/Volumes/Untitled/offload_data",
                    help="external HDD root (default: /Volumes/Untitled/offload_data)")
    args = ap.parse_args()

    ext_root = pathlib.Path(args.ext_root)
    print(f"Probing {len(HOSTS)} remotes in parallel ...", file=sys.stderr)

    results: dict[str, tuple[str, str]] = {}
    with ThreadPoolExecutor(max_workers=len(HOSTS)) as ex:
        futures = [ex.submit(probe_host, *h) for h in HOSTS]
        for f in futures:
            label, out, err = f.result()
            results[label] = (out, err)

    ext_cohorts, ext_sources, ext_ig = build_external_inventory(ext_root)

    totals = {"COHORT": 0, "SOURCE": 0, "IG": 0}
    missing = {"COHORT": [], "SOURCE": [], "IG": []}

    for host, (out, _err) in results.items():
        for line in out.splitlines():
            if "|" not in line:
                continue
            parts = line.split("|")
            kind = parts[0]
            if kind == "COHORT" and len(parts) == 5:
                _, top, name, nfiles, size = parts
                if name not in ext_cohorts:
                    missing["COHORT"].append((host, top, name, int(nfiles), int(size)))
                    totals["COHORT"] += int(size)
            elif kind == "SOURCE" and len(parts) == 4:
                _, name, nfiles, size = parts
                if name not in ext_sources:
                    missing["SOURCE"].append((host, name, int(nfiles), int(size)))
                    totals["SOURCE"] += int(size)
            elif kind == "IG" and len(parts) == 4:
                _, name, nfiles, size = parts
                if name not in ext_ig:
                    missing["IG"].append((host, name, int(nfiles), int(size)))
                    totals["IG"] += int(size)

    if args.json:
        print(json.dumps({
            "external_known": {
                "pipeline_cohorts": len(ext_cohorts),
                "source_dirs":      len(ext_sources),
                "ig_trading_dirs":  len(ext_ig),
            },
            "missing": {k: [{"host": x[0], "container": x[1] if k == "COHORT" else None,
                             "name": x[-3], "n_files": x[-2], "size_bytes": x[-1]}
                            for x in v]
                        for k, v in missing.items()},
            "totals_gb": {k: v / 1e9 for k, v in totals.items()},
        }, indent=2))
        return 0

    print(f"\n=== EXTERNAL HDD KNOWS ===")
    print(f"  pipeline cohorts: {len(ext_cohorts)}")
    print(f"  source dirs:      {len(ext_sources)}")
    print(f"  ig_trading dirs:  {len(ext_ig)}")

    print(f"\n=== UNIQUE-TO-REMOTE (would be lost if remote deleted) ===\n")
    for kind, label in [("COHORT", "PIPELINE OUTPUTS"),
                        ("SOURCE", "SOURCE DATA"),
                        ("IG", "IG_TRADING / RESEARCH ARTIFACTS")]:
        items = missing[kind]
        if not items:
            print(f"  {label}:  ✓ all on external")
            continue
        print(f"  {label}  ({totals[kind]/1e9:.2f} GB total, {len(items)} items):")
        for item in sorted(items, key=lambda x: -x[-1])[:20]:
            if kind == "COHORT":
                host, top, name, n, sz = item
                print(f"    {sz/1e9:>7.2f} GB  {n:>4} mats  {host:9s}  {top:30s}  {name}")
            else:
                host, name, n, sz = item
                print(f"    {sz/1e9:>7.2f} GB  {n:>5} files  {host:9s}  {name}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
