from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import sys

import pytest

from .common import stamp, utcnow
from .demo import DemoAdapter, position_signature
from utils.ig_index.session import DEMO_BASE_URL, LIVE_BASE_URL


@pytest.fixture(autouse=True)
def deterministic_market_clock(monkeypatch):
    from . import demo
    moment = datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(demo, "utcnow", lambda: moment)
    monkeypatch.setattr(demo, "stamp", lambda: moment.isoformat())
    monkeypatch.setattr(sys.modules[__name__], "utcnow", lambda: moment)


class Broker:
    def __init__(self):
        self.credentials = SimpleNamespace(base_url=DEMO_BASE_URL)
        self.account_id = "test-account"
        self.rows = [{"position": {"dealId": "manual", "direction": "SELL", "size": .24, "currency": "GBP"},
                      "market": {"epic": "SG.D.T.DAILY.IP"}}]
        self.confirms = {}
        self.opens = []; self.closes = []; self.timeout_after_accept = False

    def request(self, method, path, **kwargs):
        if path == "/accounts":
            return {"accounts": [{"accountId": self.account_id, "accountType": "SPREADBET", "currency": "GBP", "balance": {"available": 10000}}]}
        if path == "/indicativecostsandcharges/open":
            return {"openingSpread": .5, "overnightFundingFee": .2, "borrowingCharge": None}
        if path == "/history/transactions":
            return {"transactions": []}
        assert method == "POST" and path == "/positions/otc"
        if kwargs.get("before_send"):
            kwargs["before_send"]()
        body = kwargs["payload"]
        assert body["forceOpen"] is True
        self.opens.append(copy.deepcopy(body))
        deal = "owned" + str(len(self.opens))
        self.rows.append({"position": {"dealId": deal, "direction": body["direction"], "size": body["size"], "currency": body["currencyCode"]},
                          "market": {"epic": body["epic"]}})
        self.confirms[body["dealReference"]] = dict(dealId=deal, dealStatus="ACCEPTED", status="OPEN", epic=body["epic"],
                                                   size=body["size"], direction=body["direction"], level=2500)
        if self.timeout_after_accept:
            raise TimeoutError("response lost after broker accepted")
        return {"dealReference": body["dealReference"]}

    def positions(self):
        return copy.deepcopy(self.rows)

    def confirm(self, reference):
        return copy.deepcopy(self.confirms[reference])

    def market_details(self, epic):
        return {"instrument": {"epic": epic, "expiry": "DFB", "type": "SHARES", "forceOpenAllowed": True,
                "marginFactor": 20, "marginFactorUnit": "PERCENTAGE", "currencies": [
                    {"code": "USD", "baseExchangeRate": 1.32, "isDefault": False},
                    {"code": "GBP", "baseExchangeRate": 1., "isDefault": True}]},
                "snapshot": {"marketStatus": "TRADEABLE", "delayTime": 0, "bid": 2499, "offer": 2501, "updateTime": "12:00:00"},
                "dealingRules": {"minDealSize": {"value": .24}, "marketOrderPreference": "AVAILABLE"}}

    def close_position(self, **kwargs):
        self.closes.append(kwargs)
        before = len(self.rows)
        self.rows = [x for x in self.rows if x["position"]["dealId"] != kwargs["deal_id"]]
        assert len(self.rows) == before - 1
        ref = "close" + str(len(self.closes))
        self.confirms[ref] = dict(dealStatus="ACCEPTED", dealId=kwargs["deal_id"], status="CLOSED", level=2499)
        return {"dealReference": ref}


def prepared(tmp_path):
    broker = Broker()
    adapter = DemoAdapter(broker, "crash90", tmp_path)
    target = {"target_id": "test-target", "not_before": (utcnow() - timedelta(seconds=1)).isoformat(), "targets": {"T": 1},
              "source_day": "2026-09-23", "effective_session": "2026-09-24",
              "source_observed_at": (utcnow() - timedelta(hours=2)).isoformat(),
              "published_at": (utcnow() - timedelta(hours=1)).isoformat()}
    quote = adapter.quote("T", target=target)
    sized = adapter.size("T", 1, quote, max_gross_gbp=2000, max_margin_gbp=1500)
    return broker, adapter, target, quote, sized


@pytest.mark.parametrize("direction", [1, -1])
def test_real_path_contract_and_foreign_same_epic_preserved(tmp_path, direction):
    broker, adapter, target, _, _ = prepared(tmp_path)
    target["targets"]["T"] = direction
    before = position_signature(broker.rows)
    result = adapter.canary(target, "T")
    assert result["operational_path_verified"]
    assert not result["performance_evidence"]
    assert before == position_signature(broker.rows)
    assert broker.opens[0]["forceOpen"]
    assert broker.opens[0]["direction"] == ("BUY" if direction > 0 else "SELL")
    assert broker.closes[0]["direction"] == ("SELL" if direction > 0 else "BUY")
    assert broker.closes[0]["deal_id"] != "manual"
    assert adapter.journal.owned(adapter.owner) == []
    assert adapter.journal.verify()["events"] >= 15
    assert result["indicative_costs"][0]["missing_fields"] == ["borrowingCharge"]


