"""Atomically refresh the two IQFeed daily directories behind the 192-name panel,
then sync data/ibkr/iqfeed_192_daily - the directory the LIVE frozen models
(carry_zrev_96 IBKR near-close adapter and IG spreadbet adapter) actually read
their signal from - to match.

IQFeed HDT/HDX daily history is split-adjusted.  This refresher requests the
full available range so a split correction cannot leave old and new adjustment
bases mixed in one symbol file.  It never requests or places broker orders.

iqfeed_192_daily is NOT re-fetched from IQFeed independently. Verified
(2026-08-05): iqfeed_max_daily (96 symbols) and iqfeed_b_universe_daily (96
symbols) are disjoint and their union is exactly iqfeed_192_daily's 192-symbol
set. So once those two are freshly refreshed here, iqfeed_192_daily's files
are updated by a local copy of that already-correct content - halving IQFeed
load for this step and giving it one less independent chance to fail. This is
the fix for the 2026-08-05 finding that iqfeed_192_daily had been silently
stuck a day stale: the daemon's "panel_iqfeed_192 ok" status was checking this
module's return code, but this module never actually touched that directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import socket
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from utils.ibkr.common import REPO_ROOT
from utils.trading.calendar import last_completed_session
from utils.data_paths import CONFIGURED_DATA_ROOT, resolve_data_path


SCHEMA = "iqfeed_daily_refresh.v2"
DEFAULT_DIRECTORIES = (
    resolve_data_path('ibkr/iqfeed_max_daily'),
    resolve_data_path('ibkr/iqfeed_b_universe_daily'),
)
IQFEED_192_DIRECTORY = resolve_data_path('ibkr/iqfeed_192_daily')
DEFAULT_REPORT = resolve_data_path("research/iqfeed_daily_refresh_report.json")
DEFAULT_192_SYNC_REPORT = resolve_data_path("research/iqfeed_192_daily_sync_report.json")
HEADER = '"Date","Time","Open","High","Low","Close","Volume"\n'


def hdt_command(
    symbol: str,
    *,
    begin: str,
    end: str,
    request_id: str,
    points_per_send: int = 5000,
) -> str:
    return f"HDT,{symbol},{begin},{end},,1,{request_id},{int(points_per_send)}"


def parse_daily_line(line: str, request_id: str) -> tuple[str, str, str, str, str, str, str]:
    fields = next(csv.reader([line.strip()]))
    if fields and fields[0] == request_id:
        fields = fields[1:]
    if fields and fields[0] == "LH":
        fields = fields[1:]
    if len(fields) < 7:
        raise ValueError(f"too few IQFeed daily fields: {line!r}")
    day = datetime.strptime(fields[0], "%Y-%m-%d").date()
    high, low, open_, close, volume = fields[1:6]
    for label, value in (("open", open_), ("high", high), ("low", low), ("close", close)):
        if float(value) <= 0.0:
            raise ValueError(f"non-positive {label} in {line!r}")
    return day.strftime("%m/%d/%Y"), "0000", open_, high, low, close, volume


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = _temporary_sibling(path)
    try:
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _temporary_sibling(path: Path) -> Path:
    """Return a process-unique temporary path on the destination filesystem."""
    return path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")


def _symbol_paths(directories: tuple[Path, ...]) -> list[Path]:
    paths: dict[str, Path] = {}
    for directory in directories:
        for path in sorted(directory.glob("*.txt")):
            if path.is_symlink():
                continue
            symbol = path.stem.upper()
            if symbol in paths:
                raise RuntimeError(f"duplicate IQFeed daily symbol {symbol}")
            paths[symbol] = path
    return [paths[symbol] for symbol in sorted(paths)]


def _send(writer, text: str) -> None:
    writer.write((text + "\r\n").encode("ascii"))
    writer.flush()


def _refresh_one(reader, writer, path: Path, *, begin: str, end: str, request_id: str) -> dict:
    command = hdt_command(path.stem.upper(), begin=begin, end=end, request_id=request_id)
    _send(writer, command)
    rows: list[tuple[str, str, str, str, str, str, str]] = []
    errors: list[str] = []
    while True:
        raw = reader.readline()
        if not raw:
            raise ConnectionError("IQFeed closed lookup socket before !ENDMSG!")
        line = raw.decode("utf-8", errors="replace").strip()
        if "!ENDMSG!" in line:
            break
        if "!ERROR!" in line or "!NO_DATA!" in line or ",E," in line:
            errors.append(line)
            continue
        if not line.startswith(request_id + ","):
            continue
        rows.append(parse_daily_line(line, request_id))
    if errors or not rows:
        raise RuntimeError(f"IQFeed daily error for {path.stem}: {errors[:2] or ['no_rows']}")
    latest = datetime.strptime(rows[-1][0], "%m/%d/%Y").date().strftime("%Y%m%d")
    if latest != end:
        raise RuntimeError(f"IQFeed {path.stem} latest={latest}, expected={end}")
    temp = _temporary_sibling(path)
    try:
        with temp.open("w", newline="") as handle:
            handle.write(HEADER)
            for row in rows:
                handle.write(",".join(row) + "\n")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return {"symbol": path.stem.upper(), "rows": len(rows), "first": rows[0][0], "last": rows[-1][0]}


def refresh(
    *,
    directories: tuple[Path, ...] = DEFAULT_DIRECTORIES,
    report_path: Path = DEFAULT_REPORT,
    host: str = "127.0.0.1",
    port: int = 9100,
    timeout: float = 120.0,
    begin: str = "19900101",
    end: str | None = None,
    symbols: set[str] | None = None,
) -> dict[str, Any]:
    end = end or last_completed_session().replace("-", "")
    paths = _symbol_paths(directories)
    missing_symbols: list[str] = []
    if symbols is not None:
        wanted = {symbol.upper() for symbol in symbols}
        available = {path.stem.upper() for path in paths}
        missing_symbols = sorted(wanted - available)
        paths = [path for path in paths if path.stem.upper() in wanted]
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "DTN_IQFeed_HDT_split_adjusted_daily",
        "does_not_place_orders": True,
        "begin": begin,
        "end": end,
        "directories": [str(path) for path in directories],
        "requested_symbols": len(symbols) if symbols is not None else len(paths),
        "selected_symbols": len(paths),
        "symbols": [],
        "errors": [
            {"symbol": symbol, "error": "requested symbol has no source file"}
            for symbol in missing_symbols
        ],
    }
    if not paths:
        report["errors"].append({"symbol": None, "error": "no IQFeed source files selected"})
        report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["ok"] = False
        _atomic_json(report_path, report)
        return report

    try:
        sock = socket.create_connection((host, int(port)), timeout=float(timeout))
        sock.settimeout(float(timeout))
        reader = sock.makefile("rb")
        writer = sock.makefile("wb")
    except Exception as exc:  # noqa: BLE001 - stale prior reports must not survive a failed connection
        report["errors"].append({"symbol": None, "error": f"IQFeed connection failed: {exc}"})
        report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["ok"] = False
        _atomic_json(report_path, report)
        return report
    try:
        _send(writer, "S,SET PROTOCOL,6.2")
        for index, path in enumerate(paths, start=1):
            request_id = f"D{index:06d}"
            try:
                report["symbols"].append(
                    _refresh_one(
                        reader,
                        writer,
                        path,
                        begin=begin,
                        end=end,
                        request_id=request_id,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - retain per-symbol failures
                report["errors"].append({"symbol": path.stem.upper(), "error": str(exc)[:300]})
            _atomic_json(report_path, report)
    finally:
        writer.close()
        reader.close()
        sock.close()
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["ok"] = bool(len(report["symbols"]) == len(paths) and not report["errors"])
    _atomic_json(report_path, report)
    return report


def sync_192_from_sources(
    *,
    source_directories: tuple[Path, ...] = DEFAULT_DIRECTORIES,
    target_directory: Path = IQFEED_192_DIRECTORY,
    report_path: Path = DEFAULT_192_SYNC_REPORT,
    expected_end: str | None = None,
) -> dict[str, Any]:
    """Copy each source directory's freshly-refreshed file content into the
    matching data/ibkr/iqfeed_192_daily/{symbol}.txt. See module docstring for
    why this is a local copy, not an independent IQFeed re-fetch.

    Every source and target is validated before any target is replaced. This
    prevents a missing, duplicate, or stale source from producing a mixed-date
    panel that nevertheless looks authoritative.
    """
    source_paths: dict[str, Path] = {}
    errors: list[dict[str, Any]] = []
    for directory in source_directories:
        for path in sorted(directory.glob("*.txt")):
            if path.is_symlink():
                continue
            symbol = path.stem.upper()
            if symbol in source_paths:
                errors.append(
                    {
                        "symbol": symbol,
                        "error": f"duplicate source files: {source_paths[symbol]} and {path}",
                    }
                )
            else:
                source_paths[symbol] = path

    target_paths: dict[str, Path] = {}
    for path in sorted(target_directory.glob("*.txt")):
        if path.is_symlink():
            continue
        symbol = path.stem.upper()
        if symbol in target_paths:
            errors.append(
                {
                    "symbol": symbol,
                    "error": f"duplicate target files: {target_paths[symbol]} and {path}",
                }
            )
        else:
            target_paths[symbol] = path

    if not source_paths:
        errors.append({"symbol": None, "error": "no source files found"})
    if not target_paths:
        errors.append({"symbol": None, "error": "no target files found"})
    for symbol in sorted(set(target_paths) - set(source_paths)):
        errors.append({"symbol": symbol, "error": "target has no matching source file"})
    for symbol in sorted(set(source_paths) - set(target_paths)):
        errors.append({"symbol": symbol, "error": "source has no matching target file"})

    expected_display_date: str | None = None
    if expected_end is not None:
        for date_format in ("%Y%m%d", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                expected_display_date = datetime.strptime(expected_end, date_format).strftime("%m/%d/%Y")
                break
            except ValueError:
                continue
        if expected_display_date is None:
            errors.append({"symbol": None, "error": f"invalid expected_end: {expected_end!r}"})

    validated: dict[str, tuple[str, str]] = {}
    observed_dates: set[str] = set()
    for symbol, source_path in sorted(source_paths.items()):
        if symbol not in target_paths:
            continue
        try:
            content = source_path.read_text()
            lines = content.strip().splitlines()
            if len(lines) < 2:
                raise ValueError("source contains no daily rows")
            fields = next(csv.reader([lines[-1]]))
            if not fields:
                raise ValueError("source has an empty final row")
            latest = datetime.strptime(fields[0], "%m/%d/%Y").strftime("%m/%d/%Y")
            if expected_display_date is not None and latest != expected_display_date:
                raise ValueError(f"latest={latest}, expected={expected_display_date}")
            observed_dates.add(latest)
            validated[symbol] = (content, latest)
        except Exception as exc:  # noqa: BLE001 - report every invalid source
            errors.append({"symbol": symbol, "error": str(exc)[:300]})

    if expected_display_date is None and len(observed_dates) > 1:
        errors.append(
            {
                "symbol": None,
                "error": f"source files do not share one latest session: {sorted(observed_dates)}",
            }
        )

    def finish(
        *, synced: list[dict[str, Any]], status: str = "complete"
    ) -> dict[str, Any]:
        report = {
            "schema": "iqfeed_192_daily_sync.v2",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_directories": [str(d) for d in source_directories],
            "target_directory": str(target_directory),
            "expected_end": expected_display_date,
            "source_symbol_count": len(source_paths),
            "target_symbol_count": len(target_paths),
            "synced": len(synced),
            "skipped": errors,
            "errors": errors,
            "symbols": synced,
            "status": status,
            "ok": (
                status == "complete"
                and not errors
                and len(synced) == len(target_paths) == len(source_paths)
            ),
        }
        _atomic_json(report_path, report)
        return report

    if errors:
        return finish(synced=[])

    # Invalidate the previous success receipt before touching any target. If
    # this process is killed mid-copy, observers see an interrupted sync, not
    # yesterday's authoritative-looking `ok: true`.
    finish(synced=[], status="in_progress")

    staged: dict[str, Path] = {}
    try:
        for symbol, target_path in sorted(target_paths.items()):
            temp = _temporary_sibling(target_path)
            temp.write_text(validated[symbol][0])
            staged[symbol] = temp
    except Exception as exc:  # noqa: BLE001 - fail closed before replacing targets
        errors.append({"symbol": symbol, "error": f"could not stage target: {exc}"})
        for temp in staged.values():
            temp.unlink(missing_ok=True)
        return finish(synced=[])

    backups: dict[str, Path] = {}
    try:
        for symbol, target_path in sorted(target_paths.items()):
            backup = _temporary_sibling(target_path)
            backup.write_bytes(target_path.read_bytes())
            backups[symbol] = backup
    except Exception as exc:  # noqa: BLE001 - no targets have been replaced yet
        errors.append({"symbol": symbol, "error": f"could not back up target: {exc}"})
        for temp in (*staged.values(), *backups.values()):
            temp.unlink(missing_ok=True)
        return finish(synced=[])

    synced: list[dict[str, Any]] = []
    replaced: list[str] = []
    try:
        for symbol, target_path in sorted(target_paths.items()):
            staged[symbol].replace(target_path)
            replaced.append(symbol)
            synced.append({"symbol": symbol, "last": validated[symbol][1]})
    except Exception as exc:  # noqa: BLE001 - accurately report any partial replacement
        errors.append({"symbol": symbol, "error": f"could not replace target: {exc}"})
        rollback_failed: set[str] = set()
        for replaced_symbol in reversed(replaced):
            try:
                backups[replaced_symbol].replace(target_paths[replaced_symbol])
            except Exception as rollback_exc:  # noqa: BLE001 - retain exact partial state
                rollback_failed.add(replaced_symbol)
                errors.append(
                    {
                        "symbol": replaced_symbol,
                        "error": f"could not roll back target: {rollback_exc}",
                    }
                )
        synced = [row for row in synced if row["symbol"] in rollback_failed]
    finally:
        for temp in (*staged.values(), *backups.values()):
            temp.unlink(missing_ok=True)

    return finish(synced=synced)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9100)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--begin", default="19900101")
    parser.add_argument("--end", default=None, help="YYYYMMDD; defaults to last completed NYSE session")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--skip-192-sync",
        action="store_true",
        help="only refresh iqfeed_max_daily/iqfeed_b_universe_daily; leave iqfeed_192_daily untouched",
    )
    args = parser.parse_args(argv)
    wanted = {item.strip().upper() for item in args.symbols.split(",") if item.strip()} or None
    result = refresh(
        report_path=args.report,
        host=args.host,
        port=args.port,
        timeout=args.timeout,
        begin=args.begin,
        end=args.end,
        symbols=wanted,
    )
    summary = {"ok": result["ok"], "updated": len(result["symbols"]), "errors": result["errors"][:5]}
    ok = result["ok"]
    if not args.skip_192_sync:
        if not result["ok"]:
            summary["sync_192"] = {
                "ok": False,
                "synced": 0,
                "skipped": [{"reason": "source refresh failed; 192 sync not attempted"}],
            }
            print(json.dumps(summary, indent=2))
            return 1
        sync_result = sync_192_from_sources(expected_end=result["end"])
        summary["sync_192"] = {
            "ok": sync_result["ok"],
            "synced": sync_result["synced"],
            "skipped": sync_result["skipped"][:5],
        }
        ok = ok and sync_result["ok"]
    print(json.dumps(summary, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
