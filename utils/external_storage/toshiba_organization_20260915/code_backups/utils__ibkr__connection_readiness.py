#!/usr/bin/env python3
"""Non-ordering IBKR Gateway/TWS socket readiness report."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from utils.ibkr.common import DEFAULT_GATEWAY_LIVE_PORT, DEFAULT_GATEWAY_PAPER_PORT, DEFAULT_HOST, DEFAULT_TWS_LIVE_PORT, DEFAULT_TWS_PAPER_PORT, REPO_ROOT
from utils.data_paths import CONFIGURED_DATA_ROOT


SCHEMA = "ibkr_connection_readiness.v1"
DEFAULT_OUTPUT_JSON = CONFIGURED_DATA_ROOT / "ibkr" / "ibkr_connection_readiness_report.json"
DEFAULT_PORTS = (
    DEFAULT_GATEWAY_PAPER_PORT,
    DEFAULT_TWS_PAPER_PORT,
    DEFAULT_GATEWAY_LIVE_PORT,
    DEFAULT_TWS_LIVE_PORT,
)
PAPER_PORTS = frozenset({DEFAULT_GATEWAY_PAPER_PORT, DEFAULT_TWS_PAPER_PORT})
DEFAULT_JTS_LAUNCHER_LOG = Path.home() / "Jts" / "launcher.log"
IBKR_PROCESS_MARKERS = (
    "IB Gateway",
    "Trader Workstation",
    "JavaApplicationStub",
)
AUTH_FAILURE_MARKERS = (
    "Authorization failed",
    "Invalid username or password",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def probe_socket(host: str, port: int, *, timeout_seconds: float = 1.0) -> dict[str, Any]:
    try:
        with socket.create_connection((host, int(port)), timeout=float(timeout_seconds)):
            return {
                "host": host,
                "port": int(port),
                "reachable": True,
                "error_type": None,
                "error": None,
            }
    except OSError as exc:
        return {
            "host": host,
            "port": int(port),
            "reachable": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _collect_ibkr_processes() -> list[dict[str, Any]]:
    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid,etime,command"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines()[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        if not any(marker.lower() in stripped.lower() for marker in IBKR_PROCESS_MARKERS):
            continue
        parts = stripped.split(None, 2)
        if len(parts) < 3:
            continue
        pid, elapsed, command = parts
        rows.append(
            {
                "pid": int(pid) if pid.isdigit() else pid,
                "elapsed": elapsed,
                "command": command,
            }
        )
    return rows


def _recent_auth_failures(path: Path, *, max_lines: int = 500) -> list[dict[str, str]]:
    try:
        lines = Path(path).read_text(errors="ignore").splitlines()
    except OSError:
        return []
    failures: list[dict[str, str]] = []
    for line in lines[-max_lines:]:
        if not any(marker in line for marker in AUTH_FAILURE_MARKERS):
            continue
        timestamp = line[:23] if len(line) >= 23 and line[:4].isdigit() else ""
        failures.append(
            {
                "timestamp": timestamp,
                "message": line[-500:],
            }
        )
    return failures[-5:]


def build_connection_readiness_report(
    *,
    host: str = DEFAULT_HOST,
    ports: Iterable[int] = DEFAULT_PORTS,
    timeout_seconds: float = 1.0,
    generated_at_utc: str | None = None,
    jts_launcher_log: Path | None = DEFAULT_JTS_LAUNCHER_LOG,
    include_process_snapshot: bool = True,
) -> dict[str, Any]:
    probes = [
        probe_socket(host, int(port), timeout_seconds=timeout_seconds)
        for port in ports
    ]
    any_reachable = any(bool(probe["reachable"]) for probe in probes)
    paper_reachable = any(
        bool(probe["reachable"]) and int(probe["port"]) in PAPER_PORTS
        for probe in probes
    )
    blockers: list[str] = []
    if not any_reachable:
        blockers.append("ibkr_any_api_socket_not_reachable")
    if not paper_reachable:
        blockers.append("ibkr_paper_api_socket_not_reachable")
    process_snapshot = _collect_ibkr_processes() if include_process_snapshot else []
    auth_failures = _recent_auth_failures(jts_launcher_log) if jts_launcher_log else []
    if process_snapshot and not any_reachable:
        blockers.append("ibkr_process_present_but_api_listener_closed")
    auth_failure_blocking = bool(auth_failures and not any_reachable)
    if auth_failure_blocking:
        blockers.append("ibkr_gateway_recent_auth_failure")
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at_utc or _utc_now(),
        "host": host,
        "ports": [int(port) for port in ports],
        "timeout_seconds": float(timeout_seconds),
        "probes": probes,
        "any_api_socket_reachable": any_reachable,
        "paper_api_socket_reachable": paper_reachable,
        "connection_ready_for_capture": any_reachable,
        "connection_ready_for_paper_validation": paper_reachable,
        "ibkr_process_count": len(process_snapshot),
        "ibkr_processes": process_snapshot,
        "jts_launcher_log": str(jts_launcher_log) if jts_launcher_log else None,
        "recent_gateway_auth_failures": auth_failures,
        "recent_gateway_auth_failure_blocking": auth_failure_blocking,
        "promotion_blockers": blockers,
        "rule": (
            "This report only checks local API socket reachability. A reachable "
            "socket is necessary but not sufficient: market-data permissions, "
            "account mode, quote subscriptions, and actual non-header event rows "
            "must still be proven by capture and execution manifests. Process "
            "and launcher-log diagnostics are explanatory evidence only; socket "
            "reachability remains the readiness gate."
        ),
    }


def _parse_ports(value: str) -> tuple[int, ...]:
    ports = tuple(int(part.strip()) for part in str(value).split(",") if part.strip())
    if not ports:
        raise ValueError("at least one port is required")
    return ports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check local IBKR Gateway/TWS API socket readiness")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument(
        "--ports",
        default=",".join(str(port) for port in DEFAULT_PORTS),
        help="Comma-separated ports to probe.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=1.0)
    parser.add_argument("--jts-launcher-log", type=Path, default=DEFAULT_JTS_LAUNCHER_LOG)
    parser.add_argument(
        "--no-process-snapshot",
        action="store_true",
        help="Skip local process-table diagnostics.",
    )
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_connection_readiness_report(
        host=args.host,
        ports=_parse_ports(args.ports),
        timeout_seconds=args.timeout_seconds,
        jts_launcher_log=args.jts_launcher_log,
        include_process_snapshot=not args.no_process_snapshot,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.output_json}")
    print(
        json.dumps(
            {
                "any_api_socket_reachable": report["any_api_socket_reachable"],
                "paper_api_socket_reachable": report["paper_api_socket_reachable"],
                "promotion_blockers": report["promotion_blockers"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
