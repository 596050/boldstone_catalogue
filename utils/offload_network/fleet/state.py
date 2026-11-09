"""fleet/state.py — atomic state.json IO + schema validation.

Solves two P0 issues from the 2026-06-05 scripts audit:
  1. state.json writes are not atomic across processes
     ➜ fcntl.LOCK_EX around every read-modify-write cycle
  2. No schema validation
     ➜ FleetJob dataclass + validate() rejects malformed records at read time

Usage:

    from fleet import load_state, save_state, mutate_state, FleetJob

    # Read-only (no lock held)
    state = load_state()

    # Read-modify-write with lock
    with mutate_state() as state:
        state["jobs"].append(new_job_dict)
        # auto-saves on context exit; lock released after write

    # Programmatic record building
    job = FleetJob(id=42, host="kenne", cohort="aapl_csv_uoa",
                   status=WorkStatus.RUNNING, wrapper_pid=12345)
    with mutate_state() as state:
        state["jobs"].append(job.to_dict())

The lock is process-level via fcntl. Multiple in-process readers may share
LOCK_SH but every mutator must acquire LOCK_EX. This blocks the
auto_collect_watcher from racing manual ``fleet collect`` invocations — the
suspected cause of the unexplained rc=137/143 watcher exits.
"""
from __future__ import annotations

import contextlib
import dataclasses
import enum
try:
    import fcntl
except ImportError:
    from lib import compat_fcntl as fcntl
import json
import os
import pathlib
import shutil
import time
from typing import Any, Iterator, Optional

from .paths import fleet_dir as _fleet_dir
from .paths import scopes_root, fleet_state_file, fleet_state_lock_file

# --- Storage paths (env-driven; see paths.py for external HDD + state-root resolution) ---
# Paths are resolved LAZILY so tests/fixtures can flip $FLEET_DIR without needing
# to reload the module (and so reload doesn't create duplicate StateError classes
# that break pytest.raises).
def fleet_dir() -> pathlib.Path:
    return _fleet_dir()


def state_path() -> pathlib.Path:
    return fleet_state_file()


def lock_path() -> pathlib.Path:
    return fleet_state_lock_file()


def _legacy_state_root() -> pathlib.Path:
    return pathlib.Path.home() / ".fleet"


def _copy_missing(src: pathlib.Path, dst: pathlib.Path) -> None:
    """Copy src to dst if dst does not exist.

    Recurses into directories and only creates/copies files that are missing.
    Existing targets are left untouched to preserve any in-flight local state.
    """
    if not src.exists():
        return
    if src.is_file():
        if dst.exists():
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            _copy_missing(child, dst / child.name)
        return


def _migrate_legacy_state_if_needed() -> None:
    """One-time migration from legacy ~/.fleet into scoped repo root.

    This is only run for default path resolution (states/scopes) and only
    when the local state.json is not already present.
    """
    if os.environ.get("FLEET_DIR"):
        return
    target_root = fleet_dir()
    if target_root != scopes_root():
        return
    target_state = fleet_state_file()
    if target_state.exists():
        return

    src_root = _legacy_state_root()
    if not src_root.exists():
        return

    marker = target_root / ".legacy_state_migrated"
    if marker.exists():
        return

    # Preserve in-flight metadata from the historical ~/.fleet layout. We
    # intentionally omit .fleet/wg secrets from this migration.
    for name in [
        "state.json",
        "state.lock",
        "network_cache.json",
        "remote_state_audit.json",
    ]:
        _copy_missing(src_root / name, target_root / name)

    for dirname in ["logs", "op_journal", "v2_bundles", "orchestrator"]:
        _copy_missing(src_root / dirname, target_root / dirname)

    for job_glob in src_root.glob("job_*.sh"):
        _copy_missing(job_glob, target_root / job_glob.name)

    target_root.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"migrated from {src_root} at {time.ctime()}")


# Back-compat for legacy callers that imported the constants directly.
# These resolve at IMPORT time using the env at startup; for env-sensitive
# code, always call state_path()/lock_path() instead.
STATE_PATH = state_path()
LOCK_PATH  = lock_path()


# --- Schema -----------------------------------------------------------------
class WorkStatus(str, enum.Enum):
    """Authoritative set of legal state.json job statuses.

    Mirrors trading_common.orchestrator.schema.WorkStatus but is the
    fleet-side source of truth (orchestrator imports from state.json).
    """
    PENDING    = "pending"
    QUEUED     = "queued"
    RUNNING    = "running"
    EXITED     = "exited"
    COLLECTED  = "collected"
    ARCHIVED   = "archived"
    FAILED     = "failed"
    CANCELLED  = "cancelled"
    KILLED     = "killed"
    WRAPPER_DEAD_PIPELINE_UNKNOWN = "wrapper_dead_pipeline_unknown"


class StateError(Exception):
    """Raised when state.json fails schema validation."""


