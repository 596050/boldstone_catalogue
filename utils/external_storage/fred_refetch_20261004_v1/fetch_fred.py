#!/usr/bin/env python3
"""Re-fetch FRED observations and upload them to the Hetzner Storage Box.

Replaces the toshiba-fred-7887b862 batch. That batch is 535,143 files in one
exFAT directory with a 67.6 MB directory table; measured cost to read it is
4.3-10.1 s per file (~62 days), because exFAT has no directory index and every
open-by-name linearly scans the table. The content is public FRED API data, so
re-fetching is far cheaper than copying.

Output is consolidated gzipped JSONL shards, not one file per series, so the
upload is a handful of large objects rather than half a million small ones.
Resumable: completed shards are recorded, and an interrupted shard resumes from
the series already written to its .part file.
"""
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SHARDS = HERE / "shards"
STATE = HERE / "STATE.json"
LOG = HERE / "errors.jsonl"

SHARD_COUNT = 128
REQ_PER_MIN = 110          # FRED documents 120/min; stay under it.
UPLOAD_EVERY = 16          # upload after this many completed shards
TIMEOUT = 30
MAX_TRIES = 5
GROUP = "fred-refetch-20261004"
PROFILE = "market-data-fred"   # own operation.lock; research iex_* jobs hold market-data's
ENDPOINT = "https://api.stlouisfed.org/fred/series/observations"


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def api_key():
    text = (ROOT / ".env").read_text()
    m = re.search(r"^FRED_API_KEY\s*=\s*(.*)$", text, re.M)
    if not m:
        raise SystemExit("FRED_API_KEY is not set in .env")
    key = m.group(1).strip().strip('"').strip("'")
    if not re.fullmatch(r"[0-9a-z]{32}", key):
        raise SystemExit("FRED_API_KEY does not look like a FRED key")
    return key


def series_ids():
    ids = json.loads((HERE / "SERIES_IDS.json").read_text())
    extra = (HERE / "SERIES_IDS_EXTRA.json")
    if extra.exists():
        ids = sorted(set(ids) | set(json.loads(extra.read_text())))
    return ids


def shard_of(ids, index):
    step = (len(ids) + SHARD_COUNT - 1) // SHARD_COUNT
    return ids[index * step:(index + 1) * step]


def load_state(total_shards):
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"status": "RUNNING", "started_at": now(), "updated_at": now(),
            "total_shards": total_shards, "completed_shards": [],
            "series_done": 0, "series_error": 0, "req_per_min": REQ_PER_MIN,
            "current_shard": None, "error": None}


def save_state(state):
    state["updated_at"] = now()
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE)


def note_error(series, kind, detail):
    with LOG.open("a") as fh:
        fh.write(json.dumps({"at": now(), "series": series,
                             "kind": kind, "detail": str(detail)[:300]}) + "\n")


class Limiter:
    """Simple pacing with backoff when FRED pushes back."""

    def __init__(self, per_min):
        self.interval = 60.0 / per_min
        self.last = 0.0

    def wait(self):
        gap = time.time() - self.last
        if gap < self.interval:
            time.sleep(self.interval - gap)
        self.last = time.time()

    def slow_down(self):
        self.interval = min(self.interval * 1.5, 5.0)

    def speed_up(self):
        self.interval = max(self.interval * 0.95, 60.0 / 120)


def fetch(series, key, limiter):
    """Return the parsed response, or None if FRED rejects this series."""
    params = urllib.parse.urlencode({"series_id": series, "api_key": key,
                                     "file_type": "json"})
    for attempt in range(MAX_TRIES):
        limiter.wait()
        try:
            with urllib.request.urlopen(ENDPOINT + "?" + params, timeout=TIMEOUT) as r:
                body = json.load(r)
            limiter.speed_up()
            return body
        except urllib.error.HTTPError as e:
            if e.code == 429:
                limiter.slow_down()
                time.sleep(30 + random.uniform(0, 15))
                continue
            if e.code == 400:
                note_error(series, "rejected", e.read()[:200])
                return None
            if e.code >= 500:
                time.sleep(2 ** attempt + random.uniform(0, 1))
                continue
            note_error(series, "http_%d" % e.code, e.read()[:200])
            return None
        except Exception as e:
            if attempt == MAX_TRIES - 1:
                raise
            time.sleep(2 ** attempt + random.uniform(0, 1))
    raise RuntimeError("exhausted retries for " + series)


