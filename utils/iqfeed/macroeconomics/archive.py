"""One-writer IQFeed archive with durable queues and byte-preserved responses.

Payloads, logs, queue, receipts and checkpoints live on the verified external
volume. This never launches IQConnect, alters entitlements, fills observations,
or writes into the existing equity archive. Raw contracts and vendor-derived
continuous series are different sources. Only the cooperative download lock is
shared. A complete response does not certify gap-free market history.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import gzip
import hashlib
import io
import json
import math
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import uuid
from collections import Counter
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .catalog import GUIDES, MONTHS, ROOTS, SERIES

MODULE = "utils.iqfeed.macroeconomics.archive"
SCHEMA = "iqfeed_macroeconomics.v1"
CSV_FIELDS = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "total_volume",
    "period_volume",
    "number_of_trades",
    "open_interest",
    "quality_flags",
)
TERMINAL = (
    "COMPLETE",
    "COMPLETE_WITH_ANOMALIES",
    "NO_DATA",
    "NOT_AUTHORIZED",
    "FAILED",
    "SPLIT",
)
STOP = False
SQLITE_RETRY_SECONDS = 300
SQLITE_RETRY_POLL_SECONDS = 0.25


def utc():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temp.open("xb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def safe_symbol(symbol):
    # Injective encoding, unlike replacing all punctuation with underscores.
    return symbol.replace("@", "AT-").replace("#", "-CONT")


def stop_requested():
    if STOP:
        raise InterruptedError("graceful stop requested")


def guard(root, *, force=False, reserve=20 * 1024**3):
    from utils.data_paths import ensure_external_storage, resolve_source_location

    storage = ensure_external_storage(force=force)
    expected = resolve_source_location("iqfeed_macroeconomics")
    root = Path(root)
    if root != expected or root.name != "macroeconomics":
        raise ValueError(
            "archive must be the centrally registered macroeconomics directory"
        )
    mount = storage["mount_point"]
    if not os.path.ismount(mount):
        raise OSError("Toshiba disappeared; refusing an internal shadow directory")
    current = mount
    for part in root.relative_to(mount).parts:
        current /= part
        if current.is_symlink():
            raise OSError("symlink in archive path")
    existing = root if root.exists() else mount
    if existing.stat().st_dev != mount.stat().st_dev:
        raise OSError("archive is not on the verified device")
    stat = os.statvfs(existing)
    available = stat.f_bavail * stat.f_frsize
    if available < reserve:
        raise OSError(f"SPACE_RESERVE: {available} bytes free, reserve {reserve}")
    return storage


@contextmanager
def lock(path):
    # Never truncate before kernel ownership and never delete a lock file.
    with Path(path).open("a+b") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            stream.seek(0)
            stream.truncate()
            stream.write(
                canonical({"pid": os.getpid(), "owner": MODULE, "since": utc()})
            )
            stream.flush()
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


class ArchiveConnection(sqlite3.Connection):
    """Retry only SQLite contention, keeping the same statement/transaction.

    In DELETE journal mode a read-only monitor can delay COMMIT. Retrying that
    COMMIT is safe; replaying the request/download or the preceding INSERTs is
    not. Disk, corruption, constraint and other errors still fail closed.
    """

    def _retry(self, operation, callback):
        deadline = time.monotonic() + SQLITE_RETRY_SECONDS
        reported = False
        while True:
            try:
                return callback()
            except sqlite3.OperationalError as exc:
                code = getattr(exc, "sqlite_errorcode", 0) & 0xFF
                if code not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                    raise
                stop_requested()
                if (self.archive_root / "metadata/STOP").exists():
                    raise InterruptedError("graceful stop requested during SQLite wait") from exc
                if time.monotonic() >= deadline:
                    raise
                guard(self.archive_root, reserve=0)
                if not reported:
                    print(json.dumps({"at": utc(), "event": "WAITING_FOR_SQLITE",
                                      "operation": operation}), flush=True)
                    reported = True
                time.sleep(min(SQLITE_RETRY_POLL_SECONDS, max(0, deadline - time.monotonic())))

    def execute(self, sql, parameters=(), /):
        return self._retry("statement", lambda: super(ArchiveConnection, self).execute(sql, parameters))

    def commit(self):
        return self._retry("commit", super().commit)


def connect_db(root):
    db = sqlite3.connect(Path(root) / "metadata/queue.sqlite3", timeout=30,
                         factory=ArchiveConnection)
    db.archive_root = Path(root)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=DELETE")
    db.execute("PRAGMA synchronous=FULL")
    # Keep queue/index pages in RAM while building the catalogue. The default
    # 2 MiB cache causes many tiny synchronous writes on this exFAT hard drive.
    # Transactions still commit durably to Toshiba, never to an internal file.
    db.execute("PRAGMA cache_size=-32768")
    # Every schema statement is idempotent if a competing reader delays DDL.
    db._retry("schema", lambda: db.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, spec TEXT NOT NULL, priority INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0,
            receipt TEXT, updated TEXT
        );
        CREATE INDEX IF NOT EXISTS queue_order ON jobs(status,priority);
        CREATE TABLE IF NOT EXISTS responses (
            job_id TEXT NOT NULL, attempt INTEGER NOT NULL, receipt TEXT NOT NULL,
            small_raw_gzip BLOB, PRIMARY KEY(job_id,attempt)
        );
    """))
    return db


