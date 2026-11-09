import time

from utils.trading.shared_market_data import MarketDataStore


def _live(store, symbol="AAPL", *, provider="iqfeed", **overrides):
    row = {
        "provider": provider,
        "provider_version": "test-v1",
        "bid": 99.9,
        "ask": 100.1,
        "bid_size": 200,
        "ask_size": 300,
        "bid_market_center": "Q",
        "ask_market_center": "P",
        "delay_minutes": None,
        "is_delayed": False,
        **overrides,
    }
    return store.update_data(symbol, row)


def test_update_stamps_receipt_and_snapshot_id_is_stable():
    store = MarketDataStore()
    _live(store)

    first = store.quote_snapshot("AAPL", provider="iqfeed", max_age_seconds=10)
    second = store.quote_snapshot("AAPL", provider="iqfeed", max_age_seconds=10)

    assert first["received_at_epoch"] > 0
    assert first["received_at_iso"].endswith("+00:00")
    assert first["quote_snapshot_id"].startswith("sha256:")
    assert first["quote_snapshot_id"] == second["quote_snapshot_id"]
    assert first["bid_size"] == 200.0
    assert first["bid_market_center"] == "Q"


def test_receipt_age_marks_cached_quote_stale():
    store = MarketDataStore()
    _live(store)
    with store.lock:
        store.data["AAPL"]["received_at_monotonic"] = time.monotonic() - 11.0

    snapshot = store.quote_snapshot("AAPL", provider="iqfeed", max_age_seconds=10)

    assert snapshot["fresh"] is False
    assert snapshot["age_seconds"] >= 11.0
    assert store.quote_snapshot(
        "AAPL", provider="iqfeed", max_age_seconds=10, require_fresh=True
    ) is None


def test_coverage_requires_health_every_symbol_and_live_quotes():
    store = MarketDataStore()
    store.set_provider_health("iqfeed", connected=True, live=True, delayed=False)
    _live(store, "AAPL")

    partial = store.coverage(
        ["AAPL", "MSFT"], provider="iqfeed", max_age_seconds=10
    )
    assert partial["passed"] is False
    assert partial["missing_symbols"] == ["MSFT"]

    _live(store, "MSFT")
    complete = store.coverage(
        ["AAPL", "MSFT"], provider="iqfeed", max_age_seconds=10
    )
    assert complete["passed"] is True
    assert complete["valid_count"] == 2


def test_delayed_or_wrong_provider_quote_fails_coverage():
    store = MarketDataStore()
    store.set_provider_health("iqfeed", connected=True, live=True, delayed=False)
    _live(store, "AAPL", delay_minutes=15, is_delayed=True)
    _live(store, "MSFT", provider="ibkr")

    result = store.coverage(
        ["AAPL", "MSFT"], provider="iqfeed", max_age_seconds=10
    )

    assert result["passed"] is False
    assert result["delayed_symbols"] == ["AAPL"]
    assert result["provider_mismatch_symbols"] == ["MSFT"]


def test_invalid_coverage_retains_exact_book_diagnostics():
    store = MarketDataStore()
    store.set_provider_health("iqfeed", connected=True, live=True, delayed=False)
    _live(
        store,
        "SHEL",
        bid=83.87,
        ask=83.86,
        quote_validation_error="crossed_book",
        iqfeed_message_type="Q",
    )

    result = store.coverage(["SHEL"], provider="iqfeed", max_age_seconds=10)

    assert result["invalid_symbols"] == ["SHEL"]
    bad = result["invalid_quote_snapshots"]["SHEL"]
    assert bad["bid"] == 83.87
    assert bad["ask"] == 83.86
    assert bad["quote_validation_error"] == "crossed_book"
    assert bad["iqfeed_message_type"] == "Q"
