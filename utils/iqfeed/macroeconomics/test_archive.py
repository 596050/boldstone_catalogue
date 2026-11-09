from __future__ import annotations

import gzip
import json
import socket
import sqlite3
import threading
from contextlib import contextmanager

import pytest

from . import archive as a


def test_sqlite_busy_commit_retries_without_repeating_inserts(tmp_path, monkeypatch):
    setup_root(tmp_path)
    monkeypatch.setattr(a, "guard", lambda *args, **kwargs: None)
    monkeypatch.setattr(a, "SQLITE_RETRY_POLL_SECONDS", 0.01)
    db = a.connect_db(tmp_path)
    db.execute("PRAGMA busy_timeout=5")
    a.put_job(db, spec(), 0)
    db.commit()
    reader = sqlite3.connect(tmp_path / "metadata/queue.sqlite3", check_same_thread=False)
    reader.execute("BEGIN")
    reader.execute("SELECT id FROM jobs").fetchall()
    trace = []
    db.set_trace_callback(trace.append)
    db.execute("UPDATE jobs SET attempts=attempts+1")
    timer = threading.Timer(0.08, reader.close)
    timer.start()
    try:
        db.commit()
        assert db.execute("SELECT attempts FROM jobs").fetchone()[0] == 1
        assert sum(s.startswith("UPDATE jobs") for s in trace) == 1
        assert trace.count("COMMIT") > 1
    finally:
        timer.join(timeout=2)
        db.close()


@pytest.mark.parametrize("stop", [False, True])
def test_sqlite_busy_timeout_or_stop_retains_transaction_for_explicit_rollback(tmp_path, monkeypatch, stop):
    setup_root(tmp_path)
    monkeypatch.setattr(a, "guard", lambda *args, **kwargs: None)
    monkeypatch.setattr(a, "SQLITE_RETRY_SECONDS", 0.02)
    monkeypatch.setattr(a, "SQLITE_RETRY_POLL_SECONDS", 0.005)
    monkeypatch.setattr(a, "STOP", stop)
    db = a.connect_db(tmp_path)
    db.execute("PRAGMA busy_timeout=1")
    a.put_job(db, spec(), 0)
    db.commit()
    reader = sqlite3.connect(tmp_path / "metadata/queue.sqlite3")
    reader.execute("BEGIN")
    reader.execute("SELECT id FROM jobs").fetchall()
    try:
        db.execute("UPDATE jobs SET attempts=attempts+1")
        with pytest.raises(InterruptedError if stop else sqlite3.OperationalError):
            db.commit()
        assert db.in_transaction
        db.rollback()
        assert db.execute("SELECT attempts FROM jobs").fetchone()[0] == 0
    finally:
        reader.close()
        db.close()


def test_sqlite_noncontention_error_is_not_retried(tmp_path, monkeypatch):
    setup_root(tmp_path)
    db = a.connect_db(tmp_path)
    calls = []
    monkeypatch.setattr(a, "guard", lambda *args, **kwargs: calls.append(True))
    try:
        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            db.execute("INSERT INTO nonexistent VALUES (1)")
        assert not calls
    finally:
        db.close()


@contextmanager
def fake_feed(rows=(), errors=(), *, finish=True, wrong_id=False):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    problems = []

    def serve():
        try:
            with server:
                conn, _ = server.accept()
                with conn, conn.makefile("rb") as stream:
                    assert stream.readline() == b"S,SET PROTOCOL,6.2\r\n"
                    conn.sendall(b"S,CURRENT PROTOCOL,6.2\r\n")
                    command = stream.readline().decode().strip().split(",")
                    rid = command[6] if command[0] == "HDT" else command[9]
                    if wrong_id:
                        rid = "WRONG"
                    for row in rows:
                        conn.sendall(f"{rid},LH,{row},\r\n".encode())
                    for error in errors:
                        conn.sendall(f"{rid},E,{error},\r\n".encode())
                    if finish:
                        conn.sendall(f"{rid},!ENDMSG!,\r\n".encode())
        except (OSError, AssertionError, IndexError) as exc:
            problems.append(exc)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        thread.join(3)
        assert not thread.is_alive()
        assert not problems


def spec(cadence="daily"):
    return a.make_spec("QCLZ20", "oil/contracts", "dated_contract", cadence, "20201231")


def setup_root(tmp_path):
    for folder in ("metadata", "reference", "incomplete"):
        (tmp_path / folder).mkdir()
    return tmp_path


