from __future__ import annotations

import gzip
import hashlib
import io
import json
import zipfile
from datetime import date, timedelta

import pytest

from . import archive as a
from . import parsers as p
from . import storage as s


def make_zip(rows="2020-01-01,100,2020-02-01,\n", dates=("2020-02-01",), extra=None):
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w") as z:
        z.writestr(
            "README.txt",
            "Series ID: TEST\nHistorical metadata\nVintage Dates Specified:\n----------\n"
            + "\n".join(dates)
            + "\n----------\n",
        )
        z.writestr(
            "obs._by_real-time_period.csv",
            "period_start_date,TEST,realtime_start_date,realtime_end_date\n" + rows,
        )
        if extra:
            z.writestr(extra, "unsafe")
    return target.getvalue()


def test_current_preserves_original_strings_missing_and_negative_values():
    rows, stats = p.current_csv(
        b"observation_date,TEST\n2020-01-01,1.000\n2020-01-02,.\n2020-01-03,-0.25\n",
        "TEST",
        "2020-01-03",
    )
    assert rows == [
        ["2020-01-01", "1.000"],
        ["2020-01-02", "."],
        ["2020-01-03", "-0.25"],
    ]
    assert stats["missing_values"] == 1


@pytest.mark.parametrize(
    "body",
    [
        b"<html>challenge</html>",
        b"observation_date,WRONG\n2020-01-01,1\n",
        b"observation_date,TEST\n",
    ],
)
def test_wrong_or_empty_current_source_rejected(body):
    with pytest.raises(ValueError):
        p.current_csv(body, "TEST", "2020-01-03")


@pytest.mark.parametrize(
    "rows",
    [
        "2020-01-01,1\n2020-01-01,2\n",
        "2020-01-04,1\n",
        "2020-01-01,nan\n",
        "2020-01-01,invalid\n",
    ],
)
def test_bad_current_rows_rejected(rows):
    with pytest.raises(ValueError):
        p.current_csv(("observation_date,TEST\n" + rows).encode(), "TEST", "2020-01-03")


def test_vintage_rows_and_metadata_preserved():
    csv_body, notes, stats = p.vintage_zip(make_zip(), "TEST", ["2020-02-01"])
    assert stats["rows"] == 1
    assert stats["clock_precision"] == "DAY_NOT_INTRADAY"
    assert b"2020-01-01,100,2020-02-01,\n" in csv_body
    assert b"Historical metadata" in notes


def test_vintage_acknowledgement_catches_silent_form_truncation():
    with pytest.raises(ValueError, match="truncated"):
        p.vintage_zip(make_zip(), "TEST", ["2020-02-01", "2020-03-01"])


@pytest.mark.parametrize(
    "rows",
    [
        "2020-01-01,100,2020-03-01,\n",
        "2020-01-01,100,2020-02-01,2020-01-01\n",
        "2020-01-01,100,2020-02-01,\n2020-01-01,101,2020-02-01,\n",
    ],
)
def test_invalid_or_conflicting_vintage_intervals_rejected(rows):
    with pytest.raises(ValueError):
        p.vintage_zip(make_zip(rows), "TEST", ["2020-02-01"])


def test_zip_has_no_path_extraction_or_unexpected_members():
    with pytest.raises(ValueError):
        p.vintage_zip(make_zip(extra="../escape"), "TEST", ["2020-02-01"])


def test_vintage_form_excludes_future_dates_and_keeps_all_available():
    body = b'<input id="form_obs_start_date" value="1947-01-01"><input id="form_obs_end_date" value="2026-07-01"><select id="form_selected_vintage_dates"><option value="1972-07-21"></option><option value="2026-08-12"></option><option value="2026-09-11"></option></select>'
    result = p.vintage_form(body, "2026-09-10")
    assert result["vintages"] == ["1972-07-21", "2026-08-12"]
    assert result["begin"] == "1947-01-01"


@pytest.mark.parametrize(
    "stamp,zone,expected",
    [
        ("20260911T083000", "America/New_York", "2026-09-11T12:30:00+00:00"),
        ("20260113T083000", "US/Eastern", "2026-01-13T13:30:00+00:00"),
        ("20260911T123000Z", "", "2026-09-11T12:30:00+00:00"),
    ],
)
def test_ics_uses_explicit_timezone_and_dst(stamp, zone, expected):
    parameter = ";TZID=" + zone if zone else ""
    body = f"BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:test\r\nDTSTART{parameter}:{stamp}\r\nSUMMARY:CPI\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n".encode()
    event = p.calendar_ics(body)[0]
    assert event["scheduled_at_utc"] == expected
    assert event["dtstart_original"] == stamp


