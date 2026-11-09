"""Auto-import workitem events from /tmp/migrate_*.log and
/tmp/auto_collect_watcher.log produced by the session's bash workflows.

These logs are written by ad-hoc scripts (migrate_kenne_stale_to_archive.sh,
auto_collect_watcher.sh, etc.). They're our primary source of truth for
migrations, collects, and recoveries that fleet.py doesn't track natively.

Each parser is idempotent at the LINE level — re-importing the same log
appends duplicate events to events.jsonl, which is fine because materialise()
just keeps the last-known status per workitem id. We make ids deterministic
from (log_path, host, source/jid, line_offset) so replay is stable.
"""
from __future__ import annotations

import pathlib
import re

from .schema import WorkType, WorkStatus
from .store import get_store


# Migration script format (migrate_*_stale_to_archive.sh):
#   [21:21:59] === migrating fleet-offload-validation-20260602 ===
#   [21:21:59] === migrating cdec:fleet-offload-goal-20260602 ===
#   [21:21:59]   rsync rc=0
#   [21:29:50]   ✓ counts match — deleting remote
#   [21:29:51]   delete rc=0
RE_MIG_START   = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\] === migrating (?:([^:]+):)?(\S+) ===')
RE_MIG_RSYNC   = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\]\s+rsync rc=(\d+)')
RE_MIG_DELETE  = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\]\s+delete rc=(\d+)')
RE_MIG_COMPLETE = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\].*migration complete')

# Auto-collect watcher format (auto_collect_watcher.sh):
#   [2026-06-05 00:04:47] auto_collect_watcher started (poll=...)
#   [00:04:47] cycle 1: launching collect 12
#   [00:04:47] cycle 1: collect 12 rc=23
#   [00:04:47] cycle 1: collect 12 already running, skip
#   [00:10:00] cycle 2: 0 exited jobs (idle=1/6)
RE_WATCH_LAUNCH  = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\] cycle (\d+): launching collect (\d+)')
RE_WATCH_FINISH  = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\] cycle (\d+): collect (\d+) rc=(-?\d+)')
RE_WATCH_SKIP    = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\] cycle (\d+): collect (\d+) already running, skip')
RE_WATCH_IDLE    = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\] cycle (\d+): 0 exited jobs')

# Chain2 format (similar to watcher but separate file):
#   [16:18:30] starting collect 8
#   [16:18:30] finished collect 8 rc=0
RE_CHAIN_START   = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\] starting collect (\d+)')
RE_CHAIN_FINISH  = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\] finished collect (\d+) rc=(-?\d+)')


def _rc_to_status(rc: int) -> tuple[WorkStatus, str | None]:
    """Map rsync/fleet exit code to a WorkStatus and optional error note."""
    if rc == 0:
        return WorkStatus.COLLECTED, None
    if rc == 23:
        # rsync "vanished source" — remote dir was already deleted, no-op success
        return WorkStatus.COLLECTED, "rsync rc=23 (remote dir gone — no-op)"
    if rc == 2:
        # fleet.py verify-failure (log files mismatched during transfer)
        return WorkStatus.FAILED, "rc=2 (verify mismatch — retry via .rsync-partial)"
    return WorkStatus.FAILED, f"rc={rc}"


def import_migration_log(path: pathlib.Path) -> int:
    """Parse a migration log; emit one workitem per `=== migrating ... ===` block.
    Returns the count of events emitted (create + status pairs)."""
    if not path.exists():
        return 0
    store = get_store()
    count = 0
    current_id: str | None = None
    log_stem = path.stem

    with open(path) as f:
        for ln_no, line in enumerate(f, start=1):
            line = line.rstrip()

            m = RE_MIG_START.match(line)
            if m:
                ts, host, src = m.groups()
                host = host or "?"
                wid = f"mig-{log_stem}-{ln_no}-{src}"
                store.submit_workitem(
                    id=wid, work_type=WorkType.MIGRATION, host=host,
                    notes=f"log={path.name} ts={ts} src={src}",
                )
                store.update_status(wid, WorkStatus.RUNNING)
                current_id = wid
                count += 2
                continue

            m = RE_MIG_RSYNC.match(line)
            if m and current_id:
                ts, rc = m.groups()
                status, err = _rc_to_status(int(rc))
                # for migrations, rsync success means the data is on external (archive)
                final = WorkStatus.ARCHIVED if status == WorkStatus.COLLECTED else WorkStatus.FAILED
                store.update_status(current_id, final, last_error=err)
                current_id = None
                count += 1
                continue
    return count


