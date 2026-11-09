#!/usr/bin/env python3
"""Safe IBKR connectivity check — connects, confirms the (paper) account, lists
managed accounts + open positions, then disconnects. Places NO orders.

Run with the project venv once TWS/Gateway has the API enabled:
    PYTHONPATH=. .venv/bin/python check_ibkr.py --port 7497        # TWS paper
    PYTHONPATH=. .venv/bin/python check_ibkr.py --port 4002        # Gateway paper
"""
import argparse
import asyncio

asyncio.set_event_loop(asyncio.new_event_loop())  # Python 3.14 + ib_insync compat

import ib_insync  # noqa: E402,F401
from utils.trading.main import connect_to_ib  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7497, help="TWS paper=7497, Gateway paper=4002")
    ap.add_argument("--client-id", type=int, default=9)
    args = ap.parse_args()

    ib = connect_to_ib(args.host, args.port, args.client_id)
    if not ib:
        print(f"NOT CONNECTED to {args.host}:{args.port} — is the API enabled and are you logged in?")
        return 1
    try:
        accounts = ib.managedAccounts()
        paper = [a for a in accounts if a.startswith("DU")]
        print(f"CONNECTED to {args.host}:{args.port}")
        print(f"  managed accounts : {accounts}")
        print(f"  paper (DU...)    : {paper or '(none — this looks LIVE)'}")
        positions = ib.positions()
        if positions:
            print("  open positions   :")
            for p in positions:
                print(f"    {p.contract.symbol:6s} {p.position:+g} @ avgCost {p.avgCost}")
        else:
            print("  open positions   : (flat)")
    finally:
        ib.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