def test_floating_calendar_timestamp_is_not_assigned_a_guessed_timezone():
    with pytest.raises(ValueError, match="timezone"):
        p.calendar_ics(
            b"BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART:20260911T083000\nEND:VEVENT\nEND:VCALENDAR"
        )


def test_calendar_date_only_is_not_given_midnight_availability():
    event = p.calendar_ics(
        b"BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART;VALUE=DATE:20260911\nEND:VEVENT\nEND:VCALENDAR"
    )[0]
    assert event["scheduled_at_utc"] is None


def test_bls_archive_links_confined_to_source_and_cutoff():
    body = b'<a href="/news.release/archives/cpi_08122026.htm">OK</a><a href="/news.release/archives/cpi_09112026.htm">Future</a><a href="https://evil.example/news.release/archives/cpi_08122026.htm">Wrong host</a>'
    result = p.bls_archive_links(
        body, "https://www.bls.gov/bls/news-release/cpi.htm", "2026-09-10"
    )
    assert len(result) == 1
    assert result[0]["filename_date"] == "2026-08-12"


def test_lock_does_not_clobber_active_owner(tmp_path):
    path = tmp_path / "lock"
    with s.lock(path):
        content = path.read_bytes()
        with pytest.raises(BlockingIOError), s.lock(path):
            pass
        assert path.read_bytes() == content


def test_derived_artifacts_are_immutable_and_reusable(tmp_path):
    result = a.persist(tmp_path, "data/a.csv.gz", b"a,b\n1,2\n")
    assert a.persist(tmp_path, "data/a.csv.gz", b"a,b\n1,2\n") == result
    with pytest.raises(ValueError, match="Immutable"):
        a.persist(tmp_path, "data/a.csv.gz", b"changed")


@pytest.mark.parametrize("value", ["1.000", "999"])
def test_verifier_compares_derived_values_with_source_not_only_recorded_hashes(
    tmp_path, monkeypatch, value
):
    monkeypatch.setattr(a, "guard", lambda *args, **kwargs: None)
    (tmp_path / "metadata").mkdir()
    s.atomic_json(
        tmp_path / "metadata/ARCHIVE.json",
        {"observation_and_vintage_cutoff": "2020-01-01"},
    )
    body = b"observation_date,TEST\n2020-01-01,1.000\n"
    raw = tmp_path / "source.raw.gz"
    raw.write_bytes(gzip.compress(body, mtime=0))
    s.atomic_json(
        tmp_path / "source.receipt.json",
        {
            "raw_file": raw.name,
            "raw_sha256": s.sha(raw),
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "body_bytes": len(body),
        },
    )
    artifact = a.persist(
        tmp_path,
        "derived.csv.gz",
        f"observation_date,value\n2020-01-01,{value}\n".encode(),
    )
    spec = {"kind": "current", "series": "TEST"}
    db = a.database(tmp_path)
    key = a.add_job(db, spec, 0)
    report = {
        "spec": spec,
        "rows": 1,
        "artifacts": [artifact],
        "request_receipts": ["source.receipt.json"],
    }
    db.execute(
        "UPDATE jobs SET state='COMPLETE',report=? WHERE id=?",
        (json.dumps(report), key),
    )
    db.commit()
    db.close()
    if value == "1.000":
        assert a.verify(tmp_path)["status"] == "PASS"
    else:
        with pytest.raises(ValueError, match="differ from source"):
            a.verify(tmp_path)


def test_http_tampering_is_detected(tmp_path):
    body = b"source body"
    path = tmp_path / "raw.gz"
    path.write_bytes(gzip.compress(body, mtime=0))
    receipt = {
        "raw_file": "raw.gz",
        "raw_sha256": s.sha(path),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "body_bytes": len(body),
    }
    assert s.verify_http(tmp_path, receipt) == "HASH_AND_GZIP_PASS"
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash"):
        s.verify_http(tmp_path, receipt)


