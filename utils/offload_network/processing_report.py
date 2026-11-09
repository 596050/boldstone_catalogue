#!/usr/bin/env python3
"""processing_report.py — generate the 4-layer cluster-processing report.

Layers:
  1. Computation types (42 work types, 10 categories)
  2. Artifact types (14 types, 6 categories)
  3. Lifecycle states (the WorkStatus enum + transient states)
  4. Cross-host distribution (who runs what)

The taxonomy is static (embedded below). Live enrichment overlays each work
type with current status (ACTIVE / IDLE / DONE / STALE) by:
  - reading ~/.fleet/state.json for jobs
  - reading ~/.fleet/remote_state_audit.json for last-known cohort state
  - invoking remote_state_audit.py if --probe is passed (slow, 1-2 min)

Output modes:
  default          — full 4-layer human-readable report
  --layers 1 4     — only layers 1 + 4
  --markdown       — markdown tables (suitable for copy-paste into docs)
  --json           — machine-readable JSON
  --probe          — re-probe all remotes live (else use cached audit state)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from fleet.paths import fleet_dir


# ============================================================================
# LAYER 1 — Computation types (the taxonomy)
# ============================================================================
@dataclass
class WorkTypeDef:
    n: int
    category: str
    name: str
    what_produces_it: str
    where_it_ran: str
    memory_ref: str
    # Live state (filled in at runtime if --probe or cached audit available)
    current_status: str = ""

LAYER1: list[WorkTypeDef] = [
    # Data ingestion
    WorkTypeDef(1, "Data ingestion", "download", "IQFeed historical pull (1-min bars, ticks)", "scan-xeon (1min_bars), cdec, kenne", "iqfeed_data/ dirs"),
    WorkTypeDef(2, "Data ingestion", "download_tick", "IQFeed HTT tick downloads", "scan-xeon, mac (via Wine)", "iqfeed_data/tick_downloads/"),
    WorkTypeDef(3, "Data ingestion", "sync_source", "rsync source data between hosts", "kenne ↔ cdec ↔ scan-xeon", "AA2_IQKollect, *_UOA-EMD restoration"),
    # Infrastructure
    WorkTypeDef(4, "Infrastructure", "build", "Compile libemd.dll from c_emd/src/*.c via MSYS2 gcc/make", "scan-new (just built), kenne, cdec, scan-xeon", "c_emd/build/libemd.dll"),
    WorkTypeDef(5, "Infrastructure", "sync_repo", "Push fleet-offload code from Mac to remote", "all hosts", "fleet.py sync <host>"),
    WorkTypeDef(6, "Infrastructure", "host_bootstrap", "First-time host setup (OpenSSH, Python, MSYS2, etc.)", "scan-new (this session), historical kenne/cdec/scan-xeon", "setup_windows_host.ps1"),
    # Bar construction
    WorkTypeDef(7, "Bar construction", "tick_to_1min", "Deterministic tick→1min bar builder", "kenne (oil_ticks_1min_from_ticks/), Mac", "live_data/iqfeed_data/oil_ticks_1min_from_ticks/"),
    # EMD generation
    WorkTypeDef(8, "EMD generation", "pipeline_run", "random_windows_pipeline.py — per-window EMD decomposition → .mat", "kenne, cdec, scan-xeon, scan-new (one dead attempt)", "every random_windows_<cohort>/ dir"),
    WorkTypeDef(9, "EMD generation", "chunk_coalesce", "Parallel batch workers coalesce chunks into final .mat", "implicit within pipeline_run", "*_chunks/ → root .mat files"),
    # Strategy replay / selection
    WorkTypeDef(10, "Strategy replay / selection", "cache_replay", "cache_replay_experiments.py — strategy scoring against existing .mat", "kenne, cdec, scan-xeon", "ig_trading/cache_replay/cache_replay_<config>/"),
    WorkTypeDef(11, "Strategy replay / selection", "adaptive_strategy", "Online strategy adaptation per cohort", "kenne", "ig_trading/adaptive_strategy*"),
    WorkTypeDef(12, "Strategy replay / selection", "per_instrument_selector", "Per-instrument strategy verdict", "kenne", "ig_trading/per_instrument_selector_verdict_*"),
    WorkTypeDef(13, "Strategy replay / selection", "soft_blend_dro", "Distributionally robust optimisation blending", "kenne", "ig_trading/soft_blend_dro_verdict_*"),
    WorkTypeDef(14, "Strategy replay / selection", "audit_stack", "Multi-step audit chain on selectors", "kenne", "ig_trading/audit_stack_*"),
    WorkTypeDef(15, "Strategy replay / selection", "ab_combinations", "A/B factorial combinations of selectors", "kenne", "ig_trading/ab_combinations_*"),
    WorkTypeDef(16, "Strategy replay / selection", "preregistered_minimal", "Preregistration-style minimal selector", "kenne", "ig_trading/preregistered_minimal_*"),
    WorkTypeDef(17, "Strategy replay / selection", "strict_holdout_combined", "Held-out cohort validation", "kenne", "ig_trading/strict_holdout_combined_*"),
    WorkTypeDef(18, "Strategy replay / selection", "raw_mat_features", "Feature extraction from raw .mat", "kenne", "ig_trading/raw_mat_features_*"),
    WorkTypeDef(19, "Strategy replay / selection", "discovery_screens", "Discovery / screening over the cohort space", "kenne (validation-20260602)", "discovery_screens/"),
    # Proxy replay
    WorkTypeDef(20, "Proxy replay", "nq_proxy_replay", "Fast NQ-decomp proxy for selector eval", "cdec", "nq_proxy_replay*, fleet-offload-nq-realdecomp-20260602/"),
    WorkTypeDef(21, "Proxy replay", "es_fresh_proxy_replay", "ES fresh proxy with scheduled-task pipeline", "kenne (validation-20260602)", "es_fresh_proxy_replay/"),
    WorkTypeDef(22, "Proxy replay", "es_proxy_shards", "Sharded ES proxy across windows", "kenne, scan-xeon", "es_proxy_shards/"),
    WorkTypeDef(23, "Proxy replay", "ty_replay", "Treasury (TY 10Y) replay smoke + bg", "cdec", "ty_replay/, ty_replay_bg/, ty_replay_smoke/"),
    # Validation
    WorkTypeDef(24, "Validation", "kurt_range_es_scaled_validation", "Scaled-data ES kurt+range validation", "kenne, scan-xeon", "kurt_range_es_scaled_validation/"),
    WorkTypeDef(25, "Validation", "kurt_range_scaled_validate", "General scaled-data validation", "kenne", "kurt_range_scaled_validate/"),
    WorkTypeDef(26, "Validation", "oil_lock_validate", "Oil production lock validation", "kenne, scan-xeon", "oil_lock_validate/"),
    WorkTypeDef(27, "Validation", "live_holdout_smoke", "Live-holdout paper-trade smoke test", "kenne (offload-20260601)", "live_holdout_smoke/"),
    # Production live trade
    WorkTypeDef(28, "Production live trade", "kurt_range_ig_production", "Continuous live IG signal evaluation", "kenne, scan-xeon (validation-20260602)", "kurt_range_ig_production/"),
    WorkTypeDef(29, "Production live trade", "oil_ig_production", "Continuous oil IG signal evaluation", "kenne, scan-xeon", "oil_ig_production/"),
    # Tick microstructure
    WorkTypeDef(30, "Tick microstructure", "oil_ticks_emd", "EMD applied to tick-built bars", "kenne (fleet-offload-data)", "oil_ticks_emd/"),
    # Data movement / preservation
    WorkTypeDef(31, "Data movement / preservation", "collect", "rsync remote → external HDD live_data tree", "all hosts → Mac/external", "fleet.py collect <jid>"),
    WorkTypeDef(32, "Data movement / preservation", "migration", "rsync remote workspace → external archive", "all hosts → archive/", "migrate_*_to_archive.sh"),
    WorkTypeDef(33, "Data movement / preservation", "archive", "Final atomic publish to live_data/c_emd/results/random_windows/", "Mac", "staged_publish_directory()"),
    WorkTypeDef(34, "Data movement / preservation", "recover_delta", "Re-rsync only mismatched files via .rsync-partial", "Mac", "cluster_state.recover.recollect_delta"),
    # Disk hygiene
    WorkTypeDef(35, "Disk hygiene", "cleanup_chunks", "Delete *_chunks/ scratch dirs", "kenne (3 passes this session)", "clean_kenne_chunks.py"),
    WorkTypeDef(36, "Disk hygiene", "cleanup_temp", "Delete ~Temp, Windows Temp, pip cache", "kenne", "manual"),
    WorkTypeDef(37, "Disk hygiene", "disk_recover", "Auto-triggered cleanup under disk pressure", "kenne", "cluster_state.recover.chunks_cleanup_recover (Phase 4.5), disk_pressure_collect (Phase 4)"),
    # Observability / orchestration
    WorkTypeDef(38, "Observability / orchestration", "reconcile", "Detect wrapper-PID death, mark stale-running", "Mac", "cluster_state.reconcile_once()"),
    WorkTypeDef(39, "Observability / orchestration", "recover_stale", "Reclassify dead-wrapper jobs to exited", "Mac", "cluster_state.recover-stale --apply"),
    WorkTypeDef(40, "Observability / orchestration", "rollup_summary", "Rebuild summary.json from per-batch JSONs", "Mac → remote", "fleet.py rollup-summary <id>"),
    WorkTypeDef(41, "Observability / orchestration", "inventory_probe", "SSH+PowerShell probe of cohort state", "Mac", "remote_state_audit.py"),
    WorkTypeDef(42, "Observability / orchestration", "orchestrator_record", "Persist workitem/artifact events to catalog", "Mac", "trading_common/orchestrator/store.py"),
]


# ============================================================================
# LAYER 2 — Artifact types
# ============================================================================
LAYER2: list[tuple[str, str, str]] = [
    ("Input",            "SOURCE_DATA",         "AA2_IQKollect/, *_UOA-EMD/, iqfeed_data/ raw downloads"),
    ("Input",            "TICK_RAW",            "tick_downloads/*.csv.gz"),
    ("Intermediate",     "SCRATCH",             "*_chunks/, .rsync-partial/ — safe to delete"),
    ("Intermediate",     "INTERMEDIATE_BAR",    "oil_ticks_1min_from_ticks/ (tick→1min)"),
    ("Pipeline output",  "MAT_FILE",            "Per-window .mat (h5py-format EMD decomposition)"),
    ("Pipeline output",  "COHORT_OUTPUT",       "random_windows_<cohort>/ containing many .mat"),
    ("Pipeline output",  "LOG",                 "batch<i>.log, scheduled_task.log"),
    ("Pipeline output",  "SUMMARY",             "summary.json, summary_batch<i>.json"),
    ("Strategy output",  "CACHE_REPLAY_RESULT", "cache_replay_<config>/psr_dsr_by_config.json"),
    ("Strategy output",  "SELECTOR_VERDICT",    "per_instrument_selector_verdict_<config>.json"),
    ("Strategy output",  "AUDIT_REPORT",        "audit_report.json, COMPARE_TO_BTL_ORACLE.md"),
    ("Preservation",     "ARCHIVE_SNAPSHOT",    "/Volumes/.../archive/2026-06-02-snapshots/..."),
    ("Live",             "LIVE_SIGNAL",         "live_state/signal_table.json, trade_log.jsonl"),
    ("Infrastructure",   "LIBRARY",             "libemd.dll (compiled C library)"),
    ("Infrastructure",   "REPO_CLONE",          "fleet-offload/ source tree on a remote"),
    ("Infrastructure",   "CONFIG",              "wg0.conf, hosts.json, .env"),
    ("Infrastructure",   "SCRIPT",              "launch_*.ps1, check_*.ps1"),
]


# ============================================================================
# LAYER 3 — Lifecycle states
# ============================================================================
LAYER3_DIAGRAM = """\
PENDING → QUEUED → RUNNING → EXITED → COLLECTED → ARCHIVED
                          ↓
                        FAILED      (any of: rsync err, OOM, wrapper death)
                        CANCELLED   (operator kill)

