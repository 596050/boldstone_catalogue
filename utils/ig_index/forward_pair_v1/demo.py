"""Isolated, resumable IG demo execution using the existing sizing/REST code.

All opens use forceOpen and a persisted client reference; all closes use an
owned deal ID. No live URL or shared-symbol netting is accepted. A canary closes
its own tiny validation deal and is explicitly separate from strategy P&L.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import research  # noqa: F401
from dotenv import load_dotenv
from frozen_models_running.ig_index.carry_zrev_96_ig_spreadbet_v1.instruments import load_account, load_instruments
from frozen_models_running.ig_index.carry_zrev_96_ig_spreadbet_v1.sizing import size_symbol
from utils.ig_index import session as ig_session_module
from utils.ig_index.session import DEMO_BASE_URL, connect
from utils.trading.calendar import last_completed_session

from . import MODELS, VERSION
from .common import atomic_json, digest_bytes, identity, parse_stamp, stamp, utcnow
from .journal import Journal
from .provider import NY, load_provider
from .session_window import bounds as session_bounds

RUNTIME = Path(".runtime/ig_pair_forward_v1")


def validate_target_clock(target, now):
    if target["source_day"] != last_completed_session(now):
        raise ValueError("stale target")
    if not (parse_stamp(target["source_observed_at"]) <= parse_stamp(target["published_at"])
            <= parse_stamp(target["not_before"]) <= now):
        raise ValueError("signal/source/publication/execution clocks are out of order")
    local = now.astimezone(NY)
    opening, closing = session_bounds(local.date())
    if target["effective_session"] != local.date().isoformat() or not opening <= local < closing:
        raise ValueError("outside declared regular-session execution window")


def verify_target(path, model, now=None):
    now = now or utcnow()
    target = json.loads(Path(path).read_text())
    bound = dict(target); target_id = bound.pop("target_id")
    if identity(bound) != target_id or target["model"] != model or target["version"] != VERSION:
        raise ValueError("target identity/model/version mismatch")
    provider, arrays = load_provider(target["source_folder"])
    row = dict(zip(arrays["symbols"].tolist(), arrays[model][-1].astype(float).tolist()))
    if provider["provider_id"] != target["provider_id"] or row != target["targets"]:
        raise ValueError("target does not reproduce the bound provider")
    validate_target_clock(target, now)
    return target


def position_signature(rows):
    return {r["position"]["dealId"]: {"epic": r["market"]["epic"],
            "direction": r["position"]["direction"], "size": float(r["position"]["size"]),
            "currency": r["position"].get("currency")}
            for r in rows}


class DemoAdapter:
    def __init__(self, session, model, root=RUNTIME):
        if model not in MODELS or session.credentials.base_url != DEMO_BASE_URL:
            raise ValueError("only the explicitly named model on the IG demo endpoint is supported")
        self.session, self.model = session, model
        self.owner = model + "@" + VERSION
        accounts = session.request("GET", "/accounts").get("accounts", [])
        self.account = next((a for a in accounts if a["accountId"] == session.account_id), None)
        if not self.account or self.account.get("accountType") != "SPREADBET" or self.account.get("currency") != "GBP":
            raise ValueError("selected demo account must be a GBP spread-bet account")
        self.account_key = identity({"environment": "demo", "account_id": session.account_id})
        self.journal = Journal(Path(root), self.account_key)
        self.journal.verify()
        code = {}
        archive = self.journal.folder / "runtime_code"
        archive.mkdir(exist_ok=True)
        for path in [*Path(__file__).parent.glob("*.py"), Path(ig_session_module.__file__)]:
            data = path.read_bytes(); digest = digest_bytes(data)
            saved = archive / (digest + ".py")
            if not saved.exists():
                with saved.open("xb") as handle:
                    handle.write(data)
            code[str(path.resolve())] = {"sha256": digest, "archive": str(saved)}
        self.journal.event(self.owner, "runtime_implementation", {"version": VERSION, "files": code})
        self.instruments, self.config = load_instruments(), load_account()
        self.journal.event(self.owner, "account_preflight", {"environment": "demo", "account_key": self.account_key,
                           "currency": "GBP", "account_type": "SPREADBET", "balance": self.account.get("balance")})

    def positions(self):
        rows = self.session.positions()
        self.journal.event(self.owner, "positions", {"observed_at": stamp(), "rows": rows})
        return rows

    def reconcile(self):
        rows = self.positions()
        actual = position_signature(rows)
        problems = []
        for owned in self.journal.owned(self.owner):
            value = actual.get(owned["deal_id"])
            if value is None:
                problems.append({"deal_id": owned["deal_id"], "reason": "owned position missing; explicit close recovery required"})
            elif (value["epic"] != owned["epic"] or value["direction"] != owned["direction"]
                  or abs(value["size"] - owned["size"]) > 1e-9 or value["currency"] != owned["currency"]):
                problems.append({"deal_id": owned["deal_id"], "reason": "owned position differs from confirmation"})
        result = {"problems": problems, "unresolved": self.journal.unresolved(self.owner),
                  "owned_open": len(self.journal.owned(self.owner)), "account_open": len(rows)}
        self.journal.event(self.owner, "reconciliation", result)
        return result

    def quote(self, symbol, *, target=None, opening=True):
        instrument = self.instruments[symbol]
        if not instrument.is_tradable:
            raise ValueError("instrument lacks verified dealing metadata")
        requested = stamp()
        market = self.session.market_details(instrument.epic)
        received = stamp()
        result = {"symbol": symbol, "epic": instrument.epic, "requested_at": requested,
                  "received_at": received, "market": market,
                  "broker_update_time_raw": market.get("snapshot", {}).get("updateTime"),
                  "broker_update_time_timezone": "not supplied; not used as an absolute availability clock"}
        self.journal.event(self.owner, "quote", result)
        m, s, rules = market["instrument"], market["snapshot"], market["dealingRules"]
        if m.get("epic") != instrument.epic or m.get("expiry") != "DFB" or m.get("type") != "SHARES":
            raise ValueError("market identity differs from configured DFB share")
        if s.get("marketStatus") != "TRADEABLE" or s.get("delayTime") != 0:
            raise ValueError("a current tradeable quote is required")
        bid, ask = s.get("bid"), s.get("offer")
        if any(v is None or not math.isfinite(float(v)) or v <= 0 for v in (bid, ask)) or ask < bid:
            raise ValueError("invalid bid/ask")
        if target is not None and parse_stamp(requested) < parse_stamp(target["not_before"]):
            raise ValueError("quote requested before signal availability")
        if opening and not m.get("forceOpenAllowed"):
            raise ValueError("broker cannot isolate model ownership on this market")
        if rules.get("marketOrderPreference") == "NOT_AVAILABLE":
            raise ValueError("market orders unavailable")
        default = [x for x in m.get("currencies", []) if x.get("isDefault")]
        if len(default) != 1 or default[0]["code"] != "GBP":
            raise ValueError("market default dealing currency differs from GBP")
        return result

    def size(self, symbol, units, quote, *, max_gross_gbp, max_margin_gbp):
        market = quote["market"]; meta = market["instrument"]; snap = market["snapshot"]
        i = self.instruments[symbol]
        minimum = float(market["dealingRules"]["minDealSize"]["value"])
        if not math.isfinite(minimum) or minimum <= 0:
            raise ValueError("invalid minimum stake")
        fx = next((float(x["baseExchangeRate"]) for x in meta["currencies"] if x["code"] == i.quote_currency), None)
        if fx is None or not math.isfinite(fx) or fx <= 0:
            raise ValueError("missing current quote-currency conversion")
        if meta.get("marginFactorUnit") != "PERCENTAGE":
            raise ValueError("unsupported margin units")
        # Conservative largest tier: sufficient for a minimum-stake canary and
        # does not understate margin when other models share this account.
        margin_pct = max([float(meta["marginFactor"])] + [float(b["margin"]) for b in meta.get("marginDepositBands", [])]) / 100
        live_i = replace(i, min_stake=minimum, margin_pct=margin_pct)
        config = replace(self.config, fx_rates={"GBP": {i.quote_currency: fx}}, fx_rates_as_of=utcnow().date().isoformat())
        mid = (float(snap["bid"]) + float(snap["offer"])) / 2
        sized = size_symbol(symbol=symbol, target=units, price=mid * i.point_size, instrument=live_i, account=config)
        if sized.dropped or sized.stake <= 0:
            raise ValueError(f"unrepresentable target: {sized.drop_reason}")
        gross = sized.stake * max(float(snap["bid"]), float(snap["offer"]))
        margin = gross * margin_pct
        if gross > max_gross_gbp or margin > max_margin_gbp:
            raise ValueError(f"minimum stake exceeds demo cap: gross={gross:.2f}, conservative margin={margin:.2f}")
        available = float(self.account["balance"]["available"])
        if margin > available:
            raise ValueError("insufficient demo available funds")
        self.journal.event(self.owner, "sizing", {"symbol": symbol, "units": units, "sizing": asdict(sized),
                           "current_fx": fx, "gross_gbp": gross, "conservative_margin_gbp": margin,
                           "bid_offer_roundtrip_gbp": sized.stake * (snap["offer"] - snap["bid"])})
        return sized

    def indicative_costs(self, symbol, size, quote):
        """Capture side-specific indicative terms; absent API fields stay null."""
        market = quote["market"]
        outputs = []
        for side in ("BUY", "SELL"):
            body = {"epic": self.instruments[symbol].epic, "direction": side,
                    "size": size, "dealCurrencyCode": "GBP", "bid": market["snapshot"]["bid"],
                    "ask": market["snapshot"]["offer"], "guaranteedStop": False,
                    "dealReference": "FPCC" + identity({"model": self.model, "symbol": symbol, "side": side, "at": stamp()})[:24]}
            try:
                response = self.session.request("POST", "/indicativecostsandcharges/open", payload=body)
                record = {"side": side, "status": "OBSERVED_INDICATIVE", "response": response,
                          "missing_fields": [k for k in ("borrowingCharge", "overnightFundingFee", "openingSpread") if response.get(k) is None]}
            except Exception as exc:
                record = {"side": side, "status": "UNAVAILABLE", "error": str(exc)[:400],
                          "borrowingCharge": None, "overnightFundingFee": None}
            record.update(symbol=symbol, observed_at=stamp(), actual_realised_cost=False)
            self.journal.event(self.owner, "indicative_costs", record); outputs.append(record)
        return outputs

    def open(self, target, symbol, sized, quote, *, purpose="strategy"):
        now = utcnow()
        validate_target_clock(target, now)
        if not 0 <= (now - parse_stamp(quote["received_at"])).total_seconds() <= 45:
            raise ValueError("quote too old at submission")
        if now < parse_stamp(target["not_before"]):
            raise ValueError("order before signal availability")
        i = self.instruments[symbol]
        op_id = identity({"account": self.account_key, "model": self.model, "target": target["target_id"],
                          "symbol": symbol, "phase": "open", "purpose": purpose})
        prior = self.journal.operation(op_id)
        if prior:
            return self.recover_open(op_id, symbol)
        reconciliation = self.reconcile()
        if reconciliation["problems"] or reconciliation["unresolved"]:
            raise ValueError("existing model state requires reconciliation before another open")
        validate_target_clock(target, utcnow())
        if not 0 <= (utcnow() - parse_stamp(quote["received_at"])).total_seconds() <= 45:
            raise ValueError("quote expired during pre-order reconciliation")
        if self.journal.unresolved(self.owner):
            raise ValueError("unresolved prior order; reconciliation required")
        if any(o["symbol"] == symbol for o in self.journal.owned(self.owner)):
            raise ValueError("model already owns this symbol; reconcile its target first")
        reference = "FP" + op_id[:28]
        body = dict(epic=i.epic, expiry="DFB", direction=sized.direction, size=sized.stake,
                    orderType="MARKET", currencyCode="GBP", forceOpen=True, guaranteedStop=False,
                    timeInForce="FILL_OR_KILL", dealReference=reference)
        self.journal.begin(self.owner, op_id, body, reference)
        self.journal.event(self.owner, "decision", {"op_id": op_id, "target": target,
                           "quote": quote, "purpose": purpose, "decision_at": stamp()})
        send_permitted = False

        def before_send():
            nonlocal send_permitted
            current = utcnow()
            validate_target_clock(target, current)
            if not 0 <= (current - parse_stamp(quote["received_at"])).total_seconds() <= 45:
                raise ValueError("quote expired while waiting for the API allowance")
            send_permitted = True

        try:
            response = self.session.request("POST", "/positions/otc", version="2", payload=body, before_send=before_send)
            if response.get("dealReference") != reference:
                self.journal.update(op_id, "UNKNOWN", reference=response.get("dealReference"))
                raise ValueError("broker returned a different reference; explicit reconciliation required")
            self.journal.update(op_id, "SUBMITTED", reference=reference)
        except Exception as exc:
            if not send_permitted:
                self.journal.update(op_id, "REJECTED", confirmation={"dealStatus": "REJECTED", "reason": "LOCAL_PRE_SEND_GUARD", "error": str(exc)[:400]})
            self.journal.event(self.owner, "submission_uncertain" if send_permitted else "submission_rejected_locally",
                               {"op_id": op_id, "error": str(exc)[:400]})
            raise
        return self.recover_open(op_id, symbol)

    def recover_open(self, op_id, symbol):
        operation = self.journal.operation(op_id)
        if operation is None or operation["model"] != self.owner:
            raise ValueError("operation is not model-owned")
        confirmation = operation["confirmation"]
        if confirmation is None:
            confirmation = self.session.confirm(operation["reference"])
            self.journal.event(self.owner, "confirmation", {"op_id": op_id, "received_at": stamp(), "response": confirmation})
        if confirmation.get("dealStatus") == "REJECTED":
            self.journal.update(op_id, "REJECTED", confirmation=confirmation)
            raise RuntimeError(f"demo order rejected: {confirmation.get('reason')}")
        if confirmation.get("dealStatus") != "ACCEPTED" or confirmation.get("status") != "OPEN":
            raise ValueError("open not confirmed as an isolated OPEN deal")
        request = operation["request"]
        if (confirmation.get("direction") != request["direction"] or confirmation.get("epic") != request["epic"]
                or abs(float(confirmation.get("size", -1)) - request["size"]) > 1e-9):
            raise ValueError("confirmation differs from requested open")
        self.journal.claim(self.owner, symbol, request, op_id, confirmation["dealId"])
        self.journal.update(op_id, "ACCEPTED", confirmation=confirmation)
        result = self.reconcile()
        if result["problems"] or result["unresolved"]:
            raise ValueError("post-open reconciliation failed")
        return confirmation

    def close(self, deal_id, *, purpose):
        owned = next((x for x in self.journal.owned(self.owner, open_only=False) if x["deal_id"] == deal_id), None)
        if owned is None:
            raise ValueError("refusing to close another model's or a manual position")
        op_id = identity({"account": self.account_key, "model": self.model, "deal_id": deal_id, "phase": "close", "purpose": purpose})
        previous = self.journal.operation(op_id)
        if previous:
            if previous["status"] == "ACCEPTED":
                return previous["confirmation"]
            if not previous["reference"]:
                # Query positions/activity, never blindly repeat a timed-out close.
                self.reconcile()
                raise ValueError("close response uncertain; no reference, manual activity reconciliation required")
        else:
            if owned["status"] != "OPEN":
                raise ValueError("owned deal already closed")
            actual = position_signature(self.positions()).get(deal_id)
            if not actual or actual["direction"] != owned["direction"] or abs(actual["size"] - owned["size"]) > 1e-9:
                raise ValueError("owned position not present at exact confirmed size")
            quote = self.quote(owned["symbol"], opening=False)
            body = {"deal_id": deal_id, "direction": "SELL" if owned["direction"] == "BUY" else "BUY", "size": owned["size"]}
            self.journal.begin(self.owner, op_id, body)
            self.journal.event(self.owner, "close_decision", {"op_id": op_id, "quote": quote, "purpose": purpose})
            response = self.session.close_position(**body)
            self.journal.update(op_id, "SUBMITTED", reference=response["dealReference"])
            previous = self.journal.operation(op_id)
        confirmation = self.session.confirm(previous["reference"])
        self.journal.event(self.owner, "confirmation", {"op_id": op_id, "received_at": stamp(), "response": confirmation})
        if confirmation.get("dealStatus") != "ACCEPTED":
            self.journal.update(op_id, "REJECTED", confirmation=confirmation)
            raise RuntimeError(f"demo close rejected: {confirmation.get('reason')}")
        actual = position_signature(self.positions())
        if deal_id in actual:
            raise ValueError("accepted close did not remove the model-owned position")
        self.journal.closed(self.owner, deal_id)
        self.journal.update(op_id, "ACCEPTED", confirmation=confirmation)
        return confirmation

    def collect_cash(self):
        """Keep all raw account transactions; no speculative ownership matching."""
        day = utcnow().date().isoformat()
        start_day = (utcnow() - timedelta(days=1)).date().isoformat()
        try:
            response = self.session.request("GET", "/history/transactions", version="2",
                                            params={"type": "ALL", "from": start_day, "to": day, "pageSize": 0})
            record = {"observed_at": stamp(), "response": response, "status": "OBSERVED",
                      "query_dates": [start_day, day], "query_scope": "all pages; date-only inclusive end avoids broker-local intraday cutoff ambiguity",
                      "ownership_matching": "only explicit deal references; unassigned adjustments remain unassigned"}
        except Exception as exc:
            record = {"observed_at": stamp(), "status": "UNAVAILABLE", "error": str(exc)[:400]}
        self.journal.event(self.owner, "cash_transactions", record)
        return record

    def canary(self, target, symbol):
        with self.journal.lock():
            original = position_signature(self.positions())
            if self.journal.owned(self.owner):
                raise ValueError("canary requires an empty model-owned book; other books are allowed")
            units = float(target["targets"][symbol])
            if units == 0:
                raise ValueError("canary must follow a nonzero model target")
            quote = self.quote(symbol, target=target)
            sized = self.size(symbol, units, quote, max_gross_gbp=2000, max_margin_gbp=1500)
            costs = self.indicative_costs(symbol, sized.stake, quote)
            quote = self.quote(symbol, target=target)  # costs calls consumed time
            sized = self.size(symbol, units, quote, max_gross_gbp=2000, max_margin_gbp=1500)
            confirmation = self.open(target, symbol, sized, quote, purpose="operational_canary")
            closing = self.close(confirmation["dealId"], purpose="operational_canary_cleanup")
            final = position_signature(self.positions())
            preserved = original == final
            if not preserved:
                raise ValueError("pre-existing account position signatures changed during canary")
            cash = self.collect_cash()
            result = {"schema": "ig_pair_demo_canary.v1", "version": VERSION, "model": self.model,
                      "completed_at": stamp(), "owner": self.owner, "target_id": target["target_id"], "symbol": symbol,
                      "stake_gbp_per_point": sized.stake, "open_confirmation": confirmation,
                      "close_confirmation": closing, "prior_positions_preserved": preserved,
                      "owned_open_after": len(self.journal.owned(self.owner)),
                      "cash_collection_status": cash["status"], "indicative_costs": costs,
                      "journal": str(self.journal.path), "journal_verification": self.journal.verify(),
                      "operational_path_verified": True, "full_portfolio_execution_verified": False,
                      "performance_evidence": False, "live_deployment": False}
            self.journal.event(self.owner, "canary_complete", result)
            return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("canary", "reconcile"))
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--symbol")
    parser.add_argument("--execute-demo", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "canary" and (not args.execute_demo or not args.target or not args.symbol or not args.output):
        parser.error("canary needs --execute-demo, --target, --symbol and --output")
    target = verify_target(args.target, args.model) if args.command == "canary" else None
    load_dotenv(Path(".env"), override=False)
    adapter = DemoAdapter(connect(demo=True), args.model)
    result = adapter.canary(target, args.symbol) if target else adapter.reconcile()
    if args.output:
        atomic_json(args.output, result, private=True)
    print(json.dumps({k: result[k] for k in result if k in ("model", "symbol", "operational_path_verified", "owned_open_after", "problems", "unresolved")}))


if __name__ == "__main__":
    main()
