"""Match closed model deals to cash via IG's explicit activity identifiers."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation


def gbp_amount(value):
    text = str(value).strip()
    if text.startswith("£"):
        text = text[1:]
    elif text.startswith("GBP "):
        text = text[4:]
    else:
        raise ValueError("settlement currency is not explicitly GBP")
    try:
        result = Decimal(text.replace(",", ""))
    except InvalidOperation as error:
        raise ValueError("unparseable GBP amount") from error
    if not result.is_finite():
        raise ValueError("nonfinite GBP settlement")
    return result


def reconcile(owned, activities, transactions):
    matched, unresolved = [], []
    for deal in owned:
        if deal["status"] != "CLOSED":
            continue
        closing = [a for a in activities if a.get("status") == "ACCEPTED" and
                   any(action.get("affectedDealId") == deal["deal_id"] and
                       action.get("actionType") == "POSITION_CLOSED"
                       for action in a.get("details", {}).get("actions", []))]
        links = [(a, t) for a in closing for t in transactions
                 if a.get("dealId") and t.get("reference") == a["dealId"] and t.get("transactionType") == "DEAL"]
        if len(links) != 1:
            unresolved.append({"deal_id": deal["deal_id"], "reason": "missing or ambiguous explicit activity-to-cash link", "matches": len(links)})
            continue
        activity, cash = links[0]
        details = activity.get("details", {})
        if (activity.get("epic") != deal["epic"] or details.get("currency") != deal["currency"]
                or abs(float(details.get("size", -1)) - deal["size"]) > 1e-9):
            unresolved.append({"deal_id": deal["deal_id"], "reason": "closing activity geometry mismatch"})
            continue
        try:
            amount = gbp_amount(cash.get("profitAndLoss"))
        except ValueError as error:
            unresolved.append({"deal_id": deal["deal_id"], "reason": str(error)})
            continue
        matched.append({"owner": deal["model"], "deal_id": deal["deal_id"],
                        "closing_activity_id": activity["dealId"], "transaction_reference": cash["reference"],
                        "cash_date_utc": cash.get("dateUtc"), "realised_trade_pnl_gbp": float(amount),
                        "method": "owned deal -> accepted POSITION_CLOSED affectedDealId -> activity dealId -> cash reference",
                        "overnight_and_other_adjustments_included": False})
    return {"matched": matched, "unresolved": unresolved,
            "sum_matched_trade_pnl_gbp": float(sum(Decimal(str(x["realised_trade_pnl_gbp"])) for x in matched)),
            "all_closed_trade_settlements_linked": not unresolved,
            "financing_borrow_dividend_adjustments_complete": False}