Special transient:
  WRAPPER_DEAD_PIPELINE_UNKNOWN  ← state.json says running but Mac-side wrapper PID is dead;
                                   children may or may not still be writing on the remote
  STALE                           ← chunks/ present but no write >60 min
"""


# ============================================================================
# LAYER 4 — Host distribution
# ============================================================================
@dataclass
class HostDist:
    label: str
    spec: str
    primary: str
    secondary: str
    observed: str
    # Live state (filled in at runtime)
    current_state: str = ""
    proc_count: int = 0
    disk_free_gb: float = 0.0

LAYER4: list[HostDist] = [
    HostDist("kenne",     "128 cores, 256 GB", "pipeline_run (EMD generation)", "cache_replay, all strategy work, live production", "jobs 16, 21, 22, 26, 30-34, 37-42, 45, 46, 48, 49 + ig_trading + oil_ticks"),
    HostDist("cdec",      "32 cores, 128 GB",  "pipeline_run",                  "nq_proxy_replay, ty_replay",                      "jobs 17, 20, 23, 28, 36, 44, 52 + nq_realdecomp"),
    HostDist("scan-xeon", "32 cores, 128 GB",  "pipeline_run",                  "live production (kurt_range, oil_ig), validation, ES proxy shards", "jobs 18, 19, 29, 35, 43 + offload-20260601 workspace cohorts"),
    HostDist("scan-new",  "128 cores, 512 GB", "(nothing yet — one dead pipeline_run, then idle)", "—",                            "one orphan attempt (already cleaned)"),
    HostDist("mac",       "12 cores, 24 GB",   "orchestration, collect, migration, sync, reconcile", "tick-builder local",          "fleet.py + cluster_state + orchestrator + auto_collect_watcher"),
]


# ============================================================================
# Live enrichment (overlays current state onto the static taxonomy)
# ============================================================================
def enrich_live_state(probe: bool = False) -> None:
    """Read recent audit + fleet state to mark which work types are RUNNING."""
    fleet_root = fleet_dir()
    fleet_state_path = fleet_root / "state.json"
    audit_state_path = fleet_root / "remote_state_audit.json"

    # --- Optionally re-probe ---
    if probe:
        repo = pathlib.Path(__file__).parent
        try:
            subprocess.run(
                [sys.executable, str(repo / "remote_state_audit.py"), "--json"],
                check=True, capture_output=True, timeout=600,
            )
        except Exception as e:
            print(f"WARN: live probe failed ({e}); using cached state", file=sys.stderr)

    # --- Mark work types as RUNNING / IDLE based on state files ---
    running_pipeline = False
    running_collect = False
    running_migration = False
    if fleet_state_path.exists():
        try:
            s = json.loads(fleet_state_path.read_text())
            running_pipeline = any(j.get("status") == "running" for j in s.get("jobs", []))
        except Exception:
            pass

    # cohort dir scan (from audit) tells us which other types are active
    has_active_cohort = False
    has_stale_cohort = False
    host_proc_counts: dict[str, int] = {}
    host_disk_gb: dict[str, float] = {}
    if audit_state_path.exists():
        try:
            audit = json.loads(audit_state_path.read_text())
            for host_label, host in audit.items():
                if isinstance(host, dict):
                    host_proc_counts[host_label] = host.get("proc_count", 0)
                    host_disk_gb[host_label] = host.get("disk_free_gb", 0.0)
                    for c in host.get("cohorts", []):
                        if c.get("chunks", 0) > 0:
                            if c.get("age_min", 0) < 60:
                                has_active_cohort = True
                            else:
                                has_stale_cohort = True
        except Exception:
            pass

    # Watcher process alive?
    ps = subprocess.run(["pgrep", "-f", "auto_collect_watcher"], capture_output=True, text=True)
    watcher_alive = bool(ps.stdout.strip())

    # Mark Layer 1 entries
    for wt in LAYER1:
        if wt.name == "pipeline_run":
            wt.current_status = "🟢 RUNNING" if (running_pipeline or has_active_cohort) else "💤 idle"
        elif wt.name == "chunk_coalesce":
            wt.current_status = "🟢 RUNNING" if has_active_cohort else "💤 idle"
        elif wt.name == "collect":
            wt.current_status = "🟢 RUNNING (watcher)" if watcher_alive else "💤 idle"
        elif wt.name == "inventory_probe":
            wt.current_status = "🟢 RUNNING (audit cached)" if audit_state_path.exists() else "💤 idle"
        elif wt.name == "orchestrator_record":
            orch_path = fleet_root / "orchestrator" / "events.jsonl"
            wt.current_status = "🟢 ACTIVE (catalog)" if orch_path.exists() else "💤 idle"
        elif wt.name == "reconcile":
            wt.current_status = "✓ ON-DEMAND"
        elif has_stale_cohort and wt.name in ("disk_recover", "cleanup_chunks"):
            wt.current_status = "⚠️ NEEDED (stale cohorts)"
        else:
            wt.current_status = "✓ HISTORICAL"

    # Mark Layer 4 entries
    for h in LAYER4:
        h.proc_count = host_proc_counts.get(h.label, 0)
        h.disk_free_gb = host_disk_gb.get(h.label, 0.0)
        if h.label == "mac":
            h.current_state = "🟢 ORCHESTRATING" if watcher_alive else "💤 idle"
        elif h.proc_count > 0:
            h.current_state = "🟢 ACTIVE"
        else:
            h.current_state = "💤 idle"


# ============================================================================
# Rendering
# ============================================================================
def render_text(layers: set[int]) -> None:
    if 1 in layers:
        print("\n=== LAYER 1 — Computation types (42 work types, 10 categories) ===\n")
        last_cat = ""
        for wt in LAYER1:
            cat = wt.category if wt.category != last_cat else ""
            last_cat = wt.category
            print(f"  {wt.n:2d}  {cat:30s}  {wt.name:30s}  {wt.current_status:30s}")
            print(f"      {' '*30}  {wt.what_produces_it}")
            print(f"      {' '*30}  ran on: {wt.where_it_ran}")
            print(f"      {' '*30}  ref:    {wt.memory_ref}")
            print()

    if 2 in layers:
        print("\n=== LAYER 2 — Artifact types (14 types, 6 categories) ===\n")
        last_cat = ""
        for cat, name, ex in LAYER2:
            c = cat if cat != last_cat else ""
            last_cat = cat
            print(f"  {c:18s}  {name:22s}  {ex}")
        print()

    if 3 in layers:
        print("\n=== LAYER 3 — Lifecycle states ===\n")
        print(LAYER3_DIAGRAM)

    if 4 in layers:
        print("\n=== LAYER 4 — Cross-host distribution (current live state) ===\n")
        for h in LAYER4:
            print(f"  {h.label:9s} ({h.spec})  {h.current_state:18s}")
            print(f"    procs={h.proc_count:>4}  disk_free_gb={h.disk_free_gb:>7.2f}")
            print(f"    primary:   {h.primary}")
            print(f"    secondary: {h.secondary}")
            print(f"    observed:  {h.observed}")
            print()


def render_markdown(layers: set[int]) -> None:
    if 1 in layers:
        print("\n## Layer 1 — Computation types\n")
        print("| # | category | work type | current | what produces it | where it ran | ref |")
        print("|---|---|---|---|---|---|---|")
        for wt in LAYER1:
            print(f"| {wt.n} | {wt.category} | `{wt.name}` | {wt.current_status} | {wt.what_produces_it} | {wt.where_it_ran} | {wt.memory_ref} |")
    if 2 in layers:
        print("\n## Layer 2 — Artifact types\n")
        print("| category | type | examples |")
        print("|---|---|---|")
        for cat, name, ex in LAYER2:
            print(f"| {cat} | `{name}` | {ex} |")
    if 3 in layers:
        print("\n## Layer 3 — Lifecycle states\n")
        print("```text")
        print(LAYER3_DIAGRAM)
        print("```")
    if 4 in layers:
        print("\n## Layer 4 — Cross-host distribution (live)\n")
        print("| host | spec | current | procs | disk free | primary | secondary | observed |")
        print("|---|---|---|---|---|---|---|---|")
        for h in LAYER4:
            print(f"| {h.label} | {h.spec} | {h.current_state} | {h.proc_count} | {h.disk_free_gb:.2f} GB | {h.primary} | {h.secondary} | {h.observed} |")


def render_json(layers: set[int]) -> None:
    out: dict = {}
    if 1 in layers:
        out["layer1"] = [{"n": w.n, "category": w.category, "name": w.name,
                          "what_produces_it": w.what_produces_it,
                          "where_it_ran": w.where_it_ran, "memory_ref": w.memory_ref,
                          "current_status": w.current_status} for w in LAYER1]
    if 2 in layers:
        out["layer2"] = [{"category": c, "type": n, "examples": e} for c, n, e in LAYER2]
    if 3 in layers:
        out["layer3"] = LAYER3_DIAGRAM
    if 4 in layers:
        out["layer4"] = [{"label": h.label, "spec": h.spec, "current_state": h.current_state,
                          "proc_count": h.proc_count, "disk_free_gb": h.disk_free_gb,
                          "primary": h.primary, "secondary": h.secondary, "observed": h.observed}
                         for h in LAYER4]
    print(json.dumps(out, indent=2, ensure_ascii=False))


# ============================================================================
# CLI
# ============================================================================
def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--layers", type=int, nargs="+", choices=[1, 2, 3, 4],
                   default=[1, 2, 3, 4],
                   help="which layers to include (default: all)")
    p.add_argument("--markdown", action="store_true", help="emit markdown tables")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    p.add_argument("--probe", action="store_true",
                   help="re-probe remotes live before report (slow: 1-2 min)")
    args = p.parse_args()

    enrich_live_state(probe=args.probe)
    layers = set(args.layers)
    if args.json:
        render_json(layers)
    elif args.markdown:
        render_markdown(layers)
    else:
        render_text(layers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