def put_job(db, spec, priority):
    job_id = digest(spec)[:24]
    db.execute(
        "INSERT OR IGNORE INTO jobs(id,spec,priority) VALUES (?,?,?)",
        (job_id, json.dumps(spec, sort_keys=True), priority),
    )
    return job_id


def make_spec(symbol, folder, kind, cadence, end, begin="19000101"):
    return {
        "symbol": symbol,
        "folder": folder,
        "kind": kind,
        "cadence": cadence,
        "begin": begin,
        "end": end,
    }


def initialise(root, end, first_year=1959, last_year=None):
    """Only new archives: stable cutoff and code/catalog hashes bind resumption."""
    from utils.data_paths import CONFIG_PATH

    guard(root, force=True)
    if (root / "metadata/ARCHIVE.json").exists():
        raise FileExistsError("archive exists; use run/status/verify to resume it")
    last_year = last_year or int(end[:4]) + 20
    if not 1900 <= first_year <= last_year or last_year - first_year >= 100:
        raise ValueError(
            "expiry scan must have unique two-digit years and span less than 100 years"
        )
    date.fromisoformat(f"{end[:4]}-{end[4:6]}-{end[6:]}")
    root.mkdir(exist_ok=True)
    for folder in ("metadata", "logs", "reference", "incomplete"):
        (root / folder).mkdir(exist_ok=True)
    code = {p.name: file_sha(p) for p in Path(__file__).parent.glob("*.py")}
    archive = {
        "schema": SCHEMA,
        "created_at_utc": utc(),
        "cutoff": end,
        "root": str(root),
        "provider": "DTN IQFeed",
        "protocol": "6.2",
        "host": "127.0.0.1",
        "port": 9100,
        "code_sha256": code,
        "registry_sha256": file_sha(CONFIG_PATH),
        "minimum_free_gib": 20,
        "bar_cadences": ["daily", "minute"],
        "ticks_and_order_book": "NOT_REQUESTED",
        "daily_begin": "19000101",
        "minute_begin": "19000101",
        "expiry_scan": {
            "first_year": first_year,
            "last_year": last_year,
            "months": MONTHS,
            "meaning": "Candidate symbols, not evidence of listing. Current listed futures supplement this scan.",
        },
        "source_timestamp_policy": "Preserve IQFeed timestamps verbatim; no timezone shifts or imputed observations.",
        "price_basis": "Provider current-vintage bars; daily may include settlements. # and #C are explicitly separate derived series.",
        "completeness": "Provider response completion is not calendar or lifetime completeness.",
        "rights": "Existing account only; no subscriptions purchased or authentication bypasses.",
        "guides": GUIDES,
        "roots": [
            {"symbol_root": r, "folder": f, "description": d} for r, f, d in ROOTS
        ],
        "series": [
            {"symbol": s, "folder": f, "description": d, "kind": k}
            for s, f, d, k in SERIES
        ],
    }
    db = connect_db(root)
    for symbol, folder, _, kind in SERIES:
        for cadence in ("daily", "minute"):
            (root / "iqfeed" / folder / cadence).mkdir(parents=True, exist_ok=True)
            put_job(
                db,
                make_spec(symbol, folder, kind, cadence, end),
                0 if cadence == "daily" else 4,
            )
    for symbol, folder, _ in ROOTS:
        put_job(db, make_spec(symbol, folder, "directory", "directory", end), -1)
        for suffix, sub in (
            ("#", "continuous_front_month"),
            ("#C", "continuous_back_adjusted"),
        ):
            for cadence in ("daily", "minute"):
                target = folder + "/" + sub
                (root / "iqfeed" / target / cadence).mkdir(parents=True, exist_ok=True)
                put_job(
                    db,
                    make_spec(symbol + suffix, target, sub, cadence, end),
                    0 if cadence == "daily" else 5,
                )
        for cadence in ("daily", "minute"):
            (root / "iqfeed" / folder / "contracts" / cadence).mkdir(
                parents=True, exist_ok=True
            )
    # Recent and stress-period contracts first; empty pre-listing candidates last.
    for year in range(last_year, first_year - 1, -1):
        for symbol, folder, _ in ROOTS:
            for month in MONTHS:
                dated = f"{symbol}{month}{year % 100:02d}"
                for cadence in ("daily", "minute"):
                    priority = 20 if cadence == "daily" else 30
                    if year in (2008, 2020, 2025) and month == "Z":
                        priority = 2 if cadence == "daily" else 3
                    elif year > int(end[:4]) or year < 2008:
                        priority += 30
                    put_job(
                        db,
                        make_spec(
                            dated, folder + "/contracts", "dated_contract", cadence, end
                        ),
                        priority,
                    )
    db.commit()
    archive["initial_jobs"] = db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    db.close()
    atomic_json(root / "metadata/ARCHIVE.json", archive)
    atomic_json(
        root / "metadata/STATUS.json",
        {"state": "QUEUED", "jobs": archive["initial_jobs"], "updated_at_utc": utc()},
    )
    # Generated archive documentation is an output of this acquisition utility.
    readme = Path(__file__).with_name("README.md").read_bytes()
    with (root / "README.md").open("xb") as stream:
        stream.write(readme)
    return archive


