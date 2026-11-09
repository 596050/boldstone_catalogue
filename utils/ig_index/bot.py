import argparse
import json
import sys
import time

from utils.ig_index.client import IGCredentials, IGRestClient
from utils.ig_index.models import PositionState, TradeDecision
from utils.ig_index.risk import IGRiskManager, RiskSettings
from utils.ig_index.strategy import SpreadAwareIGStrategy, StrategySettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IG spread-aware directional strategy runner")
    parser.add_argument("--epic", required=True, help="IG market EPIC, e.g. IX.D.FTSE.CFD.IP")
    parser.add_argument("--currency-code", default="GBP")
    parser.add_argument("--expiry", default="-")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--live-orders", action="store_true",
                        help="Actually send IG orders. Default is dry-run.")

    parser.add_argument("--trade-size", type=float, default=1.0)
    parser.add_argument("--max-abs-position", type=float, default=1.0)
    parser.add_argument("--min-samples", type=int, default=20)
    parser.add_argument("--min-edge-points", type=float, default=1.0)
    parser.add_argument("--max-spread-points", type=float, default=5.0)
    parser.add_argument("--stop-loss-points", type=float, default=20.0)
    parser.add_argument("--take-profit-points", type=float, default=10.0)
    return parser


def decision_to_payload(decision: TradeDecision, position: PositionState) -> dict:
    if decision.action == "OPEN_LONG":
        return {"direction": "BUY"}
    if decision.action == "OPEN_SHORT":
        return {"direction": "SELL"}
    if decision.action == "CLOSE_LONG":
        return {"deal_id": position.deal_id, "direction": "SELL"}
    if decision.action == "CLOSE_SHORT":
        return {"deal_id": position.deal_id, "direction": "BUY"}
    return {}


def print_event(event: dict) -> None:
    print(json.dumps(event, sort_keys=True))


def execute_decision(
    *,
    client: IGRestClient,
    args: argparse.Namespace,
    decision: TradeDecision,
    position: PositionState,
) -> None:
    if decision.action == "HOLD":
        return

    payload = decision_to_payload(decision, position)
    if not args.live_orders:
        print_event({"mode": "dry_run", "would_send": payload, "decision": decision.action})
        return

    if decision.opens_position:
        result = client.create_otc_position(
            epic=args.epic,
            direction=payload["direction"],
            size=decision.size,
            currency_code=args.currency_code,
            expiry=args.expiry,
        )
        print_event({"mode": "live", "order_result": result})
        return

    if decision.closes_position:
        if not payload.get("deal_id"):
            raise RuntimeError("Cannot close IG position without a deal_id")
        result = client.close_otc_position(
            deal_id=payload["deal_id"],
            direction=payload["direction"],
            size=decision.size,
        )
        print_event({"mode": "live", "order_result": result})


def run(args: argparse.Namespace) -> int:
    credentials = IGCredentials.from_env()
    client = IGRestClient(credentials)
    strategy = SpreadAwareIGStrategy(
        StrategySettings(
            trade_size=args.trade_size,
            max_abs_position=args.max_abs_position,
            min_samples=args.min_samples,
            min_edge_points=args.min_edge_points,
            stop_loss_points=args.stop_loss_points,
            take_profit_points=args.take_profit_points,
        )
    )
    risk = IGRiskManager(
        RiskSettings(
            max_spread_points=args.max_spread_points,
            max_abs_position=args.max_abs_position,
            max_trade_size=args.trade_size,
        )
    )

    client.login()
    try:
        while True:
            quote = client.get_market_quote(args.epic)
            position = client.find_position(args.epic)
            decision = strategy.on_quote(quote, position)
            risk_check = risk.check(quote, position, decision)

            print_event(
                {
                    "epic": args.epic,
                    "bid": quote.bid,
                    "offer": quote.offer,
                    "spread": quote.spread,
                    "status": quote.status,
                    "position": position.direction,
                    "position_size": position.size,
                    "decision": decision.action,
                    "reason": decision.reason,
                    "risk_accepted": risk_check.accepted,
                    "risk_reason": risk_check.reason,
                    "metadata": decision.metadata,
                }
            )

            if risk_check.accepted:
                execute_decision(
                    client=client,
                    args=args,
                    decision=decision,
                    position=position,
                )

            if args.once:
                break
            time.sleep(args.poll_seconds)
    finally:
        client.logout()
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