def test_commands_have_no_truncating_maximum_and_explicit_bar_label():
    assert a.command_for(spec(), "R") == "HDT,QCLZ20,19000101,20201231,,1,R,5000"
    assert (
        a.command_for(spec("minute"), "R")
        == "HIT,QCLZ20,60,19000101 000000,20201231 235959,,,,1,R,5000,s,0"
    )


def test_symbol_encoding_has_no_continuous_or_root_collision():
    symbols = ("@TY#", "@TY#C", "TY", "@TY", "XAUUSD.FXCM")
    assert len({a.safe_symbol(x) for x in symbols}) == len(symbols)


def test_negative_oil_is_preserved():
    fields = ["2020-04-20", "-35", "-40", "-36", "-37", "100", "30"]
    row, flags = a.parse_bar(fields, "daily", "19000101", "20201231", None)
    assert row[1:5] == ("-36", "-35", "-40", "-37")
    assert flags == []


def test_minute_volume_is_not_confused_with_cumulative_volume():
    fields = a.interval_fields(
        ["2020-04-20 14:00:00", "2", "1", "1.2", "1.5", "1000", "15", "8"]
    )
    row, flags = a.parse_bar(fields, "minute", "19000101", "20201231", None)
    assert row[5:9] == ("1000", "15", "8", "")
    assert flags == []


@pytest.mark.parametrize(
    "row,flag",
    [
        ("2020-04-20,2,1,3,1.5,10,0", "OHLC_ENVELOPE"),
        ("2020-04-20,2,1,1,1.5,-10,0", "NEGATIVE_VOLUME_OR_COUNT"),
    ],
)
def test_quality_flags_do_not_repair_or_drop_parseable_rows(row, flag):
    result, flags = a.parse_bar(row.split(","), "daily", "19000101", "20201231", None)
    assert flag in flags
    assert result[1] == row.split(",")[3]


def test_outside_window_is_not_accepted():
    with pytest.raises(ValueError, match="OUTSIDE_REQUEST_RANGE"):
        a.parse_bar(
            ["2021-01-01", "2", "1", "1", "1.5", "0", "0"],
            "daily",
            "19000101",
            "20201231",
            None,
        )


