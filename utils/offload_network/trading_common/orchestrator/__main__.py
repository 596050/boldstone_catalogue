"""CLI: python3 -m trading_common.orchestrator <command>

Commands:
    init                Bootstrap from ~/.fleet/state.json (creates events.jsonl)
    status              Show summary: workitems by type×status, artifacts by tier
    inventory <host>    Print cached inventory for one host (or 'all')
    refresh <host>      Force a fresh remote probe of one host (or 'all')
    workitems           List all workitems (filterable by --type / --status / --host)
    artifacts           List all artifacts (filterable by --tier / --host / --type)
    lineage <id>        Walk lineage backward from an artifact id
    where <cohort>      Find every host + path where a named cohort exists
    recommend           Suggest the next collect / cleanup / migrate action
    import-logs         Parse /tmp/migrate_*.log + auto_collect_watcher.log → events
    record <kind>       Push a single workitem event (used by watcher hook)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter

from . import (
    get_store, materialise_view,
    refresh_inventory, load_inventory,
    trace_lineage, WorkType, WorkStatus, ArtifactType, StorageTier,
)
from .import_state import import_fleet_jobs


def _cmd_init(args):
    res = import_fleet_jobs()
    print(f"Imported {res['imported']} fleet jobs from ~/.fleet/state.json")
    if res.get("error"):
        print(f"  error: {res['error']}")
    workitems, artifacts = materialise_view()
    print(f"Materialised view: {len(workitems)} workitems / {len(artifacts)} artifacts")


def _cmd_status(args):
    workitems, artifacts = materialise_view()
    print(f"=== ORCHESTRATOR STATUS ({len(workitems)} workitems / {len(artifacts)} artifacts) ===")
    print()
    print("Workitems by (type, status):")
    counts = Counter((wi.work_type.value, wi.status.value) for wi in workitems.values())
    for (wt, st), n in sorted(counts.items()):
        print(f"  {wt:14s}  {st:11s}  {n}")
    print()
    print("Artifacts by storage tier:")
    tier_counts = Counter(a.storage_tier.value for a in artifacts.values())
    for tier, n in sorted(tier_counts.items()):
        sz = sum(a.size_bytes for a in artifacts.values() if a.storage_tier.value == tier)
        print(f"  {tier:14s}  {n:>5} artifacts  {sz/1e9:>8.2f} GB")
    print()
    print("Artifacts by host:")
    host_counts = Counter(a.host or "?" for a in artifacts.values())
    for host, n in sorted(host_counts.items()):
        print(f"  {host:14s}  {n:>5} artifacts")


def _cmd_inventory(args):
    host = args.host
    if host == "all":
        for h in ["kenne", "cdec", "scan-xeon", "scan-new"]:
            d = load_inventory(h) or {}
            print(f"=== {h} ===  (probed_at={d.get('probed_at','never')})")
            for c in (d.get("_cohorts") or []):
                sz = c["size_bytes"] / 1e9
                print(f"  {c['name']:60s}  {c['file_count']:>4} mats  {sz:>6.2f} GB  {c['container']}")
            if d.get("_error"):
                print(f"  ERROR: {d['_error']}")
    else:
        d = load_inventory(host)
        if not d:
            print(f"No cached inventory for {host}. Run: refresh {host}")
            return
        print(json.dumps(d, indent=2)[:5000])


def _cmd_refresh(args):
    hosts = None if args.host == "all" else [args.host]
    res = refresh_inventory(hosts=hosts, max_age_hours=0.0)  # force
    for h, d in res.items():
        n = len(d.get("_cohorts") or [])
        err = d.get("_error") or "ok"
        print(f"  {h}: {n} cohorts, status={err}")


def _cmd_workitems(args):
    workitems, _ = materialise_view()
    filtered = list(workitems.values())
    if args.type:   filtered = [w for w in filtered if w.work_type.value == args.type]
    if args.status: filtered = [w for w in filtered if w.status.value == args.status]
    if args.host:   filtered = [w for w in filtered if w.host == args.host]
    for w in sorted(filtered, key=lambda x: x.created_at or ""):
        print(f"  {w.id:30s}  {w.work_type.value:14s}  {w.status.value:11s}  "
              f"host={w.host:9s}  cohort={w.cohort or '-'}")
    print(f"  ({len(filtered)} of {len(workitems)} total)")


def _cmd_artifacts(args):
    _, artifacts = materialise_view()
    filtered = list(artifacts.values())
    if args.tier:  filtered = [a for a in filtered if a.storage_tier.value == args.tier]
    if args.host:  filtered = [a for a in filtered if a.host == args.host]
    if args.type:  filtered = [a for a in filtered if a.artifact_type.value == args.type]
    total_gb = sum(a.size_bytes for a in filtered) / 1e9
    for a in sorted(filtered, key=lambda x: -x.size_bytes)[:50]:
        print(f"  {a.size_bytes/1e9:>7.2f} GB  {a.storage_tier.value:11s}  "
              f"{a.host or '?':9s}  {a.id}")
    print(f"  ({len(filtered)} artifacts, total {total_gb:.2f} GB)")


def _cmd_lineage(args):
    out = trace_lineage(args.artifact_id, max_depth=args.depth)
    print(json.dumps(out, indent=2, default=str))


def _cmd_where(args):
    _, artifacts = materialise_view()
    name = args.cohort
    hits = [a for a in artifacts.values()
            if a.cohort_name == name or (a.path and name in a.path)]
    if not hits:
        print(f"No artifacts found for cohort '{name}'")
        return
    for a in hits:
        print(f"  {a.host or '?':9s}  {a.storage_tier.value:11s}  "
              f"{a.size_bytes/1e9:>6.2f} GB  {a.path}")


def _cmd_recommend(args):
    """Rule engine: surface highest-impact actions (collects, cleanups, migrations).
    Each rule reads the materialised view + cached inventory snapshots."""
    import json as _json
    workitems, artifacts = materialise_view()
    store = get_store()

    # ---- Rule 1: ready-to-collect (fleet jobs with status=EXITED) ----
    ready_to_collect = [w for w in workitems.values()
                        if w.status == WorkStatus.EXITED]
    if ready_to_collect:
        print(f"COLLECT — {len(ready_to_collect)} workitems status=EXITED ready to collect:")
        for w in ready_to_collect[:10]:
            print(f"  fleet collect {w.fleet_job_id}  ({w.host}, cohort={w.cohort})")
        print()

    # ---- Rule 2: chunks-cleanup opportunities (Phase 4.5) ----
    # For each host, check the cached inventory; if it has cohort dirs whose
    # parent workitem is status=EXITED, the *_chunks/ scratch in that cohort
    # is safe to delete (per clean_kenne_chunks.py's 3-layer safety).
    # Combined with a disk-pressure heuristic from the latest inventory.
    print("CLEANUP (chunks scratch) — Phase 4.5 disk relief without collect cost:")
    chunks_candidates_by_host: dict[str, int] = {}
    for host in ("kenne", "cdec", "scan-xeon", "scan-new"):
        inv_path = store.base_dir / "inventory" / f"{host}.json"
        if not inv_path.exists():
            continue
        try:
            inv = _json.loads(inv_path.read_text())
        except Exception:
            continue
        # Find cohorts whose workitem status=EXITED (chunks now orphaned)
        cohorts_in_inv = {c["name"] for c in (inv.get("_cohorts") or [])}
        exited_wis = [w for w in workitems.values()
                      if w.host == host and w.status == WorkStatus.EXITED]
        eligible_cohorts = {w.cohort for w in exited_wis if w.cohort in cohorts_in_inv}
        if eligible_cohorts:
            chunks_candidates_by_host[host] = len(eligible_cohorts)
    if chunks_candidates_by_host:
        for h, n in chunks_candidates_by_host.items():
            print(f"  {h}: {n} cohorts have status=EXITED; their *_chunks/ are safe to delete")
        print("  Run:  python3 scripts/offload_orchestration/clean_kenne_chunks.py --apply")
    else:
        print("  (no exited cohorts with cached inventory; run `refresh all` for fresh data)")
    print()

    # ---- Rule 3: stale workspace migrations (offload-* >24h not touched) ----
    print("ARCHIVE — stale workspace dirs that could migrate to /Volumes/.../archive/:")
    workspace_archived = [w for w in workitems.values() if w.work_type == WorkType.MIGRATION
                          and w.status == WorkStatus.ARCHIVED]
    workspace_running = [w for w in workitems.values() if w.work_type == WorkType.MIGRATION
                         and w.status == WorkStatus.RUNNING]
    if workspace_running:
        print(f"  {len(workspace_running)} migration(s) in flight — wait for completion")
    print(f"  ({len(workspace_archived)} already archived this session)")
    print()

    # ---- Summary footers ----
    archived = [a for a in artifacts.values() if a.storage_tier == StorageTier.ARCHIVE_EXT]
    warm = [a for a in artifacts.values() if a.storage_tier == StorageTier.WARM_EXT]
    hot_remote = [a for a in artifacts.values() if a.storage_tier == StorageTier.HOT_REMOTE]
    print("ARTIFACT TOTALS by tier:")
    print(f"  HOT_REMOTE:  {len(hot_remote):>3} ({sum(a.size_bytes for a in hot_remote)/1e9:>7.2f} GB)")
    print(f"  WARM_EXT:    {len(warm):>3} ({sum(a.size_bytes for a in warm)/1e9:>7.2f} GB)")
    print(f"  ARCHIVE_EXT: {len(archived):>3} ({sum(a.size_bytes for a in archived)/1e9:>7.2f} GB)")


def _cmd_import_logs(args):
    """Auto-import workitem events from /tmp/migrate_*.log + watcher logs."""
    from .log_importer import import_all_logs
    log_dir = pathlib.Path(args.log_dir or "/tmp")
    res = import_all_logs(log_dir)
    print(f"Imported events from {len(res)} log files under {log_dir}:")
    for path, count in res.items():
        print(f"  {count:>4} events  {path}")
    workitems, artifacts = materialise_view()
    print(f"\nMaterialised view now: {len(workitems)} workitems / {len(artifacts)} artifacts")


def _cmd_record(args):
    """Record a single workitem event (used by the auto_collect_watcher hook
    + future scripts to push state changes into the orchestrator without
    parsing logs after-the-fact)."""
    from .schema import WorkType as _WT, WorkStatus as _WS
    store = get_store()
    wid = args.id
    if args.kind == "create":
        store.submit_workitem(
            id=wid, work_type=_WT(args.work_type), host=args.host,
            cohort=args.cohort, fleet_job_id=args.fleet_job_id,
            parent_id=args.parent_id, command=args.command,
            notes=args.notes or "",
        )
        print(f"created workitem {wid} type={args.work_type} host={args.host}")
    elif args.kind == "status":
        store.update_status(
            wid, _WS(args.status),
            retry_count=args.retry_count, last_error=args.last_error,
        )
        print(f"updated workitem {wid} status={args.status}")
    else:
        print(f"unknown kind: {args.kind}", file=sys.stderr)
        return 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="python3 -m trading_common.orchestrator",
                                description=__doc__)
    sp = p.add_subparsers(dest="cmd", required=True)

    sp.add_parser("init").set_defaults(func=_cmd_init)
    sp.add_parser("status").set_defaults(func=_cmd_status)

    p_inv = sp.add_parser("inventory"); p_inv.add_argument("host")
    p_inv.set_defaults(func=_cmd_inventory)

    p_ref = sp.add_parser("refresh"); p_ref.add_argument("host")
    p_ref.set_defaults(func=_cmd_refresh)

    p_wi = sp.add_parser("workitems")
    p_wi.add_argument("--type"); p_wi.add_argument("--status"); p_wi.add_argument("--host")
    p_wi.set_defaults(func=_cmd_workitems)

    p_art = sp.add_parser("artifacts")
    p_art.add_argument("--tier"); p_art.add_argument("--host"); p_art.add_argument("--type")
    p_art.set_defaults(func=_cmd_artifacts)

    p_lin = sp.add_parser("lineage"); p_lin.add_argument("artifact_id")
    p_lin.add_argument("--depth", type=int, default=5)
    p_lin.set_defaults(func=_cmd_lineage)

    p_wh = sp.add_parser("where"); p_wh.add_argument("cohort")
    p_wh.set_defaults(func=_cmd_where)

    sp.add_parser("recommend").set_defaults(func=_cmd_recommend)

    p_imp = sp.add_parser("import-logs",
                          help="Parse /tmp/migrate_*.log + auto_collect_watcher.log → events")
    p_imp.add_argument("--log-dir", default="/tmp")
    p_imp.set_defaults(func=_cmd_import_logs)

    p_rec = sp.add_parser("record",
                          help="Push a single workitem event (for hook integration)")
    p_rec.add_argument("kind", choices=["create", "status"],
                       help="'create' or 'status'")
    p_rec.add_argument("--id", required=True)
    # for 'create':
    p_rec.add_argument("--work-type", default="collect")
    p_rec.add_argument("--host", default="?")
    p_rec.add_argument("--cohort", default=None)
    p_rec.add_argument("--fleet-job-id", type=int, default=None)
    p_rec.add_argument("--parent-id", default=None)
    p_rec.add_argument("--command", default=None)
    p_rec.add_argument("--notes", default=None)
    # for 'status':
    p_rec.add_argument("--status", default=None,
                       help="pending|queued|running|exited|collected|archived|failed|cancelled")
    p_rec.add_argument("--retry-count", type=int, default=None)
    p_rec.add_argument("--last-error", default=None)
    p_rec.set_defaults(func=_cmd_record)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