def command_for(spec, request_id):
    s, b, e = spec["symbol"], spec["begin"], spec["end"]
    if spec["cadence"] == "directory":
        return f"SBF,s,{s},t,8,{request_id}"
    if spec["cadence"] == "daily":
        return f"HDT,{s},{b},{e},,1,{request_id},5000"
    # No maximum-datapoint cap: IQFeed otherwise silently returns only a tail.
    # Explicit end timestamps preserve the protocol default end-of-bar convention.
    return f"HIT,{s},60,{b} 000000,{e} 235959,,,,1,{request_id},5000,s,0"


def provider_no_data(receipt):
    # IQFeed sends optional empty error columns (e.g. E,!NO_DATA!,,).
    # Preserve those bytes and error strings; normalize only for classification.
    return bool(
        receipt.get("protocol_acknowledged")
        and receipt.get("end_seen")
        and not receipt.get("failure")
        and not receipt.get("provider_rows")
        and receipt.get("errors")
        and all(error.rstrip(",") == "!NO_DATA!" for error in receipt["errors"])
    )


def parse_bar(fields, cadence, begin, end, previous):
    expected = 7 if cadence == "daily" else 9
    if len(fields) != expected:
        raise ValueError(f"FIELD_COUNT:{len(fields)}:{expected}")
    stamp = fields[0]
    # Validate the provider's wall-clock label, deliberately without converting it.
    dt = datetime.strptime(  # noqa: DTZ007 - preserve the provider wall-clock label.
        stamp, "%Y-%m-%d" if cadence == "daily" else "%Y-%m-%d %H:%M:%S"
    )
    if not begin <= dt.strftime("%Y%m%d") <= end:
        raise ValueError("OUTSIDE_REQUEST_RANGE")
    high, low, opening, close = fields[1:5]
    values = [float(v) for v in fields[1:] if v != ""]
    flags = []
    if not all(math.isfinite(v) for v in values):
        flags.append("NONFINITE")
    if (
        not values[1] <= values[2] <= values[0]
        or not values[1] <= values[3] <= values[0]
    ):
        flags.append("OHLC_ENVELOPE")
    if previous is not None and stamp <= previous:
        flags.append("NONINCREASING_TIMESTAMP")
    if any(v < 0 for v in values[4:]):
        flags.append("NEGATIVE_VOLUME_OR_COUNT")
    # Negative futures prices, zero-volume indices and negative breadth are valid.
    if cadence == "daily":
        row = (stamp, opening, high, low, close, "", fields[5], "", fields[6])
    else:
        row = (
            stamp,
            opening,
            high,
            low,
            close,
            fields[5],
            fields[6],
            fields[7],
            fields[8],
        )
        # OI is absent from interval data, not a zero-valued observation.
    return (*row, "|".join(flags)), flags


def interval_fields(fields):
    # Minute payload has eight fields; daily has seven. Keep OI absent, not zero.
    if len(fields) != 8:
        raise ValueError(f"INTERVAL_FIELD_COUNT:{len(fields)}")
    return fields + [""]