def already_written(part):
    """Series ids already present in an interrupted shard."""
    done = set()
    if not part.exists():
        return done
    try:
        with gzip.open(part, "rt") as fh:
            for line in fh:
                try:
                    done.add(json.loads(line)["series_id"])
                except Exception:
                    break          # truncated final line
    except (OSError, EOFError):
        pass
    return done


def upload(state):
    cmd = [sys.executable, str(ROOT / "utils/external_storage/hetzner/storage_box.py"),
           "--profile", PROFILE, "upload", "--group", GROUP, str(SHARDS)]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError("upload failed (exit %d): %s"
                           % (result.returncode, (result.stderr or "")[-400:]))
    print(json.dumps({"at": now(), "event": "uploaded",
                      "completed_shards": len(state["completed_shards"])}), flush=True)


def main():
    SHARDS.mkdir(exist_ok=True)
    key = api_key()
    ids = series_ids()
    state = load_state(SHARD_COUNT)
    state["status"] = "RUNNING"
    state["total_series"] = len(ids)
    limiter = Limiter(state.get("req_per_min") or REQ_PER_MIN)
    done_shards = set(state["completed_shards"])
    since_upload = 0

    for index in range(SHARD_COUNT):
        if index in done_shards:
            continue
        members = shard_of(ids, index)
        if not members:
            continue
        final = SHARDS / ("fred_obs_shard_%03d.jsonl.gz" % index)
        part = SHARDS / ("fred_obs_shard_%03d.jsonl.gz.part" % index)
        if final.exists():
            state["completed_shards"].append(index)
            save_state(state)
            continue

        skip = already_written(part)
        if skip:
            # Rewrite cleanly, keeping what was already fetched.
            kept = []
            with gzip.open(part, "rt") as fh:
                for line in fh:
                    try:
                        kept.append(json.loads(line))
                    except Exception:
                        break
            with gzip.open(part, "wt") as fh:
                for row in kept:
                    fh.write(json.dumps(row, separators=(",", ":")) + "\n")
            skip = {r["series_id"] for r in kept}

        state["current_shard"] = index
        save_state(state)
        print(json.dumps({"at": now(), "event": "shard_start", "shard": index,
                          "series": len(members), "resumed_from": len(skip)}), flush=True)

        with gzip.open(part, "at") as fh:
            for series in members:
                if series in skip:
                    continue
                body = fetch(series, key, limiter)
                if body is None:
                    state["series_error"] += 1
                else:
                    fh.write(json.dumps({"series_id": series, "fetched_at": now(),
                                         "response": body},
                                        separators=(",", ":")) + "\n")
                    state["series_done"] += 1
                if state["series_done"] % 500 == 0:
                    fh.flush()
                    state["req_per_min"] = round(60.0 / limiter.interval, 1)
                    save_state(state)

        part.replace(final)
        state["completed_shards"].append(index)
        state["current_shard"] = None
        save_state(state)
        since_upload += 1
        print(json.dumps({"at": now(), "event": "shard_done", "shard": index,
                          "bytes": final.stat().st_size,
                          "series_done": state["series_done"],
                          "series_error": state["series_error"]}), flush=True)

        if since_upload >= UPLOAD_EVERY:
            upload(state)
            since_upload = 0

    upload(state)
    state["status"] = "COMPLETE"
    save_state(state)
    print(json.dumps({"status": "COMPLETE", "series_done": state["series_done"],
                      "series_error": state["series_error"]}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if STATE.exists():
            s = json.loads(STATE.read_text())
            s["status"] = "STOPPED_INCOMPLETE"
            s["error"] = "%s: %s" % (type(e).__name__, e)
            s["updated_at"] = now()
            STATE.write_text(json.dumps(s, indent=2))
        print("Error: %s: %s" % (type(e).__name__, e), file=sys.stderr)
        raise SystemExit(1)
