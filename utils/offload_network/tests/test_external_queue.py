from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from trading_common.data_storage.external_queue import (
    acquire_task,
    cancel_tasks,
    connect,
    default_db_path,
    default_traffic_log,
    enqueue_task,
    main,
    queue_status,
)
from trading_common.data_storage.layout import DataLayout


def _layout(tmp_path: Path) -> DataLayout:
    return DataLayout(root=tmp_path / "live_data", work_root=tmp_path / ".data_work")


def _safe_health(root: Path) -> dict[str, object]:
    return {
        "root": str(root),
        "monitorPath": str(root),
        "mount": {"fsType": "apfs", "options": ["local"]},
        "okForLiveWrites": True,
        "warnings": [],
        "summary": "safe",
        "processes": {"matched": 0, "uninterruptible": 0, "rsync": 0, "broadScans": 0, "entries": []},
    }


def _unsafe_health(root: Path) -> dict[str, object]:
    health = _safe_health(root)
    health["okForLiveWrites"] = False
    health["summary"] = "blocked by U-state processes"
    health["warnings"] = ["U-state process present"]
    health["processes"] = {
        "matched": 1,
        "uninterruptible": 1,
        "rsync": 1,
        "broadScans": 0,
        "entries": [],
    }
    return health


def test_enqueue_records_task_and_jsonl_traffic(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    conn = connect(default_db_path(layout))
    traffic = default_traffic_log(layout)

    task_id = enqueue_task(
        conn,
        traffic_log=traffic,
        name="sync-google-ticks",
        command=["rsync", "-a", "src/", "dst/"],
        lane="external-drive",
        priority=10,
        metadata={"symbol": "GOOGL"},
    )

    status = queue_status(conn)
    assert status["counts"] == {"queued": 1}
    assert status["activeLanes"] == {"external-drive": 1}
    assert status["tasks"][0]["id"] == task_id
    assert status["tasks"][0]["metadata"] == {"symbol": "GOOGL"}

    events = [json.loads(line) for line in traffic.read_text(encoding="utf-8").splitlines()]
    assert events == [
        {
            "at": events[0]["at"],
            "detail": {
                "command": ["rsync", "-a", "src/", "dst/"],
                "lane": "external-drive",
                "name": "sync-google-ticks",
                "priority": 10,
            },
            "event": "enqueued",
            "taskId": task_id,
        }
    ]


def test_run_once_executes_command_and_records_logs(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    layout = _layout(tmp_path)
    marker = tmp_path / "ran.txt"
    monkeypatch.setattr("trading_common.data_storage.external_queue.external_health_payload", _safe_health)

    assert main(
        [
            "--root",
            str(layout.root),
            "--work-root",
            str(layout.work_root),
            "enqueue",
            "--name",
            "marker",
            "--lane",
            "external-drive",
            "--",
            sys.executable,
            "-c",
            f"from pathlib import Path; Path({str(marker)!r}).write_text('ok')",
        ]
    ) == 0
    assert main(
        [
            "--root",
            str(layout.root),
            "--work-root",
            str(layout.work_root),
            "run-once",
            "--lane",
            "external-drive",
            "--worker-id",
            "test-worker",
        ]
    ) == 0

    conn = connect(default_db_path(layout))
    status = queue_status(conn)
    assert marker.read_text(encoding="utf-8") == "ok"
    assert status["counts"] == {"succeeded": 1}
    task = status["tasks"][0]
    assert task["worker_id"] == "test-worker"
    assert Path(task["stdout_path"]).exists()
    assert Path(task["stderr_path"]).exists()

    events = [
        json.loads(line)["event"]
        for line in default_traffic_log(layout).read_text(encoding="utf-8").splitlines()
    ]
    assert events == ["enqueued", "started", "succeeded"]


def test_lane_with_running_task_does_not_start_another(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    conn = connect(default_db_path(layout))
    traffic = default_traffic_log(layout)
    enqueue_task(
        conn,
        traffic_log=traffic,
        name="first",
        command=["echo", "first"],
        lane="external-drive",
        priority=10,
    )
    enqueue_task(
        conn,
        traffic_log=traffic,
        name="second",
        command=["echo", "second"],
        lane="external-drive",
        priority=20,
    )

    first = acquire_task(conn, traffic_log=traffic, worker_id="worker-a", lane="external-drive")
    second = acquire_task(conn, traffic_log=traffic, worker_id="worker-b", lane="external-drive")

    assert first is not None
    assert second is None
    status = queue_status(conn)
    assert status["counts"] == {"queued": 1, "running": 1}


def test_defer_on_unhealthy_drive_requeues_task(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    layout = _layout(tmp_path)
    monkeypatch.setattr("trading_common.data_storage.external_queue.external_health_payload", _unsafe_health)
    assert main(
        [
            "--root",
            str(layout.root),
            "--work-root",
            str(layout.work_root),
            "enqueue",
            "--name",
            "would-write-drive",
            "--lane",
            "external-drive",
            "--",
            "echo",
            "write",
        ]
    ) == 0

    rc = main(
        [
            "--root",
            str(layout.root),
            "--work-root",
            str(layout.work_root),
            "run-once",
            "--lane",
            "external-drive",
            "--defer-on-unhealthy",
            "--max-u-processes",
            "0",
        ]
    )

    assert rc == 2
    conn = connect(default_db_path(layout))
    status = queue_status(conn)
    assert status["counts"] == {"queued": 1}
    assert "drive unhealthy" in status["tasks"][0]["error"]
    events = [
        json.loads(line)["event"]
        for line in default_traffic_log(layout).read_text(encoding="utf-8").splitlines()
    ]
    assert events == ["enqueued", "started", "deferred"]


def test_unhealthy_drive_does_not_defer_local_only_task(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    layout = _layout(tmp_path)
    marker = tmp_path / "local-stage.txt"
    monkeypatch.setattr("trading_common.data_storage.external_queue.external_health_payload", _unsafe_health)
    assert main(
        [
            "--root",
            str(layout.root),
            "--work-root",
            str(layout.work_root),
            "enqueue",
            "--name",
            "local-stage",
            "--lane",
            "iqfeed-staged",
            "--metadata-json",
            '{"requiresExternalDrive": false}',
            "--",
            sys.executable,
            "-c",
            f"from pathlib import Path; Path({str(marker)!r}).write_text('ok')",
        ]
    ) == 0

    rc = main(
        [
            "--root",
            str(layout.root),
            "--work-root",
            str(layout.work_root),
            "run-once",
            "--lane",
            "iqfeed-staged",
            "--defer-on-unhealthy",
            "--max-u-processes",
            "0",
        ]
    )

    assert rc == 0
    assert marker.read_text(encoding="utf-8") == "ok"
    assert queue_status(connect(default_db_path(layout)))["counts"] == {"succeeded": 1}


def test_skip_unhealthy_external_runs_later_local_task(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    layout = _layout(tmp_path)
    marker = tmp_path / "later-local.txt"
    monkeypatch.setattr("trading_common.data_storage.external_queue.external_health_payload", _unsafe_health)
    conn = connect(default_db_path(layout))
    traffic = default_traffic_log(layout)
    enqueue_task(
        conn,
        traffic_log=traffic,
        name="transfer-first",
        command=["echo", "transfer"],
        lane="iqfeed-staged",
        priority=1,
        metadata={"requiresExternalDrive": True},
    )
    enqueue_task(
        conn,
        traffic_log=traffic,
        name="stage-second",
        command=[sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('ok')"],
        lane="iqfeed-staged",
        priority=2,
        metadata={"requiresExternalDrive": False},
    )

    rc = main(
        [
            "--root",
            str(layout.root),
            "--work-root",
            str(layout.work_root),
            "run-once",
            "--lane",
            "iqfeed-staged",
            "--defer-on-unhealthy",
            "--skip-unhealthy-external",
            "--max-u-processes",
            "0",
        ]
    )

    assert rc == 0
    assert marker.read_text(encoding="utf-8") == "ok"
    status = queue_status(connect(default_db_path(layout)))
    assert status["counts"] == {"queued": 1, "succeeded": 1}
    by_name = {task["name"]: task for task in status["tasks"]}
    assert by_name["transfer-first"]["status"] == "queued"
    assert by_name["stage-second"]["status"] == "succeeded"


def test_same_database_accepts_multiple_process_like_connections(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    db_path = default_db_path(layout)
    traffic = default_traffic_log(layout)
    producer_a = connect(db_path)
    producer_b = connect(db_path)

    task_a = enqueue_task(
        producer_a,
        traffic_log=traffic,
        name="a",
        command=["echo", "a"],
        lane="rsync",
        priority=100,
    )
    task_b = enqueue_task(
        producer_b,
        traffic_log=traffic,
        name="b",
        command=["echo", "b"],
        lane="iqfeed",
        priority=100,
    )

    assert isinstance(producer_a, sqlite3.Connection)
    assert queue_status(connect(db_path))["counts"] == {"queued": 2}
    assert {task_a, task_b} == {1, 2}


def test_cancel_tasks_marks_matching_queued_tasks(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    conn = connect(default_db_path(layout))
    traffic = default_traffic_log(layout)
    enqueue_task(
        conn,
        traffic_log=traffic,
        name="iqfeed-intervals-spy",
        command=["echo", "download"],
        lane="iqfeed-download",
        priority=1,
    )
    enqueue_task(
        conn,
        traffic_log=traffic,
        name="other",
        command=["echo", "other"],
        lane="other",
        priority=1,
    )

    canceled = cancel_tasks(
        conn,
        traffic_log=traffic,
        lane="iqfeed-download",
        name_prefix="iqfeed-",
    )

    assert canceled == [1]
    assert queue_status(conn)["counts"] == {"canceled": 1, "queued": 1}
    events = [
        json.loads(line)["event"]
        for line in traffic.read_text(encoding="utf-8").splitlines()
    ]
    assert events == ["enqueued", "enqueued", "canceled"]