def read_line(stream):
    line = stream.readline(1024 * 1024 + 1)
    if not line:
        raise ConnectionError("EOF before request-specific ENDMSG")
    if len(line) > 1024 * 1024 or not line.endswith(b"\n"):
        raise ValueError("malformed or oversized protocol line")
    return line


def collect(
    root, spec, job_id, attempt, check, *, host="127.0.0.1", port=9100, timeout=300
):
    check()
    rid = "MACRO_" + job_id + "_" + str(attempt)
    command = command_for(spec, rid)
    base = f"{safe_symbol(spec['symbol'])}__{spec['begin']}_{spec['end']}__{job_id}__a{attempt}"
    if spec["cadence"] == "directory":
        folder = root / "reference"
    else:
        folder = root / "iqfeed" / spec["folder"] / spec["cadence"]
    folder.mkdir(parents=True, exist_ok=True)
    raw_path = folder / (base + ".raw.gz")
    csv_path = folder / (base + ".csv.gz")
    temp_raw = root / "incomplete" / (base + ".raw.gz.part")
    temp_csv = root / "incomplete" / (base + ".csv.gz.part")
    receipt = {
        "job_id": job_id,
        "attempt": attempt,
        "spec": spec,
        "request_id": rid,
        "command": command,
        "started_at_utc": utc(),
        "protocol_acknowledged": False,
        "end_seen": False,
        "provider_rows": 0,
        "rows": 0,
        "malformed_rows": 0,
        "first": None,
        "last": None,
        "errors": [],
        "quality_flags": {},
        "raw_bytes": 0,
        "verification": "NOT_VERIFIED",
    }
    raw_hash = hashlib.sha256()
    small = bytearray()
    quality = Counter()
    previous = None
    directory_symbols = []
    error = None
    last_check = time.monotonic()
    with temp_raw.open("xb") as raw_file, temp_csv.open("xb") as csv_file:
        with (
            gzip.GzipFile(
                fileobj=raw_file, mode="wb", filename="", mtime=0, compresslevel=3
            ) as raw_zip,
            gzip.GzipFile(
                fileobj=csv_file, mode="wb", filename="", mtime=0, compresslevel=3
            ) as csv_zip,
            io.TextIOWrapper(csv_zip, encoding="utf-8", newline="") as text,
        ):
            writer = csv.writer(text, lineterminator="\n")
            writer.writerow(CSV_FIELDS)

            def retain(line):
                raw_zip.write(line)
                raw_hash.update(line)
                receipt["raw_bytes"] += len(line)
                if receipt["raw_bytes"] <= 65536:
                    small.extend(line)

            try:
                with socket.create_connection((host, port), timeout=10) as sock:
                    sock.settimeout(30)
                    with sock.makefile("rb") as stream:
                        sock.sendall(b"S,SET PROTOCOL,6.2\r\n")
                        line = read_line(stream)
                        retain(line)
                        if line.rstrip(b"\r\n,") != b"S,CURRENT PROTOCOL,6.2":
                            raise ValueError("protocol acknowledgement mismatch")
                        receipt["protocol_acknowledged"] = True
                        sock.sendall((command + "\r\n").encode("ascii"))
                        deadline = time.monotonic() + timeout
                        while True:
                            stop_requested()
                            if (
                                time.monotonic() > deadline
                                or receipt["raw_bytes"] > 256 * 1024**2
                            ):
                                raise TimeoutError(
                                    "SPLIT_REQUIRED: bounded response limit"
                                )
                            if time.monotonic() - last_check > 2:
                                check()
                                last_check = time.monotonic()
                            line = read_line(stream)
                            retain(line)
                            fields = line.decode("ascii").rstrip("\r\n").split(",")
                            if fields and fields[-1] == "":
                                fields.pop()
                            if len(fields) < 2 or fields[0] != rid:
                                raise ValueError(
                                    "wrong request ID or unexpected protocol record"
                                )
                            if fields[1:] == ["!ENDMSG!"]:
                                receipt["end_seen"] = True
                                break
                            if fields[1] == "E":
                                receipt["errors"].append(",".join(fields[2:]))
                                continue
                            if spec["cadence"] == "directory":
                                if fields[1] != "LS":
                                    raise ValueError("non-symbol directory record")
                                directory_symbols.append(fields[2:])
                                receipt["provider_rows"] += 1
                                continue
                            if fields[1] != "LH":
                                raise ValueError("non-history record")
                            receipt["provider_rows"] += 1
                            try:
                                payload = fields[2:]
                                if spec["cadence"] == "minute":
                                    payload = interval_fields(payload)
                                row, flags = parse_bar(
                                    payload,
                                    spec["cadence"],
                                    spec["begin"],
                                    spec["end"],
                                    previous,
                                )
                                writer.writerow(row)
                                quality.update(flags)
                                previous = row[0]
                                receipt["first"] = receipt["first"] or row[0]
                                receipt["last"] = row[0]
                                receipt["rows"] += 1
                            except (ValueError, IndexError) as exc:
                                receipt["malformed_rows"] += 1
                                quality[str(exc).split(":")[0]] += 1
            except (OSError, ValueError, UnicodeError) as exc:
                error = f"{type(exc).__name__}: {exc}"
        raw_file.flush()
        csv_file.flush()
        os.fsync(raw_file.fileno())
        os.fsync(csv_file.fileno())
    receipt.update(
        completed_at_utc=utc(),
        raw_uncompressed_sha256=raw_hash.hexdigest(),
        quality_flags=dict(quality),
        failure=error,
    )
    receipt["directory_symbols"] = directory_symbols
    if error or not receipt["end_seen"]:
        status = "INTERRUPTED" if STOP else "RETRY"
    elif receipt["errors"]:
        if all("uthoriz" in e for e in receipt["errors"]):
            status = "NOT_AUTHORIZED"
        elif provider_no_data(receipt):
            status = "NO_DATA"
        else:
            status = "RETRY"
    elif receipt["provider_rows"]:
        status = (
            "COMPLETE_WITH_ANOMALIES"
            if quality or receipt["malformed_rows"]
            else "COMPLETE"
        )
    else:
        status = "NO_DATA"
    receipt["status"] = status
    check()
    if receipt["provider_rows"] or receipt["raw_bytes"] > 65536 or error:
        # Failed partial responses are retained, never used as completed inputs.
        if status in ("RETRY", "INTERRUPTED"):
            raw_path, csv_path = temp_raw, temp_csv
        else:
            if raw_path.exists() or csv_path.exists():
                raise FileExistsError("immutable artifact destination already exists")
            os.replace(temp_raw, raw_path)
            os.replace(temp_csv, csv_path)
        receipt.update(
            raw_file=str(raw_path.relative_to(root)),
            raw_sha256=file_sha(raw_path),
            csv_file=str(csv_path.relative_to(root)),
            csv_sha256=file_sha(csv_path),
        )
        raw_blob = None
    else:
        # Tiny denials/no-data receipts belong in SQLite, avoiding exFAT's very
        # large allocation overhead for tens of thousands of 100-byte files.
        raw_blob = gzip.compress(bytes(small), mtime=0)
        receipt["raw_inline"] = "responses.small_raw_gzip"
        receipt["raw_sha256"] = hashlib.sha256(raw_blob).hexdigest()
        temp_raw.unlink()
        temp_csv.unlink()
    receipt["verification"] = verify_receipt(root, receipt, raw_blob)
    return receipt, raw_blob


