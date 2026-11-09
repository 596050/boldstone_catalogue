#!/usr/bin/env python3
"""Download raw IB historical bars to CSV files.

This is intentionally a data-export utility, not a backtest. It writes the raw
bars returned by IBKR before any bid/ask approximation or replay conversion.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from utils.ibkr.common import DEFAULT_HOST, DEFAULT_TWS_PAPER_PORT, REPO_ROOT, ensure_repo_root_on_path


ensure_repo_root_on_path()

from utils.trading.market_maker_config import DEFAULT_SETTINGS  # noqa: E402
from utils.data_paths import CONFIGURED_DATA_ROOT
from utils.data_paths import resolve_data_path


DEFAULT_STALE_AFTER_HOURS = 24.0


def _ensure_event_loop_for_ib_insync_import() -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def effective_stale_after_hours(stale_after_hours: float) -> float:
    """Return the freshness threshold, capped so files older than one day refetch."""
    requested = float(stale_after_hours)
    if not math.isfinite(requested):
        return DEFAULT_STALE_AFTER_HOURS
    return min(requested, DEFAULT_STALE_AFTER_HOURS)


def _slug(value: str) -> str:
    return "_".join(value.strip().split()).replace("/", "_").replace(":", "")


def _parse_symbols(value: str) -> list[str]:
    if value.strip().upper() == "ALL":
        return list(DEFAULT_SETTINGS)
    symbols = [part.strip().upper() for part in value.split(",") if part.strip()]
    if not symbols:
        raise argparse.ArgumentTypeError("provide comma-separated symbols or ALL")
    return symbols


def _date_to_text(value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _bar_sort_key(bar) -> tuple[float, str]:
    value = getattr(bar, "date", "")
    if isinstance(value, datetime):
        return value.timestamp(), ""
    return 0.0, str(value)


def _duration_days(value: str) -> int:
    parts = value.strip().split()
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("duration must look like '90 D'")
    amount = int(parts[0])
    unit = parts[1].upper()
    multipliers = {
        "D": 1,
        "W": 7,
        "M": 30,
        "Y": 365,
    }
    if unit not in multipliers:
        raise argparse.ArgumentTypeError("duration unit must be D, W, M, or Y")
    return amount * multipliers[unit]


def _parse_bar_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    # Epoch timestamps appear in a few exogenous CSVs. Treat 8-digit values as
    # yyyymmdd dates, not Unix seconds.
    if text.replace(".", "", 1).isdigit() and len(text.split(".", 1)[0]) != 8:
        try:
            parsed_epoch = float(text)
        except ValueError:
            parsed_epoch = -1.0
        if parsed_epoch > 0:
            try:
                return datetime.fromtimestamp(parsed_epoch, timezone.utc)
            except (OSError, OverflowError, ValueError):
                pass
    # Date-only daily bars represent the full trading date.  Use the next UTC
    # midnight as the freshness reference so they do not become stale at the
    # start of their own calendar day.
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            parsed_date = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            return parsed_date + timedelta(days=1)
        except ValueError:
            continue
    # Intraday bars written by this utility use ISO-8601, usually with an
    # exchange timezone offset.
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass
    return None


def _latest_csv_bar_time(
    path: Path,
    timestamp_columns: tuple[str, ...] = (
        "date",
        "datetime_utc",
        "downloaded_at_utc",
        "asof_utc",
        "timestamp",
    ),
) -> datetime | None:
    try:
        with Path(path).open(newline="") as fh:
            reader = csv.DictReader(fh)
            latest: datetime | None = None
            for row in reader:
                parsed = None
                for column in timestamp_columns:
                    parsed = _parse_bar_datetime(row.get(column, ""))
                    if parsed is not None:
                        break
                if parsed is not None and (latest is None or parsed > latest):
                    latest = parsed
            return latest
    except (OSError, UnicodeDecodeError, csv.Error):
        return None


def existing_csv_freshness(
    path: Path,
    *,
    stale_after_hours: float,
    now: datetime | None = None,
    prefer_cache_time: bool = False,
) -> dict:
    """Return freshness metadata for an existing raw-bar CSV.

    Staleness is based on the last bar timestamp, falling back to file mtime if
    the CSV cannot be parsed.  ``prefer_cache_time`` lets command-backed cache
    refresh checks use explicit fetch/as-of timestamps first, then file mtime,
    instead of stale economic observation dates.  The downloader uses this only
    when ``--skip-existing`` is requested, so stale files are refetched instead
    of skipped forever.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)

    if prefer_cache_time:
        latest_bar = _latest_csv_bar_time(
            path,
            (
                "downloaded_at_utc",
                "asof_utc",
                "generated_at_utc",
                "generated_utc",
            ),
        )
    else:
        latest_bar = _latest_csv_bar_time(path)
    effective_stale_after = effective_stale_after_hours(stale_after_hours)
    basis = "cache_time" if prefer_cache_time and latest_bar is not None else "latest_bar"
    reference = latest_bar
    if reference is None:
        try:
            reference = datetime.fromtimestamp(Path(path).stat().st_mtime, timezone.utc)
            basis = "file_mtime"
        except OSError:
            return {
                "exists": False,
                "stale": True,
                "basis": "missing",
                "age_hours": None,
                "stale_after_hours": effective_stale_after,
            }

    age_hours = max(0.0, (current - reference.astimezone(timezone.utc)).total_seconds() / 3600.0)
    return {
        "exists": True,
        "stale": bool(age_hours > effective_stale_after),
        "basis": basis,
        "latest_bar": latest_bar.isoformat() if latest_bar else None,
        "reference_time": reference.isoformat(),
        "age_hours": float(age_hours),
        "stale_after_hours": effective_stale_after,
    }