def test_timeout_recovery_reuses_reference_without_resubmission(tmp_path):
    broker, adapter, target, quote, sized = prepared(tmp_path)
    broker.timeout_after_accept = True
    with pytest.raises(TimeoutError):
        adapter.open(target, "T", sized, quote)
    assert len(broker.opens) == 1
    # A new process instance uses persistent state. It must recover the broker
    # confirmation and existing position instead of placing a duplicate order.
    restarted = DemoAdapter(broker, "crash90", tmp_path)
    result = restarted.open(target, "T", sized, quote)
    assert len(broker.opens) == 1
    assert result["dealId"] == "owned1"
    assert not restarted.journal.unresolved(restarted.owner)


def test_other_model_cannot_close_position(tmp_path):
    broker, adapter, target, quote, sized = prepared(tmp_path)
    result = adapter.open(target, "T", sized, quote)
    second = DemoAdapter(broker, "carry96", tmp_path)
    with pytest.raises(ValueError, match="another model"):
        second.close(result["dealId"], purpose="test")
    with pytest.raises(ValueError, match="another model"):
        adapter.close("manual", purpose="test")
    assert not broker.closes


def test_expired_quote_and_live_endpoint_rejected(tmp_path):
    broker, adapter, target, quote, sized = prepared(tmp_path)
    quote["received_at"] = (utcnow() - timedelta(seconds=46)).isoformat()
    with pytest.raises(ValueError, match="quote too old"):
        adapter.open(target, "T", sized, quote)
    broker.credentials.base_url = LIVE_BASE_URL
    with pytest.raises(ValueError, match="demo endpoint"):
        DemoAdapter(broker, "crash90", tmp_path)
    assert not broker.opens


def test_position_drift_blocks_new_submission(tmp_path):
    broker, adapter, target, quote, sized = prepared(tmp_path)
    adapter.open(target, "T", sized, quote)
    broker.rows[-1]["position"]["size"] *= 2
    assert adapter.reconcile()["problems"]
    target["target_id"] = "next-target"
    with pytest.raises(ValueError, match="requires reconciliation"):
        adapter.open(target, "T", sized, quote)
    assert len(broker.opens) == 1


def test_account_lock_and_journal_tampering(tmp_path):
    broker, adapter, _, _, _ = prepared(tmp_path)
    second = DemoAdapter(broker, "carry96", tmp_path)
    with adapter.journal.lock():
        with pytest.raises(RuntimeError, match="account lock"):
            with second.journal.lock():
                pass
    adapter.journal.db.execute("UPDATE events SET payload='{}' WHERE seq=1")
    adapter.journal.db.commit()
    with pytest.raises(ValueError, match="event-chain"):
        adapter.journal.verify()


def test_complete_cycle_and_cap_failure_do_not_select_partial_book(tmp_path):
    from .cycle import cycle
    broker, adapter, target, _, _ = prepared(tmp_path)
    denied = cycle(adapter, target, max_gross_gbp=10, max_margin_gbp=10, execute=False)
    assert not denied["executable_plan"]
    assert not broker.opens
    good = cycle(adapter, target, max_gross_gbp=2000, max_margin_gbp=1500, execute=True)
    assert good["executable_plan"]
    assert len(broker.opens) == 1
    assert len(adapter.journal.owned(adapter.owner)) == 1
    repeat = cycle(adapter, target, max_gross_gbp=2000, max_margin_gbp=1500, execute=True)
    assert repeat["intents"] == []
    assert len(broker.opens) == 1


def test_version_namespace_keeps_old_model_deals_separate(tmp_path):
    broker, adapter, target, quote, sized = prepared(tmp_path)
    assert adapter.owner.startswith("crash90@")
    adapter.open(target, "T", sized, quote)
    assert adapter.journal.owned("crash90") == []
    assert len(adapter.journal.owned(adapter.owner)) == 1


def test_slow_cycle_cannot_enter_after_declared_session_close(tmp_path, monkeypatch):
    from . import demo
    broker, adapter, target, quote, sized = prepared(tmp_path)
    late = datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(demo, "utcnow", lambda: late)
    quote["received_at"] = late.isoformat()
    with pytest.raises(ValueError, match="outside declared"):
        adapter.open(target, "T", sized, quote)
    assert not broker.opens


def test_guard_runs_after_api_throttle_before_network_mutation(tmp_path, monkeypatch):
    from . import demo
    broker, adapter, target, quote, sized = prepared(tmp_path)
    request = broker.request

    def delayed_request(method, path, **kwargs):
        if method == "POST" and path == "/positions/otc":
            monkeypatch.setattr(demo, "utcnow", lambda: datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc))
        return request(method, path, **kwargs)

    broker.request = delayed_request
    with pytest.raises(ValueError, match="outside declared"):
        adapter.open(target, "T", sized, quote)
    assert not broker.opens
    assert adapter.journal.unresolved(adapter.owner) == []