def verify_receipt(root, receipt, raw_blob=None):
    raw = root / receipt["raw_file"] if receipt.get("raw_file") else None
    if raw:
        if file_sha(raw) != receipt["raw_sha256"]:
            raise ValueError("raw compressed hash mismatch")
        source = gzip.open(raw, "rb")  # noqa: SIM115 - both branches close in the immediately following with.
    else:
        if (
            raw_blob is None
            or hashlib.sha256(raw_blob).hexdigest() != receipt["raw_sha256"]
        ):
            raise ValueError("inline raw hash mismatch")
        source = io.BytesIO(gzip.decompress(raw_blob))
    with source:
        h = hashlib.sha256()
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
        if h.hexdigest() != receipt["raw_uncompressed_sha256"]:
            raise ValueError("raw uncompressed hash mismatch")
    if receipt.get("csv_file"):
        if file_sha(root / receipt["csv_file"]) != receipt["csv_sha256"]:
            raise ValueError("CSV hash mismatch")
        with gzip.open(root / receipt["csv_file"], "rt", newline="") as source:
            reader = csv.reader(source)
            if tuple(next(reader)) != CSV_FIELDS:
                raise ValueError("CSV header mismatch")
            if sum(1 for _ in reader) != receipt["rows"]:
                raise ValueError("CSV row count mismatch")
    if receipt["status"] in ("COMPLETE", "COMPLETE_WITH_ANOMALIES") and (
        not receipt["end_seen"]
        or not receipt["protocol_acknowledged"]
        or receipt["errors"]
    ):
        raise ValueError("incomplete protocol cannot be complete")
    return "HASH_AND_ROW_COUNT_PASS_NOT_CALENDAR_COMPLETENESS"


