"""Strict source-format checks; no resampling, filling, rebasing or clock invention."""

from __future__ import annotations

import bisect
import csv
import io
import re
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo


def iso_day(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"Non-ISO observation or vintage date: {value!r}")
    date.fromisoformat(value)
    return value


def missing_value(value):
    if value in ("", "."):
        return True
    try:
        if not Decimal(value).is_finite():
            raise ValueError("Nonfinite observation")
    except InvalidOperation as exc:
        raise ValueError("Nonnumeric observation") from exc
    return False


def current_csv(body, series, cutoff):
    reader = csv.reader(io.StringIO(body.decode("utf-8-sig")))
    header = next(reader, [])
    if header not in (["observation_date", series], ["DATE", series]):
        raise ValueError(f"Unexpected FRED CSV header: {header[:3]}")
    rows = []
    missing = 0
    previous = ""
    for fields in reader:
        if len(fields) != 2:
            raise ValueError("Wrong FRED field count")
        stamp, value = fields
        iso_day(stamp)
        if stamp <= previous or stamp > cutoff:
            raise ValueError("Non-increasing or outside-cutoff observation date")
        previous = stamp
        missing += missing_value(value)
        rows.append(fields)
    if not rows:
        raise ValueError("Empty FRED series is not a successful acquisition")
    return rows, {
        "rows": len(rows),
        "missing_values": missing,
        "first_observation": rows[0][0],
        "last_observation": rows[-1][0],
    }


class DownloadForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = {}
        self.vintages = []
        self.selected = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input":
            self.inputs[attrs.get("id", "")] = attrs.get("value", "")
        elif tag == "select":
            self.selected = attrs.get("id", "")
        elif tag == "option" and self.selected == "form_selected_vintage_dates":
            self.vintages.append(attrs.get("value", ""))

    def handle_endtag(self, tag):
        if tag == "select":
            self.selected = ""


def vintage_form(body, cutoff):
    parser = DownloadForm()
    parser.feed(body.decode("utf-8"))
    begin = iso_day(parser.inputs.get("form_obs_start_date", ""))
    end = iso_day(parser.inputs.get("form_obs_end_date", ""))
    vintages = [iso_day(v) for v in parser.vintages if v <= cutoff]
    if not vintages or vintages != sorted(set(vintages)) or len(vintages) > 25000:
        raise ValueError("Invalid, empty or unexpectedly large ALFRED vintage list")
    return {"begin": begin, "end": min(end, cutoff), "vintages": vintages}


