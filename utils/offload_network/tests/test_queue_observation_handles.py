"""Repeated read-only queue polling closes SQLite handles and preserves phase age."""

import json
import sqlite3

import pytest

from research_workflows import queue_view
from research_workflows.common import atomic
from tests.test_research_workflows import worker


@pytest.mark.parametrize("failed_read", [False, True])
def test_local_fallback_closes_every_connection(tmp_path, worker, monkeypatch, failed_read):
    token = tmp_path / "token"
    token.write_text("synthetic-local-token")
    config = tmp_path / "worker.json"
    atomic(config, {"port": 34567, "token_file": str(token), "root": str(worker.root),
                    "concurrency": worker.concurrency, "min_free_mb": worker.min_free_mb,
                    "workflows": {"capacity": worker.capacity}})
    profile = {"url": "http://127.0.0.1:34567", "token_file": str(token)}
    connect, opened = sqlite3.connect, []

    def tracked(*args, **kwargs):
        connection = connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(queue_view.sqlite3, "connect", tracked)
    if failed_read:
        def failed(_):
            raise RuntimeError("controlled snapshot failure")
        monkeypatch.setattr(queue_view, "read_rows", failed)
    for _ in range(3):
        if failed_read:
            with pytest.raises(RuntimeError, match="controlled snapshot failure"):
                queue_view.local_snapshot(config, profile)
        else:
            assert queue_view.local_snapshot(config, profile)["jobs"] == []
    assert len(opened) == 3
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


def test_queue_projection_preserves_phase_clock_and_rejects_wrong_attempt():
    phase = {"job_id": "phase-job", "attempt": "attempt-one", "phase": "VERIFYING_RESULT",
             "updated_at": 123.0, "observation_kind": "PHASE_TRANSITION_NOT_HEARTBEAT"}
    row = {"id": "phase-job", "state": "running", "attempt": "attempt-one", "created": 1,
           "updated": 123.0, "receipt": json.dumps({"worker_phase": phase}), "payload": "{}"}
    args = {"capacity": {}, "slots": 1, "free_bytes": 100, "min_free_mb": 0}
    first = queue_view.describe([row], [], **args)
    second = queue_view.describe([row], [], **args)
    assert first["jobs"][0]["worker_phase"] == second["jobs"][0]["worker_phase"] == phase
    row["attempt"] = "replacement"
    assert "worker_phase" not in queue_view.describe([row], [], **args)["jobs"][0]