def add_directory_contracts(db, spec, receipt):
    import re

    pattern = re.compile(re.escape(spec["symbol"]) + "[FGHJKMNQUVXZ][0-9]{2}$")
    for fields in receipt["directory_symbols"]:
        if fields and pattern.fullmatch(fields[0]):
            for cadence in ("daily", "minute"):
                put_job(
                    db,
                    make_spec(
                        fields[0],
                        spec["folder"] + "/contracts",
                        "dated_contract",
                        cadence,
                        spec["end"],
                    ),
                    10,
                )


def save_response(db, spec, job_id, attempt, receipt, blob, priority):
    status = receipt["status"]
    if status == "RETRY" and receipt["failure"] and "Timeout" in receipt["failure"]:
        begin = date.fromisoformat(spec["begin"])
        end = date.fromisoformat(spec["end"])
        if spec["cadence"] != "directory" and (end - begin).days > 31:
            mid = begin + (end - begin) // 2
            put_job(db, {**spec, "end": mid.strftime("%Y%m%d")}, priority)
            put_job(
                db,
                {**spec, "begin": (mid + timedelta(days=1)).strftime("%Y%m%d")},
                priority,
            )
            status = "SPLIT"
    if status == "RETRY":
        status = "FAILED" if attempt >= 3 else "PENDING"
    if status == "INTERRUPTED":
        status = "PENDING"
    receipt["queue_status"] = status
    db.execute(
        "INSERT INTO responses VALUES (?,?,?,?)",
        (job_id, attempt, json.dumps(receipt), blob),
    )
    db.execute(
        "UPDATE jobs SET status=?,receipt=?,updated=? WHERE id=?",
        (status, json.dumps(receipt), utc(), job_id),
    )
    if spec["cadence"] == "directory" and receipt["status"] == "COMPLETE":
        add_directory_contracts(db, spec, receipt)
    db.commit()


def status(root, db, state, **extra):
    counts = dict(
        db.execute("SELECT status,COUNT(*) FROM jobs GROUP BY status").fetchall()
    )
    totals = db.execute("""SELECT COALESCE(SUM(json_extract(receipt,'$.rows')),0),
        MIN(json_extract(receipt,'$.first')), MAX(json_extract(receipt,'$.last'))
        FROM jobs WHERE status IN ('COMPLETE','COMPLETE_WITH_ANOMALIES')""").fetchone()
    rows, first, last = totals
    failed = []
    for result in db.execute(
        "SELECT receipt FROM jobs WHERE status IN ('NOT_AUTHORIZED','FAILED') LIMIT 30"
    ):
        rec = json.loads(result[0])
        failed.append(
            {
                "symbol": rec["spec"]["symbol"],
                "cadence": rec["spec"]["cadence"],
                "errors": rec["errors"],
                "failure": rec["failure"],
            }
        )
    report = {
        "schema": SCHEMA,
        "state": state,
        "pid": os.getpid(),
        "updated_at_utc": utc(),
        "jobs": sum(counts.values()),
        "counts": counts,
        "retained_parsed_rows": rows,
        "first_observed": first,
        "last_observed": last,
        "sample_blockers": failed,
        "calendar_and_inception_completeness": "NOT_ESTABLISHED",
        **extra,
    }
    atomic_json(root / "metadata/STATUS.json", report)
    return report


def export_manifest(root, db):
    temp = root / "metadata/MANIFEST.csv.tmp"
    with temp.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "job_id",
                "symbol",
                "kind",
                "cadence",
                "requested_begin",
                "requested_end",
                "status",
                "rows",
                "first",
                "last",
                "raw_file",
                "csv_file",
                "raw_sha256",
                "csv_sha256",
                "errors",
                "verification",
            )
        )
        for job in db.execute("SELECT * FROM jobs ORDER BY priority,id"):
            s, r = json.loads(job["spec"]), json.loads(job["receipt"] or "{}")
            writer.writerow(
                (
                    job["id"],
                    s["symbol"],
                    s["kind"],
                    s["cadence"],
                    s["begin"],
                    s["end"],
                    job["status"],
                    r.get("rows", 0),
                    r.get("first"),
                    r.get("last"),
                    r.get("raw_file", ""),
                    r.get("csv_file", ""),
                    r.get("raw_sha256", ""),
                    r.get("csv_sha256", ""),
                    "|".join(r.get("errors", [])),
                    r.get("verification", "NOT_ATTEMPTED"),
                )
            )
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, root / "metadata/MANIFEST.csv")