def vintage_zip(body, series, requested):
    requested = sorted(requested)
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        entries = archive.infolist()
        if len(entries) != 2 or sum(e.file_size for e in entries) > 512 * 1024**2:
            raise ValueError("Unexpected ALFRED ZIP size or entry count")
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or len(path.parts) != 1
                or entry.flag_bits & 1
            ):
                raise ValueError("Unsafe ALFRED ZIP member")
        if set(archive.namelist()) != {"README.txt", "obs._by_real-time_period.csv"}:
            raise ValueError("Unexpected ALFRED ZIP members")
        notes = archive.read("README.txt")
        csv_body = archive.read("obs._by_real-time_period.csv")
    notes_text = notes.decode("utf-8-sig")
    if f"Series ID: {series}\n" not in notes_text.replace("\r\n", "\n"):
        raise ValueError("ALFRED metadata series ID mismatch")
    if "Vintage Dates Specified:" not in notes_text:
        raise ValueError("ALFRED ZIP does not confirm its vintage selection")
    acknowledged = re.findall(
        r"\b\d{4}-\d{2}-\d{2}\b", notes_text.split("Vintage Dates Specified:", 1)[1]
    )
    if acknowledged != requested:
        raise ValueError(
            "ALFRED silently truncated or changed the requested vintage dates"
        )
    reader = csv.reader(io.StringIO(csv_body.decode("utf-8-sig")))
    expected = ["period_start_date", series, "realtime_start_date", "realtime_end_date"]
    if next(reader, []) != expected:
        raise ValueError("Unexpected ALFRED interval CSV header")
    count = missing = 0
    previous = None
    first_obs = last_obs = None
    for fields in reader:
        if len(fields) != 4:
            raise ValueError("Wrong ALFRED field count")
        observation, value, start, end = fields
        iso_day(observation)
        iso_day(start)
        if end not in ("", "."):
            iso_day(end)
            if end < start:
                raise ValueError("Reversed ALFRED validity interval")
        point = bisect.bisect_left(requested, start)
        if point == len(requested) or (end not in ("", ".") and requested[point] > end):
            raise ValueError("ALFRED interval does not intersect a requested vintage")
        key = (observation, start, end)
        if previous is not None and key <= previous:
            raise ValueError("Duplicate or non-increasing ALFRED interval identity")
        previous = key
        missing += missing_value(value)
        count += 1
        first_obs = first_obs or observation
        last_obs = observation
    if not count:
        raise ValueError("Empty ALFRED ZIP is not a successful acquisition")
    return (
        csv_body,
        notes,
        {
            "rows": count,
            "missing_values": missing,
            "first_observation": first_obs,
            "last_observation": last_obs,
            "requested_vintages": len(requested),
            "first_vintage": requested[0],
            "last_vintage": requested[-1],
            "clock_precision": "DAY_NOT_INTRADAY",
            "historical_metadata_in_readme": True,
        },
    )


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def bls_archive_links(body, page_url, cutoff):
    parser = Links()
    parser.feed(body.decode("utf-8", errors="replace"))
    found = {}
    for href in parser.hrefs:
        url = urljoin(page_url, href)
        parsed = urlsplit(url)
        match = re.fullmatch(
            r"/news\.release/archives/(cpi|ppi|empsit)_(\d{8})\.(htm|txt)", parsed.path
        )
        if parsed.scheme != "https" or parsed.netloc != "www.bls.gov" or not match:
            continue
        stamp = datetime.strptime(match[2], "%m%d%Y").date().isoformat()  # noqa: DTZ007 - source filename is a date, not a timestamp.
        if stamp <= cutoff:
            key = (match[1], stamp)
            if key not in found or match[3] == "htm":
                found[key] = {
                    "url": url,
                    "release_type": match[1],
                    "filename_date": stamp,
                }
    return [found[key] for key in sorted(found)]


def calendar_ics(body):
    text = body.decode("utf-8-sig").replace("\r\n", "\n")
    text = re.sub(r"\n[ \t]", "", text)
    if "BEGIN:VCALENDAR" not in text or "END:VCALENDAR" not in text:
        raise ValueError("Not an iCalendar document")
    events = []
    for block in re.findall(r"BEGIN:VEVENT\n(.*?)\nEND:VEVENT", text, re.DOTALL):
        fields = {}
        parameters = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            parts = key.split(";")
            fields[parts[0]] = value
            parameters[parts[0]] = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
        stamp = fields.get("DTSTART", "")
        zone = parameters.get("DTSTART", {}).get("TZID", "")
        instant = None
        precision = "DATE_ONLY"
        if "T" in stamp:
            dt = datetime.strptime(stamp.rstrip("Z"), "%Y%m%dT%H%M%S")  # noqa: DTZ007 - timezone attached only from explicit source metadata.
            if stamp.endswith("Z"):
                dt = dt.replace(tzinfo=timezone.utc)
            elif zone:
                dt = dt.replace(tzinfo=ZoneInfo(zone.strip('"')))
            else:
                raise ValueError("Floating calendar timestamp has no explicit timezone")
            instant = dt.astimezone(timezone.utc).isoformat()
            precision = "SOURCE_TIMESTAMP"
        elif not re.fullmatch(r"\d{8}", stamp):
            raise ValueError("Invalid calendar date")
        events.append(
            {
                "uid": fields.get("UID"),
                "summary": fields.get("SUMMARY"),
                "dtstart_original": stamp,
                "source_timezone": zone,
                "scheduled_at_utc": instant,
                "precision": precision,
                "status": fields.get("STATUS"),
                "source_fields": fields,
            }
        )
    if not events:
        raise ValueError("No calendar events returned")
    return events
