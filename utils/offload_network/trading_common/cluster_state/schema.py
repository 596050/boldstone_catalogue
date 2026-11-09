"""Dataclasses for cluster_state events + alerts.

Append-only JSONL is the wire format on disk (one JSON per line in
job_ledger.jsonl and alerts.jsonl). These dataclasses are how Python code
constructs them safely.

Principle: every record carries enough provenance (actor, time, host,
job_id) that an operator reading the ledger six weeks later can reconstruct
WHY each action happened.
"""
from __future__ import annotations

import dataclasses
import enum
import json
import time
from typing import Any


class Severity(str, enum.Enum):
    INFO  = "info"
    WARN  = "warn"
    ERROR = "error"


def _utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclasses.dataclass
class JobEvent:
    """One row in ``job_ledger.jsonl``. Append-only; never edited.

    Every event captures who/what acted (``actor``), what changed
    (``event``), and any operation-specific context (``details``).
    """
    event:    str            # "job_launched", "wrapper_died", "auto_recovery", etc.
    actor:    str            # "fleet.cmd_run", "cluster_state.recover.reclassify_running_jobs"
    job_id:   int | None = None
    host:     str | None = None
    cohort:   str | None = None
    details:  dict[str, Any] = dataclasses.field(default_factory=dict)
    time:     str = dataclasses.field(default_factory=_utc_iso)

    def to_json_line(self) -> str:
        return json.dumps(dataclasses.asdict(self), sort_keys=True, default=str)


@dataclasses.dataclass
class Alert:
    """One row in ``alerts.jsonl``. Operator-readable divergence signal."""
    kind:      str             # "wrapper_dead", "source_missing", "verify_mismatch", ...
    severity:  Severity        # INFO/WARN/ERROR
    host:      str | None = None
    job_id:    int | None = None
    detail:    str = ""        # human-readable description
    context:   dict[str, Any] = dataclasses.field(default_factory=dict)
    time:      str = dataclasses.field(default_factory=_utc_iso)

    def to_json_line(self) -> str:
        d = dataclasses.asdict(self)
        d["severity"] = self.severity.value if isinstance(self.severity, Severity) else self.severity
        return json.dumps(d, sort_keys=True, default=str)
