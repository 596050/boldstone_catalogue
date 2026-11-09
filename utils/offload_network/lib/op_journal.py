"""lib/op_journal.py — durable per-operation journal so HDD writes can
be resumed/repaired after a crash, HDD detach, or operator interruption.

DESIGN:
  ``~/.fleet/op_journal/<op_id>.json`` — one file per in-flight operation.

  Schema (see ``OperationRecord`` dataclass):
    op_id           UUID-style identifier
    op_type         "collect" | "publish" | "sync" | "delete_remote" | ...
    state           "planned" | "preflight" | "copying" | "verifying" |
                    "publishing" | "done" | "failed" | "interrupted"
    started_at      ISO timestamp
    last_update_at  ISO timestamp
    job_id          optional fleet job id (for collect ops)
    host            remote host (for collect/sync ops)
    source          remote source URI
    dest            local destination path
    progress_bytes  number of bytes successfully transferred so far
    expected_bytes  total bytes we plan to transfer (may be unknown)
    fingerprint     opaque dict — caller-defined; used to detect drift
                    between resume time and original (e.g. remote manifest hash)
    attempts        list of {ts, action, rc, note} for forensics
    last_error      most recent error string

Each write is atomic: write to .tmp, fcntl LOCK_EX the target, rename.
This means a half-written entry never appears to readers.

Resume flow (`recover` command — see fleet.py):
  1. ``list_incomplete()`` — find non-terminal entries
  2. for each: probe HDD + remote to ensure we CAN resume
  3. for each: continue from where state left off
  4. terminal state → ``finish_op(state="done")``
"""
from __future__ import annotations

import dataclasses
try:
    import fcntl
except ImportError:
    from lib import compat_fcntl as fcntl
import json
import os
import pathlib
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from fleet.paths import op_journal_dir


JOURNAL_DIR = op_journal_dir()

TERMINAL_STATES = frozenset({"done", "failed"})
ALL_STATES = frozenset({
    "planned", "preflight", "copying", "verifying", "publishing",
    "done", "failed", "interrupted",
})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclasses.dataclass
class OperationRecord:
    op_id: str
    op_type: str
    state: str = "planned"
    started_at: str = ""
    last_update_at: str = ""
    job_id: Optional[str] = None
    host: Optional[str] = None
    source: Optional[str] = None
    dest: Optional[str] = None
    progress_bytes: int = 0
    expected_bytes: int = 0
    fingerprint: dict = dataclasses.field(default_factory=dict)
    attempts: list = dataclasses.field(default_factory=list)
    last_error: Optional[str] = None

    def __post_init__(self):
        if not self.started_at:
            self.started_at = _now_iso()
        if not self.last_update_at:
            self.last_update_at = self.started_at
        if self.state not in ALL_STATES:
            raise ValueError(f"unknown state {self.state!r}")

    def to_json(self) -> str:
        d = dataclasses.asdict(self)
        return json.dumps(d, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "OperationRecord":
        return cls(**json.loads(text))


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def _journal_path(op_id: str) -> pathlib.Path:
    return JOURNAL_DIR / f"{op_id}.json"


@contextmanager
def _locked_write(target: pathlib.Path):
    """Acquire an exclusive lock on ``target`` (creating it if missing),
    yield the file handle, atomic-rename on close. Safe across processes."""
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_suffix(target.suffix + ".lock")
    lock_fh = open(lock_path, "w")
    try:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        tmp = target.with_suffix(target.suffix + ".tmp")
        try:
            with open(tmp, "w") as fh:
                yield fh
            os.replace(tmp, target)
        finally:
            if tmp.exists():
                try: tmp.unlink()
                except FileNotFoundError: pass
    finally:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)
        lock_fh.close()


def start_op(op_type: str, **fields) -> str:
    """Create a new journal entry. Returns the op_id."""
    op_id = fields.pop("op_id", None) or f"op-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"
    record = OperationRecord(op_id=op_id, op_type=op_type, **fields)
    target = _journal_path(op_id)
    with _locked_write(target) as fh:
        fh.write(record.to_json())
    return op_id