def _write_bars_csv(path: Path, symbol: str, contract, bars: Iterable[object]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temp_path.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "symbol",
                "con_id",
                "exchange",
                "primary_exchange",
                "currency",
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "average",
                "bar_count",
            ],
        )
        writer.writeheader()
        for bar in bars:
            writer.writerow(
                {
                    "symbol": symbol,
                    "con_id": getattr(contract, "conId", ""),
                    "exchange": getattr(contract, "exchange", ""),
                    "primary_exchange": getattr(contract, "primaryExchange", ""),
                    "currency": getattr(contract, "currency", ""),
                    "date": _date_to_text(getattr(bar, "date", "")),
                    "open": getattr(bar, "open", ""),
                    "high": getattr(bar, "high", ""),
                    "low": getattr(bar, "low", ""),
                    "close": getattr(bar, "close", ""),
                    "volume": getattr(bar, "volume", ""),
                    "average": getattr(bar, "average", ""),
                    "bar_count": getattr(bar, "barCount", ""),
                }
            )
            count += 1
    temp_path.replace(path)
    return count


def _manifest_path(run_dir: Path) -> Path:
    return run_dir / "manifest.json"


def _write_manifest(run_dir: Path, manifest: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = _manifest_path(run_dir)
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    temp_path.replace(path)


def _request_bars(ib, contract, args, *, duration: str, end_datetime):
    return ib.reqHistoricalData(
        contract,
        endDateTime=end_datetime,
        durationStr=duration,
        barSizeSetting=args.bar_size,
        whatToShow=args.what_to_show,
        useRTH=not args.include_extended_hours,
        formatDate=1,
        keepUpToDate=False,
        timeout=args.data_timeout,
    )


def _configure_ib_request_timeout(ib, data_timeout: float) -> None:
    ib.RequestTimeout = max(float(data_timeout), 1.0)


def _download_bars(ib, contract, args, symbol: str):
    if not args.chunk_duration:
        return _request_bars(
            ib,
            contract,
            args,
            duration=args.duration,
            end_datetime=args.end_datetime,
        )

    total_days = _duration_days(args.duration)
    chunk_days = _duration_days(args.chunk_duration)
    if chunk_days <= 0:
        raise ValueError("chunk duration must be positive")
    chunk_count = (total_days + chunk_days - 1) // chunk_days

    all_bars = []
    seen_dates = set()
    end_datetime = args.end_datetime
    for chunk_index in range(chunk_count):
        bars = _request_bars(
            ib,
            contract,
            args,
            duration=args.chunk_duration,
            end_datetime=end_datetime,
        )
        if not bars:
            raise RuntimeError(
                f"empty historical response for chunk {chunk_index + 1}/{chunk_count}"
            )
        new_count = 0
        for bar in bars:
            key = _date_to_text(getattr(bar, "date", ""))
            if key in seen_dates:
                continue
            seen_dates.add(key)
            all_bars.append(bar)
            new_count += 1

        first = bars[0].date
        last = bars[-1].date
        print(
            f"    {symbol} chunk {chunk_index + 1}/{chunk_count}: "
            f"{len(bars)} bars ({new_count} new) {first} -> {last}",
            flush=True,
        )
        if not isinstance(first, datetime):
            raise RuntimeError("chunked downloads require datetime bar dates")
        end_datetime = first - timedelta(minutes=1)
        time.sleep(max(args.sleep, 1.0))

    return sorted(all_bars, key=_bar_sort_key)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download raw IB historical bars")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_TWS_PAPER_PORT)
    parser.add_argument("--client-id", type=int, default=250)
    parser.add_argument("--connect-timeout", type=float, default=10.0)
    parser.add_argument("--data-timeout", type=float, default=180.0)
    parser.add_argument("--symbols", type=_parse_symbols, default=list(DEFAULT_SETTINGS))
    parser.add_argument("--duration", default="90 D")
    parser.add_argument(
        "--end-datetime",
        default="",
        help=(
            "Fixed IB endDateTime for the newest chunk. Example: "
            "'20260617 23:59:59 US/Eastern'. Default asks for latest available."
        ),
    )
    parser.add_argument("--bar-size", default="1 min")
    parser.add_argument("--what-to-show", default="TRADES")
    parser.add_argument(
        "--chunk-duration",
        default=None,
        help="Fetch requested duration in smaller backward chunks, e.g. '30 D'",
    )
    parser.add_argument("--include-extended-hours", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=resolve_data_path('ibkr'))
    parser.add_argument("--sleep", type=float, default=3.0, help="Pause between symbols")
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help=(
            "Do not redownload a symbol if its CSV already exists and is fresh. "
            "Freshness is controlled by --stale-after-hours."
        ),
    )
    parser.add_argument(
        "--stale-after-hours",
        type=float,
        default=DEFAULT_STALE_AFTER_HOURS,
        help="When --skip-existing is set, refetch existing CSVs older than this many hours, capped at 24.",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    effective_stale_after = effective_stale_after_hours(float(args.stale_after_hours))

    try:
        _ensure_event_loop_for_ib_insync_import()
        from ib_insync import IB, Stock
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: cannot import ib_insync: {exc}", file=sys.stderr)
        return 2

    run_name = "_".join(
        [
            _slug(args.what_to_show.lower()),
            _slug(args.bar_size.lower()),
            _slug(args.duration),
            "eth" if args.include_extended_hours else "rth",
        ]
    )
    run_dir = args.output_dir / run_name
    symbols = args.symbols
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": args.host,
        "port": args.port,
        "duration": args.duration,
        "end_datetime": args.end_datetime,
        "chunk_duration": args.chunk_duration,
        "bar_size": args.bar_size,
        "what_to_show": args.what_to_show,
        "use_rth": not args.include_extended_hours,
        "stale_after_hours": effective_stale_after,
        "requested_stale_after_hours": float(args.stale_after_hours),
        "symbols_requested": symbols,
        "symbols": {},
    }

    ib = IB()
    _configure_ib_request_timeout(ib, args.data_timeout)
    errors = []

    def on_error(req_id, code, message, contract):
        if code not in {2104, 2106, 2158}:
            errors.append(
                {
                    "req_id": req_id,
                    "code": code,
                    "message": message,
                    "symbol": getattr(contract, "symbol", None),
                }
            )

    ib.errorEvent += on_error

    try:
        ib.connect(args.host, args.port, clientId=args.client_id, timeout=args.connect_timeout)
        manifest["server_version"] = ib.client.serverVersion()
        manifest["accounts"] = ib.managedAccounts()
        print(
            f"connected serverVersion={manifest['server_version']} "
            f"accounts={manifest['accounts']}"
        )
        print(f"writing raw bars to {run_dir}")

        for index, symbol in enumerate(symbols, start=1):
            csv_path = run_dir / f"{symbol}.csv"
            existing_freshness = None
            if args.skip_existing and csv_path.exists():
                existing_freshness = existing_csv_freshness(
                    csv_path,
                    stale_after_hours=effective_stale_after,
                )
                if not existing_freshness["stale"]:
                    age = existing_freshness.get("age_hours")
                    age_text = "unknown" if age is None else f"{float(age):.2f}h"
                    print(
                        f"{index:02d}/{len(symbols)} {symbol}: skip fresh existing "
                        f"age={age_text} {csv_path}"
                    )
                    manifest["symbols"][symbol] = {
                        "status": "skipped_fresh_existing",
                        "path": str(csv_path),
                        "freshness": existing_freshness,
                    }
                    _write_manifest(run_dir, manifest)
                    continue
                age = existing_freshness.get("age_hours")
                age_text = "unknown" if age is None else f"{float(age):.2f}h"
                print(
                    f"{index:02d}/{len(symbols)} {symbol}: refetch stale existing "
                    f"age={age_text} {csv_path}",
                    flush=True,
                )

            last_error = None
            for attempt in range(1, args.retries + 2):
                errors.clear()
                try:
                    contract = Stock(symbol, "SMART", "USD")
                    qualified = ib.qualifyContracts(contract)
                    if not qualified:
                        raise RuntimeError("contract qualification returned no contracts")
                    contract = qualified[0]
                    bars = _download_bars(ib, contract, args, symbol)
                    if not bars:
                        raise RuntimeError(f"empty historical response errors={errors[-3:]}")
                    count = _write_bars_csv(csv_path, symbol, contract, bars)
                    first = _date_to_text(bars[0].date)
                    last = _date_to_text(bars[-1].date)
                    manifest["symbols"][symbol] = {
                        "status": "ok",
                        "path": str(csv_path),
                        "bar_count": count,
                        "first": first,
                        "last": last,
                        "con_id": getattr(contract, "conId", None),
                        "exchange": getattr(contract, "exchange", None),
                        "primary_exchange": getattr(contract, "primaryExchange", None),
                        "currency": getattr(contract, "currency", None),
                    }
                    if existing_freshness is not None:
                        manifest["symbols"][symbol]["refetched_existing"] = True
                        manifest["symbols"][symbol]["previous_freshness"] = existing_freshness
                    print(
                        f"{index:02d}/{len(symbols)} {symbol}: "
                        f"{count} bars {first} -> {last} {csv_path}",
                        flush=True,
                    )
                    _write_manifest(run_dir, manifest)
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = f"{type(exc).__name__}: {exc}"
                    if attempt <= args.retries:
                        print(
                            f"{index:02d}/{len(symbols)} {symbol}: "
                            f"{last_error}; retrying",
                            flush=True,
                        )
                        time.sleep(max(args.sleep, 1.0) * 2)
                    else:
                        manifest["symbols"][symbol] = {
                            "status": "error",
                            "error": last_error,
                            "api_errors": errors[-5:],
                        }
                        print(f"{index:02d}/{len(symbols)} {symbol}: ERROR {last_error}", flush=True)
                        _write_manifest(run_dir, manifest)

            if index < len(symbols):
                time.sleep(args.sleep)
    finally:
        if ib.isConnected():
            ib.disconnect()

    ok = sum(1 for item in manifest["symbols"].values() if item["status"] == "ok")
    failed = sum(1 for item in manifest["symbols"].values() if item["status"] == "error")
    print(f"done ok={ok} failed={failed} manifest={_manifest_path(run_dir)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