def import_watcher_log(path: pathlib.Path) -> int:
    """Parse the auto_collect_watcher log. Each `launching collect N` →
    a COLLECT workitem; the matching `collect N rc=X` updates its status."""
    if not path.exists():
        return 0
    store = get_store()
    count = 0
    log_stem = path.stem
    open_collects: dict[str, str] = {}  # "cycle-jid" -> workitem_id

    with open(path) as f:
        for ln_no, line in enumerate(f, start=1):
            line = line.rstrip()

            m = RE_WATCH_LAUNCH.match(line)
            if m:
                ts, cycle, jid = m.groups()
                key = f"{cycle}-{jid}"
                wid = f"watcher-c{cycle}-job{jid}-ln{ln_no}"
                store.submit_workitem(
                    id=wid, work_type=WorkType.COLLECT, host="?",
                    fleet_job_id=int(jid),
                    parent_id=f"watcher-cycle-{cycle}",
                    notes=f"auto_collect_watcher cycle {cycle} ts={ts}",
                )
                store.update_status(wid, WorkStatus.RUNNING)
                open_collects[key] = wid
                count += 2
                continue

            m = RE_WATCH_FINISH.match(line)
            if m:
                ts, cycle, jid, rc = m.groups()
                key = f"{cycle}-{jid}"
                wid = open_collects.pop(key, None)
                if not wid:
                    wid = f"watcher-c{cycle}-job{jid}-ln{ln_no}"
                    store.submit_workitem(
                        id=wid, work_type=WorkType.COLLECT, host="?",
                        fleet_job_id=int(jid),
                        parent_id=f"watcher-cycle-{cycle}",
                        notes=f"auto_collect_watcher (orphan finish) cycle {cycle} ts={ts}",
                    )
                    count += 1
                status, err = _rc_to_status(int(rc))
                store.update_status(wid, status, last_error=err)
                count += 1
                continue
    return count


def import_chain_log(path: pathlib.Path) -> int:
    """Parse the legacy chain2_all_exited.log (same format as watcher start/finish)."""
    if not path.exists():
        return 0
    store = get_store()
    count = 0
    log_stem = path.stem
    open_collects: dict[str, str] = {}

    with open(path) as f:
        for ln_no, line in enumerate(f, start=1):
            line = line.rstrip()
            m = RE_CHAIN_START.match(line)
            if m:
                ts, jid = m.groups()
                wid = f"chain-{log_stem}-job{jid}-ln{ln_no}"
                store.submit_workitem(
                    id=wid, work_type=WorkType.COLLECT, host="?",
                    fleet_job_id=int(jid),
                    parent_id="chain-legacy",
                    notes=f"legacy chain wrapper ts={ts}",
                )
                store.update_status(wid, WorkStatus.RUNNING)
                open_collects[jid] = wid
                count += 2
                continue
            m = RE_CHAIN_FINISH.match(line)
            if m:
                ts, jid, rc = m.groups()
                wid = open_collects.pop(jid, None)
                if not wid:
                    wid = f"chain-{log_stem}-job{jid}-ln{ln_no}-orphan"
                    store.submit_workitem(
                        id=wid, work_type=WorkType.COLLECT, host="?",
                        fleet_job_id=int(jid), parent_id="chain-legacy",
                        notes=f"legacy chain (orphan finish) ts={ts}",
                    )
                    count += 1
                status, err = _rc_to_status(int(rc))
                store.update_status(wid, status, last_error=err)
                count += 1
                continue
    return count


def import_all_logs(log_dir: pathlib.Path | str = "/tmp") -> dict[str, int]:
    """Find and import every log family we know about under log_dir."""
    log_dir = pathlib.Path(log_dir)
    results: dict[str, int] = {}

    for p in sorted(log_dir.glob("migrate_*.log")):
        # Skip the *_wrapper.log files (they're empty stdout captures)
        if "_wrapper" in p.name:
            continue
        results[str(p)] = import_migration_log(p)

    for name in ("auto_collect_watcher.log",):
        p = log_dir / name
        if p.exists():
            results[str(p)] = import_watcher_log(p)

    for name in ("chain2_all_exited.log", "kenne_chain.log",
                 "collect_chain_kenne.log", "recover_26_30.log"):
        p = log_dir / name
        if p.exists():
            results[str(p)] = import_chain_log(p)

    return results