def update_op(op_id: str, **fields):
    """Atomically update an existing journal entry. Any field on
    OperationRecord may be set; ``attempts`` is appended via the
    special key ``attempt`` (a single dict)."""
    target = _journal_path(op_id)
    if not target.exists():
        raise FileNotFoundError(f"no journal entry for {op_id}")
    with _locked_write(target) as fh:
        cur = OperationRecord.from_json(target.read_text()) \
              if target.stat().st_size else None
        # We re-read INSIDE the lock to win the race against another writer
        cur = OperationRecord.from_json(target.read_text())
        if "attempt" in fields:
            cur.attempts.append(fields.pop("attempt"))
        for k, v in fields.items():
            setattr(cur, k, v)
        cur.last_update_at = _now_iso()
        if cur.state not in ALL_STATES:
            raise ValueError(f"unknown state {cur.state!r}")
        fh.write(cur.to_json())


def finish_op(op_id: str, *, state: str = "done", note: Optional[str] = None,
              error: Optional[str] = None):
    """Mark a journal entry terminal. Subsequent reads see the final state."""
    if state not in TERMINAL_STATES:
        raise ValueError(f"finish state must be terminal: got {state!r}")
    update_op(op_id, state=state, last_error=error,
              attempt={"ts": _now_iso(), "action": "finish",
                       "rc": 0 if state == "done" else 1, "note": note})


def get_op(op_id: str) -> Optional[OperationRecord]:
    p = _journal_path(op_id)
    if not p.exists():
        return None
    return OperationRecord.from_json(p.read_text())


def list_incomplete() -> list[OperationRecord]:
    """Return every journal entry NOT in a terminal state."""
    if not JOURNAL_DIR.exists():
        return []
    out: list[OperationRecord] = []
    for p in sorted(JOURNAL_DIR.glob("*.json")):
        try:
            rec = OperationRecord.from_json(p.read_text())
            if rec.state not in TERMINAL_STATES:
                out.append(rec)
        except (json.JSONDecodeError, FileNotFoundError, OSError):
            # Corrupt entry — surface for repair but don't crash the scan
            out.append(OperationRecord(
                op_id=p.stem, op_type="UNKNOWN_CORRUPT",
                state="interrupted", last_error=f"could not parse {p}",
            ))
    return out


def list_all() -> list[OperationRecord]:
    """Every journal entry, terminal + non-terminal. For audit/reporting."""
    if not JOURNAL_DIR.exists():
        return []
    out: list[OperationRecord] = []
    for p in sorted(JOURNAL_DIR.glob("*.json")):
        try:
            out.append(OperationRecord.from_json(p.read_text()))
        except Exception:
            continue
    return out


def purge_old(max_age_days: int = 30):
    """Delete terminal entries older than N days. Non-terminal entries
    are NEVER purged — they need explicit resume or operator action."""
    if not JOURNAL_DIR.exists():
        return 0
    deadline = time.time() - max_age_days * 86400
    n = 0
    for p in JOURNAL_DIR.glob("*.json"):
        try:
            rec = OperationRecord.from_json(p.read_text())
            if rec.state in TERMINAL_STATES:
                mtime = p.stat().st_mtime
                if mtime < deadline:
                    p.unlink()
                    n += 1
        except Exception:
            continue
    return n


@contextmanager
def journal_op(op_type: str, **fields) -> Iterator[str]:
    """Context manager: creates a journal entry, yields the op_id, marks
    state=done on clean exit or state=failed on exception.

    Usage::

        with journal_op("collect", job_id=42, host="kenne",
                         source="kenne:C:/...", dest="/Volumes/Untitled/...") as op_id:
            # do the work, calling update_op(op_id, ...) as you progress
            ...
    """
    op_id = start_op(op_type, **fields)
    try:
        yield op_id
    except Exception as e:
        finish_op(op_id, state="failed", error=f"{type(e).__name__}: {e}")
        raise
    else:
        # Caller may have already finished — only finalise if still non-terminal
        rec = get_op(op_id)
        if rec and rec.state not in TERMINAL_STATES:
            finish_op(op_id, state="done")
