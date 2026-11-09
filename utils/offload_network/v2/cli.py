"""v2 CLI — minimal one-shot submit.

Usage:
  python -m v2 build  <manifest.json>  --out <dir>
  python -m v2 submit <manifest.json>  --out <dir>   [--keep-remote] [--poll N]
  python -m v2 verify <seal.tar.gz>

The CLI is intentionally thin; library callers should use the public
functions in seal/submit/result directly for richer control.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

from .manifest import SealedManifest, SealError
from .spec import SpecError
from .seal import build_seal, verify_seal
from .submit import submit_one

from fleet.paths import v2_bundles_root

_DEFAULT_V2_BATCH_ROOT = v2_bundles_root() / "batches"


def _cmd_build(args: argparse.Namespace) -> int:
    m = SealedManifest.from_path(args.manifest)
    seal = build_seal(m, out_dir=args.out)
    print(json.dumps({
        "ok": True,
        "seal_path": str(seal),
        "seal_sha256": m.seal_sha256,
        "seal_size_bytes": m.seal_size_bytes,
    }, indent=2))
    return 0


def _cmd_submit(args: argparse.Namespace) -> int:
    m = SealedManifest.from_path(args.manifest)

    def _emit(_m: SealedManifest, stage: str, info: dict) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {m.job_id} {stage}: {json.dumps(info, default=str)[:300]}", flush=True)

    out = submit_one(
        m,
        bundle_out_dir=args.out,
        poll_interval_s=args.poll,
        keep_remote_workdir=args.keep_remote,
        on_state_change=_emit,
    )
    # Strip non-serialisable bits
    out["manifest"] = out["manifest"].to_dict() if isinstance(out["manifest"], SealedManifest) else out["manifest"]
    print(json.dumps(out, indent=2, default=str))
    rc = 0
    if out.get("status", {}).get("phase") not in ("exited",):
        rc = 1
    elif out.get("status", {}).get("exit_code") != 0:
        rc = out["status"]["exit_code"]
    return rc


def _cmd_verify(args: argparse.Namespace) -> int:
    m = verify_seal(args.seal)
    print(json.dumps({"ok": True, "job_id": m.job_id, "n_blobs": len(m.blobs)}, indent=2))
    return 0


# --- batch subcommands ----------------------------------------------------

def _load_hosts_for_batch(args: argparse.Namespace) -> dict:
    """Load hosts.json from the orchestration root (same source fleet.py uses)."""
    from lib.inventory import hosts_path
    hp = pathlib.Path(args.hosts) if args.hosts else hosts_path()
    if not hp.is_file():
        raise SealError(f"hosts file not found: {hp}")
    h = json.loads(hp.read_text())
    # hosts.json wraps the actual dict under "hosts"
    return h.get("hosts", h)


def _cmd_batch_submit(args: argparse.Namespace) -> int:
    from .batch import submit_batch
    hosts = _load_hosts_for_batch(args)
    state = submit_batch(
        args.batch,
        hosts,
        state_path=args.state_file,
        bundle_out_root=args.out,
        dry_run=args.dry_run,
    )
    counts = {}
    for j in state.jobs.values():
        counts[j.status] = counts.get(j.status, 0) + 1
    print(json.dumps({
        "batch": state.batch,
        "started_at": state.started_at,
        "finished_at": state.finished_at,
        "state_file": state.state_path,
        "status_counts": counts,
    }, indent=2))
    return 0 if counts.get("failed", 0) == 0 else 1


def _cmd_batch_status(args: argparse.Namespace) -> int:
    from .batch import BatchState
    sp = pathlib.Path(args.state_file)
    if not sp.is_file():
        print(f"state file not found: {sp}", file=sys.stderr)
        return 2
    bs = BatchState.from_dict(json.loads(sp.read_text()))
    print(f"batch: {bs.batch}")
    print(f"started_at:  {bs.started_at}")
    print(f"finished_at: {bs.finished_at or '(in progress)'}")
    print()
    counts: dict[str, int] = {}
    for j in bs.jobs.values():
        counts[j.status] = counts.get(j.status, 0) + 1
    print("status counts:")
    for s, n in sorted(counts.items()):
        print(f"  {s:12s} {n}")
    print()
    print(f"{'name':<40} {'status':<12} {'host':<12} {'exit':>5} {'rc':>5}")
    for name in sorted(bs.jobs):
        j = bs.jobs[name]
        print(f"  {j.name:<38} {j.status:<12} {j.host or '-':<12} {str(j.exit_code or '-'):>5} {j.attempts:>5}")
    return 0


def _cmd_batch_resume(args: argparse.Namespace) -> int:
    """Re-run a partially-completed batch: completed jobs skip, interrupted
    or pending jobs run. Same surface as submit but assumes a state file
    already exists.
    """
    if not pathlib.Path(args.state_file).is_file():
        print(f"no state file to resume: {args.state_file}", file=sys.stderr)
        return 2
    # Reuse the submit path — BatchExecutor's constructor detects existing
    # state and resumes.
    return _cmd_batch_submit(args)


def _cmd_batch_doctor(args: argparse.Namespace) -> int:
    """Scan a state file for ghost jobs (status=running with stale
    heartbeat). Exit code is 0 if zero ghosts, 1 otherwise."""
    from .batch import diagnose_batch
    report = diagnose_batch(args.state_file)
    print(json.dumps(report, indent=2))
    n_ghosts = report.get("summary", {}).get("ghosts", 0)
    return 0 if n_ghosts == 0 else 1


def _cmd_batch_rebuild_state(args: argparse.Namespace) -> int:
    """Rebuild a corrupted/missing state file by scanning the per-bundle
    pulled dirs for completed jobs. The new state file marks each scanned
    job as 'succeeded' (we trust the per-bundle status.json), every other
    job as 'pending'. Operator can then `batch resume`."""
    from .batch import _rebuild_state_from_disk
    out_path = pathlib.Path(args.state_file)
    rebuilt = _rebuild_state_from_disk(
        pathlib.Path(args.batch),
        bundle_out_root=pathlib.Path(args.out) if args.out else None,
    )
    out_path.write_text(json.dumps(rebuilt, indent=2, default=str))
    print(json.dumps({"rebuilt_state_file": str(out_path),
                      "summary": rebuilt.get("status_counts", {})}, indent=2))
    return 0


def _cmd_batch_list(args: argparse.Namespace) -> int:
    """List every batch state file under the configured batch root (default:
    `v2_bundles_root()/batches`) or the operator's chosen --root.
    the operator's chosen --root) with a one-line summary per batch."""
    from .batch import list_batches
    root = pathlib.Path(args.root) if args.root else (
        _DEFAULT_V2_BATCH_ROOT
    )
    rows = list_batches(root)
    if not rows:
        print(f"no batch state files under {root}")
        return 0
    print(f"{'batch':<60} {'started':<20} {'finished':<20} {'counts'}")
    for r in rows:
        counts_s = ",".join(f"{k}={v}" for k, v in r["status_counts"].items())
        print(f"  {r['batch']:<58} {r['started_at']:<18} "
              f"{(r['finished_at'] or '(running)'):<18} {counts_s}")
    return 0


