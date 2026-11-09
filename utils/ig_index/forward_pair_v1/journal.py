"""Durable intent/confirmation/ownership journal, with one writer per account."""
from __future__ import annotations

import fcntl
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .common import canonical, identity, stamp


class Journal:
    def __init__(self, folder, account_key):
        self.folder = Path(folder) / account_key
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / "journal.sqlite3"
        self.db = sqlite3.connect(self.path, timeout=5)
        os.chmod(self.path, 0o600)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY, at TEXT NOT NULL, model TEXT NOT NULL,
                kind TEXT NOT NULL, payload TEXT NOT NULL, previous TEXT NOT NULL,
                digest TEXT NOT NULL UNIQUE);
            CREATE TABLE IF NOT EXISTS operations (
                op_id TEXT PRIMARY KEY, model TEXT NOT NULL, status TEXT NOT NULL,
                request TEXT NOT NULL, reference TEXT, confirmation TEXT);
            CREATE TABLE IF NOT EXISTS owned (
                deal_id TEXT PRIMARY KEY, model TEXT NOT NULL, symbol TEXT NOT NULL,
                epic TEXT NOT NULL, direction TEXT NOT NULL, size REAL NOT NULL,
                currency TEXT NOT NULL, status TEXT NOT NULL, open_op TEXT NOT NULL);
        """)

    @contextmanager
    def lock(self):
        with (self.folder / "account.lock").open("a+") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("another forward adapter owns the account lock") from exc
            try:
                yield self
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def event(self, model, kind, payload):
        with self.db:
            row = self.db.execute("SELECT digest FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            previous = row[0] if row else "0" * 64
            at = stamp()
            record = dict(at=at, model=model, kind=kind, payload=payload, previous=previous)
            digest = identity(record)
            self.db.execute("INSERT INTO events(at,model,kind,payload,previous,digest) VALUES(?,?,?,?,?,?)",
                            (at, model, kind, canonical(payload).decode(), previous, digest))
        return digest

    def operation(self, op_id):
        row = self.db.execute("SELECT model,status,request,reference,confirmation FROM operations WHERE op_id=?", (op_id,)).fetchone()
        return None if row is None else dict(model=row[0], status=row[1], request=json.loads(row[2]),
                                            reference=row[3], confirmation=json.loads(row[4]) if row[4] else None)

    def begin(self, model, op_id, request, reference=None):
        # Committed BEFORE network mutation: an uncertain submission is never
        # silently retried. Resume uses the exact client reference/positions.
        with self.db:
            self.db.execute("INSERT INTO operations VALUES(?,?,?,?,?,NULL)",
                            (op_id, model, "SUBMITTING", canonical(request).decode(), reference))
        self.event(model, "order_submission", dict(op_id=op_id, request=request, reference=reference))

    def update(self, op_id, status, *, reference=None, confirmation=None):
        with self.db:
            self.db.execute("UPDATE operations SET status=?,reference=COALESCE(?,reference),confirmation=COALESCE(?,confirmation) WHERE op_id=?",
                            (status, reference, canonical(confirmation).decode() if confirmation is not None else None, op_id))

    def claim(self, model, symbol, request, op_id, deal_id):
        with self.db:
            prior = self.db.execute("SELECT model,open_op FROM owned WHERE deal_id=?", (deal_id,)).fetchone()
            if prior is not None:
                if prior != (model, op_id):
                    raise ValueError("deal belongs to another operation/model")
                return
            self.db.execute("INSERT INTO owned VALUES(?,?,?,?,?,?,?,?,?)",
                            (deal_id, model, symbol, request["epic"], request["direction"],
                             request["size"], request["currencyCode"], "OPEN", op_id))

    def owned(self, model=None, *, open_only=True):
        self.db.row_factory = sqlite3.Row
        query, args = "SELECT * FROM owned WHERE 1=1", []
        if model is not None:
            query += " AND model=?"; args.append(model)
        if open_only:
            query += " AND status='OPEN'"
        rows = [dict(row) for row in self.db.execute(query, args)]
        self.db.row_factory = None
        return rows

    def closed(self, model, deal_id):
        with self.db:
            result = self.db.execute("UPDATE owned SET status='CLOSED' WHERE model=? AND deal_id=?", (model, deal_id))
            if result.rowcount != 1:
                raise ValueError("cannot close unowned deal")

    def unresolved(self, model):
        return self.db.execute("SELECT op_id,status FROM operations WHERE model=? AND status NOT IN ('ACCEPTED','REJECTED')", (model,)).fetchall()

    def verify(self):
        previous = "0" * 64
        count = 0
        for at, model, kind, payload, prev, digest in self.db.execute("SELECT at,model,kind,payload,previous,digest FROM events ORDER BY seq"):
            if prev != previous or identity(dict(at=at, model=model, kind=kind, payload=json.loads(payload), previous=prev)) != digest:
                raise ValueError("journal event-chain mismatch")
            previous = digest; count += 1
        return {"events": count, "last_digest": previous}
