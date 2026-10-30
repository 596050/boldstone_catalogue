from __future__ import annotations

import fcntl
import importlib.metadata
import json
import os
import platform
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__
from .errors import Blocked, IntegrityError
from .util import (
    canonical,
    check_no_symlinks,
    digest,
    file_sha256,
    json_write,
    new_id,
    redact,
    utc_now,
)


def environment():
    versions = {}
    for package in ("dropbox", "Pillow", "keyring", "boldstone-local"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not_installed"
    try:
        from PIL import features

        versions["libjpeg"] = features.version("jpg")
        versions["libjpeg_turbo"] = features.version("libjpeg_turbo")
    except ImportError:
        pass
    code_files = sorted(p for p in Path(__file__).parent.iterdir() if p.suffix in (".py", ".sql"))
    return {
        "python": platform.python_version(),
        "os": platform.platform(),
        "packages": versions,
        "source_code_sha256": digest({p.name: file_sha256(p) for p in code_files}),
    }


class State:
    def __init__(self, config):
        self.config = config
        check_no_symlinks(config.database)
        if not config.database.is_file():
            raise Blocked("Historical state is missing; run 'boldstone import --pack PATH'")
        self.conn = sqlite3.connect(config.database, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._lock_file = None

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @contextmanager
    def writer(self):
        lock_path = check_no_symlinks(self.config.database.with_suffix(".writer.lock"))
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Blocked("Another local writer is running") from exc
            yield self
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def migrate(self):
        version = self.conn.execute(
            "SELECT value FROM schema_meta WHERE key='app_schema_version'"
        ).fetchone()
        if version:
            if version[0] != "1":
                raise IntegrityError("Unsupported local application schema")
            return
        backup = (
            self.config.directory("backup")
            / f"before-readonly-migration-{new_id('snapshot')}.sqlite3"
        )
        self.backup(backup)
        script = Path(__file__).with_name("migrations.sql").read_text()
        try:
            self.conn.executescript(
                "BEGIN IMMEDIATE;\n"
                + script
                + "\nINSERT INTO schema_meta VALUES ('app_schema_version','1');\nCOMMIT;"
            )
        except BaseException:
            self.conn.rollback()
            raise
        with self.conn:
            self.event(
                "database",
                "schema",
                "read_only_schema_initialized",
                {
                    "version": 1,
                    "before_migration_backup": str(backup),
                    "backup_sha256": file_sha256(backup),
                },
            )

    def backup(self, destination):
        destination = check_no_symlinks(destination)
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        with sqlite3.connect(destination) as backup:
            self.conn.backup(backup)
            if backup.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise IntegrityError("Consistent backup failed integrity verification")
            if backup.execute("PRAGMA foreign_key_check").fetchall():
                raise IntegrityError("Consistent backup has foreign-key violations")
        return destination

    def event(self, kind, entity_id, event_type, payload, run_id=None):
        # Caller holds one SQLite transaction, so event and its related state commit together.
        previous = self.conn.execute(
            "SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        body = {
            "event_id": new_id("event"),
            "run_id": run_id,
            "event_utc": utc_now(),
            "entity_kind": kind,
            "entity_id": entity_id,
            "event_type": event_type,
            "payload_json": canonical(redact(payload)),
            "previous_event_hash": previous[0] if previous else None,
        }
        body["event_hash"] = digest(body)
        self.conn.execute(
            """INSERT INTO events(event_id,run_id,event_utc,entity_kind,entity_id,
            event_type,payload_json,previous_event_hash,event_hash) VALUES
            (:event_id,:run_id,:event_utc,:entity_kind,:entity_id,:event_type,:payload_json,
             :previous_event_hash,:event_hash)""",
            body,
        )
        return body["event_id"]

    def validate_events(self):
        previous = None
        count = 0
        for row in self.conn.execute("SELECT * FROM events ORDER BY sequence"):
            body = dict(row)
            actual = body.pop("event_hash")
            body.pop("sequence")
            if body["previous_event_hash"] != previous:
                raise IntegrityError("Event predecessor hash mismatch")
            if count == 0 and body["event_type"] == "offline_import":
                expected = digest(
                    {
                        "event_type": "offline_import",
                        "utc": body["event_utc"],
                        "payload": json.loads(body["payload_json"]),
                    }
                )
            else:
                expected = digest(body)
            if actual != expected:
                raise IntegrityError("Event content hash mismatch")
            previous, count = actual, count + 1
        return {"events": count, "last_hash": previous, "result": "pass"}

    def run(self, mode="read_only"):
        return Run(self, mode)

    def evidence(self, payload, prefix="response"):
        path = self.config.directory("evidence") / (new_id(prefix) + ".json")
        json_write(path, redact(payload))
        return str(path), file_sha256(path)

    def observe(self, run, metadata, endpoint, *, outcome="present", asset_id=None, evidence=None):
        payload = redact(metadata)
        evidence_path, evidence_hash = evidence or self.evidence(payload)
        name = metadata.get("name")
        if endpoint == "users/get_current_account" and isinstance(name, dict):
            # Account names are structured; file and folder names are plain strings.
            # Preserve the original name object in response_json and raw evidence.
            name = name.get("display_name")
        self.conn.execute(
            """INSERT INTO observations(observation_id,run_id,asset_id,
            observed_utc,endpoint,account_id,namespace_id,parent_folder_id,path_display,
            path_lower,name,revision,byte_size,dropbox_content_hash,observation_outcome,
            raw_evidence_path,raw_evidence_sha256,response_json,request_id,is_historical)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
            (
                new_id("observation"),
                run.id,
                asset_id or metadata.get("id"),
                utc_now(),
                endpoint,
                run.account_id,
                run.namespace_id,
                metadata.get("parent_folder_id"),
                metadata.get("path_display"),
                metadata.get("path_lower"),
                name,
                metadata.get("rev"),
                metadata.get("size"),
                metadata.get("content_hash"),
                outcome,
                evidence_path,
                evidence_hash,
                canonical(payload),
                metadata.get("request_id"),
            ),
        )

    def start_attempt(self, run, batch_id, new_attempt=False):
        batch = self.conn.execute("SELECT * FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
        if not batch:
            raise Blocked("Unknown fixed batch")
        prior = self.conn.execute(
            "SELECT count(*) FROM attempts WHERE batch_id=?", (batch_id,)
        ).fetchone()[0]
        if (batch["saved_status"] != "Planned" or prior) and not new_attempt:
            raise Blocked(
                "Batch has historical or local attempts; use --new-attempt to retain them"
            )
        attempt = new_id("attempt")
        with self.conn:
            self.conn.execute(
                """INSERT INTO attempts(attempt_id,run_id,batch_id,started_utc,
                attempt_state) VALUES (?,?,?,?,?)""",
                (attempt, run.id, batch_id, utc_now(), "RUNNING"),
            )
            self.event(
                "attempt",
                attempt,
                "review_started",
                {"batch_id": batch_id, "fixed_scope_hash": batch["manifest_sha256"]},
                run.id,
            )
        return attempt

    def finish_attempt(self, run, attempt, outcome, counts, details, *, complete=False):
        now = utc_now()
        with self.conn:
            self.conn.execute(
                """UPDATE attempts SET ended_utc=?,objective_completed_utc=?,
                attempt_state='FINISHED',objective_outcome=?,counts_json=?,evidence_json=?
                WHERE attempt_id=?""",
                (
                    now,
                    now if complete else None,
                    outcome,
                    canonical(counts),
                    canonical(redact(details)),
                    attempt,
                ),
            )
            batch_id = self.conn.execute(
                "SELECT batch_id FROM attempts WHERE attempt_id=?", (attempt,)
            ).fetchone()[0]
            self.conn.execute(
                "UPDATE batches SET local_objective_state=? WHERE batch_id=?", (outcome, batch_id)
            )
            self.event(
                "attempt",
                attempt,
                "review_finished",
                {"outcome": outcome, "counts": counts, "complete_to_stated_scope": complete},
                run.id,
            )


class Run:
    def __init__(self, state, mode):
        self.state, self.mode, self.id = state, mode, new_id("run")
        self.account_id = self.namespace_id = self.root_id = None

    def __enter__(self):
        with self.state.conn:
            self.state.conn.execute(
                """INSERT INTO runs(run_id,started_utc,code_version,
                configuration_sha256,mode,environment_json) VALUES (?,?,?,?,?,?)""",
                (
                    self.id,
                    utc_now(),
                    __version__,
                    self.state.config.checksum,
                    self.mode,
                    canonical(environment()),
                ),
            )
            self.state.event("run", self.id, "run_started", {"mode": self.mode}, self.id)
            self.heartbeat()
        return self

    def bind(self, account, namespace, root):
        self.account_id, self.namespace_id, self.root_id = account, namespace, root
        with self.state.conn:
            self.state.conn.execute(
                "UPDATE runs SET account_id=?,namespace_id=?,root_folder_id=? WHERE run_id=?",
                (account, namespace, root, self.id),
            )

    def heartbeat(self):
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        self.state.conn.execute(
            "INSERT OR REPLACE INTO leases VALUES (?,?,?,?,?)",
            ("local-writer", self.id, utc_now(), expiry, "{}"),
        )

    def __exit__(self, exc_type, exc, tb):
        with self.state.conn:
            result = "finished" if exc_type is None else "interrupted_or_failed"
            self.state.conn.execute(
                "UPDATE runs SET ended_utc=?,result=? WHERE run_id=?", (utc_now(), result, self.id)
            )
            self.state.conn.execute("DELETE FROM leases WHERE holder_run_id=?", (self.id,))
            self.state.event(
                "run",
                self.id,
                "run_finished",
                {"result": result, "error_type": exc_type.__name__ if exc_type else None},
                self.id,
            )
