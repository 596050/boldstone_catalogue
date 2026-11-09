"""Plan/reconcile the complete named model book; demo execution is explicit.

This interface uses the existing frozen target-to-intent planner with only
model-owned holdings. Both the completed plan and each fresh entry must fit
the declared gross/margin allocation; no favourable partial basket is selected.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, replace
from pathlib import Path

import research  # noqa: F401
from dotenv import load_dotenv
from frozen_models_running.ig_index.carry_zrev_96_ig_spreadbet_v1.execution import HeldPosition, plan_session
from utils.ig_index.session import connect
from . import MODELS, VERSION
from .common import atomic_json, stamp, utcnow
from .demo import DemoAdapter, verify_target


def current_geometry(adapter, symbol, quote):
    market = quote["market"]; meta = market["instrument"]
    i = adapter.instruments[symbol]
    minimum = float(market["dealingRules"]["minDealSize"]["value"])
    fx = next(float(x["baseExchangeRate"]) for x in meta["currencies"] if x["code"] == i.quote_currency)
    margin = max([float(meta["marginFactor"])] + [float(b["margin"]) for b in meta.get("marginDepositBands", [])]) / 100
    instrument = replace(i, min_stake=minimum, margin_pct=margin)
    account = replace(adapter.config, fx_rates={"GBP": {i.quote_currency: fx}}, fx_rates_as_of=utcnow().date().isoformat())
    snap = market["snapshot"]
    price = .5 * (float(snap["bid"]) + float(snap["offer"])) * i.point_size
    return instrument, account, price


def cycle(adapter, target, *, max_gross_gbp, max_margin_gbp, execute=False):
    if any(not math.isfinite(v) or v <= 0 for v in (max_gross_gbp, max_margin_gbp)):
        raise ValueError("positive explicit model allocations are required")
    if not adapter.config.is_direction_only:
        raise ValueError("this version supports the frozen direction-only minimum-stake geometry")
    with adapter.journal.lock():
        status = adapter.reconcile()
        if status["problems"] or status["unresolved"]:
            raise ValueError("reconciliation required before planning a new cycle")
        owned = adapter.journal.owned(adapter.owner)
        by_symbol = {}
        for row in owned:
            by_symbol.setdefault(row["symbol"], []).append(row)
        held = {}
        for symbol, rows in by_symbol.items():
            net = sum(x["size"] * (1 if x["direction"] == "BUY" else -1) for x in rows)
            held[symbol] = HeldPosition(symbol, "BUY" if net > 0 else "SELL" if net < 0 else "FLAT", abs(net),
                                        rows[0]["deal_id"], tuple(x["deal_id"] for x in rows), len(rows),
                                        tuple((x["deal_id"], x["direction"], x["size"]) for x in rows))
        needed = sorted({s for s, t in target["targets"].items() if t} | set(held))
        instruments, quotes, prices, sized = {}, {}, {}, {}
        skips = []
        config = adapter.config
        gross = margin = 0.
        for symbol in needed:
            try:
                quote = adapter.quote(symbol, target=target)
                instrument, config, price = current_geometry(adapter, symbol, quote)
                instruments[symbol], quotes[symbol], prices[symbol] = instrument, quote, price
                units = float(target["targets"].get(symbol, 0))
                if units:
                    q = adapter.size(symbol, units, quote, max_gross_gbp=max_gross_gbp, max_margin_gbp=max_margin_gbp)
                    sized[symbol] = q
                    snap = quote["market"]["snapshot"]
                    notional = q.stake * max(snap["bid"], snap["offer"])
                    gross += notional; margin += notional * instrument.margin_pct
            except (ValueError, RuntimeError, KeyError) as error:
                skips.append({"symbol": symbol, "reason": str(error)[:400]})
        intents, planner_skips = plan_session(targets=target["targets"], prices=prices,
                                              instruments=instruments, account=config, held=held)
        skips += planner_skips
        for intent in intents:
            if not intent.closes_deal_id and (intent.symbol not in sized or
                    intent.size != sized[intent.symbol].stake or intent.direction != sized[intent.symbol].direction):
                skips.append({"symbol": intent.symbol,
                              "reason": "existing stake differs from new broker minimum; full close/reopen transition required"})
        allocation_ok = (gross <= max_gross_gbp and margin <= max_margin_gbp)
        plan = {"schema": "ig_pair_demo_cycle.v1", "version": VERSION, "model": adapter.model,
                "target_id": target["target_id"], "planned_at": stamp(), "scope": "complete_named_model_book",
                "intents": [asdict(x) for x in intents], "skipped": skips,
                "gross_gbp": gross, "conservative_margin_gbp": margin,
                "max_gross_gbp": max_gross_gbp, "max_margin_gbp": max_margin_gbp,
                "allocation_ok": allocation_ok, "executable_plan": allocation_ok and not skips,
                "execution_requested": execute, "performance_evidence": False, "executed": []}
        adapter.journal.event(adapter.owner, "cycle_plan", plan)
        if not execute:
            return plan
        if not plan["executable_plan"]:
            raise ValueError("complete plan fails quote/representation/allocation checks; receipt retained")
        # Close-first reversals inherit the existing planner: the opposite side
        # can enter on the next explicitly published session, not in this cycle.
        for intent in sorted(intents, key=lambda x: x.closes_deal_id is None):
            if intent.closes_deal_id:
                result = adapter.close(intent.closes_deal_id, purpose="strategy_rebalance")
            else:
                # Never send an old preflight quote. A changed dealing minimum
                # or price must remain within the frozen complete-book allocation.
                quote = adapter.quote(intent.symbol, target=target)
                fresh = adapter.size(intent.symbol, intent.target, quote,
                                     max_gross_gbp=max_gross_gbp, max_margin_gbp=max_margin_gbp)
                if fresh.stake != intent.size or fresh.direction != intent.direction:
                    raise ValueError("dealing minimum/size changed; publish a new complete plan")
                before = quotes[intent.symbol]["market"]["snapshot"]
                after = quote["market"]["snapshot"]
                old_gross = fresh.stake * max(before["bid"], before["offer"])
                new_gross = fresh.stake * max(after["bid"], after["offer"])
                live_i, _, _ = current_geometry(adapter, intent.symbol, quote)
                margin += new_gross * live_i.margin_pct - old_gross * instruments[intent.symbol].margin_pct
                gross += new_gross - old_gross
                if gross > max_gross_gbp or margin > max_margin_gbp:
                    raise ValueError("refreshed complete book exceeds allocation; no further entries")
                result = adapter.open(target, intent.symbol, fresh, quote)
            plan["executed"].append({"symbol": intent.symbol, "confirmation": result})
        plan["reconciliation"] = adapter.reconcile()
        plan["completed_at"] = stamp()
        adapter.journal.event(adapter.owner, "cycle_complete", plan)
        return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-gross-gbp", type=float, required=True)
    parser.add_argument("--max-margin-gbp", type=float, required=True)
    parser.add_argument("--execute-demo", action="store_true")
    args = parser.parse_args()
    target = verify_target(args.target, args.model)
    load_dotenv(Path(".env"), override=False)
    adapter = DemoAdapter(connect(demo=True), args.model)
    result = cycle(adapter, target, max_gross_gbp=args.max_gross_gbp,
                   max_margin_gbp=args.max_margin_gbp, execute=args.execute_demo)
    atomic_json(args.output, result, private=True)
    print(json.dumps({k: result[k] for k in ("model", "gross_gbp", "conservative_margin_gbp", "executable_plan", "execution_requested")}))


if __name__ == "__main__":
    main()