@pytest.mark.parametrize("status", [500, 502, 503, 504, 401, 403, 429, 0])
def test_explicit_split_recovers_only_server_errors_and_preserves_evidence(
    tmp_path, monkeypatch, status
):
    monkeypatch.setattr(a, "guard", lambda *args, **kwargs: None)
    (tmp_path / "metadata").mkdir()
    body = b"source failure"
    raw = tmp_path / "failure.raw.gz"
    raw.write_bytes(gzip.compress(body, mtime=0))
    receipt = {
        "http_status": status,
        "raw_file": raw.name,
        "raw_sha256": s.sha(raw),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "body_bytes": len(body),
    }
    s.atomic_json(tmp_path / "failure.receipt.json", receipt)
    dates = ["2020-01-01", "2020-02-01", "2020-03-01", "2020-04-01"]
    spec = {
        "kind": "vintage_zip",
        "series": "TEST",
        "url": "https://example.test",
        "folder": "test",
        "vintages": dates,
        "form": {"form[selected_vintage_dates][]": dates, "form[units]": "lin"},
    }
    db = a.database(tmp_path)
    key = a.add_job(db, spec, 2)
    report = {
        "state": "FAILED_HTTP",
        "spec": spec,
        "request_receipts": ["failure.receipt.json"],
        "error": f"HTTP {status}",
    }
    db.execute(
        "UPDATE jobs SET state='FAILED_HTTP',report=? WHERE id=?",
        (json.dumps(report), key),
    )
    db.commit()
    db.close()
    result = a.split_failed_vintages(tmp_path)
    db = a.database(tmp_path, readonly=True)
    parent = db.execute("SELECT * FROM jobs WHERE id=?", (key,)).fetchone()
    saved = json.loads(parent["report"])
    assert saved["request_receipts"] == report["request_receipts"]
    assert saved["error"] == report["error"]
    if status in (500, 502, 503, 504):
        assert result["children_queued"] == 2
        assert parent["state"] == "SPLIT_HTTP_FAILURE"
        children = [
            json.loads(row[0])
            for row in db.execute(
                "SELECT spec FROM jobs WHERE state='PENDING' ORDER BY rowid"
            )
        ]
        assert [d for child in children for d in child["vintages"]] == dates
        assert all(
            c["form"]["form[selected_vintage_dates][]"] == c["vintages"]
            for c in children
        )
        assert all(c["split_from_job"] == key for c in children)
        assert all(c["form"]["form[units]"] == "lin" for c in children)
    else:
        assert result["children_queued"] == 0
        assert parent["state"] == "FAILED_HTTP"
    db.close()
    assert s.verify_http(tmp_path, receipt) == "HASH_AND_GZIP_PASS"


def test_interrupted_download_temporary_bytes_are_retained(tmp_path):
    with pytest.raises(InterruptedError), s.download_temporary(tmp_path) as directory:
        (directory / "body").write_bytes(b"partial")
        raise InterruptedError("stop")
    assert (directory / "body").read_bytes() == b"partial"
    with s.download_temporary(tmp_path) as completed:
        (completed / "body").write_bytes(b"already retained copy")
    assert not completed.exists()


def test_local_output_path_cannot_escape_or_follow_symlink(tmp_path):
    with pytest.raises(ValueError):
        s.local_path(tmp_path, "../escape")
    (tmp_path / "link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(OSError):
        s.local_path(tmp_path, "link/file")


def test_form_job_schedules_every_vintage_exactly_once_in_bounded_chunks(tmp_path):
    (tmp_path / "metadata").mkdir()
    db = a.database(tmp_path)
    dates = [(date(2020, 1, 1) + timedelta(days=i)).isoformat() for i in range(801)]
    body = (
        '<input id="form_obs_start_date" value="1947-01-01"><input id="form_obs_end_date" value="2022-03-01"><select id="form_selected_vintage_dates">'
        + "".join(f'<option value="{d}"></option>' for d in dates)
        + "</select>"
    ).encode()

    class FakeFetcher:
        def fetch(self, *args, **kwargs):
            return {"status": "DOWNLOADED", "receipt_file": "fake.receipt.json"}

        def body(self, receipt):
            return body

    spec = {
        "kind": "vintage_form",
        "series": "TEST",
        "folder": "vintages/TEST",
        "url": "https://example.test",
    }
    key = a.add_job(db, spec, 0)
    job = db.execute("SELECT * FROM jobs WHERE id=?", (key,)).fetchone()
    result = a.execute_job(
        tmp_path,
        db,
        FakeFetcher(),
        job,
        {"snapshot": "test", "observation_and_vintage_cutoff": "2026-09-10"},
        "run1",
    )
    assert result["state"] == "COMPLETE"
    children = [
        json.loads(row[0])
        for row in db.execute(
            "SELECT spec FROM jobs WHERE id<>? ORDER BY rowid", (key,)
        )
    ]
    assert [len(child["vintages"]) for child in children] == [400, 400, 1]
    assert [d for child in children for d in child["vintages"]] == dates
    db.close()
