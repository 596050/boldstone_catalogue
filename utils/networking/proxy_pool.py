#!/usr/bin/env python3
"""
proxy_pool.py -- Comprehensive proxy fetcher and validator.

Fetches HTTP/HTTPS/SOCKS5 proxies from multiple public sources AND
authenticated proxies from Webshare.io (via API key in .env), deduplicates
them, optionally validates each one, and persists the pool to disk as JSON.

Library usage:
    from utils.networking.proxy_pool import configure, fetch_all_sources, deduplicate, validate_proxies, save_pool

    configure(pool_path="/path/to/proxy_pool.json")
    raw = fetch_all_sources()
    proxies = deduplicate(raw)
    proxies = validate_proxies(proxies)
    save_pool(proxies, len(raw))

CLI usage:
    python -m utils.networking.proxy_pool fetch --state-dir /path/to/state [--validate]
    python -m utils.networking.proxy_pool validate --state-dir /path/to/state
    python -m utils.networking.proxy_pool refresh --state-dir /path/to/state
    python -m utils.networking.proxy_pool status --state-dir /path/to/state

Dependencies: requests, python-dotenv (only stdlib + these two)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from dotenv import load_dotenv

# Load .env — search upward from CWD
load_dotenv()

# ---------------------------------------------------------------------------
# Configurable module-level defaults
# ---------------------------------------------------------------------------

_default_pool_path: Path | None = None
_default_log_path: Path | None = None


def configure(
    pool_path: str | Path | None = None,
    log_path: str | Path | None = None,
) -> None:
    """Set module-level default paths.

    Call this before using save_pool/load_pool/CLI commands if you don't want
    to pass pool_path explicitly every time.
    """
    global _default_pool_path, _default_log_path
    if pool_path is not None:
        _default_pool_path = Path(pool_path)
    if log_path is not None:
        _default_log_path = Path(log_path)
        _add_file_handler(_default_log_path)


def _resolve_pool_path(pool_path: str | Path | None = None) -> Path:
    """Resolve pool_path from argument or module default."""
    if pool_path is not None:
        return Path(pool_path)
    if _default_pool_path is not None:
        return _default_pool_path
    raise ValueError(
        "pool_path required — pass it explicitly or call configure(pool_path=...)"
    )


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger("proxy_pool")

def _setup_console_logging() -> None:
    """Add a console handler (INFO+) if none exist yet."""
    if log.handlers:
        return
    log.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    log.addHandler(ch)

_setup_console_logging()


def _add_file_handler(log_path: Path) -> None:
    """Add a file handler (DEBUG+) to the module logger."""
    # Don't add duplicate file handlers to the same path
    for h in log.handlers:
        if isinstance(h, logging.FileHandler) and Path(h.baseFilename) == log_path.resolve():
            return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = logging.FileHandler(str(log_path), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    log.addHandler(fh)


# ---------------------------------------------------------------------------
# Type alias for a proxy record
# ---------------------------------------------------------------------------
ProxyRecord = Dict[str, Any]

# Regex: match ip:port (IPv4 only)
_IP_PORT_RE = re.compile(
    r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5})"
)

# Common request headers to look like a normal client
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,text/plain,*/*",
}

# ---------------------------------------------------------------------------
# Individual source fetchers
# ---------------------------------------------------------------------------

def _get(url: str, timeout: int = 15) -> str:
    """Perform a GET with standard headers and return response text."""
    resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _parse_plain_list(text: str) -> List[Tuple[str, int]]:
    """Extract (host, port) pairs from plain text containing ip:port lines."""
    results: List[Tuple[str, int]] = []
    for m in _IP_PORT_RE.finditer(text):
        host = m.group(1)
        port = int(m.group(2))
        if 1 <= port <= 65535:
            results.append((host, port))
    return results


def _make_record(
    host: str,
    port: int,
    protocol: str,
    source: str,
    valid: Optional[bool] = None,
    response_ms: Optional[int] = None,
    checked_at: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    country: Optional[str] = None,
) -> ProxyRecord:
    """Build a proxy record dictionary."""
    rec: ProxyRecord = {
        "host": host,
        "port": port,
        "protocol": protocol,
        "source": source,
        "valid": valid,
        "response_ms": response_ms,
        "checked_at": checked_at,
    }
    if username:
        rec["username"] = username
        rec["password"] = password
    if country:
        rec["country"] = country
    return rec


# -- proxyscrape.com --------------------------------------------------------

def fetch_proxyscrape() -> List[ProxyRecord]:
    """Fetch from proxyscrape.com API (http/https mixed)."""
    url = (
        "https://api.proxyscrape.com/v2/"
        "?request=displayproxies&protocol=http"
        "&timeout=10000&country=all&ssl=all&anonymity=all"
    )
    text = _get(url)
    pairs = _parse_plain_list(text)
    log.info("proxyscrape: fetched %d proxies", len(pairs))
    return [_make_record(h, p, "http", "proxyscrape") for h, p in pairs]


# -- geonode.com ------------------------------------------------------------

def fetch_geonode() -> List[ProxyRecord]:
    """Fetch from geonode.com JSON API."""
    url = (
        "https://proxylist.geonode.com/api/proxy-list"
        "?limit=500&page=1&sort_by=lastChecked&sort_type=desc"
    )
    text = _get(url)
    data = json.loads(text)
    proxies: List[ProxyRecord] = []
    for entry in data.get("data", []):
        host = entry.get("ip", "").strip()
        port_str = entry.get("port", "")
        protocols = entry.get("protocols", [])
        if not host or not port_str:
            continue
        try:
            port = int(port_str)
        except (ValueError, TypeError):
            continue
        proto = "http"
        if protocols:
            proto = protocols[0].lower()
            if proto not in ("http", "https", "socks5"):
                proto = "http"
        proxies.append(_make_record(host, port, proto, "geonode"))
    log.info("geonode: fetched %d proxies", len(proxies))
    return proxies


# -- free-proxy-list.net ----------------------------------------------------

def fetch_free_proxy_list_net() -> List[ProxyRecord]:
    """Scrape free-proxy-list.net via regex (no BeautifulSoup dependency)."""
    url = "https://free-proxy-list.net/"
    text = _get(url)

    # Strategy 1: look for a <textarea> blob with ip:port lines
    textarea_match = re.search(
        r"<textarea[^>]*>(.*?)</textarea>", text, re.DOTALL
    )
    if textarea_match:
        pairs = _parse_plain_list(textarea_match.group(1))
        if pairs:
            log.info(
                "free-proxy-list.net (textarea): fetched %d proxies",
                len(pairs),
            )
            return [
                _make_record(h, p, "http", "free-proxy-list.net")
                for h, p in pairs
            ]

    # Strategy 2: parse HTML table rows -- <td>IP</td><td>Port</td>
    row_re = re.compile(
        r"<tr[^>]*>\s*<td>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</td>"
        r"\s*<td>(\d{2,5})</td>",
        re.DOTALL,
    )
    pairs_list: List[Tuple[str, int]] = []
    for m in row_re.finditer(text):
        host = m.group(1)
        port = int(m.group(2))
        if 1 <= port <= 65535:
            pairs_list.append((host, port))

    # Strategy 3: fallback -- just grab any ip:port on the page
    if not pairs_list:
        pairs_list = _parse_plain_list(text)

    log.info("free-proxy-list.net: fetched %d proxies", len(pairs_list))
    return [
        _make_record(h, p, "http", "free-proxy-list.net")
        for h, p in pairs_list
    ]


# -- GitHub raw lists (simple text) -----------------------------------------

def _fetch_github_raw(
    url: str, protocol: str, source: str
) -> List[ProxyRecord]:
    """Generic fetcher for raw GitHub text proxy lists."""
    text = _get(url)
    pairs = _parse_plain_list(text)
    log.info("%s: fetched %d proxies", source, len(pairs))
    return [_make_record(h, p, protocol, source) for h, p in pairs]


def fetch_thespeedx_http() -> List[ProxyRecord]:
    return _fetch_github_raw(
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "http",
        "thespeedx-http",
    )


def fetch_thespeedx_https() -> List[ProxyRecord]:
    return _fetch_github_raw(
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/https.txt",
        "https",
        "thespeedx-https",
    )


def fetch_thespeedx_socks5() -> List[ProxyRecord]:
    return _fetch_github_raw(
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "socks5",
        "thespeedx-socks5",
    )


def fetch_clarketm() -> List[ProxyRecord]:
    """clarketm format: 'IP:Port COUNTRY ANON ...' per line -- extract IP:Port."""
    url = (
        "https://raw.githubusercontent.com/clarketm/"
        "proxy-list/master/proxy-list-raw.txt"
    )
    text = _get(url)
    pairs = _parse_plain_list(text)
    log.info("clarketm: fetched %d proxies", len(pairs))
    return [_make_record(h, p, "http", "clarketm") for h, p in pairs]


def fetch_shiftytr() -> List[ProxyRecord]:
    return _fetch_github_raw(
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "http",
        "shiftytr",
    )


def fetch_monosans_http() -> List[ProxyRecord]:
    return _fetch_github_raw(
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "http",
        "monosans-http",
    )


def fetch_monosans_https() -> List[ProxyRecord]:
    return _fetch_github_raw(
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/https.txt",
        "https",
        "monosans-https",
    )


def fetch_monosans_socks5() -> List[ProxyRecord]:
    return _fetch_github_raw(
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "socks5",
        "monosans-socks5",
    )


# -- proxy-list.download ---------------------------------------------------

def fetch_proxy_list_download() -> List[ProxyRecord]:
    return _fetch_github_raw(
        "https://www.proxy-list.download/api/v1/get?type=http",
        "http",
        "proxy-list-download",
    )


# -- openproxylist.xyz ------------------------------------------------------

def fetch_openproxylist() -> List[ProxyRecord]:
    return _fetch_github_raw(
        "https://openproxylist.xyz/http.txt",
        "http",
        "openproxylist",
    )


# -- webshare.io (authenticated, from .env) --------------------------------

def fetch_webshare() -> List[ProxyRecord]:
    """Fetch authenticated proxies from Webshare.io API.

    Reads WEB_SHARE_API_KEY from .env. Returns empty list if key is missing.
    Paginates through all available proxies.
    """
    api_key = os.environ.get("WEB_SHARE_API_KEY", "").strip().strip("'\"")
    if not api_key:
        log.debug("WEB_SHARE_API_KEY not set, skipping webshare")
        return []

    proxies: List[ProxyRecord] = []
    page = 1
    page_size = 100

    while True:
        url = (
            f"https://proxy.webshare.io/api/v2/proxy/list/"
            f"?mode=direct&page={page}&page_size={page_size}"
        )
        resp = requests.get(
            url,
            headers={"Authorization": f"Token {api_key}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        for entry in data.get("results", []):
            host = entry.get("proxy_address", "").strip()
            port = entry.get("port")
            uname = entry.get("username", "")
            pwd = entry.get("password", "")
            country = entry.get("country_code", "")
            if not host or not port:
                continue
            proxies.append(_make_record(
                host, int(port), "http", "webshare",
                username=uname, password=pwd, country=country,
            ))

        # Check for next page
        if data.get("next"):
            page += 1
        else:
            break

    log.info("webshare: fetched %d authenticated proxies", len(proxies))
    return proxies


# ---------------------------------------------------------------------------
# Registry of all source fetchers
# ---------------------------------------------------------------------------

ALL_FETCHERS = [
    fetch_webshare,
    fetch_proxyscrape,
    fetch_geonode,
    fetch_free_proxy_list_net,
    fetch_thespeedx_http,
    fetch_thespeedx_https,
    fetch_thespeedx_socks5,
    fetch_clarketm,
    fetch_shiftytr,
    fetch_monosans_http,
    fetch_monosans_https,
    fetch_monosans_socks5,
    fetch_proxy_list_download,
    fetch_openproxylist,
]

# ---------------------------------------------------------------------------
# Concurrent fetching from all sources
# ---------------------------------------------------------------------------

def fetch_all_sources(max_workers: int = 10) -> List[ProxyRecord]:
    """Fetch proxies from every registered source concurrently.

    Each failing source is logged as a warning and silently skipped.
    Returns the combined (not yet deduplicated) list.
    """
    all_proxies: List[ProxyRecord] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_name = {
            pool.submit(fn): fn.__name__ for fn in ALL_FETCHERS
        }
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                result = future.result()
                all_proxies.extend(result)
            except Exception as exc:
                log.warning("Source %s failed: %s", name, exc)

    log.info("Total fetched (before dedup): %d", len(all_proxies))
    return all_proxies


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate(proxies: List[ProxyRecord]) -> List[ProxyRecord]:
    """Remove duplicates by host:port, keeping the first occurrence."""
    seen: Set[str] = set()
    unique: List[ProxyRecord] = []
    for rec in proxies:
        key = f"{rec['host']}:{rec['port']}"
        if key not in seen:
            seen.add(key)
            unique.append(rec)
    log.info("After dedup: %d unique proxies", len(unique))
    return unique


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_one(proxy: ProxyRecord, timeout: int) -> ProxyRecord:
    """Test a single proxy against httpbin and update the record in-place."""
    host = proxy["host"]
    port = proxy["port"]
    protocol = proxy["protocol"]

    # Build the proxy URL for the requests library
    uname = proxy.get("username", "")
    pwd = proxy.get("password", "")
    auth_prefix = f"{uname}:{pwd}@" if uname else ""

    if protocol == "socks5":
        proxy_url = f"socks5h://{auth_prefix}{host}:{port}"
    else:
        proxy_url = f"http://{auth_prefix}{host}:{port}"

    proxies_dict = {
        "http": proxy_url,
        "https": proxy_url,
    }

    now_iso = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()
    try:
        resp = requests.get(
            "http://httpbin.org/ip",
            proxies=proxies_dict,
            timeout=timeout,
            headers=_HEADERS,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if resp.status_code == 200:
            proxy["valid"] = True
            proxy["response_ms"] = elapsed_ms
        else:
            proxy["valid"] = False
            proxy["response_ms"] = elapsed_ms
    except Exception:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        proxy["valid"] = False
        proxy["response_ms"] = elapsed_ms

    proxy["checked_at"] = now_iso
    return proxy


def validate_proxies(
    proxies: List[ProxyRecord],
    workers: int = 50,
    timeout: int = 5,
) -> List[ProxyRecord]:
    """Validate a list of proxies concurrently.

    Updates each record's valid / response_ms / checked_at fields.
    Returns the full list (both valid and invalid).
    """
    total = len(proxies)
    log.info(
        "Validating %d proxies with %d workers (timeout=%ds)...",
        total, workers, timeout,
    )

    validated = 0
    valid_count = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_validate_one, p, timeout): p for p in proxies
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                validated += 1
                if result.get("valid"):
                    valid_count += 1
                if validated % 100 == 0 or validated == total:
                    log.info(
                        "  validated %d/%d  (valid so far: %d)",
                        validated, total, valid_count,
                    )
            except Exception as exc:
                validated += 1
                log.debug("Validation worker error: %s", exc)

    log.info("Validation complete: %d valid out of %d", valid_count, total)
    return proxies


# ---------------------------------------------------------------------------
# Metadata / stats helpers
# ---------------------------------------------------------------------------

def _compute_metadata(
    total_fetched: int,
    proxies: List[ProxyRecord],
) -> Dict[str, Any]:
    """Compute summary statistics from the proxy list."""
    by_source: Dict[str, int] = {}
    by_protocol: Dict[str, int] = {}
    valid_count = 0

    for p in proxies:
        src = p.get("source", "unknown")
        by_source[src] = by_source.get(src, 0) + 1
        proto = p.get("protocol", "http")
        by_protocol[proto] = by_protocol.get(proto, 0) + 1
        if p.get("valid") is True:
            valid_count += 1

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_fetched": total_fetched,
        "unique": len(proxies),
        "validated": valid_count,
        "by_source": dict(sorted(by_source.items())),
        "by_protocol": dict(sorted(by_protocol.items())),
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_pool(
    proxies: List[ProxyRecord],
    total_fetched: int,
    pool_path: str | Path | None = None,
) -> Path:
    """Write the proxy pool to disk as JSON."""
    path = _resolve_pool_path(pool_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    metadata = _compute_metadata(total_fetched, proxies)
    payload = {
        "metadata": metadata,
        "proxies": proxies,
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("Pool saved to %s  (%d proxies)", path, len(proxies))
    return path


def load_pool(pool_path: str | Path | None = None) -> Optional[Dict[str, Any]]:
    """Load existing pool from disk. Returns None if file missing/corrupt."""
    path = _resolve_pool_path(pool_path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Failed to load pool from %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_fetch(
    validate: bool = False,
    workers: int = 50,
    timeout: int = 5,
    pool_path: str | Path | None = None,
) -> None:
    """Fetch from all sources, deduplicate, optionally validate, and save."""
    raw = fetch_all_sources()
    total_fetched = len(raw)
    proxies = deduplicate(raw)

    if validate:
        proxies = validate_proxies(proxies, workers=workers, timeout=timeout)

    path = save_pool(proxies, total_fetched, pool_path=pool_path)
    meta = _compute_metadata(total_fetched, proxies)
    _print_stats(meta)


def cmd_validate(
    workers: int = 50,
    timeout: int = 5,
    pool_path: str | Path | None = None,
) -> None:
    """Validate the existing pool on disk."""
    pool_data = load_pool(pool_path)
    if pool_data is None:
        path = _resolve_pool_path(pool_path)
        log.error("No existing pool found at %s. Run 'fetch' first.", path)
        sys.exit(1)

    proxies: List[ProxyRecord] = pool_data.get("proxies", [])
    if not proxies:
        log.error("Pool file exists but contains no proxies.")
        sys.exit(1)

    log.info("Loaded %d proxies from disk for validation.", len(proxies))
    proxies = validate_proxies(proxies, workers=workers, timeout=timeout)

    total_fetched = pool_data.get("metadata", {}).get(
        "total_fetched", len(proxies)
    )
    save_pool(proxies, total_fetched, pool_path=pool_path)
    meta = _compute_metadata(total_fetched, proxies)
    _print_stats(meta)


def cmd_status(pool_path: str | Path | None = None) -> None:
    """Print current pool statistics."""
    pool_data = load_pool(pool_path)
    if pool_data is None:
        path = _resolve_pool_path(pool_path)
        print(f"No proxy pool found at {path}")
        return

    meta = pool_data.get("metadata", {})
    proxies = pool_data.get("proxies", [])

    # Recompute stats from the actual proxy list in case metadata is stale
    live_meta = _compute_metadata(
        meta.get("total_fetched", len(proxies)),
        proxies,
    )
    # Preserve original fetched_at timestamp
    live_meta["fetched_at"] = meta.get("fetched_at", live_meta["fetched_at"])
    _print_stats(live_meta)


def _print_stats(meta: Dict[str, Any]) -> None:
    """Pretty-print pool statistics to the console."""
    print()
    print("=" * 56)
    print("  PROXY POOL STATUS")
    print("=" * 56)
    print(f"  Fetched at    : {meta.get('fetched_at', 'N/A')}")
    print(f"  Total fetched : {meta.get('total_fetched', 'N/A')}")
    print(f"  Unique        : {meta.get('unique', 'N/A')}")
    print(f"  Validated     : {meta.get('validated', 'N/A')}")
    print("-" * 56)
    print("  By source:")
    for src, count in sorted(meta.get("by_source", {}).items()):
        print(f"    {src:30s} {count:>6d}")
    print("-" * 56)
    print("  By protocol:")
    for proto, count in sorted(meta.get("by_protocol", {}).items()):
        print(f"    {proto:30s} {count:>6d}")
    print("=" * 56)
    print()


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proxy_pool",
        description=(
            "Fetch, validate and manage a pool of free "
            "HTTP/HTTPS/SOCKS5 proxies."
        ),
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help="Directory for proxy_pool.json and proxy_pool.log",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # -- fetch
    p_fetch = sub.add_parser("fetch", help="Fetch proxies from all sources")
    p_fetch.add_argument(
        "--validate",
        action="store_true",
        help="Also validate each fetched proxy",
    )
    p_fetch.add_argument(
        "--workers",
        type=int,
        default=50,
        help="Number of concurrent validation workers (default: 50)",
    )
    p_fetch.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Validation timeout in seconds (default: 5)",
    )

    # -- validate
    p_val = sub.add_parser(
        "validate", help="Validate the existing proxy pool on disk"
    )
    p_val.add_argument(
        "--workers",
        type=int,
        default=50,
        help="Number of concurrent validation workers (default: 50)",
    )
    p_val.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Validation timeout in seconds (default: 5)",
    )

    # -- refresh
    p_ref = sub.add_parser(
        "refresh", help="Fetch + validate (replace entire pool)"
    )
    p_ref.add_argument(
        "--workers",
        type=int,
        default=50,
        help="Number of concurrent validation workers (default: 50)",
    )
    p_ref.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Validation timeout in seconds (default: 5)",
    )

    # -- status
    sub.add_parser("status", help="Show current pool statistics")

    return parser


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Configure paths from --state-dir
    if args.state_dir:
        configure(
            pool_path=args.state_dir / "proxy_pool.json",
            log_path=args.state_dir / "proxy_pool.log",
        )

    if args.command == "fetch":
        cmd_fetch(
            validate=args.validate,
            workers=args.workers,
            timeout=args.timeout,
        )
    elif args.command == "validate":
        cmd_validate(workers=args.workers, timeout=args.timeout)
    elif args.command == "refresh":
        cmd_fetch(
            validate=True, workers=args.workers, timeout=args.timeout
        )
    elif args.command == "status":
        cmd_status()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
