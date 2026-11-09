"""Download IQFeed historical data.

The script expects IQConnect to be installed locally and logged in. It uses the
History/Lookup socket on localhost:9100.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from typing import Iterable
import urllib.request
from utils.data_paths import CONFIGURED_DATA_ROOT
from utils.data_paths import resolve_data_path


DOWNLOAD_ROOT = resolve_data_path('iqfeed_downloads_v2')
DEFAULT_SYMBOLS_FILE = resolve_data_path('iqfeed_downloads_v2/mktsymbols/mktsymbols_v2.txt')
DEFAULT_UNIVERSE_FILE = resolve_data_path('iqfeed_downloads_v2/commodity_frontmonth_symbols.csv')
DEFAULT_OUTPUT_DIR = resolve_data_path('iqfeed_downloads_v2/tick_downloads')
DEFAULT_SP500_UNIVERSE_FILE = resolve_data_path('iqfeed_downloads_v2/sp500_symbols.csv')
DEFAULT_INTERVAL_OUTPUT_DIR = resolve_data_path('iqfeed_downloads_v2/sp500_1min')
DEFAULT_COMMODITY_INTERVAL_OUTPUT_DIR = resolve_data_path('iqfeed_downloads_v2/commodities_1min_500')
DEFAULT_IQCONNECT = Path(r"C:\Program Files\DTN\IQFeed\iqconnect.exe")
SP500_CONSTITUENTS_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
)

# Broad commodity-futures exchanges. Entitlement gaps are handled by the
# downloader and recorded as IQFeed errors.
DEFAULT_COMMODITY_EXCHANGES = {
    "ASXCM",
    "B3",
    "CBOT",
    "CME",
    "COMEX",
    "DCE",
    "EEXE",
    "EEXN",
    "EEXP",
    "ENCOM",
    "ICEEA",
    "ICEEC",
    "ICEEF",
    "ICEENDEX",
    "ICEFC",
    "ICEFU",
    "MCX",
    "MDEX",
    "MGE",
    "NYMEX",
    "SAFEX",
    "SGX",
    "SGXAC",
    "ZCE",
}

FINANCIAL_DESCRIPTION_PATTERNS = [
    " AEX ",
    " BOND",
    " BUND",
    " CAC ",
    " CURRENCY",
    " DAX ",
    " DOW ",
    " EQUITY INDEX",
    " EURO FX",
    " EURO STOXX",
    " EURODOLLAR",
    " FED FUND",
    " FTSE ",
    " IBOVESPA",
    " INDEX",
    " INTEREST RATE",
    " MSCI ",
    " NASDAQ",
    " NIKKEI",
    " NOTE",
    " RUSSELL",
    " S&P ",
    " SCHATZ",
    " SOFR",
    " STOXX",
    " T-NOTE",
    " TREASUR",
    " VOLATILITY",
    " YIELD",
    "ETHER",
    "EURO-BTP",
    "EUROBOBL",
    "EUROBUND",
    "EUROSCHATZ",
    "VIX",
]

MONTH_CODES = set("FGHJKMNQUVXZ")


def parse_exchange_list(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {item.strip().upper() for item in value.split(",") if item.strip()}


def normalize_description(value: str) -> str:
    return f" {value.upper()} "


def looks_financial(row: dict[str, str]) -> bool:
    description = normalize_description(row.get("DESCRIPTION", ""))
    return any(pattern in description for pattern in FINANCIAL_DESCRIPTION_PATTERNS)


def is_continuous_symbol(symbol: str) -> bool:
    return symbol.endswith("#") or symbol.endswith("#C")


def parse_market_symbols(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f, delimiter="\t")


def load_iqfeed_equity_symbols(path: Path) -> set[str]:
    symbols: set[str] = set()
    for row in parse_market_symbols(path):
        if row.get("SECURITY TYPE", "").strip().upper() == "EQUITY":
            symbol = row.get("SYMBOL", "").strip()
            if symbol:
                symbols.add(symbol.upper())
    return symbols


def sp500_candidate_symbols(symbol: str) -> list[str]:
    base = symbol.strip().upper()
    candidates = [base]
    if "." in base:
        candidates.extend([base.replace(".", "-"), base.replace(".", "")])
    if "-" in base:
        candidates.extend([base.replace("-", "."), base.replace("-", "")])
    # Preserve order while deduplicating.
    return list(dict.fromkeys(candidates))


def build_sp500_universe(args: argparse.Namespace) -> int:
    symbols_file = Path(args.symbols_file)
    if not symbols_file.exists():
        raise SystemExit(f"IQFeed market-symbols file not found: {symbols_file}")

    print(f"Loading IQFeed equity symbols from {symbols_file}...")
    iqfeed_equities = load_iqfeed_equity_symbols(symbols_file)

    print(f"Downloading S&P 500 constituents from {args.source_url}...")
    with urllib.request.urlopen(args.source_url, timeout=60) as response:
        text = response.read().decode("utf-8-sig")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(text.splitlines()))

    fieldnames = ["symbol", "source_symbol", "company", "sector", "iqfeed_match"]
    count = 0
    missing = 0
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            source_symbol = (row.get("Symbol") or row.get("symbol") or "").strip()
            if not source_symbol:
                continue
            match = ""
            for candidate in sp500_candidate_symbols(source_symbol):
                if candidate.upper() in iqfeed_equities:
                    match = candidate
                    break
            if not match:
                missing += 1
                match = source_symbol

            writer.writerow(
                {
                    "symbol": match,
                    "source_symbol": source_symbol,
                    "company": row.get("Name") or row.get("Security") or row.get("name") or "",
                    "sector": row.get("Sector") or row.get("GICS Sector") or row.get("sector") or "",
                    "iqfeed_match": "Y" if match.upper() in iqfeed_equities else "N",
                }
            )
            count += 1

    print(f"Wrote {count} S&P 500 symbols to {out_path}; {missing} without IQFeed equity match.")
    return 0


def build_universe(args: argparse.Namespace) -> int:
    symbols_file = Path(args.symbols_file)
    if not symbols_file.exists():
        raise SystemExit(f"Symbol file not found: {symbols_file}")

    exchanges = None if args.all_exchanges else parse_exchange_list(args.exchanges)
    if exchanges is None and not args.all_exchanges:
        exchanges = DEFAULT_COMMODITY_EXCHANGES

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    seen: set[str] = set()
    count = 0
    fieldnames = [
        "symbol",
        "description",
        "exchange",
        "listed_market",
        "security_type",
        "frontmonth",
        "sic",
        "naics",
    ]

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in parse_market_symbols(symbols_file):
            symbol = row.get("SYMBOL", "").strip()
            if not symbol or symbol in seen:
                continue
            if row.get("SECURITY TYPE", "").strip().upper() != "FUTURE":
                continue
            if exchanges is not None and row.get("EXCHANGE", "").strip().upper() not in exchanges:
                continue
            if not args.include_financials and looks_financial(row):
                continue

            if args.universe == "frontmonth" and row.get("FRONTMONTH", "").strip().upper() != "Y":
                continue
            if args.universe == "all-contracts" and is_continuous_symbol(symbol):
                continue
            if args.universe == "contract-months-only" and not has_contract_month_suffix(symbol):
                continue

            seen.add(symbol)
            writer.writerow(
                {
                    "symbol": symbol,
                    "description": row.get("DESCRIPTION", ""),
                    "exchange": row.get("EXCHANGE", ""),
                    "listed_market": row.get("LISTED MARKET", ""),
                    "security_type": row.get("SECURITY TYPE", ""),
                    "frontmonth": row.get("FRONTMONTH", ""),
                    "sic": row.get("SIC", ""),
                    "naics": row.get("NAICS", ""),
                }
            )
            count += 1
            if args.limit and count >= args.limit:
                break

    print(f"Wrote {count} symbols to {out_path}")
    return 0


def has_contract_month_suffix(symbol: str) -> bool:
    if len(symbol) < 3:
        return False
    return symbol[-3] in MONTH_CODES and symbol[-2:].isdigit()


def parse_iqfeed_datetime(value: str, *, end_of_day: bool = False) -> str:
    value = value.strip()
    formats = [
        "%Y%m%d %H%M%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y%m%d",
        "%Y-%m-%d",
    ]
    parsed: dt.datetime | None = None
    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(value, fmt)
            if fmt in {"%Y%m%d", "%Y-%m-%d"}:
                parsed = parsed.replace(
                    hour=23 if end_of_day else 0,
                    minute=59 if end_of_day else 0,
                    second=59 if end_of_day else 0,
                )
            break
        except ValueError:
            continue
    if parsed is None:
        raise argparse.ArgumentTypeError(
            f"Invalid IQFeed date/time: {value!r}. Use YYYYMMDD or YYYYMMDD HHMMSS."
        )
    return parsed.strftime("%Y%m%d %H%M%S")


def default_begin() -> str:
    # IQFeed currently documents tick history as up to 180 calendar days.
    return (dt.datetime.now() - dt.timedelta(days=180)).strftime("%Y%m%d %H%M%S")


def default_end() -> str:
    return dt.datetime.now().strftime("%Y%m%d %H%M%S")


def safe_name(symbol: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\s]+', "_", symbol)
    return cleaned.strip("._") or "symbol"


def read_universe(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows: list[dict[str, str]] = []
        for row in reader:
            symbol = row.get("symbol") or row.get("SYMBOL")
            if not symbol:
                continue
            row["symbol"] = symbol.strip()
            rows.append(row)
        return rows


def apply_shard(
    universe: list[dict[str, str]], shard_count: int | None, shard_index: int | None
) -> list[dict[str, str]]:
    if not shard_count or shard_count <= 1:
        return universe
    if shard_index is None:
        raise SystemExit("--shard-index is required when --shard-count is greater than 1")
    if shard_index < 0 or shard_index >= shard_count:
        raise SystemExit("--shard-index must be between 0 and --shard-count - 1")
    return [row for index, row in enumerate(universe) if index % shard_count == shard_index]


def send_command(writer, command: str) -> None:
    writer.write(command + "\r\n")
    writer.flush()


def read_line(reader) -> str:
    line = reader.readline()
    if line == "":
        raise ConnectionError("IQFeed socket closed")
    return line.rstrip("\r\n")


def is_iqfeed_error_line(line: str) -> bool:
    fields = line.split(",", 2)
    return (
        line.startswith("E,")
        or (len(fields) > 1 and fields[1] == "E")
        or "!NO_DATA!" in line
        or "User Not Authorized" in line
        or "Unauthorized user ID" in line
        or "Too many" in line
    )


def connect_lookup(host: str, port: int, timeout: float):
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.settimeout(timeout)
    reader = sock.makefile("r", encoding="ascii", errors="replace", newline="\n")
    writer = sock.makefile("w", encoding="ascii", errors="strict", newline="")
    return sock, reader, writer


def set_protocol(reader, writer, protocol: str, timeout: float) -> str:
    send_command(writer, f"S,SET PROTOCOL,{protocol}")
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        line = read_line(reader)
        last = line
        if "CURRENT PROTOCOL" in line or "SET PROTOCOL" in line or line.startswith("E,"):
            return line
    return last


def wait_for_port(host: str, port: int, seconds: int) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(1)
    return False


def launch_iqconnect(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"IQConnect not found: {path}")
    subprocess.Popen([str(path)], cwd=str(path.parent))


def output_path_for_symbol(output_dir: Path, row: dict[str, str], gzip_output: bool) -> Path:
    exchange = safe_name(row.get("exchange") or row.get("EXCHANGE") or "unknown")
    symbol = safe_name(row["symbol"])
    suffix = ".csv.gz" if gzip_output else ".csv"
    return output_dir / exchange / f"{symbol}{suffix}"


def open_output(path: Path, gzip_output: bool):
    path.parent.mkdir(parents=True, exist_ok=True)
    if gzip_output:
        return gzip.open(path, "wt", encoding="utf-8", newline="\n")
    return path.open("w", encoding="utf-8", newline="\n")


def append_csv(path: Path, fieldnames: list[str], row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def interval_output_has_rows(path: Path, has_header: bool) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    if not has_header:
        return True
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        f.readline()
        line = f.readline().strip()
        return bool(line) and not is_iqfeed_error_line(line)


def raw_output_has_rows(path: Path, gzip_output: bool) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    opener = gzip.open if gzip_output else open
    with opener(path, "rt", encoding="utf-8", errors="ignore") as f:
        line = f.readline().strip()
        return bool(line) and not is_iqfeed_error_line(line)


def close_lookup_session(sock, reader, writer) -> None:
    for handle in (writer, reader, sock):
        try:
            handle.close()
        except Exception:
            pass


def ensure_lookup_available(args: argparse.Namespace) -> None:
    if not getattr(args, "ensure_lookup", False):
        return
    root = Path(__file__).resolve().parent
    helper = root / "lib" / "ensure_iqfeed_lookup.sh"
    if not helper.exists():
        raise ConnectionError(f"ensure helper not found: {helper}")
    env = os.environ.copy()
    env.setdefault("ROOT", str(root))
    repo = root.parents[1]
    env.setdefault("WINEPREFIX", env.get("IQFEED_WINEPREFIX", str(repo / ".runtime/iqfeed/wineprefix")))
    env.setdefault("IQFEED_LOG_DIR", str(repo / ".runtime/iqfeed/logs"))
    env_file = env.get("MARKETMAKER_ENV_FILE", str(repo / ".env"))
    command = (
        'if [ -f "$2" ]; then set -a; source "$2"; set +a; fi; '
        'export WINEPREFIX="${IQFEED_WINEPREFIX:-$WINEPREFIX}"; '
        'source "$1" && ensure_iqfeed_lookup'
    )
    try:
        subprocess.run(
            ["bash", "-c", command, "iqfeed-ensure", str(helper), env_file],
            cwd=str(root),
            env=env,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ConnectionError(f"ensure_iqfeed_lookup failed with exit code {exc.returncode}") from exc


def cleanup_lookup_if_requested(args: argparse.Namespace) -> None:
    if not getattr(args, "ensure_lookup", False) or getattr(args, "keep_wine", False):
        return
    root = Path(__file__).resolve().parent
    helper = root / "lib" / "ensure_iqfeed_lookup.sh"
    if not helper.exists():
        return
    env = os.environ.copy()
    env.setdefault("ROOT", str(root))
    repo = root.parents[1]
    env.setdefault("WINEPREFIX", env.get("IQFEED_WINEPREFIX", str(repo / ".runtime/iqfeed/wineprefix")))
    env_file = env.get("MARKETMAKER_ENV_FILE", str(repo / ".env"))
    command = (
        'if [ -f "$2" ]; then set -a; source "$2"; set +a; fi; '
        'export WINEPREFIX="${IQFEED_WINEPREFIX:-$WINEPREFIX}"; '
        'source "$1" && cleanup_iqfeed_wine'
    )
    try:
        subprocess.run(
            ["bash", "-c", command, "iqfeed-cleanup", str(helper), env_file],
            cwd=str(root),
            env=env,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001 - cleanup must not mask download results.
        print(f"WARNING: IQFeed Wine cleanup failed: {exc}", file=sys.stderr)


def open_lookup_session(args: argparse.Namespace):
    retries = int(getattr(args, "connect_retries", 0))
    retry_delay = float(getattr(args, "connect_retry_delay", 5.0))
    last_error: str | None = None
    for attempt in range(retries + 1):
        sock = reader = writer = None
        try:
            ensure_lookup_available(args)
            sock, reader, writer = connect_lookup(args.host, args.port, args.timeout)
            protocol_line = set_protocol(reader, writer, args.protocol, args.timeout)
            if not protocol_line or protocol_line.startswith("E,"):
                raise ConnectionError(f"bad protocol response: {protocol_line!r}")
            return sock, reader, writer, protocol_line
        except (OSError, ConnectionError, TimeoutError) as exc:
            close_lookup_session(sock, reader, writer)
            last_error = str(exc)
            if attempt < retries:
                print(
                    f"    lookup connect retry {attempt + 1}/{retries} after: {exc}",
                    file=sys.stderr,
                )
                time.sleep(retry_delay)
                continue
            break
    raise ConnectionError(
        f"Could not connect to IQFeed lookup socket {args.host}:{args.port}: {last_error}\n"
        "Start IQConnect, log in, or rerun with --ensure-lookup."
    )


def should_retry_errors(errors: list[str]) -> bool:
    retry_markers = (
        "too many",
        "rate",
        "timeout",
        "temporarily",
        "busy",
        "socket",
        "connection",
    )
    return any(any(marker in error.lower() for marker in retry_markers) for error in errors)


def download_one_symbol(
    reader,
    writer,
    row: dict[str, str],
    request_id: str,
    output_path: Path,
    args: argparse.Namespace,
) -> tuple[int, list[str], str]:
    symbol = row["symbol"]
    command = ",".join(
        [
            "HTT",
            symbol,
            args.begin,
            args.end,
            str(args.max_datapoints or ""),
            args.begin_filter or "",
            args.end_filter or "",
            str(args.direction),
            request_id,
            str(args.points_per_send),
        ]
    )

    errors: list[str] = []
    rows = 0
    suffix = output_path.suffix + ".part"
    temp_path = output_path.with_suffix(suffix)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if temp_path.exists():
        temp_path.unlink()

    send_command(writer, command)
    with open_output(temp_path, args.gzip) as out:
        while True:
            line = read_line(reader)
            if "!ENDMSG!" in line:
                break
            if is_iqfeed_error_line(line):
                errors.append(line)
                continue
            out.write(line + "\n")
            rows += 1

    if rows == 0:
        temp_path.unlink(missing_ok=True)
        if output_path.exists() and not raw_output_has_rows(output_path, args.gzip):
            output_path.unlink()
    else:
        if output_path.exists():
            output_path.unlink()
        temp_path.rename(output_path)
    return rows, errors, command


def parse_interval_timestamp(value: str) -> dt.datetime:
    value = value.strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y%m%d %H%M%S",
        "%Y%m%d %H%M",
    ]
    for fmt in formats:
        try:
            return dt.datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized IQFeed timestamp: {value!r}")


def parse_interval_history_line(
    line: str, request_id: str, volume_field: str
) -> tuple[str, str, str, str, str, str, str]:
    fields = next(csv.reader([line]))
    if fields and fields[-1] == request_id:
        fields = fields[:-1]
    if fields and fields[0] == request_id:
        fields = fields[1:]
    if fields and fields[0] == "LH":
        fields = fields[1:]
    if len(fields) < 6:
        raise ValueError(f"Too few interval fields: {line!r}")

    timestamp = parse_interval_timestamp(fields[0])

    # IQFeed interval bars are timestamp, high, low, open, close, total volume,
    # period volume, number of trades. Period volume matches the NFLX.txt shape.
    high = fields[1]
    low = fields[2]
    open_ = fields[3]
    close = fields[4]
    if volume_field == "total":
        volume = fields[5]
    elif len(fields) >= 7:
        volume = fields[6]
    else:
        volume = fields[5]

    date_out = timestamp.strftime("%m/%d/%Y")
    time_out = timestamp.strftime("%H%M")
    return date_out, time_out, open_, high, low, close, volume


def interval_output_path(output_dir: Path, row: dict[str, str], group_by_exchange: bool) -> Path:
    symbol = row["symbol"]
    filename_symbol = row.get("source_symbol") or symbol
    filename = f"{safe_name(filename_symbol)}.txt"
    if group_by_exchange:
        exchange = safe_name(row.get("exchange") or row.get("EXCHANGE") or "unknown")
        return output_dir / exchange / filename
    return output_dir / filename


def download_one_interval_symbol(
    reader,
    writer,
    row: dict[str, str],
    request_id: str,
    output_path: Path,
    args: argparse.Namespace,
) -> tuple[int, list[str], str]:
    symbol = row["symbol"]
    command = ",".join(
        [
            "HIT",
            symbol,
            str(args.interval_seconds),
            args.begin,
            args.end,
            str(args.max_datapoints or ""),
            args.begin_filter or "",
            args.end_filter or "",
            str(args.direction),
            request_id,
            str(args.points_per_send),
            args.interval_type,
        ]
    )

    errors: list[str] = []
    rows = 0
    temp_path = output_path.with_suffix(output_path.suffix + ".part")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if temp_path.exists():
        temp_path.unlink()

    send_command(writer, command)
    with temp_path.open("w", encoding="utf-8", newline="\n") as out:
        if args.header:
            out.write('"Date","Time","Open","High","Low","Close","Volume"\n')
        while True:
            line = read_line(reader)
            if "!ENDMSG!" in line:
                break
            if is_iqfeed_error_line(line):
                errors.append(line)
                continue
            try:
                out.write(",".join(parse_interval_history_line(line, request_id, args.volume_field)))
                out.write("\n")
                rows += 1
            except Exception as exc:  # noqa: BLE001 - preserve bad row context.
                errors.append(f"parse_error:{exc}:{line}")

    if rows == 0:
        temp_path.unlink(missing_ok=True)
        if output_path.exists() and not interval_output_has_rows(output_path, args.header):
            output_path.unlink()
    else:
        if output_path.exists():
            output_path.unlink()
        temp_path.rename(output_path)
    return rows, errors, command


def download_intervals(args: argparse.Namespace) -> int:
    universe = read_universe(Path(args.universe_file))
    if args.exchanges:
        exchanges = parse_exchange_list(args.exchanges) or set()
        universe = [
            row
            for row in universe
            if (row.get("exchange") or row.get("EXCHANGE") or "").upper() in exchanges
        ]
    if args.symbols:
        wanted = {s.strip().upper() for s in args.symbols.split(",") if s.strip()}
        universe = [
            row
            for row in universe
            if row["symbol"].upper() in wanted
            or (row.get("source_symbol") or "").upper() in wanted
        ]
    if args.start_after:
        start_after = args.start_after.upper()
        seen_start = False
        filtered = []
        for row in universe:
            if seen_start:
                filtered.append(row)
            elif row["symbol"].upper() == start_after or (row.get("source_symbol") or "").upper() == start_after:
                seen_start = True
        universe = filtered
    if args.max_symbols:
        universe = universe[: args.max_symbols]
    universe = apply_shard(universe, args.shard_count, args.shard_index)

    if not universe:
        print("No symbols selected.")
        return 1

    if args.launch_iqconnect:
        launch_iqconnect(Path(args.iqconnect_path))
        if not wait_for_port(args.host, args.port, args.wait_seconds):
            raise SystemExit(
                f"IQConnect did not open {args.host}:{args.port}. Log in to IQFeed and rerun."
            )

    output_dir = Path(args.output_dir)
    if args.shard_count and args.shard_count > 1:
        shard_label = f"shard_{args.shard_index + 1:02d}_of_{args.shard_count:02d}"
        manifest_path = output_dir / f"manifest_{shard_label}.csv"
        errors_path = output_dir / f"errors_{shard_label}.csv"
    else:
        manifest_path = output_dir / "manifest.csv"
        errors_path = output_dir / "errors.csv"
    manifest_fields = [
        "symbol",
        "source_symbol",
        "description",
        "company",
        "exchange",
        "begin",
        "end",
        "interval_seconds",
        "rows",
        "status",
        "output",
        "request",
        "completed_at",
    ]
    error_fields = ["symbol", "source_symbol", "exchange", "error", "request", "logged_at"]

    completed = 0
    try:
        sock, reader, writer, protocol_line = open_lookup_session(args)
    except ConnectionError as exc:
        raise SystemExit(str(exc)) from exc
    try:
        print(f"IQFeed protocol response: {protocol_line}")
        if args.shard_count and args.shard_count > 1:
            print(
                f"Shard {args.shard_index + 1}/{args.shard_count}: "
                f"{len(universe)} selected symbols"
            )

        for index, row in enumerate(universe, start=1):
            output_path = interval_output_path(output_dir, row, args.group_by_exchange)
            if args.resume and interval_output_has_rows(output_path, args.header):
                print(f"[{index}/{len(universe)}] skip existing {row['symbol']}")
                continue

            request_id = f"I{index:06d}"
            print(f"[{index}/{len(universe)}] {row['symbol']} -> {output_path}")
            started = time.time()
            rows = 0
            request = ""
            status = "ok"
            errors: list[str] = []
            for attempt in range(args.retries + 1):
                try:
                    rows, errors, request = download_one_interval_symbol(
                        reader, writer, row, request_id, output_path, args
                    )
                    if errors and rows == 0 and should_retry_errors(errors) and attempt < args.retries:
                        print(f"    retry {attempt + 1}/{args.retries} after IQFeed error")
                        time.sleep(args.retry_delay)
                        continue
                    break
                except Exception as exc:  # noqa: BLE001 - reconnect and retry large runs.
                    errors = [str(exc)]
                    status = f"exception:{type(exc).__name__}"
                    request = request or f"HIT,{row['symbol']},..."
                    if attempt < args.retries:
                        print(
                            f"    retry {attempt + 1}/{args.retries} after "
                            f"{type(exc).__name__}: {exc}"
                        )
                        close_lookup_session(sock, reader, writer)
                        time.sleep(args.retry_delay)
                        sock, reader, writer, protocol_line = open_lookup_session(args)
                        print(f"    reconnected: {protocol_line}")
                        continue
                    break

            if errors:
                if not status.startswith("exception:"):
                    status = "iqfeed_error"
                for error in errors:
                    append_csv(
                        errors_path,
                        error_fields,
                        {
                            "symbol": row["symbol"],
                            "source_symbol": row.get("source_symbol", ""),
                            "exchange": row.get("exchange", ""),
                            "error": error,
                            "request": request,
                            "logged_at": dt.datetime.now().isoformat(timespec="seconds"),
                        },
                    )

            if rows > 0 and status.startswith("exception:"):
                status = "ok"
            if rows == 0 and not errors and status == "ok":
                status = "no_rows"
                append_csv(
                    errors_path,
                    error_fields,
                    {
                        "symbol": row["symbol"],
                        "source_symbol": row.get("source_symbol", ""),
                        "exchange": row.get("exchange", ""),
                        "error": "No rows returned",
                        "request": request,
                        "logged_at": dt.datetime.now().isoformat(timespec="seconds"),
                    },
                )

            append_csv(
                manifest_path,
                manifest_fields,
                {
                    "symbol": row["symbol"],
                    "source_symbol": row.get("source_symbol", ""),
                    "description": row.get("description", ""),
                    "company": row.get("company", ""),
                    "exchange": row.get("exchange", ""),
                    "begin": args.begin,
                    "end": args.end,
                    "interval_seconds": args.interval_seconds,
                    "rows": rows,
                    "status": status,
                    "output": str(output_path),
                    "request": request,
                    "completed_at": dt.datetime.now().isoformat(timespec="seconds"),
                },
            )
            completed += 1
            elapsed = time.time() - started
            print(f"    {status}, rows={rows}, elapsed={elapsed:.1f}s")
            if args.request_delay:
                time.sleep(args.request_delay)
    finally:
        close_lookup_session(sock, reader, writer)

    print(f"Completed {completed} requests. Manifest: {manifest_path}")
    return 0


def download_ticks(args: argparse.Namespace) -> int:
    universe = read_universe(Path(args.universe_file))
    if args.exchanges:
        exchanges = parse_exchange_list(args.exchanges) or set()
        universe = [
            row
            for row in universe
            if (row.get("exchange") or row.get("EXCHANGE") or "").upper() in exchanges
        ]
    if args.symbols:
        wanted = {s.strip().upper() for s in args.symbols.split(",") if s.strip()}
        universe = [row for row in universe if row["symbol"].upper() in wanted]
    if args.start_after:
        start_after = args.start_after.upper()
        seen_start = False
        filtered = []
        for row in universe:
            if seen_start:
                filtered.append(row)
            elif row["symbol"].upper() == start_after:
                seen_start = True
        universe = filtered
    if args.max_symbols:
        universe = universe[: args.max_symbols]
    universe = apply_shard(universe, args.shard_count, args.shard_index)

    if not universe:
        print("No symbols selected.")
        return 1

    if args.launch_iqconnect:
        launch_iqconnect(Path(args.iqconnect_path))
        if not wait_for_port(args.host, args.port, args.wait_seconds):
            raise SystemExit(
                f"IQConnect did not open {args.host}:{args.port}. Log in to IQFeed and rerun."
            )

    output_dir = Path(args.output_dir)
    if args.shard_count and args.shard_count > 1:
        shard_label = f"shard_{args.shard_index + 1:02d}_of_{args.shard_count:02d}"
        manifest_path = output_dir / f"manifest_{shard_label}.csv"
        errors_path = output_dir / f"errors_{shard_label}.csv"
    else:
        manifest_path = output_dir / "manifest.csv"
        errors_path = output_dir / "errors.csv"
    manifest_fields = [
        "symbol",
        "description",
        "exchange",
        "begin",
        "end",
        "rows",
        "status",
        "output",
        "request",
        "completed_at",
    ]
    error_fields = ["symbol", "exchange", "error", "request", "logged_at"]

    completed = 0
    try:
        sock, reader, writer, protocol_line = open_lookup_session(args)
    except ConnectionError as exc:
        raise SystemExit(str(exc)) from exc
    try:
        print(f"IQFeed protocol response: {protocol_line}")
        if args.shard_count and args.shard_count > 1:
            print(
                f"Shard {args.shard_index + 1}/{args.shard_count}: "
                f"{len(universe)} selected symbols"
            )

        for index, row in enumerate(universe, start=1):
            output_path = output_path_for_symbol(output_dir, row, args.gzip)
            if args.resume and raw_output_has_rows(output_path, args.gzip):
                print(f"[{index}/{len(universe)}] skip existing {row['symbol']}")
                continue

            request_id = f"T{index:06d}"
            print(f"[{index}/{len(universe)}] {row['symbol']} -> {output_path}")
            started = time.time()
            status = "ok"
            rows = 0
            request = ""
            errors: list[str] = []
            for attempt in range(args.retries + 1):
                try:
                    rows, errors, request = download_one_symbol(
                        reader, writer, row, request_id, output_path, args
                    )
                    if errors and rows == 0 and should_retry_errors(errors) and attempt < args.retries:
                        print(f"    retry {attempt + 1}/{args.retries} after IQFeed error")
                        time.sleep(args.retry_delay)
                        continue
                    break
                except Exception as exc:  # noqa: BLE001 - reconnect and retry large runs.
                    errors = [str(exc)]
                    status = f"exception:{type(exc).__name__}"
                    request = request or f"HTT,{row['symbol']},..."
                    if attempt < args.retries:
                        print(
                            f"    retry {attempt + 1}/{args.retries} after "
                            f"{type(exc).__name__}: {exc}"
                        )
                        close_lookup_session(sock, reader, writer)
                        time.sleep(args.retry_delay)
                        sock, reader, writer, protocol_line = open_lookup_session(args)
                        print(f"    reconnected: {protocol_line}")
                        continue
                    break

            if errors:
                if not status.startswith("exception:"):
                    status = "iqfeed_error"
                for error in errors:
                    append_csv(
                        errors_path,
                        error_fields,
                        {
                            "symbol": row["symbol"],
                            "exchange": row.get("exchange", ""),
                            "error": error,
                            "request": request,
                            "logged_at": dt.datetime.now().isoformat(timespec="seconds"),
                        },
                    )

            if rows > 0 and status.startswith("exception:"):
                status = "ok"
            if rows == 0 and not errors and status == "ok":
                status = "no_rows"
                append_csv(
                    errors_path,
                    error_fields,
                    {
                        "symbol": row["symbol"],
                        "exchange": row.get("exchange", ""),
                        "error": "No rows returned",
                        "request": request,
                        "logged_at": dt.datetime.now().isoformat(timespec="seconds"),
                    },
                )

            append_csv(
                manifest_path,
                manifest_fields,
                {
                    "symbol": row["symbol"],
                    "description": row.get("description", ""),
                    "exchange": row.get("exchange", ""),
                    "begin": args.begin,
                    "end": args.end,
                    "rows": rows,
                    "status": status,
                    "output": str(output_path),
                    "request": request,
                    "completed_at": dt.datetime.now().isoformat(timespec="seconds"),
                },
            )
            completed += 1
            elapsed = time.time() - started
            print(f"    {status}, rows={rows}, elapsed={elapsed:.1f}s")
            if args.request_delay:
                time.sleep(args.request_delay)
    finally:
        close_lookup_session(sock, reader, writer)

    print(f"Completed {completed} requests. Manifest: {manifest_path}")
    return 0


def test_connection(args: argparse.Namespace) -> int:
    if args.launch_iqconnect:
        launch_iqconnect(Path(args.iqconnect_path))
        if not wait_for_port(args.host, args.port, args.wait_seconds):
            print(f"IQConnect did not open {args.host}:{args.port}.")
            return 1

    try:
        sock, reader, writer, line = open_lookup_session(args)
    except ConnectionError as exc:
        print(f"Connection failed: {exc}")
        return 1

    try:
        print(line)
        return 0
    finally:
        writer.close()
        reader.close()
        sock.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sp500 = subparsers.add_parser("make-sp500-universe", help="Build current S&P 500 symbol CSV")
    sp500.add_argument("--source-url", default=SP500_CONSTITUENTS_URL)
    sp500.add_argument("--symbols-file", default=str(DEFAULT_SYMBOLS_FILE))
    sp500.add_argument("--output", default=str(DEFAULT_SP500_UNIVERSE_FILE))
    sp500.set_defaults(func=build_sp500_universe)

    universe = subparsers.add_parser("make-universe", help="Build a commodity futures symbol CSV")
    universe.add_argument("--symbols-file", default=str(DEFAULT_SYMBOLS_FILE))
    universe.add_argument("--output", default=str(DEFAULT_UNIVERSE_FILE))
    universe.add_argument(
        "--universe",
        choices=["frontmonth", "all-contracts", "contract-months-only", "all-futures"],
        default="frontmonth",
        help="frontmonth is the safest default for a first full tick run.",
    )
    universe.add_argument(
        "--exchanges",
        default=",".join(sorted(DEFAULT_COMMODITY_EXCHANGES)),
        help="Comma-separated exchange filter. Ignored with --all-exchanges.",
    )
    universe.add_argument("--all-exchanges", action="store_true")
    universe.add_argument("--include-financials", action="store_true")
    universe.add_argument("--limit", type=int)
    universe.set_defaults(func=build_universe)

    common_socket = argparse.ArgumentParser(add_help=False)
    common_socket.add_argument("--host", default="127.0.0.1")
    common_socket.add_argument("--port", type=int, default=9100)
    common_socket.add_argument("--timeout", type=float, default=120.0)
    common_socket.add_argument("--protocol", default="6.2")
    common_socket.add_argument("--launch-iqconnect", action="store_true")
    common_socket.add_argument("--iqconnect-path", default=str(DEFAULT_IQCONNECT))
    common_socket.add_argument("--wait-seconds", type=int, default=90)
    common_socket.add_argument(
        "--ensure-lookup",
        action="store_true",
        help="Run lib/ensure_iqfeed_lookup.sh before opening or reopening the lookup socket.",
    )
    common_socket.add_argument(
        "--connect-retries",
        type=int,
        default=0,
        help="Lookup-socket connection retries. Useful when IQConnect/Wine briefly drops port 9100.",
    )
    common_socket.add_argument(
        "--connect-retry-delay",
        type=float,
        default=5.0,
        help="Seconds between lookup-socket connection retries.",
    )
    common_socket.add_argument(
        "--keep-wine",
        action="store_true",
        help="Do not stop the IQFeed Wine prefix on exit when --ensure-lookup was used.",
    )

    intervals = subparsers.add_parser(
        "download-intervals", parents=[common_socket], help="Download historical interval OHLCV bars"
    )
    intervals.add_argument("--universe-file", default=str(DEFAULT_SP500_UNIVERSE_FILE))
    intervals.add_argument("--output-dir", default=str(DEFAULT_INTERVAL_OUTPUT_DIR))
    intervals.add_argument("--begin", default=os.environ.get("IQFEED_BEGIN", "20000101 000000"))
    intervals.add_argument("--end", default=os.environ.get("IQFEED_END", default_end()))
    intervals.add_argument("--interval-seconds", type=int, default=60)
    intervals.add_argument("--interval-type", choices=["s", "t", "v"], default="s")
    intervals.add_argument("--begin-filter", default="", help="HHMMSS session filter; blank includes all")
    intervals.add_argument("--end-filter", default="", help="HHMMSS session filter; blank includes all")
    intervals.add_argument("--direction", choices=["0", "1"], default="1", help="1 = oldest to newest")
    intervals.add_argument("--points-per-send", type=int, default=5000)
    intervals.add_argument("--max-datapoints", type=int)
    intervals.add_argument("--request-delay", type=float, default=0.1)
    intervals.add_argument("--retries", type=int, default=2, help="Per-symbol retry count")
    intervals.add_argument("--retry-delay", type=float, default=5.0, help="Seconds between retries")
    intervals.add_argument("--max-symbols", type=int)
    intervals.add_argument("--symbols", help="Comma-separated symbol override")
    intervals.add_argument("--exchanges", help="Comma-separated exchange filter")
    intervals.add_argument("--start-after", help="Resume after this symbol in the universe file")
    intervals.add_argument("--shard-count", type=int, default=1, help="Split selected universe into N shards")
    intervals.add_argument("--shard-index", type=int, default=0, help="Zero-based shard index to download")
    intervals.add_argument("--resume", action="store_true", help="Skip output files that already exist")
    intervals.add_argument("--group-by-exchange", action="store_true")
    intervals.add_argument("--header", dest="header", action="store_true", default=True)
    intervals.add_argument("--no-header", dest="header", action="store_false")
    intervals.add_argument("--volume-field", choices=["period", "total"], default="period")
    intervals.set_defaults(func=download_intervals)

    download = subparsers.add_parser(
        "download-ticks", parents=[common_socket], help="Download raw HTT tick history"
    )
    download.add_argument("--universe-file", default=str(DEFAULT_UNIVERSE_FILE))
    download.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    download.add_argument("--begin", default=os.environ.get("IQFEED_BEGIN", default_begin()))
    download.add_argument("--end", default=os.environ.get("IQFEED_END", default_end()))
    download.add_argument("--begin-filter", default="", help="HHMMSS session filter; blank includes all")
    download.add_argument("--end-filter", default="", help="HHMMSS session filter; blank includes all")
    download.add_argument("--direction", choices=["0", "1"], default="1", help="1 = oldest to newest")
    download.add_argument("--points-per-send", type=int, default=5000)
    download.add_argument("--max-datapoints", type=int)
    download.add_argument("--request-delay", type=float, default=0.05)
    download.add_argument("--retries", type=int, default=2, help="Per-symbol retry count")
    download.add_argument("--retry-delay", type=float, default=5.0, help="Seconds between retries")
    download.add_argument("--max-symbols", type=int)
    download.add_argument("--symbols", help="Comma-separated symbol override")
    download.add_argument("--exchanges", help="Comma-separated exchange filter")
    download.add_argument("--start-after", help="Resume after this symbol in the universe file")
    download.add_argument("--shard-count", type=int, default=1, help="Split selected universe into N shards")
    download.add_argument("--shard-index", type=int, default=0, help="Zero-based shard index to download")
    download.add_argument("--resume", action="store_true", help="Skip output files that already exist")
    download.add_argument("--gzip", dest="gzip", action="store_true", default=True)
    download.add_argument("--no-gzip", dest="gzip", action="store_false")
    download.set_defaults(func=download_ticks)

    test = subparsers.add_parser(
        "test-connection", parents=[common_socket], help="Verify IQConnect lookup socket"
    )
    test.set_defaults(func=test_connection)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "begin", None):
        args.begin = parse_iqfeed_datetime(args.begin)
    if getattr(args, "end", None):
        args.end = parse_iqfeed_datetime(args.end, end_of_day=True)

    try:
        return int(args.func(args) or 0)
    finally:
        cleanup_lookup_if_requested(args)


if __name__ == "__main__":
    raise SystemExit(main())