def run(root, *, max_jobs=0):
    from utils.data_paths import resolve_source_location

    global STOP
    STOP = False
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: globals().__setitem__("STOP", True))
    guard(root, force=True)
    config = json.loads((root / "metadata/ARCHIVE.json").read_text())
    current = {p.name: file_sha(p) for p in Path(__file__).parent.glob("*.py")}
    if current != config["code_sha256"]:
        raise ValueError(
            "code changed since queue creation; review and rebind explicitly"
        )
    shared = (
        resolve_source_location("iqfeed_equity_minute_archive")
        / ".locks/iqfeed_external_archive_download_supervisor_v1.lock"
    )
    completed = 0
    with lock(root / "metadata/WORKER.lock"), closing(connect_db(root)) as db:
        # A crashed attempt cannot be silently accepted. Preserve its .part files
        # and issue a new attempt ID. Completed jobs are never downloaded again.
        db.execute("UPDATE jobs SET status='PENDING' WHERE status='RUNNING'")
        db.commit()
        last_export = 0.0
        last_status = 0.0
        try:
            while not STOP:
                if (root / "metadata/STOP").exists():
                    break
                job = db.execute(
                    "SELECT * FROM jobs WHERE status='PENDING' ORDER BY priority,rowid LIMIT 1"
                ).fetchone()
                if job is None:
                    break
                spec = json.loads(job["spec"])
                guard(root, force=True)
                try:
                    with lock(shared):
                        attempt = job["attempts"] + 1
                        db.execute(
                            "UPDATE jobs SET status='RUNNING',attempts=?,updated=? WHERE id=?",
                            (attempt, utc(), job["id"]),
                        )
                        db.commit()
                        if time.monotonic() - last_status > 10:
                            status(root, db, "DOWNLOADING", current=spec)
                            last_status = time.monotonic()
                        receipt, blob = collect(
                            root,
                            spec,
                            job["id"],
                            attempt,
                            lambda: guard(root),
                            host=config["host"],
                            port=config["port"],
                        )
                        save_response(
                            db, spec, job["id"], attempt, receipt, blob, job["priority"]
                        )
                        completed += 1
                        print(
                            json.dumps(
                                {
                                    "at": utc(),
                                    "symbol": spec["symbol"],
                                    "cadence": spec["cadence"],
                                    "status": receipt["queue_status"],
                                    "rows": receipt["rows"],
                                    "first": receipt["first"],
                                    "last": receipt["last"],
                                }
                            ),
                            flush=True,
                        )
                except BlockingIOError:
                    status(
                        root, db, "WAITING_FOR_SHARED_DOWNLOAD_LOCK", lock=str(shared)
                    )
                    for _ in range(10):
                        if STOP:
                            break
                        time.sleep(1)
                    continue
                if time.monotonic() - last_export > 60:
                    export_manifest(root, db)
                    last_export = time.monotonic()
                if max_jobs and completed >= max_jobs:
                    break
                time.sleep(0.15)
        except Exception as exc:
            # Never export uncommitted RUNNING/COMPLETE transitions as durable
            # state after an exhausted wait or a storage error.
            db.rollback()
            # Only report on a still-mounted verified target; never create a
            # shadow STATUS.json if the external drive went away.
            guard(root, reserve=0)
            status(root, db, "PAUSED_ERROR", error=f"{type(exc).__name__}: {exc}")
            export_manifest(root, db)
            raise
        pending = db.execute(
            "SELECT COUNT(*) FROM jobs WHERE status IN ('PENDING','RUNNING')"
        ).fetchone()[0]
        state = "PAUSED" if pending else "FINISHED_WITH_RECORDED_SOURCE_LIMITATIONS"
        report = status(root, db, state)
        export_manifest(root, db)
        db.close()
        return report


