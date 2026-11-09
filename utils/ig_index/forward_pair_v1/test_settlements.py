from .settlements import reconcile


def records():
    owned = [{"deal_id": "owned", "model": "crash90@v2", "epic": "E", "currency": "GBP", "size": .24, "status": "CLOSED"}]
    activities = [{"status": "ACCEPTED", "dealId": "closing", "epic": "E", "details": {
        "actions": [{"actionType": "POSITION_CLOSED", "affectedDealId": "owned"}], "currency": "GBP", "size": .24}}]
    cash = [{"transactionType": "DEAL", "reference": "closing", "profitAndLoss": "£-0.72"}]
    return owned, activities, cash


def test_cash_requires_explicit_activity_bridge():
    owned, activities, cash = records()
    result = reconcile(owned, activities, cash)
    assert result["all_closed_trade_settlements_linked"]
    assert result["sum_matched_trade_pnl_gbp"] == -.72
    assert not result["financing_borrow_dividend_adjustments_complete"]
    assert not reconcile(owned, [], cash)["all_closed_trade_settlements_linked"]


def test_duplicate_cash_or_wrong_epic_does_not_verify():
    owned, activities, cash = records()
    assert not reconcile(owned, activities, cash + cash)["all_closed_trade_settlements_linked"]
    activities[0]["epic"] = "OTHER"
    assert not reconcile(owned, activities, cash)["all_closed_trade_settlements_linked"]
