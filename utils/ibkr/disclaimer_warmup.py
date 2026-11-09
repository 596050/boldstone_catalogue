#!/usr/bin/env python3
"""Trigger and clear the one-time IBKR paper "disclaimer must be accepted"
dialog (API error 10141) BEFORE the real model runner connects.

Why this exists
---------------
On the first API connection after a fresh Gateway login, IBKR raises::

    Error 10141: Paper trading disclaimer must first be accepted for API
    connection.

IBC dismisses that GUI dialog from inside the Gateway JVM (no macOS
Accessibility/TCC permission needed). But there is a race: whichever process
connects *first* eats the 10141 rejection. This script is a deliberate,
throwaway "warm-up" connection whose only job is to be that first connection:
it tolerates 10141, gives IBC a moment to click the dialog away, and retries
until a clean, fully-synchronised read-only session is achieved. After it
succeeds, the real runner's first connection no longer hits 10141.

It NEVER places, modifies, or cancels an order (read-only session), and it
verifies the connected account is the expected DU/DUK paper account.

Exit codes: 0 = API is clean and ready; 1 = still blocked/unhealthy.
"""
from __future__ import annotations

import argparse
import asyncio
import subprocess
import time
from pathlib import Path


asyncio.set_event_loop(asyncio.new_event_loop())  # Python 3.14 + ib_insync compatibility

DEFAULT_EXPECTED_ACCOUNT = "DUK193810"
DEFAULT_DIALOG_HANDLER_APP = Path(__file__).resolve().parents[2] / ".runtime/ibkr/IBGatewayPaperDisclaimerHandler.app"
# IBKR API error codes that mean "a one-time dialog is blocking the API and
# should clear on its own once IBC (or an operator) accepts it".
TRANSIENT_DIALOG_ERROR_CODES = {10141, 10148, 10187, 2103, 2105, 2157}


def _log(msg: str) -> None:
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} ib_gateway_warmup: {msg}", flush=True)


def _invoke_dialog_handler(app: Path | None) -> None:
    """Run the narrowly-scoped AppleScript app if installed and authorised."""
    if app is None or not app.exists():
        return
    try:
        subprocess.run(
            ["/usr/bin/open", "-gja", str(app)],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        _log(f"invoked AppleScript fallback app: {app}")
    except (OSError, subprocess.TimeoutExpired) as exc:
        _log(f"AppleScript fallback launch failed: {exc}")


def warm_up(
    host: str,
    port: int,
    expected_account: str,
    deadline_seconds: float,
    base_client_id: int,
    dialog_handler_app: Path | None = DEFAULT_DIALOG_HANDLER_APP,
) -> int:
    try:
        from ib_insync import IB
    except Exception as exc:  # pragma: no cover - environment guard
        _log(f"cannot import ib_insync: {exc}")
        return 1

    deadline = time.monotonic() + max(deadline_seconds, 5.0)
    attempt = 0
    last_error = "no attempt made"
    while time.monotonic() < deadline:
        attempt += 1
        # Vary the clientId so a lingering half-open session never blocks us.
        client_id = base_client_id + (attempt % 40)
        ib = IB()
        seen_codes: set[int] = set()

        def _on_error(reqId, errorCode, errorString, contract=None):  # noqa: ANN001
            seen_codes.add(int(errorCode))
            if int(errorCode) in TRANSIENT_DIALOG_ERROR_CODES:
                _log(f"transient dialog/info code {errorCode}: {errorString!r} (IBC should clear it)")

        try:
            ib.errorEvent += _on_error
            ib.connect(host, port, clientId=client_id, timeout=15, readonly=True)
            ib.sleep(1.0)
            accounts = list(ib.managedAccounts() or [])
            server_time = ib.reqCurrentTime()
            if accounts and expected_account in accounts and server_time is not None:
                _log(f"API clean: accounts={accounts} server_time={server_time} attempt={attempt}")
                return 0
            if accounts and expected_account not in accounts:
                last_error = f"connected but expected {expected_account!r} not in {accounts}"
                _log(last_error)
                return 1  # wrong account is not self-healing; do not spin
            last_error = f"connected but no account list yet (codes={sorted(seen_codes)})"
        except Exception as exc:  # noqa: BLE001 - report and retry
            last_error = f"{type(exc).__name__}: {exc} (codes={sorted(seen_codes)})"
            _log(f"attempt {attempt} not ready: {last_error}")
            # IBC is the primary handler. The app is only a fallback and its
            # own script refuses to click anything except a paper/simulated
            # disclaimer with an explicitly allow-listed affirmative button.
            _invoke_dialog_handler(dialog_handler_app)
        finally:
            try:
                if ib.isConnected():
                    ib.disconnect()
            except Exception:  # noqa: BLE001
                pass
        time.sleep(2.0)
    _log(f"gave up after {attempt} attempts: {last_error}")
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=4002)
    ap.add_argument("--expected-account", default=DEFAULT_EXPECTED_ACCOUNT)
    ap.add_argument("--deadline-seconds", type=float, default=90.0)
    ap.add_argument("--base-client-id", type=int, default=700)
    ap.add_argument(
        "--dialog-handler-app",
        type=Path,
        default=DEFAULT_DIALOG_HANDLER_APP,
        help="Optional compiled AppleScript fallback app; ignored if absent.",
    )
    args = ap.parse_args(argv)
    return warm_up(
        args.host,
        args.port,
        args.expected_account,
        args.deadline_seconds,
        args.base_client_id,
        args.dialog_handler_app,
    )


if __name__ == "__main__":
    raise SystemExit(main())
