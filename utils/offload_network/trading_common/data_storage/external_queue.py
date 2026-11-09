"""Local queue and traffic ledger for external-drive tasks.

The queue state lives under ``.data_work`` by default, not on the external
drive. Independent processes can safely enqueue tasks concurrently through
SQLite. A worker then executes one task at a time per lane, recording every
state transition in both SQLite and a JSONL traffic log.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
from typing import Any, Iterable
import uuid

from .layout import DataLayout, utc_now_iso
from .mount_health import external_health_payload
from lib.file_lock import file_lock
from lib.process_tree import run_tree


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    lane TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    name TEXT NOT NULL,
    command_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    worker_id TEXT,
    started_at TEXT,
    finished_at TEXT,
    returncode INTEGER,
    stdout_path TEXT,
    stderr_path TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status_lane_priority
    ON tasks(status, lane, priority, id);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    task_id INTEGER,
    event TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}'
);
"""


def default_db_path(layout: DataLayout) -> Path:
    return layout.runs_work / "external_drive_queue.sqlite"


def default_traffic_log(layout: DataLayout) -> Path:
    return layout.runs_work / "external_drive_traffic.jsonl"


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript(SCHEMA)
    return conn


def _append_traffic(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def record_event(
    conn: sqlite3.Connection,
    *,
    traffic_log: Path | None,
    task_id: int | None,
    event: str,
    detail: dict[str, Any] | None = None,
) -> None:
    payload = {
        "at": utc_now_iso(),
        "taskId": task_id,
        "event": event,
        "detail": detail or {},
    }
    conn.execute(
        "INSERT INTO events(at, task_id, event, detail_json) VALUES (?, ?, ?, ?)",
        (payload["at"], task_id, event, json.dumps(payload["detail"], sort_keys=True)),
    )
    _append_traffic(traffic_log, payload)


def enqueue_task(
    conn: sqlite3.Connection,
    *,
    traffic_log: Path | None,
    name: str,
    command: list[str],
    lane: str,
    priority: int,
    metadata: dict[str, Any] | None = None,
) -> int:
    now = utc_now_iso()
    cur = conn.execute(
        """
        INSERT INTO tasks(created_at, updated_at, lane, priority, name, command_json, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now,
            now,
            lane,
            priority,
            name,
            json.dumps(command),
            json.dumps(metadata or {}, sort_keys=True),
        ),
    )
    task_id = int(cur.lastrowid)
    record_event(
        conn,
        traffic_log=traffic_log,
        task_id=task_id,
        event="enqueued",
        detail={"lane": lane, "priority": priority, "name": name, "command": command},
    )
    return task_id


def acquire_task(
    conn: sqlite3.Connection,
    *,
    traffic_log: Path | None,
    worker_id: str,
    lane: str,
    requires_external_drive: bool | None = None,
) -> sqlite3.Row | None:
    conn.execute("BEGIN IMMEDIATE")
    try:
        active = conn.execute(
            "SELECT id FROM tasks WHERE lane = ? AND status = 'running' LIMIT 1",
            (lane,),
        ).fetchone()
        if active is not None:
            conn.execute("COMMIT")
            return None
        clauses = ["lane = ?", "status = 'queued'"]
        params: list[Any] = [lane]
        if requires_external_drive is False:
            clauses.append(
                """
                (
                    json_extract(metadata_json, '$.requiresExternalDrive') = 0
                    OR json_extract(metadata_json, '$.requires_external_drive') = 0
                )
                """
            )
        task = conn.execute(
            f"""
            SELECT * FROM tasks
            WHERE {' AND '.join(clauses)}
            ORDER BY priority ASC, id ASC
            LIMIT 1
            """,
            params,
        ).fetchone()
        if task is None:
            conn.execute("COMMIT")
            return None
        now = utc_now_iso()
        conn.execute(
            """
            UPDATE tasks
            SET status = 'running',
                updated_at = ?,
                started_at = ?,
                attempts = attempts + 1,
                worker_id = ?
            WHERE id = ?
            """,
            (now, now, worker_id, int(task["id"])),
        )
        record_event(
            conn,
            traffic_log=traffic_log,
            task_id=int(task["id"]),
            event="started",
            detail={"workerId": worker_id, "lane": lane},
        )
        conn.execute("COMMIT")
        return conn.execute("SELECT * FROM tasks WHERE id = ?", (int(task["id"]),)).fetchone()
    except Exception:
        conn.execute("ROLLBACK")
        raise


def complete_task(
    conn: sqlite3.Connection,
    *,
    traffic_log: Path | None,
    task_id: int,
    status: str,
    returncode: int | None,
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
    error: str = "",
) -> None:
    now = utc_now_iso()
    conn.execute(
        """
        UPDATE tasks
        SET status = ?,
            updated_at = ?,
            finished_at = ?,
            returncode = ?,
            stdout_path = ?,
            stderr_path = ?,
            error = ?
        WHERE id = ?
        """,
        (
            status,
            now,
            now,
            returncode,
            str(stdout_path) if stdout_path is not None else None,
            str(stderr_path) if stderr_path is not None else None,
            error,
            task_id,
        ),
    )
    record_event(
        conn,
        traffic_log=traffic_log,
        task_id=task_id,
        event=status,
        detail={
            "returncode": returncode,
            "stdoutPath": str(stdout_path) if stdout_path is not None else None,
            "stderrPath": str(stderr_path) if stderr_path is not None else None,
            "error": error,
        },
    )


def defer_task(
    conn: sqlite3.Connection,
    *,
    traffic_log: Path | None,
    task_id: int,
    reason: str,
) -> None:
    now = utc_now_iso()
    conn.execute(
        """
        UPDATE tasks
        SET status = 'queued',
            updated_at = ?,
            worker_id = NULL,
            started_at = NULL,
            error = ?
        WHERE id = ?
        """,
        (now, reason, task_id),
    )
    record_event(conn, traffic_log=traffic_log, task_id=task_id, event="deferred", detail={"reason": reason})


def cancel_tasks(
    conn: sqlite3.Connection,
    *,
    traffic_log: Path | None,
    lane: str | None = None,
    status: str = "queued",
    name_prefix: str = "",
    dry_run: bool = False,
) -> list[int]:
    clauses = ["status = ?"]
    params: list[Any] = [status]
    if lane:
        clauses.append("lane = ?")
        params.append(lane)
    if name_prefix:
        clauses.append("name LIKE ?")
        params.append(f"{name_prefix}%")
    sql = f"SELECT id FROM tasks WHERE {' AND '.join(clauses)} ORDER BY id"
    ids = [int(row["id"]) for row in conn.execute(sql, params).fetchall()]
    if dry_run:
        return ids
    now = utc_now_iso()
    for task_id in ids:
        conn.execute(
            """
            UPDATE tasks
            SET status = 'canceled',
                updated_at = ?,
                finished_at = ?,
                error = ?
            WHERE id = ?
            """,
            (now, now, "canceled by operator", task_id),
        )
        record_event(
            conn,
            traffic_log=traffic_log,
            task_id=task_id,
            event="canceled",
            detail={"lane": lane, "previousStatus": status, "namePrefix": name_prefix},
        )
    return ids


def _task_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    out["command"] = json.loads(out.pop("command_json"))
    out["metadata"] = json.loads(out.pop("metadata_json"))
    return out


def _task_requires_external_drive(row: sqlite3.Row) -> bool:
    metadata = json.loads(row["metadata_json"] or "{}")
    if "requiresExternalDrive" in metadata:
        return bool(metadata["requiresExternalDrive"])
    if "requires_external_drive" in metadata:
        return bool(metadata["requires_external_drive"])
    return True


def _uninterruptible_count(health: dict[str, Any]) -> int:
    processes = health.get("processes") or {}
    return int(processes.get("uninterruptible") or 0)


def queue_status(conn: sqlite3.Connection) -> dict[str, Any]:
    counts = {
        row["status"]: int(row["n"])
        for row in conn.execute("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status").fetchall()
    }
    lanes = {
        row["lane"]: int(row["n"])
        for row in conn.execute("SELECT lane, COUNT(*) AS n FROM tasks WHERE status IN ('queued', 'running') GROUP BY lane").fetchall()
    }
    tasks = [
        _task_to_dict(row)
        for row in conn.execute(
            """
            SELECT * FROM tasks
            ORDER BY CASE status WHEN 'running' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END,
                     priority ASC,
                     id DESC
            LIMIT 50
            """
        ).fetchall()
    ]
    return {
        "generatedAtUtc": utc_now_iso(),
        "counts": counts,
        "activeLanes": lanes,
        "tasks": tasks,
    }


def _run_task_command(
    task: sqlite3.Row,
    *,
    layout: DataLayout,
    dry_run: bool,
    timeout_s: float = 86400,
) -> tuple[int, Path | None, Path | None, str]:
    command = json.loads(task["command_json"])
    if dry_run:
        return 0, None, None, "dry_run"
    logs = layout.runs_work / "external_drive_queue" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stdout_path = logs / f"task_{int(task['id']):06d}.stdout.log"
    stderr_path = logs / f"task_{int(task['id']):06d}.stderr.log"
    with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
        proc = run_tree(command, stdout=stdout, stderr=stderr, timeout=timeout_s)
    return int(proc.returncode), stdout_path, stderr_path, ""


def _lane_lock(db_path, lane):
    digest = hashlib.sha256(lane.encode()).hexdigest()
    return Path(db_path).parent / (Path(db_path).name + ".lanes") / (digest + ".lock")


def recover_task(conn, *, db_path, task_id, confirmed_stopped, traffic_log=None):
    """Explicit reconciliation for legacy host commands, never a blind retry.

    Unlike the Docker worker we cannot safely discover all children of arbitrary
    old host commands after a crash. The operator must confirm they are stopped.
    An OS lane lock additionally prevents reconciliation of a live worker.
    """
    if not confirmed_stopped:
        raise ValueError("confirm the old command and descendants have stopped before recovery")
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if row is None:
        raise ValueError("unknown task ID")
    with file_lock(_lane_lock(db_path, row["lane"]), timeout=0):
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row["status"] != "running":
                raise ValueError("only abandoned running tasks can be recovered")
            complete_task(conn, traffic_log=traffic_log, task_id=task_id, status="interrupted",
                          returncode=None, error="operator confirmed previous process tree stopped; not replayed")
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise


def run_once(args: argparse.Namespace) -> int:
    layout = DataLayout(root=args.root, work_root=args.work_root)
    db_path = args.db_path or default_db_path(layout)
    if args.timeout_s <= 0:
        raise ValueError("timeout must be positive")
    with file_lock(_lane_lock(db_path, args.lane), timeout=0):
        return _run_once_locked(args)


def _run_once_locked(args: argparse.Namespace) -> int:
    layout = DataLayout(root=args.root, work_root=args.work_root)
    db_path = args.db_path or default_db_path(layout)
    traffic_log = None if args.no_traffic_log else (args.traffic_log or default_traffic_log(layout))
    conn = connect(db_path)
    worker_id = args.worker_id or f"{uuid.uuid4()}"
    preflight_health = external_health_payload(layout.root) if args.defer_on_unhealthy else {}
    skip_external = (
        bool(args.skip_unhealthy_external)
        and args.defer_on_unhealthy
        and _uninterruptible_count(preflight_health) > args.max_u_processes
    )
    task = acquire_task(
        conn,
        traffic_log=traffic_log,
        worker_id=worker_id,
        lane=args.lane,
        requires_external_drive=False if skip_external else None,
    )
    if task is None:
        reason = "no queued task or lane already running"
        if skip_external:
            reason = "external drive unhealthy and no local-only queued task is runnable"
        print(json.dumps({"ok": True, "ran": False, "reason": reason}, indent=2))
        return 0

    health = preflight_health if _task_requires_external_drive(task) else {}
    if (
        args.defer_on_unhealthy
        and _task_requires_external_drive(task)
        and _uninterruptible_count(health) > args.max_u_processes
    ):
        reason = f"drive unhealthy: U={_uninterruptible_count(health)} > {args.max_u_processes}"
        defer_task(conn, traffic_log=traffic_log, task_id=int(task["id"]), reason=reason)
        print(json.dumps({"ok": False, "ran": False, "deferred": True, "reason": reason, "task": _task_to_dict(task)}, indent=2))
        return 2

    try:
        returncode, stdout_path, stderr_path, error = _run_task_command(
            task, layout=layout, dry_run=args.dry_run, timeout_s=args.timeout_s)
        status = "succeeded" if returncode == 0 else "failed"
        complete_task(
            conn,
            traffic_log=traffic_log,
            task_id=int(task["id"]),
            status=status,
            returncode=returncode,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            error=error,
        )
        final_task = conn.execute("SELECT * FROM tasks WHERE id = ?", (int(task["id"]),)).fetchone()
        print(
            json.dumps(
                {"ok": returncode == 0, "ran": True, "status": status, "task": _task_to_dict(final_task)},
                indent=2,
            )
        )
        return 0 if returncode == 0 else returncode
    except Exception as exc:
        complete_task(
            conn,
            traffic_log=traffic_log,
            task_id=int(task["id"]),
            status="failed",
            returncode=None,
            error=repr(exc),
        )
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DataLayout().root)
    parser.add_argument("--work-root", type=Path, default=DataLayout().work_root)
    parser.add_argument("--db-path", type=Path)
    parser.add_argument("--traffic-log", type=Path)
    parser.add_argument("--no-traffic-log", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    enqueue = sub.add_parser("enqueue", help="Queue a command for serialized external-drive execution.")
    enqueue.add_argument("--name", required=True)
    enqueue.add_argument("--lane", default="external-drive")
    enqueue.add_argument("--priority", type=int, default=100)
    enqueue.add_argument("--metadata-json", default="{}")
    enqueue.add_argument("command", nargs=argparse.REMAINDER, help="Command after --, for example: -- rsync ...")

    run = sub.add_parser("run-once", help="Run at most one queued task.")
    run.add_argument("--lane", default="external-drive")
    run.add_argument("--worker-id", default="")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--defer-on-unhealthy", action="store_true")
    run.add_argument(
        "--skip-unhealthy-external",
        action="store_true",
        help="When the external drive is unhealthy, run the next local-only task instead of repeatedly deferring the first external task.",
    )
    run.add_argument("--max-u-processes", type=int, default=0)
    run.add_argument("--timeout-s", type=float, default=86400)

    recover = sub.add_parser("recover", help="Reconcile an abandoned host-command task; does not replay it.")
    recover.add_argument("--task-id", type=int, required=True)
    recover.add_argument("--confirmed-stopped", action="store_true")

    cancel = sub.add_parser("cancel", help="Cancel queued tasks matching filters.")
    cancel.add_argument("--lane")
    cancel.add_argument("--status", default="queued")
    cancel.add_argument("--name-prefix", default="")
    cancel.add_argument("--dry-run", action="store_true")

    sub.add_parser("status", help="Show queue status.")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    layout = DataLayout(root=args.root, work_root=args.work_root)
    db_path = args.db_path or default_db_path(layout)
    traffic_log = None if args.no_traffic_log else (args.traffic_log or default_traffic_log(layout))
    conn = connect(db_path)
    if args.cmd == "enqueue":
        command = list(args.command)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            raise SystemExit("enqueue requires a command after --")
        metadata = json.loads(args.metadata_json)
        task_id = enqueue_task(
            conn,
            traffic_log=traffic_log,
            name=args.name,
            command=command,
            lane=args.lane,
            priority=args.priority,
            metadata=metadata,
        )
        print(json.dumps({"ok": True, "taskId": task_id}, indent=2))
        return 0
    if args.cmd == "run-once":
        return run_once(args)
    if args.cmd == "recover":
        recover_task(conn, db_path=db_path, task_id=args.task_id,
                     confirmed_stopped=args.confirmed_stopped, traffic_log=traffic_log)
        print(json.dumps({"ok": True, "taskId": args.task_id, "status": "interrupted"}))
        return 0
    if args.cmd == "cancel":
        ids = cancel_tasks(
            conn,
            traffic_log=traffic_log,
            lane=args.lane,
            status=args.status,
            name_prefix=args.name_prefix,
            dry_run=args.dry_run,
        )
        print(json.dumps({"ok": True, "dryRun": args.dry_run, "matched": len(ids), "taskIds": ids}, indent=2))
        return 0
    if args.cmd == "status":
        print(json.dumps(queue_status(conn), indent=2, sort_keys=True))
        return 0
    raise SystemExit(f"unknown command {args.cmd!r}")


if __name__ == "__main__":
    raise SystemExit(main())
