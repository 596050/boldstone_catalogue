#!/usr/bin/env python3
"""Download IBKR historical tick/NBBO data for queue replay.

The output CSVs match ``backtest.tick_queue_replay``:

- ``<symbol>_nbbo.csv``: timestamp,symbol,bid,ask,bid_size,ask_size
- ``<symbol>_trades.csv``: timestamp,symbol,price,quantity,aggressor_side

IBKR historical ticks are paged in batches of at most 1000 ticks. This utility
is intentionally small and raw: it exports observed ticks and leaves queue/fill
assumptions to the replay layer.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from utils.ibkr.common import DEFAULT_GATEWAY_PAPER_PORT, DEFAULT_HOST, REPO_ROOT, ensure_repo_root_on_path
from utils.data_paths import CONFIGURED_DATA_ROOT
from utils.data_paths import resolve_data_path


ensure_repo_root_on_path()


NY_TZ = ZoneInfo("America/New_York")


def _ensure_event_loop() -> None:
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def _parse_symbols(value: str) -> list[str]:
    symbols = [part.strip().upper() for part in str(value).split(",") if part.strip()]
    if not symbols:
        raise argparse.ArgumentTypeError("provide at least one symbol")
    return symbols


def _parse_datetime(value: str | None) -> datetime:
    if value:
        text = str(value).strip()
        if text.endswith("US/Eastern"):
            parsed = datetime.strptime(text.removesuffix("US/Eastern").strip(), "%Y%m%d %H:%M:%S")
            return parsed.replace(tzinfo=NY_TZ)
        for fmt in ("%Y%m%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(text, fmt)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=NY_TZ)
                return parsed.astimezone(NY_TZ)
            except ValueError:
                continue
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=NY_TZ)
        return parsed.astimezone(NY_TZ)
    return datetime.now(NY_TZ)


def _ib_datetime(value: datetime) -> str:
    return value.astimezone(NY_TZ).strftime("%Y%m%d %H:%M:%S US/Eastern")


def _tick_time(value) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromtimestamp(float(value), NY_TZ)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=NY_TZ)
    return parsed.astimezone(NY_TZ)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def _request_pages(
    ib,
    contract,
    *,
    what_to_show: str,
    start: datetime,
    end: datetime,
    use_rth: bool,
    max_pages: int,
    sleep: float,
    timeout_retries: int,
):
    rows = []
    seen = set()
    cursor = start
    for page in range(max_pages):
        retries_left = max(int(timeout_retries), 0)
        try:
            while True:
                try:
                    ticks = ib.reqHistoricalTicks(
                        contract,
                        startDateTime=_ib_datetime(cursor),
                        endDateTime="",
                        numberOfTicks=1000,
                        whatToShow=what_to_show,
                        useRth=use_rth,
                        ignoreSize=False,
                        miscOptions=[],
                    )
                    break
                except TimeoutError:
                    if retries_left <= 0:
                        raise
                    retries_left -= 1
                    print(
                        f"    {contract.symbol} {what_to_show} page {page + 1}: "
                        f"timed out after {ib.RequestTimeout:.1f}s; retrying "
                        f"({retries_left} retries left)",
                        file=sys.stderr,
                        flush=True,
                    )
                    time.sleep(max(float(sleep), 0.0))
        except TimeoutError:
            print(
                f"    {contract.symbol} {what_to_show} page {page + 1}: "
                f"timed out after {ib.RequestTimeout:.1f}s",
                file=sys.stderr,
                flush=True,
            )
            break
        if not ticks:
            break
        newest = cursor
        added = 0
        for tick in ticks:
            ts = _tick_time(getattr(tick, "time", None))
            if ts > end:
                continue
            key = (what_to_show, ts.isoformat(), repr(tick))
            if key in seen:
                continue
            seen.add(key)
            rows.append(tick)
            newest = max(newest, ts)
            added += 1
        print(
            f"    {contract.symbol} {what_to_show} page {page + 1}: "
            f"{len(ticks)} ticks ({added} new) through {newest.isoformat()}",
            flush=True,
        )
        if newest <= cursor:
            if newest < end and len(ticks) >= 1000:
                cursor = cursor + timedelta(seconds=1)
                print(
                    f"    {contract.symbol} {what_to_show} page {page + 1}: "
                    f"dense same-second page; continuing at {cursor.isoformat()}",
                    flush=True,
                )
                time.sleep(max(float(sleep), 0.0))
                continue
            break
        if newest >= end or len(ticks) < 1000:
            break
        cursor = newest + timedelta(seconds=1)
        time.sleep(max(float(sleep), 0.0))
    return rows


def _bidask_rows(symbol: str, ticks) -> list[dict]:
    rows = []
    for tick in ticks:
        rows.append(
            {
                "timestamp": _tick_time(getattr(tick, "time", None)).isoformat(),
                "symbol": symbol,
                "bid": getattr(tick, "priceBid", ""),
                "ask": getattr(tick, "priceAsk", ""),
                "bid_size": getattr(tick, "sizeBid", ""),
                "ask_size": getattr(tick, "sizeAsk", ""),
            }
        )
    return rows


def _trade_rows(symbol: str, ticks) -> list[dict]:
    rows = []
    for tick in ticks:
        rows.append(
            {
                "timestamp": _tick_time(getattr(tick, "time", None)).isoformat(),
                "symbol": symbol,
                "price": getattr(tick, "price", ""),
                "quantity": getattr(tick, "size", ""),
                "aggressor_side": "UNKNOWN",
                "exchange": getattr(tick, "exchange", ""),
            }
        )
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download IBKR historical tick/NBBO CSVs")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_GATEWAY_PAPER_PORT)
    parser.add_argument("--client-id", type=int, default=280)
    parser.add_argument("--symbols", type=_parse_symbols, required=True)
    parser.add_argument("--exchange", default="SMART", help="IBKR contract exchange, e.g. SMART or NYSE")
    parser.add_argument("--primary-exchange", default=None, help="Optional primary exchange for SMART-routed stocks")
    parser.add_argument("--start", help="Start time, e.g. '20260625 09:30:00 US/Eastern'")
    parser.add_argument("--end", help="End time. Defaults to start + duration minutes.")
    parser.add_argument("--duration-minutes", type=float, default=60.0)
    parser.add_argument("--include-extended-hours", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=resolve_data_path('ibkr/ticks'))
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for each IBKR historical tick page before failing.",
    )
    parser.add_argument(
        "--timeout-retries",
        type=int,
        default=0,
        help="Number of times to retry a timed-out historical tick page before stopping that stream.",
    )
    parser.add_argument(
        "--skip-trades",
        action="store_true",
        help="Only download BID_ASK/NBBO rows and write an empty trades CSV.",
    )
    parser.add_argument(
        "--skip-bid-ask",
        action="store_true",
        help="Only download TRADES rows and write an empty NBBO CSV.",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.skip_trades and args.skip_bid_ask:
        raise ValueError("--skip-trades and --skip-bid-ask cannot both be set")
    _ensure_event_loop()
    try:
        from ib_insync import IB, Stock
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: cannot import ib_insync: {exc}", file=sys.stderr)
        return 2

    start = _parse_datetime(args.start) if args.start else datetime.now(NY_TZ) - timedelta(minutes=float(args.duration_minutes))
    end = _parse_datetime(args.end) if args.end else start + timedelta(minutes=float(args.duration_minutes))
    if end <= start:
        raise ValueError("end must be after start")

    ib = IB()
    ib.RequestTimeout = max(float(args.request_timeout), 1.0)
    ib.connect(args.host, args.port, clientId=args.client_id, timeout=10)
    try:
        print(f"connected serverVersion={ib.client.serverVersion()} accounts={ib.managedAccounts()}")
        for symbol in args.symbols:
            contract = Stock(symbol, args.exchange, "USD")
            if args.primary_exchange:
                contract.primaryExchange = args.primary_exchange
            qualified = ib.qualifyContracts(contract)
            if not qualified:
                print(f"{symbol}: ERROR contract qualification returned no contracts", flush=True)
                continue
            contract = qualified[0]
            print(f"{symbol}: downloading {start.isoformat()} -> {end.isoformat()}", flush=True)
            bidask = []
            if not args.skip_bid_ask:
                bidask = _request_pages(
                    ib,
                    contract,
                    what_to_show="BID_ASK",
                    start=start,
                    end=end,
                    use_rth=not args.include_extended_hours,
                    max_pages=max(int(args.max_pages), 1),
                    sleep=args.sleep,
                    timeout_retries=max(int(args.timeout_retries), 0),
                )
            else:
                print(f"    {symbol} BID_ASK: skipped by --skip-bid-ask", flush=True)
            trades = []
            if not args.skip_trades:
                trades = _request_pages(
                    ib,
                    contract,
                    what_to_show="TRADES",
                    start=start,
                    end=end,
                    use_rth=not args.include_extended_hours,
                    max_pages=max(int(args.max_pages), 1),
                    sleep=args.sleep,
                    timeout_retries=max(int(args.timeout_retries), 0),
                )
            else:
                print(f"    {symbol} TRADES: skipped by --skip-trades", flush=True)
            symbol_dir = args.output_dir / symbol
            _write_csv(symbol_dir / f"{symbol}_nbbo.csv", ["timestamp", "symbol", "bid", "ask", "bid_size", "ask_size"], _bidask_rows(symbol, bidask))
            _write_csv(
                symbol_dir / f"{symbol}_trades.csv",
                ["timestamp", "symbol", "price", "quantity", "aggressor_side", "exchange"],
                _trade_rows(symbol, trades),
            )
            print(f"{symbol}: wrote {len(bidask)} NBBO ticks and {len(trades)} trade ticks to {symbol_dir}", flush=True)
    finally:
        if ib.isConnected():
            ib.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