def test_full_response_roundtrip_and_tamper_detection(tmp_path):
    root = setup_root(tmp_path)
    with fake_feed(["2020-04-20,-35,-40,-36,-37,100,30"]) as port:
        receipt, blob = a.collect(root, spec(), "abc", 1, lambda: None, port=port)
    assert receipt["status"] == "COMPLETE"
    assert receipt["rows"] == 1
    assert receipt["verification"].startswith("HASH_AND_ROW_COUNT_PASS")
    assert b"abc_1,LH,2020-04-20" in gzip.decompress(
        (root / receipt["raw_file"]).read_bytes()
    )
    (root / receipt["csv_file"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="CSV hash"):
        a.verify_receipt(root, receipt, blob)


def test_minute_roundtrip(tmp_path):
    root = setup_root(tmp_path)
    with fake_feed(["2020-04-20 14:00:00,2,1,1.2,1.5,1000,15,8"]) as port:
        receipt, _ = a.collect(root, spec("minute"), "abc", 1, lambda: None, port=port)
    assert receipt["status"] == "COMPLETE"
    assert receipt["rows"] == 1
    assert receipt["malformed_rows"] == 0


@pytest.mark.parametrize(
    "error,status",
    [
        ("!NO_DATA!", "NO_DATA"),
        ("!NO_DATA!,", "NO_DATA"),
        ("!NO_DATA!,,", "NO_DATA"),
        ("Unauthorized user ID.", "NOT_AUTHORIZED"),
    ],
)
def test_denials_are_byte_preserved_inline_not_empty_success(tmp_path, error, status):
    root = setup_root(tmp_path)
    with fake_feed(errors=[error]) as port:
        receipt, blob = a.collect(root, spec(), "abc", 1, lambda: None, port=port)
    assert receipt["status"] == status
    assert error.encode() in gzip.decompress(blob)
    assert not list((root / "incomplete").iterdir())
    assert not receipt.get("csv_file")


@pytest.mark.parametrize("options", [{"finish": False}, {"wrong_id": True}])
def test_interrupted_or_cross_request_data_not_complete(tmp_path, options):
    root = setup_root(tmp_path)
    with fake_feed(["2020-04-20,2,1,1,1.5,10,0"], **options) as port:
        receipt, blob = a.collect(root, spec(), "abc", 1, lambda: None, port=port)
    assert receipt["status"] == "RETRY"
    assert receipt["raw_file"].startswith("incomplete/")
    assert blob is None


def test_malformed_row_retained_in_raw_and_counted(tmp_path):
    root = setup_root(tmp_path)
    with fake_feed(["BAD,ROW", "2020-04-20,2,1,1,1.5,10,0"]) as port:
        receipt, _ = a.collect(root, spec(), "abc", 1, lambda: None, port=port)
    assert receipt["status"] == "COMPLETE_WITH_ANOMALIES"
    assert (receipt["rows"], receipt["malformed_rows"], receipt["provider_rows"]) == (
        1,
        1,
        2,
    )


def test_duplicate_worker_lock_does_not_truncate_owner(tmp_path):
    path = tmp_path / "lock"
    with a.lock(path):
        before = path.read_bytes()
        with pytest.raises(BlockingIOError), a.lock(path):
            pass
        assert path.read_bytes() == before


def test_queue_identity_is_idempotent_and_cadences_independent(tmp_path):
    root = setup_root(tmp_path)
    db = a.connect_db(root)
    first = a.put_job(db, spec(), 1)
    assert a.put_job(db, spec(), 9) == first
    assert a.put_job(db, spec("minute"), 1) != first
    assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 2
    db.close()


def test_split_windows_cover_parent_without_overlap(tmp_path):
    root = setup_root(tmp_path)
    db = a.connect_db(root)
    parent = spec("minute")
    job_id = a.put_job(db, parent, 1)
    receipt = {"status": "RETRY", "failure": "TimeoutError: split", "errors": []}
    a.save_response(db, parent, job_id, 1, receipt, None, 1)
    assert (
        db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
        == "SPLIT"
    )
    children = sorted(
        (
            json.loads(r[0])
            for r in db.execute("SELECT spec FROM jobs WHERE id<>?", (job_id,))
        ),
        key=lambda s: s["begin"],
    )
    assert children[0]["begin"] == parent["begin"]
    assert children[1]["end"] == parent["end"]
    end = a.date.fromisoformat(children[0]["end"])
    assert children[1]["begin"] == (end + a.timedelta(days=1)).strftime("%Y%m%d")
    db.close()


def test_code_and_instruments_are_importable_without_accessing_provider():
    assert len(a.ROOTS) == 13
    assert any(item[0] == "MOVE.X" for item in a.SERIES)
    assert "@GC" not in {r[0] for r in a.ROOTS}


def test_no_data_classification_requires_complete_consistent_response():
    receipt = {
        "protocol_acknowledged": True,
        "end_seen": True,
        "provider_rows": 0,
        "errors": ["!NO_DATA!,"],
    }
    assert a.provider_no_data(receipt)
    assert not a.provider_no_data({**receipt, "end_seen": False})
    assert not a.provider_no_data({**receipt, "provider_rows": 1})
    assert not a.provider_no_data({**receipt, "failure": "EOF"})
    assert not a.provider_no_data(
        {**receipt, "errors": ["!NO_DATA!,", "Unknown failure"]}
    )


def test_review_rebind_preserves_original_attempt_and_audits_correction(
    tmp_path, monkeypatch
):
    root = setup_root(tmp_path)
    monkeypatch.setattr(a, "guard", lambda *args, **kwargs: None)
    db = a.connect_db(root)
    job_id = a.put_job(db, spec(), 1)
    with fake_feed(errors=["!NO_DATA!,"]) as port:
        receipt, blob = a.collect(root, spec(), job_id, 1, lambda: None, port=port)
    receipt.update(status="RETRY", queue_status="FAILED")
    original_receipt = json.dumps(receipt)
    db.execute(
        "INSERT INTO responses VALUES (?,?,?,?)", (job_id, 1, original_receipt, blob)
    )
    db.execute(
        "UPDATE jobs SET status='FAILED',receipt=? WHERE id=?",
        (original_receipt, job_id),
    )
    db.commit()
    db.close()
    old_binding = {"archive.py": "previous-implementation"}
    a.atomic_json(root / "metadata/ARCHIVE.json", {"code_sha256": old_binding})
    result = a.rebind(root, "Review tested handling of optional empty error columns")
    assert result["verified_responses"] == 1
    assert result["classification_corrections"] == 1
    db = a.connect_db(root)
    assert db.execute("SELECT status FROM jobs").fetchone()[0] == "NO_DATA"
    assert tuple(
        db.execute("SELECT receipt,small_raw_gzip FROM responses").fetchone()
    ) == (original_receipt, blob)
    db.close()
    review = json.loads(a.Path(result["review"]).read_text())
    assert review["previous_archive"]["code_sha256"] == old_binding
    with pytest.raises(ValueError, match="unchanged"):
        a.rebind(root, "Already reviewed")