def rebind(root, reason):
    """Explicit maintenance: preserve old bindings and every original attempt."""
    if not reason or not reason.strip():
        raise ValueError("rebind requires an explicit --reason")
    guard(root, force=True)
    with lock(root / "metadata/WORKER.lock"):
        archive_path = root / "metadata/ARCHIVE.json"
        config = json.loads(archive_path.read_text())
        current = {p.name: file_sha(p) for p in Path(__file__).parent.glob("*.py")}
        if current == config["code_sha256"]:
            raise ValueError("collector binding is unchanged")
        db = connect_db(root)
        corrections = []
        verified = 0
        total = db.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
        print(json.dumps({"at": utc(), "event": "VERIFY_EXISTING_FOR_REBIND",
                          "responses": total}), flush=True)
        for row in db.execute("SELECT receipt,small_raw_gzip FROM responses"):
            verify_receipt(root, json.loads(row[0]), row[1])
            verified += 1
            if verified % 250 == 0:
                print(json.dumps({"at": utc(), "event": "REBIND_VERIFICATION_PROGRESS",
                                  "verified": verified, "responses": total}), flush=True)
        for row in db.execute("SELECT id,receipt FROM jobs WHERE status='FAILED'"):
            receipt = json.loads(row["receipt"])
            if provider_no_data(receipt):
                corrections.append(
                    {
                        "job_id": row["id"],
                        "old_status": "FAILED",
                        "new_status": "NO_DATA",
                    }
                )
        review = {
            "schema": "iqfeed_macroeconomics.collector_review.v1",
            "at_utc": utc(),
            "reason": reason,
            "previous_archive": config,
            "new_code_sha256": current,
            "verified_existing_responses": verified,
            "classification_corrections": corrections,
            "original_responses": "UNCHANGED; queue classification only",
        }
        review_path = (
            root / "metadata" / ("COLLECTOR_REVIEW_" + uuid.uuid4().hex + ".json")
        )
        atomic_json(review_path, review)
        for item in corrections:
            receipt = json.loads(
                db.execute(
                    "SELECT receipt FROM jobs WHERE id=?", (item["job_id"],)
                ).fetchone()[0]
            )
            receipt.update(
                queue_status="NO_DATA",
                classification_review=str(review_path.relative_to(root)),
            )
            db.execute(
                "UPDATE jobs SET status='NO_DATA',receipt=?,updated=? WHERE id=?",
                (json.dumps(receipt), utc(), item["job_id"]),
            )
        db.commit()
        config["code_sha256"] = current
        config.setdefault("collector_reviews", []).append(
            {
                "file": str(review_path.relative_to(root)),
                "sha256": file_sha(review_path),
            }
        )
        atomic_json(archive_path, config)
        status(root, db, "PAUSED")
        export_manifest(root, db)
        db.close()
        return {
            "review": str(review_path),
            "verified_responses": verified,
            "classification_corrections": len(corrections),
        }


def main(argv=None):
    from utils.data_paths import resolve_source_location

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("init", "run", "start", "status", "verify", "rebind")
    )
    parser.add_argument(
        "--reason", help="Explicit reviewed reason for a collector-code rebind"
    )
    parser.add_argument(
        "--end",
        default=(
            datetime.now(ZoneInfo("America/New_York")).date() - timedelta(days=1)
        ).strftime("%Y%m%d"),
    )
    parser.add_argument("--max-jobs", type=int, default=0)
    parser.add_argument("--first-expiry-year", type=int, default=1959)
    parser.add_argument("--last-expiry-year", type=int)
    args = parser.parse_args(argv)
    root = resolve_source_location("iqfeed_macroeconomics")
    if args.action == "init":
        result = initialise(
            root, args.end, args.first_expiry_year, args.last_expiry_year
        )
        print(
            json.dumps(
                {
                    "root": str(root),
                    "jobs": result["initial_jobs"],
                    "cutoff": result["cutoff"],
                }
            )
        )
    elif args.action == "run":
        print(json.dumps(run(root, max_jobs=args.max_jobs)))
    elif args.action == "start":
        guard(root, force=True)
        # Refuse duplicate workers before spawning; run itself also takes this lock.
        with lock(root / "metadata/WORKER.lock"):
            pass
        repo = Path(__file__).resolve().parents[3]
        with (root / "logs/download.log").open("ab", buffering=0) as log:
            proc = subprocess.Popen(
                [sys.executable, "-B", "-m", MODULE, "run"],
                cwd=repo,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        print(
            json.dumps(
                {"started_pid": proc.pid, "status": str(root / "metadata/STATUS.json")}
            )
        )
    elif args.action == "rebind":
        print(json.dumps(rebind(root, args.reason)))
    elif args.action == "status":
        guard(root, reserve=0)
        print((root / "metadata/STATUS.json").read_text())
    else:
        guard(root, reserve=0)
        db = connect_db(root)
        checked = 0
        for row in db.execute("SELECT receipt,small_raw_gzip FROM responses"):
            rec = json.loads(row[0])
            verify_receipt(root, rec, row[1])
            checked += 1
        print(
            json.dumps(
                {
                    "verified_responses": checked,
                    "status": "PASS",
                    "calendar_completeness": "NOT_ESTABLISHED",
                }
            )
        )
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
