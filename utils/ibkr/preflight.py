#!/usr/bin/env python3
"""IB Gateway paper-trading preflight.

This is Gateway-focused and places no orders. It validates the minimum runtime
requirements before the order-loop runner is started.
"""

import argparse
import sys

from utils.ibkr.common import DEFAULT_GATEWAY_PAPER_PORT, DEFAULT_HOST, LIVE_DATA_TYPE, managed_account_buckets, market_data_type_name


def _positive_number(value):
    return value if (value is not None and value == value and value > 0) else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IB Gateway paper preflight")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_GATEWAY_PAPER_PORT,
        help="4002=Gateway paper, 4001=Gateway live, 7497=TWS paper, 7496=TWS live",
    )
    parser.add_argument(
        "--client-id",
        type=int,
        default=99,
        help="Use a clientId the bot is not using; the bot default is 0",
    )
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument(
        "--data-wait",
        type=float,
        default=4.0,
        help="Seconds to wait for a streaming quote",
    )
    parser.add_argument(
        "--allow-live-account",
        action="store_true",
        help="Allow a live U... account for diagnostics. Default requires paper DU...",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    try:
        from ib_insync import IB, Stock
    except Exception as exc:  # noqa: BLE001
        print(f"NO-GO: cannot import ib_insync: {exc}")
        print("  -> Use Python 3.12 and install ib_gateway/requirements.txt")
        return 2

    ib = IB()
    api_errors = []

    def on_error(req_id, error_code, error_string, contract):
        api_errors.append(
            {
                "req_id": req_id,
                "code": error_code,
                "message": error_string,
                "contract": getattr(contract, "symbol", None),
            }
        )

    ib.errorEvent += on_error

    try:
        ib.connect(args.host, args.port, clientId=args.client_id, timeout=10)
    except Exception as exc:  # noqa: BLE001
        print(
            f"NO-GO: could not connect to {args.host}:{args.port} "
            f"(clientId={args.client_id}): {exc}"
        )
        print("  -> Start IB Gateway, log into paper, enable API sockets, and use port 4002.")
        return 2

    try:
        print(f"GO: connected to {args.host}:{args.port} (server v{ib.client.serverVersion()})")

        accounts = ib.managedAccounts()
        paper, live = managed_account_buckets(accounts)
        print(f"    accounts: {accounts or '(none)'}")
        if live and not paper and not args.allow_live_account:
            print("NO-GO: connected account looks live (U...), not paper (DU...).")
            return 2
        if paper:
            print(f"    paper account confirmed: {paper}")
        else:
            print("WARN: no paper account (DU...) detected.")

        ib.reqMarketDataType(LIVE_DATA_TYPE)
        contract = Stock(args.symbol, "SMART", "USD")
        try:
            ib.qualifyContracts(contract)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: could not qualify {args.symbol}: {exc}")

        ticker = ib.reqMktData(contract, "", snapshot=False)
        ib.sleep(args.data_wait)

        md_type = market_data_type_name(getattr(ticker, "marketDataType", None))
        bid = _positive_number(ticker.bid)
        ask = _positive_number(ticker.ask)
        print(f"    {args.symbol}: marketDataType={md_type} bid={ticker.bid} ask={ticker.ask}")

        go = True
        read_only_errors = [
            err for err in api_errors if "read-only" in err["message"].lower()
        ]
        market_data_errors = [
            err for err in api_errors if err["code"] in {354, 10089, 10167}
        ]
        if read_only_errors:
            print("NO-GO: Gateway API is in read-only mode. The bot cannot submit/cancel orders.")
            print("       Disable the read-only API setting before running the order loop.")
            go = False
        for err in market_data_errors:
            print(f"WARN: market-data API error {err['code']}: {err['message']}")
        if md_type != "LIVE":
            print("NO-GO: market data is not live. A market maker cannot use delayed quotes.")
            go = False
        if bid is None or ask is None:
            print("NO-GO: no valid two-sided quote arrived.")
            go = False

        ib.cancelMktData(contract)
        print("-" * 60)
        if go:
            print("RESULT: GO - paper Gateway connection + live quote verified.")
            return 0
        print("RESULT: NOT READY - resolve the NO-GO items before launching the bot.")
        return 1
    finally:
        if ib.isConnected():
            ib.disconnect()


if __name__ == "__main__":
    sys.exit(main())
