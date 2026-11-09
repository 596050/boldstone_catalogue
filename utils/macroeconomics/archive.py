"""Acquire official economic series and ALFRED vintages beside the IQFeed archive."""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from utils.data_paths import resolve_source_location

from .catalog import DOCUMENTS, SERIES
from .parsers import (
    bls_archive_links,
    calendar_ics,
    current_csv,
    vintage_form,
    vintage_zip,
)
from .storage import (
    Fetcher,
    atomic_json,
    canonical,
    guard,
    local_path,
    lock,
    sha,
    utc,
    verify_http,
)

MODULE = "utils.macroeconomics.archive"
STOP = False


def check(root, **kwargs):
    if STOP:
        raise InterruptedError("Graceful stop requested")
    return guard(root, **kwargs)


def database(root, readonly=False):
    path = root / "metadata/queue.sqlite3"
    db = (
        sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        if readonly
        else sqlite3.connect(path)
    )
    db.row_factory = sqlite3.Row
    if not readonly:
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA cache_size=-16384")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, spec TEXT NOT NULL, priority INTEGER NOT NULL,
                state TEXT NOT NULL DEFAULT 'PENDING', report TEXT
            );
            CREATE INDEX IF NOT EXISTS job_order ON jobs(state,priority);
        """)
    return db


def add_job(db, spec, priority):
    import hashlib

    key = hashlib.sha256(canonical(spec)).hexdigest()[:24]
    db.execute(
        "INSERT OR IGNORE INTO jobs(id,spec,priority) VALUES (?,?,?)",
        (key, json.dumps(spec, sort_keys=True), priority),
    )
    return key


def initialise(root):
    guard(root, force=True)
    for directory in ("metadata", "logs", "consensus", "policy_expectations"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    with lock(root / "metadata/WORKER.lock"):
        config_path = root / "metadata/ARCHIVE.json"
        if config_path.exists():
            raise FileExistsError(
                "Archive already initialized; use run/start/status/verify"
            )
        snapshot = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        cutoff = datetime.now(timezone.utc).date().isoformat()
        config = {
            "schema": "economic_releases.archive.v1",
            "snapshot": snapshot,
            "created_at_utc": utc(),
            "observation_and_vintage_cutoff": cutoff,
            "root": str(root),
            "series": [
                dict(
                    zip(
                        (
                            "id",
                            "folder",
                            "description",
                            "source",
                            "frequency",
                            "adjustment",
                        ),
                        row,
                        strict=True,
                    )
                )
                for row in SERIES
            ],
            "vintage_selection": "Every vintage advertised by the public ALFRED form up to the cutoff, in batches of at most 400",
            "value_policy": "Original index levels and source strings; retain missing values; no fill, rebase, splice or substitution",
            "clock_policy": "Observation period, vintage validity dates, publisher timestamps and local capture times are distinct",
            "historical_metadata_policy": "Each ALFRED ZIP README is required; historical names, units, bases and definitions can change",
            "point_in_time_authority": "Date-level ALFRED vintage evidence, not certified intraday availability",
            "calendar_authority": "Captured schedules are known locally at capture time, not retrospectively at all earlier dates",
            "scope": "14 explicit series, their available ALFRED vintages, official calendars and linked BLS release archives",
            "original_iqfeed_archive": "../iqfeed and ../metadata; unchanged by this utility",
        }
        db = database(root)
        for series, folder, *_ in SERIES:
            add_job(
                db,
                {
                    "kind": "current",
                    "series": series,
                    "folder": f"current_vintage/{folder}/{series}",
                    "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?"
                    + urlencode({"id": series, "cosd": "1776-07-04", "coed": cutoff}),
                },
                0,
            )
            add_job(
                db,
                {
                    "kind": "series_metadata",
                    "series": series,
                    "folder": f"vintages/{folder}/{series}/metadata",
                    "url": f"https://alfred.stlouisfed.org/series?seid={series}",
                },
                0,
            )
            add_job(
                db,
                {
                    "kind": "vintage_form",
                    "series": series,
                    "folder": f"vintages/{folder}/{series}",
                    "url": f"https://alfred.stlouisfed.org/series/downloaddata?seid={series}",
                },
                1,
            )
        for label, folder, url, parser in DOCUMENTS:
            add_job(
                db,
                {
                    "kind": "document",
                    "label": label,
                    "folder": folder,
                    "url": url,
                    "parser": parser,
                },
                1,
            )
        db.commit()
        config["initial_jobs"] = db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        atomic_json(config_path, config)
        atomic_json(
            root / "consensus/ACCESS_STATUS.json",
            {
                "status": "NOT_DOWNLOADED_REQUIRES_AUTHORIZED_CALENDAR_ACCESS",
                "reason": "No Trading Economics credential was configured in this task; public documentation is not consensus data.",
                "needed": "Timestamped pre-release consensus and revision history; units, adjustment and reference period must match actuals",
                "actual_minus_consensus": "NOT_COMPUTED; missing forecasts are not filled or inferred",
            },
        )
        atomic_json(
            root / "policy_expectations/ACCESS_STATUS.json",
            {
                "dated_futures": "Already in the separate IQFeed acquisition catalogue under ../iqfeed/rates/",
                "fedwatch_probabilities": "NOT_DOWNLOADED_OR_DERIVED; methodology document only",
                "reason": "Raw futures prices are not themselves FOMC outcome probabilities; no new paid API access purchased",
            },
        )
        with (root / "README.md").open("xb") as out:
            out.write(Path(__file__).with_name("README.md").read_bytes())
        report = report_status(root, db, "QUEUED")
        db.close()
        return report


def persist(root, relative, body):
    target = local_path(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        with gzip.open(target, "rb") as existing:
            if existing.read() != body:
                raise ValueError("Immutable derived artifact would change")
    else:
        temp = target.with_name(target.name + "." + uuid.uuid4().hex + ".part")
        with temp.open("xb") as output:
            with gzip.GzipFile(
                fileobj=output, mode="wb", filename="", mtime=0
            ) as zipped:
                zipped.write(body)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, target)
    return {"file": str(target.relative_to(root)), "sha256": sha(target)}


def csv_bytes(header, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return output.getvalue().encode()


def validate_html(body):
    lower = body[:20000].lower()
    if b"<html" not in lower and b"<!doctype html" not in lower:
        raise ValueError("Expected an HTML source document")
    if any(
        marker in lower
        for marker in (
            b"<title>access denied",
            b"<title>just a moment",
            b"<title>forbidden",
        )
    ):
        raise ValueError("Access-control page is not source data")


def execute_job(root, db, fetcher, job, config, run_id):
    spec = json.loads(job["spec"])
    key = job["id"]
    label = spec.get("series", spec.get("label", "source")) + "_" + spec["kind"]
    if spec["kind"] == "vintage_zip":
        label += "_" + spec["vintages"][0] + "_" + spec["vintages"][-1]
    receipt = fetcher.fetch(
        spec["url"], spec["folder"], label, spec.get("form"), timeout=90
    )
    attempts = [receipt["receipt_file"]]
    if receipt["status"] == "FAILED":
        receipt = fetcher.fetch(
            spec["url"],
            spec["folder"],
            label + "__transport_retry",
            spec.get("form"),
            timeout=90,
        )
        attempts.append(receipt["receipt_file"])
    report = {
        "job_id": key,
        "spec": spec,
        "run_id": run_id,
        "request_receipts": attempts,
        "completed_at_utc": utc(),
        "artifacts": [],
        "rows": 0,
    }
    if receipt["status"] != "DOWNLOADED":
        report.update(
            state="BLOCKED_HTTP"
            if receipt["http_status"] in (401, 403, 429)
            else "FAILED_HTTP",
            error=f"HTTP {receipt['http_status']}: {receipt['error']}",
        )
        return report
    body = fetcher.body(receipt)
    base = f"{spec['folder']}/{config['snapshot']}/{key}"
    try:
        if spec["kind"] == "current":
            rows, stats = current_csv(
                body, spec["series"], config["observation_and_vintage_cutoff"]
            )
            report.update(stats)
            report["artifacts"].append(
                persist(
                    root,
                    base + ".observations.csv.gz",
                    csv_bytes(("observation_date", "value"), rows),
                )
            )
            report["vintage_policy"] = (
                "CURRENT_AT_CAPTURE_NOT_HISTORICAL_RELEASE_VALUES"
            )
        elif spec["kind"] == "vintage_form":
            info = vintage_form(body, config["observation_and_vintage_cutoff"])
            report.update(
                first_vintage=info["vintages"][0],
                last_vintage=info["vintages"][-1],
                advertised_vintages=len(info["vintages"]),
            )
            report["artifacts"].append(
                persist(
                    root,
                    base + ".vintage_dates.csv.gz",
                    csv_bytes(("vintage_date",), ((v,) for v in info["vintages"])),
                )
            )
            for index in range(0, len(info["vintages"]), 400):
                dates = info["vintages"][index : index + 400]
                form = {
                    "form[units]": "lin",
                    "form[obs_start_date]": info["begin"],
                    "form[obs_end_date]": info["end"],
                    "form[selected_vintage_dates][]": dates,
                    "form[entered_vintage_dates]": "",
                    "form[file_type]": "1",
                    "form[file_format]": "csv",
                    "form[download_data]": "",
                }
                add_job(
                    db,
                    {
                        "kind": "vintage_zip",
                        "series": spec["series"],
                        "folder": spec["folder"] + "/intervals",
                        "url": spec["url"],
                        "form": form,
                        "vintages": dates,
                    },
                    2,
                )
        elif spec["kind"] == "vintage_zip":
            values, notes, stats = vintage_zip(body, spec["series"], spec["vintages"])
            report.update(stats)
            report["artifacts"].append(
                persist(root, base + ".intervals.csv.gz", values)
            )
            report["artifacts"].append(
                persist(root, base + ".source_README.txt.gz", notes)
            )
        elif spec["kind"] == "series_metadata":
            validate_html(body)
            if spec["series"].encode() not in body:
                raise ValueError("Series metadata identity mismatch")
            report["metadata_policy"] = (
                "Retained source histories of names, units, base years and definitions; consult before joining vintages"
            )
        elif spec.get("parser") == "ics":
            events = calendar_ics(body)
            report["events"] = len(events)
            report["artifacts"].append(
                persist(
                    root,
                    base + ".events.json.gz",
                    canonical(
                        {
                            "captured_at_utc": receipt["completed_at_utc"],
                            "events": events,
                        }
                    ),
                )
            )
        elif spec.get("parser") == "text":
            if not body.strip() or b"<html" in body[:2000].lower():
                raise ValueError("Expected a plain-text release document")
        else:
            validate_html(body)
            if spec.get("parser") == "bls_index":
                releases = bls_archive_links(
                    body, spec["url"], config["observation_and_vintage_cutoff"]
                )
                if not releases:
                    raise ValueError(
                        "No dated release links found in BLS archive index"
                    )
                report["discovered_release_documents"] = len(releases)
                for release in releases:
                    add_job(
                        db,
                        {
                            "kind": "document",
                            "label": release["release_type"]
                            + "_"
                            + release["filename_date"],
                            "url": release["url"],
                            "folder": f"release_documents/bls/{release['release_type']}",
                            "parser": "text"
                            if release["url"].endswith(".txt")
                            else "html",
                            "source_filename_date": release["filename_date"],
                            "publication_time": "NOT_INFERRED_FROM_FILENAME",
                        },
                        3,
                    )
        report["state"] = "COMPLETE"
        report["verification"] = (
            "SOURCE_HASH_AND_FORMAT_PASS_NOT_ECONOMIC_OR_PIT_COMPLETENESS"
        )
    except (
        ValueError,
        KeyError,
        UnicodeError,
        OSError,
        zipfile.BadZipFile,
        csv.Error,
    ) as exc:
        report.update(state="FAILED_VALIDATION", error=f"{type(exc).__name__}: {exc}")
    return report


def report_status(root, db, state, **extra):
    counts = dict(
        db.execute("SELECT state,COUNT(*) FROM jobs GROUP BY state").fetchall()
    )
    complete = [
        json.loads(row[0])
        for row in db.execute("SELECT report FROM jobs WHERE state='COMPLETE'")
    ]
    current = [r for r in complete if r["spec"]["kind"] == "current"]
    vintage = [r for r in complete if r["spec"]["kind"] == "vintage_zip"]
    forms = [r for r in complete if r["spec"]["kind"] == "vintage_form"]
    blockers = [
        json.loads(row[0])
        for row in db.execute(
            "SELECT report FROM jobs WHERE state LIKE 'FAILED%' OR state LIKE 'BLOCKED%'"
        )
    ]
    report = {
        "schema": "economic_releases.status.v1",
        "state": state,
        "pid": os.getpid(),
        "updated_at_utc": utc(),
        "counts": counts,
        "jobs": sum(counts.values()),
        "current_series_complete": len(current),
        "current_observation_rows": sum(r["rows"] for r in current),
        "vintage_download_chunks_complete": len(vintage),
        "vintage_interval_rows_in_chunks": sum(r["rows"] for r in vintage),
        "vintage_interval_rows_warning": "Identical validity intervals can recur across chunks; not a unique observation count",
        "advertised_vintage_dates_across_series": sum(
            r["advertised_vintages"] for r in forms
        ),
        "vintage_dates_requested_in_completed_chunks": sum(
            r["requested_vintages"] for r in vintage
        ),
        "blocked_or_failed": [
            {"spec": r["spec"], "error": r["error"]} for r in blockers
        ],
        "consensus": "NOT_DOWNLOADED_REQUIRES_AUTHORIZED_ACCESS",
        "intraday_point_in_time_and_calendar_completeness": "NOT_ESTABLISHED",
        **extra,
    }
    atomic_json(root / "metadata/STATUS.json", report)
    return report


def export(root, db):
    entries = []
    for row in db.execute("SELECT * FROM jobs ORDER BY priority,id"):
        entries.append(
            {
                "job_id": row["id"],
                "state": row["state"],
                "spec": json.loads(row["spec"]),
                "report": json.loads(row["report"]) if row["report"] else None,
            }
        )
    atomic_json(root / "metadata/MANIFEST.json", entries)
    index = []
    by_series = {
        (e["spec"].get("series"), e["spec"]["kind"]): e
        for e in entries
        if e["spec"]["kind"] in ("current", "vintage_form")
    }
    for series, folder, description, source, frequency, adjustment in SERIES:
        current = by_series.get((series, "current"), {})
        vintage = by_series.get((series, "vintage_form"), {})
        r = current.get("report") or {}
        v = vintage.get("report") or {}
        index.append(
            (
                series,
                description,
                source,
                frequency,
                adjustment,
                current.get("state"),
                r.get("rows", 0),
                r.get("first_observation"),
                r.get("last_observation"),
                v.get("first_vintage"),
                v.get("last_vintage"),
                v.get("advertised_vintages", 0),
                folder,
            )
        )
    content = csv_bytes(
        (
            "series_id",
            "description",
            "original_publisher",
            "frequency",
            "adjustment",
            "current_state",
            "current_rows",
            "first_observation",
            "last_observation",
            "first_alfred_vintage",
            "last_alfred_vintage",
            "advertised_vintages",
            "category",
        ),
        index,
    )
    temp = root / "metadata/SERIES_INDEX.csv.part"
    with temp.open("wb") as stream:
        stream.write(content)
    os.replace(temp, root / "metadata/SERIES_INDEX.csv")


def split_failed_vintages(root):
    """Explicit recovery of 5xx batch failures; never retry access denials."""
    guard(root, force=True)
    recovered = []
    with lock(root / "metadata/WORKER.lock"):
        db = database(root)
        for row in db.execute(
            "SELECT * FROM jobs WHERE state='FAILED_HTTP'"
        ).fetchall():
            spec = json.loads(row["spec"])
            if spec["kind"] != "vintage_zip" or len(spec["vintages"]) < 2:
                continue
            report = json.loads(row["report"])
            receipt = json.loads(
                local_path(root, report["request_receipts"][-1]).read_text()
            )
            verify_http(root, receipt)
            if receipt.get("http_status") not in (500, 502, 503, 504):
                continue
            dates = spec["vintages"]
            pivot = len(dates) // 2
            children = []
            for part in (dates[:pivot], dates[pivot:]):
                child = {
                    **spec,
                    "form": {**spec["form"], "form[selected_vintage_dates][]": part},
                    "vintages": part,
                    "split_from_job": row["id"],
                }
                children.append(add_job(db, child, row["priority"]))
            report.update(
                previous_state=report["state"],
                state="SPLIT_HTTP_FAILURE",
                split_at_utc=utc(),
                split_children=children,
                recovery_policy="Exact disjoint vintage subsets; original error and receipts retained",
            )
            db.execute(
                "UPDATE jobs SET state=?,report=? WHERE id=?",
                (report["state"], json.dumps(report), row["id"]),
            )
            recovered.append(row["id"])
        db.commit()
        report_status(
            root, db, "RECOVERY_QUEUED" if recovered else "NO_ELIGIBLE_RECOVERY"
        )
        export(root, db)
        db.close()
    return {"split_parent_jobs": recovered, "children_queued": 2 * len(recovered)}


def run(root, max_jobs=0):
    global STOP
    STOP = False
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: globals().__setitem__("STOP", True))
    guard(root, force=True)
    config = json.loads((root / "metadata/ARCHIVE.json").read_text())
    run_id = uuid.uuid4().hex
    binding = {
        "run_id": run_id,
        "started_at_utc": utc(),
        "code_sha256": {p.name: sha(p) for p in Path(__file__).parent.glob("*.py")},
    }
    with lock(root / "metadata/WORKER.lock"):
        atomic_json(root / f"metadata/RUN_{run_id}.json", binding)
        db = database(root)
        db.execute("UPDATE jobs SET state='PENDING' WHERE state='RUNNING'")
        db.commit()
        fetcher = Fetcher(root, config["snapshot"], lambda: check(root))
        completed = 0
        last_export = 0.0
        try:
            while not STOP and not (root / "metadata/STOP").exists():
                job = db.execute(
                    "SELECT * FROM jobs WHERE state='PENDING' ORDER BY priority,rowid LIMIT 1"
                ).fetchone()
                if job is None:
                    break
                check(root, force=True)
                db.execute("UPDATE jobs SET state='RUNNING' WHERE id=?", (job["id"],))
                db.commit()
                report_status(root, db, "DOWNLOADING", current=json.loads(job["spec"]))
                result = execute_job(root, db, fetcher, job, config, run_id)
                db.execute(
                    "UPDATE jobs SET state=?,report=? WHERE id=?",
                    (result["state"], json.dumps(result), job["id"]),
                )
                db.commit()
                print(
                    json.dumps(
                        {
                            "at": utc(),
                            "kind": result["spec"]["kind"],
                            "series": result["spec"].get(
                                "series", result["spec"].get("label")
                            ),
                            "state": result["state"],
                            "rows": result["rows"],
                            "error": result.get("error"),
                        }
                    ),
                    flush=True,
                )
                completed += 1
                if time.monotonic() - last_export > 60:
                    export(root, db)
                    last_export = time.monotonic()
                if max_jobs and completed >= max_jobs:
                    break
        except Exception as exc:
            guard(root, reserve=0)
            report_status(
                root, db, "PAUSED_ERROR", error=f"{type(exc).__name__}: {exc}"
            )
            export(root, db)
            raise
        pending = db.execute(
            "SELECT COUNT(*) FROM jobs WHERE state IN ('PENDING','RUNNING')"
        ).fetchone()[0]
        result = report_status(
            root,
            db,
            "PAUSED" if pending else "FINISHED_WITH_RECORDED_SOURCE_LIMITATIONS",
        )
        export(root, db)
        db.close()
        return result


def verify(root):
    guard(root, force=True, reserve=0)
    sources = outputs = 0
    config = json.loads((root / "metadata/ARCHIVE.json").read_text())
    advertised, completed = {}, {}
    for path in root.rglob("*.receipt.json"):
        verify_http(root, json.loads(path.read_text()))
        sources += 1
    db = database(root, readonly=True)
    for row in db.execute("SELECT report FROM jobs WHERE state='COMPLETE'"):
        result = json.loads(row[0])
        derived = []
        for artifact in result["artifacts"]:
            target = local_path(root, artifact["file"])
            if sha(target) != artifact["sha256"]:
                raise ValueError("Derived output hash mismatch")
            with gzip.open(target, "rb") as stream:
                derived.append(stream.read())
            outputs += 1
        receipt = json.loads(
            local_path(root, result["request_receipts"][-1]).read_text()
        )
        with gzip.open(local_path(root, receipt["raw_file"]), "rb") as stream:
            body = stream.read()
        if result["spec"]["kind"] == "current":
            rows, stats = current_csv(
                body, result["spec"]["series"], config["observation_and_vintage_cutoff"]
            )
            if stats["rows"] != result["rows"]:
                raise ValueError("Current source row-count mismatch")
            if derived != [csv_bytes(("observation_date", "value"), rows)]:
                raise ValueError("Current derived values differ from source")
        elif result["spec"]["kind"] == "vintage_zip":
            values, notes, stats = vintage_zip(
                body, result["spec"]["series"], result["spec"]["vintages"]
            )
            if stats["rows"] != result["rows"]:
                raise ValueError("Vintage source row-count mismatch")
            if derived != [values, notes]:
                raise ValueError(
                    "Vintage derived values or metadata differ from source"
                )
            completed.setdefault(result["spec"]["series"], []).extend(
                result["spec"]["vintages"]
            )
        elif result["spec"]["kind"] == "vintage_form":
            info = vintage_form(body, config["observation_and_vintage_cutoff"])
            advertised[result["spec"]["series"]] = info["vintages"]
            if derived != [
                csv_bytes(("vintage_date",), ((v,) for v in info["vintages"]))
            ]:
                raise ValueError("Derived vintage dates differ from source form")
        elif result["spec"].get("parser") == "ics":
            expected = canonical(
                {
                    "captured_at_utc": receipt["completed_at_utc"],
                    "events": calendar_ics(body),
                }
            )
            if derived != [expected]:
                raise ValueError("Derived calendar events differ from source")
    db.close()
    coverage = {}
    for series, dates in advertised.items():
        requested = completed.get(series, [])
        if len(requested) != len(set(requested)) or set(requested) - set(dates):
            raise ValueError("Duplicate or unadvertised completed vintage selections")
        missing = sorted(set(dates) - set(requested))
        coverage[series] = {
            "advertised": len(dates),
            "downloaded_and_acknowledged": len(requested),
            "missing_vintage_dates": missing,
        }
    report = {
        "status": "PASS",
        "at_utc": utc(),
        "verified_http_responses": sources,
        "verified_derived_artifacts": outputs,
        "vintage_coverage": coverage,
        "all_advertised_vintages_downloaded": bool(coverage)
        and all(not v["missing_vintage_dates"] for v in coverage.values()),
        "meaning": "Hashes, gzip/ZIP integrity, source schemas, row counts, exact source-to-derived bytes and requested vintage acknowledgements; not complete intraday PIT authority",
    }
    atomic_json(
        root
        / (
            "metadata/VERIFICATION_"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + ".json"
        ),
        report,
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("init", "run", "start", "status", "verify", "split-failed-vintages"),
    )
    parser.add_argument("--max-jobs", type=int, default=0)
    args = parser.parse_args(argv)
    root = resolve_source_location("macroeconomic_releases")
    if args.action == "init":
        result = initialise(root)
    elif args.action == "run":
        result = run(root, args.max_jobs)
    elif args.action == "verify":
        result = verify(root)
    elif args.action == "split-failed-vintages":
        result = split_failed_vintages(root)
    elif args.action == "start":
        guard(root, force=True)
        with lock(root / "metadata/WORKER.lock"):
            pass
        with (root / "logs/download.log").open("ab", buffering=0) as log:
            proc = subprocess.Popen(
                [sys.executable, "-B", "-m", MODULE, "run"],
                cwd=Path(__file__).resolve().parents[2],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        result = {
            "started_pid": proc.pid,
            "status_file": str(root / "metadata/STATUS.json"),
        }
    else:
        guard(root, reserve=0)
        result = json.loads((root / "metadata/STATUS.json").read_text())
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
