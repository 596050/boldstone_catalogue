#!/usr/bin/env python3
"""Refresh the local IQFeed marketmaker-core 1-minute cache."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from utils.ibkr.common import REPO_ROOT
from utils.data_paths import CONFIGURED_DATA_ROOT


IQFEED_ROOT = REPO_ROOT
DEFAULT_DOWNLOADER = REPO_ROOT / "utils/iqfeed/downloader.py"
DEFAULT_UNIVERSE_CSV = CONFIGURED_DATA_ROOT / "iqfeed_downloads_v2/marketmaker_core_symbols.csv"
DEFAULT_OUTPUT_DIR = CONFIGURED_DATA_ROOT / "iqfeed_downloads_v2/marketmaker_core_1min"
DEFAULT_MANIFEST_CSV = DEFAULT_OUTPUT_DIR / "manifest.csv"
DEFAULT_OUTPUT_JSON = CONFIGURED_DATA_ROOT / "ibkr" / "iqfeed_marketmaker_core_1min_refresh_report.json"


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"cannot JSON encode {type(value)!r}")


def default_begin(now: dt.datetime | None = None) -> str:
    """Return a conservative prior-day begin timestamp for the IQFeed request."""
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=dt.timezone.utc)
    prior_day = current.astimezone(dt.timezone.utc).date() - dt.timedelta(days=1)
    return f"{prior_day:%Y%m%d} 000000"


def dedupe_manifest(path: Path) -> dict[str, Any]:
    """Keep the newest manifest row per symbol after the downloader appends."""
    manifest = Path(path)
    if not manifest.exists():
        return {
            "manifest": manifest,
            "exists": False,
            "rows": 0,
            "statuses": [],
            "latest_completed_at": "",
        }

    with manifest.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return {
            "manifest": manifest,
            "exists": True,
            "rows": 0,
            "statuses": [],
            "latest_completed_at": "",
        }

    latest: dict[str, dict[str, str]] = {}
    order: list[str] = []
    for row in rows:
        key = (row.get("symbol") or row.get("source_symbol") or "").upper()
        if not key:
            continue
        if key not in latest:
            order.append(key)
        previous = latest.get(key)
        if previous is None or (row.get("completed_at") or "") >= (previous.get("completed_at") or ""):
            latest[key] = row

    with manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for key in order:
            if key in latest:
                writer.writerow(latest[key])

    row_counts = []
    for row in latest.values():
        try:
            row_counts.append(int(row.get("rows") or 0))
        except ValueError:
            row_counts.append(0)
    return {
        "manifest": manifest,
        "exists": True,
        "rows": len(latest),
        "statuses": sorted({row.get("status", "") for row in latest.values()}),
        "min_rows": min(row_counts) if row_counts else 0,
        "max_rows": max(row_counts) if row_counts else 0,
        "latest_completed_at": max((row.get("completed_at") or "") for row in latest.values()),
    }


def _path_arg(path: Path, root: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(path)


def build_download_command(args: argparse.Namespace) -> list[str]:
    begin = str(args.begin or default_begin())
    root = Path(args.iqfeed_root)
    launcher = (
        [sys.executable, "-m", "utils.iqfeed.downloader"]
        if Path(args.downloader).resolve() == DEFAULT_DOWNLOADER.resolve()
        else [sys.executable, str(args.downloader)]
    )
    return launcher + [
        "download-intervals",
        "--universe-file",
        _path_arg(Path(args.universe_csv), root),
        "--output-dir",
        _path_arg(Path(args.manifest_csv).parent, root),
        "--begin",
        begin,
        "--interval-seconds",
        str(int(args.interval_seconds)),
        "--request-delay",
        str(float(args.request_delay)),
        "--retries",
        str(int(args.retries)),
        "--connect-retries",
        str(int(args.connect_retries)),
        "--connect-retry-delay",
        str(float(args.connect_retry_delay)),
        "--ensure-lookup",
        "--keep-wine",
    ]


def refresh_iqfeed_marketmaker_core(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.iqfeed_root)
    downloader = Path(args.downloader)
    if not root.exists():
        raise FileNotFoundError(f"IQFeed runtime root is missing: {root}")
    if not downloader.exists():
        raise FileNotFoundError(f"IQFeed downloader is missing: {downloader}")
    if not Path(args.universe_csv).exists():
        raise FileNotFoundError(f"IQFeed universe is missing: {args.universe_csv}")

    command = build_download_command(args)
    proc = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)

    manifest_summary = dedupe_manifest(Path(args.manifest_csv)) if proc.returncode == 0 else {}
    return {
        "schema": "iqfeed_marketmaker_core_1min_refresh_report.v1",
        "iqfeed_root": root,
        "command": command,
        "returncode": int(proc.returncode),
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-4000:],
        "manifest_summary": manifest_summary,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iqfeed-root", type=Path, default=IQFEED_ROOT)
    parser.add_argument("--downloader", type=Path, default=DEFAULT_DOWNLOADER)
    parser.add_argument("--universe-csv", type=Path, default=DEFAULT_UNIVERSE_CSV)
    parser.add_argument("--manifest-csv", type=Path, default=DEFAULT_MANIFEST_CSV)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--begin", default="", help="IQFeed begin timestamp, e.g. '20260629 000000'.")
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--request-delay", type=float, default=0.05)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--connect-retries", type=int, default=2)
    parser.add_argument("--connect-retry-delay", type=float, default=3.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = refresh_iqfeed_marketmaker_core(args)
    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n")
    print(f"wrote IQFeed refresh report: {output_json}")
    return int(payload.get("returncode") or 0)


if __name__ == "__main__":
    raise SystemExit(main())