def _cmd_batch_jobs(args: argparse.Namespace) -> int:
    """Like `batch status` but filterable by status."""
    from .batch import BatchState
    sp = pathlib.Path(args.state_file)
    if not sp.is_file():
        print(f"state file not found: {sp}", file=sys.stderr)
        return 2
    bs = BatchState.from_dict(json.loads(sp.read_text()))
    rows = list(bs.jobs.values())
    if args.status:
        rows = [j for j in rows if j.status == args.status]
    print(f"{'name':<48} {'status':<18} {'host':<12} {'rc':>4} {'attempts':>9}")
    for j in sorted(rows, key=lambda x: x.name):
        rc = j.exit_code if j.exit_code is not None else "-"
        print(f"  {j.name:<46} {j.status:<18} {(j.host or '-'):<12} {str(rc):>4} {j.attempts:>9}")
    return 0


def _cmd_batch_prestage_cache_stage(args: argparse.Namespace) -> int:
    from .prestage_cache_stage import prestage_cache_stage
    out = prestage_cache_stage(
        batch_path=args.batch,
        hosts_path=args.hosts,
        only=set(args.only or []),
        force=args.force,
        dry_run=args.dry_run,
        quiet=args.quiet,
        timeout=args.timeout,
    )
    print(json.dumps(out, indent=2))
    return 1 if out["errors"] else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="v2", description="v2 sealed-bundle offload orchestration")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="build a seal from a manifest JSON")
    p_build.add_argument("manifest", help="path to manifest.json on submitter")
    p_build.add_argument("--out", required=True, help="output dir for the built seal")
    p_build.set_defaults(func=_cmd_build)

    p_submit = sub.add_parser("submit", help="build + push + run + pull + cleanup")
    p_submit.add_argument("manifest", help="path to manifest.json")
    p_submit.add_argument("--out", required=True, help="bundle staging dir")
    p_submit.add_argument("--poll", type=float, default=15.0, help="poll interval seconds")
    p_submit.add_argument("--keep-remote", action="store_true", help="don't delete remote workdir after pull")
    p_submit.set_defaults(func=_cmd_submit)

    p_verify = sub.add_parser("verify", help="verify a seal's integrity")
    p_verify.add_argument("seal", help="path to seal archive")
    p_verify.set_defaults(func=_cmd_verify)

    # --- batch ---
    p_batch = sub.add_parser("batch", help="batch operations on a DAG of job specs")
    sp_batch = p_batch.add_subparsers(dest="batch_cmd", required=True)

    p_bs = sp_batch.add_parser("submit", help="run a batch.json to completion")
    p_bs.add_argument("batch", help="path to batch.json (defines jobs + policy + roots)")
    p_bs.add_argument("--out", default=None,
                      help=f"bundle staging root (default: {_DEFAULT_V2_BATCH_ROOT}/)")
    p_bs.add_argument("--state-file", default=None,
                      help="path to JSON state file (resumable on crash)")
    p_bs.add_argument("--hosts", default=None,
                      help="path to hosts.json (default: utils/offload_network/hosts.json)")
    p_bs.add_argument("--dry-run", action="store_true",
                      help="walk the DAG + dispatch nothing; record everything as succeeded")
    p_bs.set_defaults(func=_cmd_batch_submit)

    p_bst = sp_batch.add_parser("status", help="print a batch's per-job state")
    p_bst.add_argument("state_file", help="path to a batch state file (from a prior submit)")
    p_bst.set_defaults(func=_cmd_batch_status)

    p_brs = sp_batch.add_parser("resume", help="resume a partial batch from its state file")
    p_brs.add_argument("batch", help="path to batch.json")
    p_brs.add_argument("--state-file", required=True, help="path to existing state file")
    p_brs.add_argument("--out", default=None)
    p_brs.add_argument("--hosts", default=None)
    p_brs.add_argument("--dry-run", action="store_true")
    p_brs.set_defaults(func=_cmd_batch_resume)

    p_doc = sp_batch.add_parser("doctor",
        help="scan a state file for ghost jobs (status=running w/ stale heartbeat)")
    p_doc.add_argument("state_file", help="path to a batch state file")
    p_doc.set_defaults(func=_cmd_batch_doctor)

    p_rbs = sp_batch.add_parser("rebuild-state",
        help="reconstruct a corrupted/missing state file by scanning the configured v2 bundle root")
    p_rbs.add_argument("batch", help="path to batch.json")
    p_rbs.add_argument("--state-file", required=True,
                       help="where to write the rebuilt state file")
    p_rbs.add_argument("--out", default=None,
                       help=f"bundle root to scan (default: {_DEFAULT_V2_BATCH_ROOT})")
    p_rbs.set_defaults(func=_cmd_batch_rebuild_state)

    p_bl = sp_batch.add_parser("list", help="list all batch state files + their summary")
    p_bl.add_argument("--root", default=None,
                      help=f"dir to scan (default: {_DEFAULT_V2_BATCH_ROOT})")
    p_bl.set_defaults(func=_cmd_batch_list)

    p_bj = sp_batch.add_parser("jobs", help="per-job listing for a batch")
    p_bj.add_argument("state_file", help="path to a batch state file")
    p_bj.add_argument("--status", default=None,
                      help="filter to jobs with this status (eg. failed, skipped)")
    p_bj.set_defaults(func=_cmd_batch_jobs)

    p_prestage = sp_batch.add_parser(
        "prestage-cache-stage",
        help="rsync cache_stage .mat inputs to assigned hosts outside sealed archives",
    )
    p_prestage.add_argument("batch", help="path to batch.json")
    p_prestage.add_argument("--hosts", default=None,
                            help="hosts.json path (default: utils/offload_network/hosts.json)")
    p_prestage.add_argument("--only", action="append", default=[],
                            help="limit to a job name, instrument key, or instrument id; repeatable")
    p_prestage.add_argument("--force", action="store_true",
                            help="push even if remote byte-size already matches")
    p_prestage.add_argument("--dry-run", action="store_true",
                            help="show what would be pushed without transferring data")
    p_prestage.add_argument("--quiet", action="store_true",
                            help="suppress live rsync progress")
    p_prestage.add_argument("--timeout", type=int, default=7200,
                            help="per-transfer timeout seconds")
    p_prestage.set_defaults(func=_cmd_batch_prestage_cache_stage)

    ns = p.parse_args(argv)
    try:
        return ns.func(ns)
    except (SealError, SpecError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