@dataclasses.dataclass
class FleetJob:
    """One job record in state.json. Required fields are validated; optional
    fields are accepted as-is (legacy state.json may carry extras)."""
    id:             int
    host:           str
    status:         WorkStatus
    started_at:     Optional[str] = None
    cohort:         Optional[str] = None
    wrapper_pid:    Optional[int] = None
    log_file:       Optional[str] = None
    remote_out:     Optional[str] = None
    external_dest:  Optional[str] = None
    pipeline_args:  Optional[str] = None
    into:           Optional[str] = None
    collected_at:   Optional[str] = None
    last_collect_error: Optional[str] = None
    notes:          Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "FleetJob":
        if "id" not in d:
            raise StateError(f"FleetJob missing required 'id': {d!r}")
        if "host" not in d:
            raise StateError(f"FleetJob {d.get('id')!r} missing required 'host'")
        if "status" not in d:
            raise StateError(f"FleetJob {d.get('id')!r} missing required 'status'")
        try:
            status = WorkStatus(d["status"])
        except ValueError as e:
            raise StateError(f"FleetJob {d.get('id')!r} invalid status {d['status']!r}: {e}")
        # Accept any extras — we only require the core triple (id, host, status).
        return cls(
            id=int(d["id"]), host=str(d["host"]), status=status,
            started_at=d.get("started_at"), cohort=d.get("cohort"),
            wrapper_pid=d.get("wrapper_pid"), log_file=d.get("log_file"),
            remote_out=d.get("remote_out"), external_dest=d.get("external_dest"),
            pipeline_args=d.get("pipeline_args"), into=d.get("into"),
            collected_at=d.get("collected_at"),
            last_collect_error=d.get("last_collect_error"),
            notes=d.get("notes"),
        )

    def to_dict(self) -> dict:
        """Round-trip back to a state.json record (drops Nones)."""
        d = dataclasses.asdict(self)
        d["status"] = self.status.value
        return {k: v for k, v in d.items() if v is not None}


@dataclasses.dataclass
class FleetState:
    """Top-level state.json shape."""
    jobs: list[FleetJob] = dataclasses.field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "FleetState":
        if "jobs" not in d:
            raise StateError("state.json missing required 'jobs' key")
        if not isinstance(d["jobs"], list):
            raise StateError(f"state.json 'jobs' must be a list, got {type(d['jobs']).__name__}")
        return cls(jobs=[FleetJob.from_dict(j) for j in d["jobs"]])

    def to_dict(self) -> dict:
        return {"jobs": [j.to_dict() for j in self.jobs]}


def validate_state(state: dict) -> FleetState:
    """Parse a raw state.json dict, fail fast on schema errors.
    Returns a FleetState; callers that want to keep working with raw dicts
    should use the .to_dict() of the result."""
    return FleetState.from_dict(state)


# --- IO ---------------------------------------------------------------------
def _ensure_dir() -> None:
    _migrate_legacy_state_if_needed()
    fleet_dir().mkdir(parents=True, exist_ok=True)


def load_state(validate: bool = False) -> dict:
    """Read state.json with a SHARED lock (concurrent readers OK; blocks
    mutators briefly). Returns the raw dict (for backward compat with
    legacy fleet.py callers).

    If ``validate=True`` the dict is also schema-checked; ``StateError`` is
    raised on failure.
    """
    _ensure_dir()
    sp = state_path()
    if not sp.exists():
        return {"jobs": []}
    with open(lock_path(), "a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_SH)
        try:
            d = json.loads(sp.read_text())
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    if validate:
        validate_state(d)
    return d


def save_state(state: dict, *, atomic: bool = True) -> None:
    """Write state.json with an EXCLUSIVE lock + atomic rename.

    Atomic write semantics:
        1. acquire LOCK_EX on ~/.fleet/state.lock
        2. write the new content to state.json.tmp
        3. os.rename(tmp → state.json) — POSIX atomic
        4. release lock
    """
    _ensure_dir()
    sp = state_path()
    with open(lock_path(), "a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            if atomic:
                tmp = sp.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(state, indent=2, default=str))
                os.replace(tmp, sp)
            else:
                sp.write_text(json.dumps(state, indent=2, default=str))
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def mutate_state(*, timeout_sec: float = 30.0,
                 validate_on_read: bool = False) -> Iterator[dict]:
    """Context manager: hold LOCK_EX for the duration; auto-save on exit.

    Use for any read-modify-write cycle. Example:

        with mutate_state() as state:
            for j in state["jobs"]:
                if j["id"] == jid:
                    j["status"] = "collected"

    If acquiring the lock takes >timeout_sec seconds, raises StateError.
    """
    _ensure_dir()
    sp = state_path()
    # Acquire with timeout via fcntl LOCK_NB polling
    lock_fd = open(lock_path(), "a+")
    start = time.monotonic()
    acquired = False
    try:
        while True:
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() - start > timeout_sec:
                    raise StateError(
                        f"could not acquire state.lock within {timeout_sec}s "
                        f"(another fleet process is mutating state.json)"
                    )
                time.sleep(0.1)
        # Load
        if sp.exists():
            state = json.loads(sp.read_text())
        else:
            state = {"jobs": []}
        if validate_on_read:
            validate_state(state)
        yield state
        # Save atomically (lock still held)
        tmp = sp.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2, default=str))
        os.replace(tmp, sp)
    finally:
        if acquired:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        lock_fd.close()
