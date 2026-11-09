"""Append-only event + alert ledger writers.

The ledger lives on the external drive at:

    $FAMOUS_MODEL_DATA_ROOT/cluster_state/job_ledger.jsonl
    $FAMOUS_MODEL_DATA_ROOT/cluster_state/alerts.jsonl

Both are JSONL — one JSON object per line, append-only, never edited.

Why append-only: the only safe way to record "what happened" across
multiple writers without coordination. An operator (or another agent)
can re-read the file at any point and reconstruct history.
"""
from __future__ import annotations

import os
import pathlib
import time
from typing import Iterable

from .schema import Alert, JobEvent


def _data_root() -> pathlib.Path:
    return pathlib.Path(
        os.environ.get("FAMOUS_MODEL_DATA_ROOT")
        or os.environ.get("EXTERNAL_DRIVE")
        or "/Volumes/Untitled/famous_model"
    )


def _cluster_state_dir() -> pathlib.Path:
    return _data_root() / "cluster_state"


def _ledger_path() -> pathlib.Path:
    return _cluster_state_dir() / "job_ledger.jsonl"


def _alerts_path() -> pathlib.Path:
    return _cluster_state_dir() / "alerts.jsonl"


def _atomic_append(path: pathlib.Path, line: str) -> None:
    """Append a single line to ``path`` atomically.

    Uses POSIX O_APPEND semantics — atomic for any write smaller than
    PIPE_BUF (4 KB on macOS); a single JSON line fits well within that.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if not line.endswith("\n"):
        line = line + "\n"
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def append_event(event: JobEvent) -> None:
    """Append a JobEvent row to job_ledger.jsonl."""
    _atomic_append(_ledger_path(), event.to_json_line())


def append_alert(alert: Alert) -> None:
    """Append an Alert row to alerts.jsonl."""
    _atomic_append(_alerts_path(), alert.to_json_line())


def read_recent_alerts(hours: int = 24) -> Iterable[dict]:
    """Yield alerts.jsonl rows from the last ``hours`` hours, newest first.

    Returns dicts (not Alert objects) so callers don't need to import schema.
    """
    import json
    path = _alerts_path()
    if not path.exists():
        return iter(())

    cutoff_epoch = time.time() - hours * 3600
    rows: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Compare ISO timestamps lexically only if they share format; safer to
        # convert and use epoch.
        ts = row.get("time")
        if ts:
            try:
                # 2026-06-04T00:08:00Z
                epoch = time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
            except ValueError:
                epoch = 0
            if epoch < cutoff_epoch:
                continue
        rows.append(row)
    return reversed(rows)  # newest first


def count_recent_alerts_by_kind(kind: str, hours: int = 24,
                                 job_id: int | None = None) -> int:
    """Count recent alerts matching ``kind`` (and optionally ``job_id``).

    Per the escalation principle, the threshold should typically be per
    (kind, job_id) tuple — same kind on different jobs are different problems
    and should not collectively trip the global limit. Caller passes job_id
    when checking whether to STOP retrying for that specific job."""
    n = 0
    for r in read_recent_alerts(hours):
        if r.get("kind") != kind:
            continue
        if job_id is not None and r.get("job_id") != job_id:
            continue
        n += 1
    return n
