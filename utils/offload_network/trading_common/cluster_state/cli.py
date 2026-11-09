"""CLI entry point.

Usage:
    python3 -m trading_common.cluster_state reconcile [--verbose]
    python3 -m trading_common.cluster_state recover-stale [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys

from . import (
    reconcile_once,
    reclassify_running_jobs,
    disk_pressure_collect,
    recollect_delta,
    restore_source_dir,
    recover_summary,
    read_recent_alerts,
)


def _cmd_reconcile(args: argparse.Namespace) -> int:
    out = reconcile_once(emit_alerts=True, verbose=args.verbose)
    print(json.dumps(out, indent=2, default=str))
    return 0


def _cmd_recover_stale(args: argparse.Namespace) -> int:
    results = reclassify_running_jobs(dry_run=not args.apply, max_jobs=args.max_jobs)
    summary = recover_summary(results)
    print("Recovery summary:")
    print(json.dumps(summary, indent=2))
    if args.verbose:
        print("\nPer-job results:")
        for r in results:
            print(f"  job {r.job_id} @ {r.host}: {r.action_taken} -- {r.note}")
    return 0


def _cmd_alerts(args: argparse.Namespace) -> int:
    rows = list(read_recent_alerts(hours=args.hours))
    print(f"{len(rows)} alert(s) in last {args.hours}h (newest first):")
    for r in rows[:args.limit]:
        print(f"  [{r.get('severity'):<5}]  {r.get('time')}  kind={r.get('kind'):<28}  "
              f"job={r.get('job_id','-'):<4}  {r.get('detail','')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python3 -m trading_common.cluster_state",
        description="Detect divergence; safely recover from common failures.",
    )
    sp = p.add_subparsers(dest="cmd", required=True)

    p_rec = sp.add_parser("reconcile", help="Run detection pass; write alerts.")
    p_rec.add_argument("--verbose", action="store_true")
    p_rec.set_defaults(func=_cmd_reconcile)

    p_rs = sp.add_parser(
        "recover-stale",
        help="Reclassify status=running jobs whose wrapper PID is dead. "
             "Read-only by default; pass --apply to write state.json.",
    )
    p_rs.add_argument("--apply", action="store_true",
                      help="Actually edit state.json. Without this, just report.")
    p_rs.add_argument("--max-jobs", type=int, default=50)
    p_rs.add_argument("--verbose", action="store_true")
    p_rs.set_defaults(func=_cmd_recover_stale)

    p_al = sp.add_parser("alerts", help="Tail recent alerts.jsonl")
    p_al.add_argument("--hours", type=int, default=24)
    p_al.add_argument("--limit", type=int, default=50)
    p_al.set_defaults(func=_cmd_alerts)

    p_dp = sp.add_parser(
        "recover-disk-pressure",
        help="When a host runs low on disk, auto-collect oldest collected job's "
             "remote dir to reclaim disk. Read-only by default; pass --apply to run.",
    )
    p_dp.add_argument("--host", required=True)
    p_dp.add_argument("--apply", action="store_true")
    p_dp.add_argument("--threshold-gb", type=float, default=30.0,
                      help="Trigger when free disk on host < this many GB (default 30)")
    p_dp.set_defaults(func=_cmd_disk_pressure)

    p_rd = sp.add_parser(
        "recover-delta",
        help="Re-rsync the missing/short files for a job whose verify mismatched. "
             "Read-only by default; pass --apply to act.",
    )
    p_rd.add_argument("job_id", type=int)
    p_rd.add_argument("--apply", action="store_true")
    p_rd.set_defaults(func=_cmd_recollect_delta)

    p_rs = sp.add_parser(
        "recover-source",
        help="Restore a missing source dir on a host from the external drive. "
             "HIGH-impact action; explicitly opt-in via --apply.",
    )
    p_rs.add_argument("dir_name", help="e.g. AA2_IQKollect, AAPL_UOA-EMD")
    p_rs.add_argument("--host", required=True)
    p_rs.add_argument("--apply", action="store_true")
    p_rs.set_defaults(func=_cmd_restore_source)

    args = p.parse_args(argv)
    return args.func(args)


def _cmd_disk_pressure(args: argparse.Namespace) -> int:
    r = disk_pressure_collect(
        host=args.host, dry_run=not args.apply,
        free_threshold_gb=args.threshold_gb,
    )
    print(f"Recovery: {r.handler}")
    print(f"  host        : {r.host}")
    print(f"  action      : {r.action_taken}")
    print(f"  job_id      : {r.job_id}")
    print(f"  note        : {r.note}")
    return 0


def _cmd_recollect_delta(args: argparse.Namespace) -> int:
    r = recollect_delta(job_id=args.job_id, dry_run=not args.apply)
    print(f"Recovery: {r.handler}")
    print(f"  job_id      : {r.job_id}")
    print(f"  host        : {r.host}")
    print(f"  action      : {r.action_taken}")
    print(f"  note        : {r.note}")
    return 0


def _cmd_restore_source(args: argparse.Namespace) -> int:
    r = restore_source_dir(
        dir_name=args.dir_name, host=args.host, dry_run=not args.apply,
    )
    print(f"Recovery: {r.handler}")
    print(f"  host        : {r.host}")
    print(f"  action      : {r.action_taken}")
    print(f"  note        : {r.note}")
    if r.before:
        print(f"  before      : {r.before}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
