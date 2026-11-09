"""Persistence: append-only event log + materialised JSON views.

All writes go to events.jsonl via _atomic_append (O_APPEND on POSIX is atomic
for writes <PIPE_BUF). The materialised workitems.json / artifacts.json files
are derived from events on every read — that way crashes during view rebuild
don't corrupt history.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import threading
import sys as _sys
from typing import Iterable

try:
    from fleet.paths import orchestrator_dir
except ModuleNotFoundError:
    _OFFLOAD_DIR = pathlib.Path(__file__).resolve().parents[2]
    if str(_OFFLOAD_DIR) not in _sys.path:
        _sys.path.insert(0, str(_OFFLOAD_DIR))
    from fleet.paths import orchestrator_dir  # type: ignore[misc]

from .schema import (
    WorkItem, Artifact, Event, WorkType, WorkStatus,
    ArtifactType, StorageTier,
)


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _atomic_append(path: pathlib.Path, line: str) -> None:
    """Atomic append for <PIPE_BUF bytes (4 KB on macOS). Each call writes one
    \\n-terminated JSON object — well under the limit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not line.endswith("\n"):
        line += "\n"
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


class OrchestratorStore:
    """Manages the catalog. Thread-safe for single-process; multi-process
    relies on append-only semantics."""

    def __init__(self, base_dir: pathlib.Path | str | None = None):
        if base_dir is None:
            base_dir = orchestrator_dir()
        self.base_dir = pathlib.Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        (self.base_dir / "inventory").mkdir(exist_ok=True)
        (self.base_dir / "snapshots").mkdir(exist_ok=True)
        self.events_path     = self.base_dir / "events.jsonl"
        self.workitems_path  = self.base_dir / "workitems.json"
        self.artifacts_path  = self.base_dir / "artifacts.json"
        self._lock = threading.Lock()

    # -- append-only event log --------------------------------------------
    def record(self, kind: str, payload: dict) -> None:
        evt = Event(ts=_now_iso(), kind=kind, payload=payload)
        _atomic_append(self.events_path, json.dumps(evt.to_dict(), default=str))

    def read_events(self) -> Iterable[Event]:
        if not self.events_path.exists():
            return
        with open(self.events_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    yield Event(**d)
                except Exception:
                    continue  # tolerate partial writes / format drift

    # -- materialised views (rebuilt from events) -------------------------
    def materialise(self) -> tuple[dict[str, WorkItem], dict[str, Artifact]]:
        """Replay events into the current state of (workitems, artifacts)."""
        workitems: dict[str, WorkItem] = {}
        artifacts: dict[str, Artifact] = {}

        for evt in self.read_events():
            p = evt.payload
            try:
                if evt.kind == "workitem_create":
                    wi = WorkItem(**self._inflate_workitem(p))
                    workitems[wi.id] = wi
                elif evt.kind == "workitem_status":
                    wi = workitems.get(p["id"])
                    if wi:
                        wi.status = WorkStatus(p["status"])
                        if p.get("started_at"):    wi.started_at = p["started_at"]
                        if p.get("completed_at"):  wi.completed_at = p["completed_at"]
                        if p.get("retry_count") is not None:
                            wi.retry_count = p["retry_count"]
                        if p.get("last_error"):    wi.last_error = p["last_error"]
                elif evt.kind == "artifact_observe":
                    a = Artifact(**self._inflate_artifact(p))
                    artifacts[a.id] = a
                elif evt.kind == "artifact_delete":
                    a = artifacts.get(p["id"])
                    if a:
                        a.storage_tier = StorageTier.GONE
                        a.last_observed_at = evt.ts
            except Exception:
                continue

        # Write materialised views (best-effort; not load-bearing)
        with self._lock:
            self.workitems_path.write_text(
                json.dumps({k: v.to_dict() for k, v in workitems.items()},
                           indent=2, default=str)
            )
            self.artifacts_path.write_text(
                json.dumps({k: v.to_dict() for k, v in artifacts.items()},
                           indent=2, default=str)
            )
        return workitems, artifacts

    # -- convenience constructors -----------------------------------------
    def submit_workitem(self, *, id: str, work_type: WorkType, host: str,
                        cohort: str | None = None,
                        fleet_job_id: int | None = None,
                        parent_id: str | None = None,
                        command: str | None = None,
                        notes: str = "") -> None:
        self.record("workitem_create", {
            "id": id, "work_type": work_type.value, "host": host,
            "status": WorkStatus.PENDING.value, "created_at": _now_iso(),
            "cohort": cohort, "fleet_job_id": fleet_job_id,
            "parent_id": parent_id, "command": command, "notes": notes,
        })

    def update_status(self, workitem_id: str, status: WorkStatus,
                      *, retry_count: int | None = None,
                      last_error: str | None = None) -> None:
        payload = {"id": workitem_id, "status": status.value}
        if status == WorkStatus.RUNNING:
            payload["started_at"] = _now_iso()
        elif status in (WorkStatus.EXITED, WorkStatus.COLLECTED,
                        WorkStatus.ARCHIVED, WorkStatus.FAILED, WorkStatus.CANCELLED):
            payload["completed_at"] = _now_iso()
        if retry_count is not None:
            payload["retry_count"] = retry_count
        if last_error:
            payload["last_error"] = last_error
        self.record("workitem_status", payload)

    def observe_artifact(self, *, id: str, artifact_type: ArtifactType,
                         storage_tier: StorageTier, host: str | None,
                         path: str, size_bytes: int = 0,
                         file_count: int = 0,
                         cohort_name: str | None = None,
                         produced_by: str | None = None,
                         notes: str = "") -> None:
        self.record("artifact_observe", {
            "id": id, "artifact_type": artifact_type.value,
            "storage_tier": storage_tier.value, "host": host, "path": path,
            "size_bytes": size_bytes, "file_count": file_count,
            "cohort_name": cohort_name, "produced_by": produced_by,
            "last_observed_at": _now_iso(), "notes": notes,
        })

    def mark_artifact_gone(self, artifact_id: str) -> None:
        self.record("artifact_delete", {"id": artifact_id})

    # -- private inflation helpers ----------------------------------------
    @staticmethod
    def _inflate_workitem(d: dict) -> dict:
        d = dict(d)
        d["work_type"] = WorkType(d["work_type"])
        d["status"]    = WorkStatus(d["status"])
        d.setdefault("inputs", [])
        d.setdefault("outputs", [])
        return d

    @staticmethod
    def _inflate_artifact(d: dict) -> dict:
        d = dict(d)
        d["artifact_type"] = ArtifactType(d["artifact_type"])
        d["storage_tier"]  = StorageTier(d["storage_tier"])
        return d


# Module-level singleton helpers
_store_singleton: OrchestratorStore | None = None


def get_store() -> OrchestratorStore:
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = OrchestratorStore()
    return _store_singleton


def record_event(kind: str, payload: dict) -> None:
    get_store().record(kind, payload)


def materialise_view() -> tuple[dict, dict]:
    return get_store().materialise()
