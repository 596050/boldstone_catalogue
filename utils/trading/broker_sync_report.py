#!/usr/bin/env python3
"""On-demand sync report: frozen carry96 target vs. live broker position.

Compares each order-capable frozen adapter's last persisted target against
the real, live account state, for both running venues:

  IBKR paper  (carry_zrev_96_..._near_close_overnight_delta_paper_v1, DUK193810)
  IG demo     (carry_zrev_96_ig_spreadbet_v1, XTH2K)

Read-only by construction: it reads each adapter's own `.runtime` target
artifact (it does not recompute a target or touch execution.py), and calls
only `ib.positions()` / `ib.portfolio()` / IG `GET /positions`. It never
imports an order-path module and never places, amends, or closes anything.

Usage:
    PYTHONPATH=. .venv/bin/python utils/trading/broker_sync_report.py
    PYTHONPATH=. .venv/bin/python utils/trading/broker_sync_report.py --ibkr-only
    PYTHONPATH=. .venv/bin/python utils/trading/broker_sync_report.py --ig-only
    PYTHONPATH=. .venv/bin/python utils/trading/broker_sync_report.py --json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from utils.data_paths import CONFIGURED_DATA_ROOT
from utils.data_paths import resolve_data_path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

IBKR_ADAPTER_DIR = (
    REPO_ROOT
    / "frozen_models_running/ibkr"
    / "carry_zrev_96_lb80_veto105_health252_reb5off1_a04__near_close_overnight_delta_paper_v1"
)
IBKR_TARGETS_PATH = IBKR_ADAPTER_DIR / ".runtime" / "latest_targets.json"
IBKR_EVENTS_PATH = IBKR_ADAPTER_DIR / ".runtime" / "events.jsonl"

# Shared by both venues (same underlying signal); cached by the separate,
# heavy scripts/compute_carry96_holding_period_stats.py rather than
# recomputed on every report run. See that script to refresh it.
HOLDING_PERIOD_STATS_PATH = (
    REPO_ROOT
    / "frozen_models_running/ibkr/carry_zrev_96_lb80_veto105_health252_reb5off1_a04"
    / ".runtime/holding_period_stats.json"
)

IG_ADAPTER_DIR = (
    REPO_ROOT / "frozen_models_running/ig_index" / "carry_zrev_96_ig_spreadbet_v1"
)
IG_PLAN_PATH = IG_ADAPTER_DIR / ".runtime" / "last_plan.json"

# Both adapters' targets are built from this same direct-IQFeed HDT daily
# panel (see each adapter's provenance block in its target/plan JSON).
IQFEED_DAILY_DIR = resolve_data_path('ibkr/iqfeed_192_daily')

DEFAULT_IBKR_HOST = "127.0.0.1"
DEFAULT_IBKR_PORT = 4002
# 498 = the adapter's order session, 519 = the adapter's own market-data
# preflight (see DECISION_FLOW.md). This report stays off both so it can
# never contend for the sole order-capable client identity.
DEFAULT_IBKR_REPORT_CLIENT_ID = 777
EXPECTED_IBKR_PAPER_ACCOUNT = "DUK193810"
LIVE_EXECUTION_TIMING_PREFIX = "fixed_near_close_"
HOLD_ONLY_EXECUTION_TIMING = "bootstrap_final_close_snapshot_reconciliation_hold_only"
HOLDING_PANEL_LOADER = (
    "frozen_models_running.ibkr."
    "carry_zrev_96_lb80_veto105_health252_reb5off1_a04"
    "__near_close_overnight_delta_paper_v1.target_model.load_signal_panel"
)


def _load_env_file(path: Path) -> None:
    """Populate os.environ from a KEY=VALUE .env file, without overwriting."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _decision_age_cell(generated_at_epoch: float | None = None, generated_at_iso: str | None = None) -> str:
    """How long the CURRENT target_day decision has been standing, i.e. time
    since the model actually produced it - not the signal's own as-of date."""
    if generated_at_epoch is not None:
        iso = datetime.fromtimestamp(float(generated_at_epoch), tz=timezone.utc).isoformat()
    elif generated_at_iso is not None:
        iso = generated_at_iso
    else:
        return "unknown"
    age = _age_str(iso)
    return f"{iso} ({age} ago)"


def _age_str(iso_ts: str | None) -> str:
    if not iso_ts:
        return "unknown"
    try:
        then = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
    except ValueError:
        return "unknown"
    delta = datetime.now(timezone.utc) - then
    hours = delta.total_seconds() / 3600
    days, rem_hours = divmod(int(hours), 24)
    return f"{days}d {rem_hours}h" if days else f"{rem_hours}h"


# --------------------------------------------------------------- targets


def _execution_timing_status(value: Any) -> dict[str, Any]:
    timing = str(value or "")
    if timing.startswith(LIVE_EXECUTION_TIMING_PREFIX):
        return {
            "kind": "live_near_close_capture",
            "execution_capable": True,
            "label": "LIVE near-close capture: execution-capable target snapshot",
        }
    if timing == HOLD_ONLY_EXECUTION_TIMING:
        return {
            "kind": "hold_only_bootstrap",
            "execution_capable": False,
            "label": "HOLD-ONLY bootstrap: cannot authorize target adjustments",
        }
    return {
        "kind": "unknown",
        "execution_capable": False,
        "label": "UNKNOWN capture type: treated as non-actionable",
    }


def load_ibkr_target(path: Path = IBKR_TARGETS_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"no IBKR target snapshot yet at {path} "
            "(the adapter has not completed a capture)"
        )
    data = json.loads(path.read_text())
    positions: dict[str, int] = {}
    for row in data["symbols"]:
        symbol = str(row["symbol"]).upper()
        if symbol in positions:
            raise ValueError(f"duplicate IBKR target symbol {symbol}")
        # Zero is an explicit FLAT target, not a missing value. It must survive
        # parsing so an actual holding can be identified as a pending exit.
        positions[symbol] = int(row["target_shares"])
    timing_status = _execution_timing_status(data.get("execution_timing"))
    return {
        "target_day": data.get("target_day"),
        "signal_as_of_day": data.get("signal_as_of_day"),
        # Distinguishes a real 15:45 ET near-close capture (execution_timing
        # starts with "fixed_near_close_", the only kind that can authorize an
        # adjustment - see execution.py _target_adjustment_authorized) from the
        # hold-only bootstrap the data-freshness daemon regenerates overnight
        # ("bootstrap_final_close_snapshot_reconciliation_hold_only"). Without
        # this the report shows both identically, so a failed capture that was
        # later papered over by a bootstrap regen looks like a live target and
        # its share deltas look actionable when nothing can act on them.
        "execution_timing": data.get("execution_timing"),
        "execution_timing_status": timing_status,
        "positions": positions,
        "generated_at": data.get("generated_at"),
    }


def load_ig_target(path: Path = IG_PLAN_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"no IG target plan yet at {path} (the adapter has not run)"
        )
    data = json.loads(path.read_text())
    complete_vector = isinstance(data.get("target_directions"), dict)
    raw_directions: dict[str, Any]
    if complete_vector:
        raw_directions = data["target_directions"]
    else:
        # Legacy plans persisted only required orders. Use each intent's target
        # sign (never its order side, which is inverted for a close), but mark
        # the result incomplete so it cannot look authoritative.
        raw_directions = {}
        for row in data.get("intents", []):
            target = float(row.get("target", 0.0))
            raw_directions[str(row["symbol"]).upper()] = (
                "BUY" if target > 0.0 else "SELL" if target < 0.0 else "FLAT"
            )
    directions: dict[str, str] = {}
    for raw_symbol, raw_direction in raw_directions.items():
        symbol = str(raw_symbol).upper()
        direction = str(raw_direction).upper()
        if symbol in directions:
            raise ValueError(f"duplicate IG target symbol {symbol}")
        if direction not in {"BUY", "SELL", "FLAT"}:
            raise ValueError(f"invalid IG target direction for {symbol}: {direction}")
        directions[symbol] = direction
    return {
        "target_day": data.get("target_day"),
        "target_snapshot_day": data.get("target_snapshot_day"),
        "directions": directions,
        "generated_at_utc": data.get("generated_at_utc"),
        "dry_run": data.get("dry_run"),
        "order_capable_plan": data.get("dry_run") is False,
        "target_vector_complete": complete_vector,
    }


# ------------------------------------------------------------ signal freshness


def check_iqfeed_freshness(
    symbols: list[str],
    *,
    now: datetime | None = None,
    directory: Path = IQFEED_DAILY_DIR,
) -> dict[str, dict[str, Any]]:
    """Per-symbol freshness of the shared IQFeed daily panel both adapters
    read their signal from. Local file reads only — no network, no broker.

    "current" means exact equality with the most recent NYSE session whose
    close plus safety buffer has passed. The earlier next-session comparison
    stayed green after a new session closed until midnight in New York.
    """
    from utils.trading.calendar import last_completed_session

    expected = last_completed_session(now)
    result: dict[str, dict[str, Any]] = {}
    for sym in symbols:
        path = directory / f"{sym}.txt"
        if not path.exists():
            result[sym] = {
                "last_date": None,
                "expected_date": expected,
                "current": False,
                "note": "file missing",
            }
            continue
        text = path.read_text().strip()
        last_line = text.splitlines()[-1] if text else ""
        date_field = last_line.split(",", 1)[0] if last_line else ""
        try:
            last_date = datetime.strptime(date_field, "%m/%d/%Y").date()
        except ValueError:
            result[sym] = {
                "last_date": None,
                "expected_date": expected,
                "current": False,
                "note": "unparseable last row",
            }
            continue
        last_iso = last_date.isoformat()
        current = last_iso == expected
        if current:
            note = None
        elif last_iso < expected:
            note = f"stale — expected completed session {expected}"
        else:
            note = f"unexpected future session — expected {expected}"
        result[sym] = {
            "last_date": last_iso,
            "expected_date": expected,
            "current": current,
            "note": note,
        }
    return result


def next_expected_session(target_day: str | None) -> str | None:
    """The next NYSE session after a target's decision day — i.e. when this
    adapter's next capture/deal window happens. IG's own schedule.py uses
    the same trading_calendar helper and explicitly mirrors IBKR's 15:45-
    15:55 ET window, so this one calendar answers it for both brokers.
    """
    if not target_day:
        return None
    from utils.trading.calendar import next_nyse_session

    return next_nyse_session(date.fromisoformat(target_day)).isoformat()


def _iqfeed_cell(freshness: dict[str, dict[str, Any]], symbol: str) -> str:
    row = freshness.get(symbol)
    if not row:
        return "unknown"
    if row["last_date"] is None:
        return f"⚠️ {row['note']}"
    return f"🟢 {row['last_date']}" if row["current"] else f"🔴 {row['last_date']} STALE"


# ---------------------------------------------------------- live account state


def _ibkr_contract_key(contract: object) -> str:
    symbol = str(getattr(contract, "symbol", "?")).upper()
    security_type = str(getattr(contract, "secType", "") or "UNKNOWN").upper()
    currency = str(getattr(contract, "currency", "") or "UNKNOWN").upper()
    if security_type == "STK" and currency == "USD":
        return symbol
    con_id = getattr(contract, "conId", None)
    suffix = f":{con_id}" if con_id else ""
    return f"{symbol} [{security_type}/{currency}{suffix}]"


def normalise_ibkr_positions(raw_positions: list[object]) -> dict[str, int]:
    """Aggregate identical stocks and keep other contracts visibly distinct."""

    result: dict[str, int] = {}
    for item in raw_positions:
        key = _ibkr_contract_key(item.contract)
        result[key] = result.get(key, 0) + int(item.position)
    return result


def normalise_ibkr_portfolio(raw_items: list[object]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in raw_items:
        key = _ibkr_contract_key(item.contract)
        row = result.setdefault(
            key,
            {"unrealized": 0.0, "realized": 0.0, "market_price": None},
        )
        row["unrealized"] = round(
            float(row["unrealized"]) + float(item.unrealizedPNL), 2
        )
        row["realized"] = round(float(row["realized"]) + float(item.realizedPNL), 2)
        if item.marketPrice:
            row["market_price"] = round(float(item.marketPrice), 4)
    return result


def fetch_ibkr_positions(
    host: str = DEFAULT_IBKR_HOST,
    port: int = DEFAULT_IBKR_PORT,
    client_id: int = DEFAULT_IBKR_REPORT_CLIENT_ID,
) -> dict[str, Any]:
    import asyncio
    import logging

    asyncio.set_event_loop(asyncio.new_event_loop())  # ib_insync/py3.14 compat
    import ib_insync  # noqa: F401
    from utils.trading.main import connect_to_ib  # triggers logging_config.setup_logging() -> stdout

    # main.py's logging is intentionally stdout (repo-wide convention); this
    # report's own stdout is its data (markdown or --json), so keep the two
    # separate rather than changing shared logging config.
    for handler in logging.root.handlers:
        if getattr(handler, "stream", None) is sys.stdout:
            handler.stream = sys.stderr

    ib = connect_to_ib(host, port, client_id)
    if not ib:
        raise RuntimeError(f"could not connect to IB Gateway at {host}:{port}")
    try:
        accounts = ib.managedAccounts()
        if EXPECTED_IBKR_PAPER_ACCOUNT not in accounts:
            raise RuntimeError(
                "expected IBKR paper account is not managed by this Gateway: "
                f"{EXPECTED_IBKR_PAPER_ACCOUNT}; accounts={accounts}"
            )
        positions = normalise_ibkr_positions(
            list(ib.positions(account=EXPECTED_IBKR_PAPER_ACCOUNT))
        )
        # IB computes this itself from live marks + true average cost basis —
        # more reliable than re-deriving it from positions() + a separate
        # market-data request.
        pnl = normalise_ibkr_portfolio(
            list(ib.portfolio(account=EXPECTED_IBKR_PAPER_ACCOUNT))
        )
        # Signed WORKING order quantity per symbol. Without this the report
        # shows a drift that already has a live order against it exactly like
        # a drift nobody is acting on - the two are indistinguishable, which
        # makes a correct table look wrong (queued pre-market orders do not
        # fill until 09:30 ET). Read-only: reqAllOpenOrders places nothing.
        pending: dict[str, int] = {}
        for trade in ib.reqAllOpenOrders():
            if getattr(trade.order, "account", None) not in (
                None, "", EXPECTED_IBKR_PAPER_ACCOUNT
            ):
                continue
            remaining = float(getattr(trade.orderStatus, "remaining", 0.0) or 0.0)
            if remaining <= 0:
                continue
            sign = -1 if str(trade.order.action).upper() == "SELL" else 1
            symbol = str(trade.contract.symbol).upper()
            pending[symbol] = pending.get(symbol, 0) + sign * int(remaining)
        return {
            "account": EXPECTED_IBKR_PAPER_ACCOUNT,
            "is_paper": True,
            "managed_accounts": accounts,
            "positions": positions,
            "pnl": pnl,
            "pending": pending,
            "queried_at": _iso_now(),
        }
    finally:
        ib.disconnect()


def normalise_ig_positions(
    raw: list[dict], epic_to_symbol: dict[str, str]
) -> dict[str, dict[str, Any]]:
    """Net every IG deal while retaining gross/stack/hedge diagnostics."""

    position_legs: dict[str, list[dict[str, Any]]] = {}
    for row in raw:
        pos = row.get("position", {})
        mkt = row.get("market", {})
        epic = str(mkt.get("epic") or "")
        symbol = epic_to_symbol.get(epic, epic or "?")
        direction = str(pos.get("direction") or "").upper()
        level = pos.get("level")
        size = pos.get("dealSize") or pos.get("size")
        bid = mkt.get("bid")
        offer = mkt.get("offer")
        # Spread-bet P&L closes against the opposite side of the current
        # two-way price: a SELL closes by buying at the offer, a BUY closes
        # by selling at the bid. Stake (size) is already GBP-per-point, so
        # no separate FX conversion is needed.
        pnl = None
        if None not in (level, size, bid, offer):
            level_value = float(level)
            size_value = float(size)
            bid_value = float(bid)
            offer_value = float(offer)
            if direction == "BUY":
                pnl = round((bid_value - level_value) * size_value, 2)
            elif direction == "SELL":
                pnl = round((level_value - offer_value) * size_value, 2)
        if direction not in {"BUY", "SELL"}:
            raise ValueError(
                f"IG returned invalid position direction {direction!r} for {symbol}"
            )
        if size is None or not math.isfinite(float(size)) or float(size) <= 0.0:
            raise ValueError(f"IG returned invalid position size {size!r} for {symbol}")
        position_legs.setdefault(symbol, []).append({
            "direction": direction,
            "size": float(size),
            "created_at_utc": pos.get("createdDateUTC"),
            "deal_id": pos.get("dealId"),
            "level": level,
            "bid": bid,
            "offer": offer,
            "pnl": pnl,
        })
    positions: dict[str, dict[str, Any]] = {}
    for symbol, legs in position_legs.items():
        signed_size = sum(
            leg["size"] if leg["direction"] == "BUY" else -leg["size"]
            for leg in legs
        )
        sides = {str(leg["direction"]) for leg in legs}
        known_pnl = [float(leg["pnl"]) for leg in legs if leg["pnl"] is not None]
        created = sorted(
            str(leg["created_at_utc"])
            for leg in legs
            if leg["created_at_utc"]
        )
        positions[symbol] = {
            "direction": (
                "BUY" if signed_size > 1e-12
                else "SELL" if signed_size < -1e-12
                else "FLAT"
            ),
            "size": abs(signed_size),
            "gross_size": sum(float(leg["size"]) for leg in legs),
            "deal_count": len(legs),
            "hedged": len(sides) > 1,
            "created_at_utc": created[0] if created else None,
            "deal_ids": [leg["deal_id"] for leg in legs],
            "pnl": round(sum(known_pnl), 2) if known_pnl else None,
        }
    return positions


def fetch_ig_positions() -> dict[str, Any]:
    _load_env_file(REPO_ROOT / ".env")
    from utils.ig_index.session import Credentials, IGSession
    from utils.ig_index.instruments import load_instruments

    epic_to_symbol = {
        inst.epic: symbol for symbol, inst in load_instruments().items() if inst.epic
    }

    creds = Credentials.from_env()
    session = IGSession(creds)
    session.login()
    positions = normalise_ig_positions(session.positions(), epic_to_symbol)
    return {
        "account": creds.account_id,
        "environment": creds.environment,
        "positions": positions,
    }


# -------------------------------------------------------------- reconciliation


def load_holding_period_stats(
    path: Path = HOLDING_PERIOD_STATS_PATH,
) -> dict[str, Any]:
    """Cached per-symbol episode-holding stats (live adapter window, shared base
    signal). Returns {} if the cache hasn't been generated yet - callers
    must degrade gracefully, not fail the whole report over this."""
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _holding_cache_status(
    stats: dict[str, Any], iqfeed: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Validate both cache provenance and exact session alignment."""
    if not stats.get("computed_at_utc"):
        return {
            "usable": False,
            "reason": "missing",
            "note": "NOT COMPUTED - the nightly holding-stats job has not produced a cache",
        }
    provenance = stats.get("provenance") or {}
    if (
        stats.get("schema") != "carry96_holding_period_stats.v4"
        or provenance.get("panel_loader") != HOLDING_PANEL_LOADER
    ):
        return {
            "usable": False,
            "reason": "unverified_provenance",
            "note": (
                "** UNVERIFIED: cache does not attest that it used the live adapter's exact "
                "series; values suppressed until the nightly holding-stats job rebuilds it **"
            ),
        }
    panel_dates = {
        str(row["last_date"])
        for row in iqfeed.values()
        if row.get("last_date") is not None
    }
    if not iqfeed or not panel_dates:
        return {
            "usable": False,
            "reason": "panel_date_unknown",
            "note": "** UNVERIFIED: no signal-panel tail is available; cached values suppressed **",
        }
    if any(not row.get("current") for row in iqfeed.values()):
        return {
            "usable": False,
            "reason": "signal_panel_not_current",
            "note": "** STALE: signal panel is not current; cached values suppressed **",
        }
    cache_day = str(stats.get("window_end_day") or "")
    if len(panel_dates) != 1 or panel_dates != {cache_day}:
        return {
            "usable": False,
            "reason": "session_mismatch",
            "note": (
                f"** STALE/MIXED: cache ends {cache_day or '?'}, panel tails are "
                f"{sorted(panel_dates)}; cached values suppressed **"
            ),
        }
    return {
        "usable": True,
        "reason": None,
        "note": (
            f"verified live-series cache {stats['computed_at_utc']}, "
            f"{stats['window_start_day']}..{cache_day}"
        ),
    }


def _holding_cell(stats: dict[str, Any], symbol: str, direction: str) -> str:
    """direction: 'buy' or 'sell'. Measured separately, not assumed equal -
    across the roster SELL episodes run ~5x longer than BUY on average, and
    several symbols (e.g. AZN, PFE) have zero episodes of one direction."""
    row = (stats.get("per_symbol", {}).get(symbol) or {}).get(direction)
    if not row:
        return "n/a (no such episodes in window)"
    completed = int(row.get("completed_episodes", row.get("episodes", 0)))
    left = int(row.get("left_censored_episodes", 0))
    right = int(row.get("right_censored_episodes", 0))
    censoring = f", L={left}, R={right}" if left or right else ""
    if row.get("median_days") is None:
        return f"n/a (no completed episodes; n={completed}{censoring})"
    return (
        f"median {row['median_days']:g}d / mean {row['mean_days']:g}d "
        f"(n={completed}{censoring})"
    )


def _short_day(value: str | None) -> str:
    """2026-07-31... -> 07-31. Keeps wide tables narrow enough to render as a
    table rather than overflowing into raw text; the full year/window is
    always stated once in the header line above the table."""
    if not value:
        return "—"
    text = str(value)
    return text[5:10] if len(text) >= 10 and text[4] == "-" else text


def _short_status(status: str) -> str:
    return {
        "synced": "synced",
        "drift": "drift",
        "missing (target not filled)": "not filled",
        "missing (not dealt)": "not dealt",
        "exit pending (target flat)": "exit pending",
        "unexpected position (not in target)": "unexpected",
    }.get(status, status.split(" (")[0])


def _compact_holding(stats: dict[str, Any], symbol: str, direction: str) -> str:
    row = (stats.get("per_symbol", {}).get(symbol) or {}).get(direction)
    if not row:
        return "—"
    completed = int(row.get("completed_episodes", row.get("episodes", 0)))
    left = int(row.get("left_censored_episodes", 0))
    right = int(row.get("right_censored_episodes", 0))
    censored = f" L{left}/R{right}" if left or right else ""
    if row.get("median_days") is None:
        return f"n/a n={completed}{censored}"
    return f"{row['median_days']:g}d/{row['mean_days']:g}d n={completed}{censored}"


def _compact_direction(stats: dict[str, Any], symbol: str) -> str:
    row = stats.get("current_direction", {}).get(symbol)
    if not row:
        return "—"
    if row["direction"] == "FLAT":
        return "FLAT"
    bound = "≤" if row.get("since_day_is_left_censored") else ""
    return (
        f"{row['direction']} {bound}{_short_day(row['since_day'])} "
        f"({row['trading_days_held']}d)"
    )


def _holding_note(stats: dict[str, Any], iqfeed: dict[str, dict[str, Any]]) -> str:
    """Header note for the cached hold/direction columns, and - importantly -
    whether that cache has fallen behind the signal panel.

    The cache is generated by a separate heavy script, so a nightly panel
    refresh silently leaves "Typical Hold when BUY/SELL" and "Current
    Direction Set Since" a session stale while the IQFeed Signal column
    already shows the newer date. That happened on 2026-08-05 (panel 08/05,
    cache 08/04) and is indistinguishable from a correct report unless the two
    dates are compared here.
    """
    return str(_holding_cache_status(stats, iqfeed)["note"])


def _current_direction_cell(stats: dict[str, Any], symbol: str) -> str:
    """When the model itself first flipped this symbol to the direction it
    is STILL holding as of the cache's own last session - not a snapshot
    write timestamp. Walks back from the latest day in the rebuilt panel
    while the sign stays constant (scripts/compute_carry96_holding_period_stats.py);
    a fresh model run, not a cached file's metadata."""
    row = stats.get("current_direction", {}).get(symbol)
    if not row:
        return "n/a (re-run scripts/compute_carry96_holding_period_stats.py)"
    if row["direction"] == "FLAT":
        return "FLAT as of model's last session"
    since = (
        f"on or before {row['since_day']}"
        if row.get("since_day_is_left_censored")
        else f"{row['since_day']}"
    )
    return (
        f"{row['direction']} since {since} "
        f"({row['trading_days_held']} trading days, as of model's last session "
        f"{stats.get('window_end_day', '?')})"
    )


def load_ibkr_last_fill_times(path: Path = IBKR_EVENTS_PATH) -> dict[str, str]:
    """Most recent fill timestamp per symbol from the adapter's own durable
    event log (NOT from ib.fills()/ib.executions(), which only cover
    executions placed by the current API connection and would silently miss
    everything from earlier sessions).

    This is "when was this position last adjusted," not "when was it first
    opened" - the near-close adapter reconciles-and-holds, so a position can
    have been open far longer than its most recent fill. There is no
    "opened from flat" tracking here; callers should label it accordingly.
    """
    last_fill: dict[str, str] = {}
    if not path.is_file():
        return last_fill
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event_type") != "fill":
                continue
            symbol = event.get("symbol")
            ts = event.get("execution_time") or event.get("logged_at_iso")
            if not symbol or not ts:
                continue
            # Events are appended in order, so the last one wins; guard
            # against any out-of-order lines anyway.
            prior = last_fill.get(symbol)
            if prior is None or str(ts) >= str(prior):
                last_fill[symbol] = str(ts)
    return last_fill


def build_ibkr_rows(
    target: dict[str, Any],
    actual: dict[str, Any],
    last_fill: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    nonflat_targets = {
        symbol for symbol, shares in target["positions"].items() if int(shares) != 0
    }
    actual_symbols = {
        symbol for symbol, shares in actual["positions"].items() if int(shares) != 0
    }
    # The snapshot deliberately contains all 96 symbols, including explicit
    # zero targets. Show those FLAT rows only when there is something held to
    # exit; otherwise the useful reconciliation would be buried in 89 no-ops.
    symbols = sorted(nonflat_targets | actual_symbols)
    pnl_map = actual.get("pnl", {})
    last_fill = last_fill or {}
    rows = []
    for sym in symbols:
        tgt = target["positions"].get(sym, 0)
        act = actual["positions"].get(sym, 0)
        diff = act - tgt
        if sym not in target["positions"]:
            status = "unexpected position (not in target)"
        elif tgt == 0 and act != 0:
            status = "exit pending (target flat)"
        elif act == 0:
            status = "missing (target not filled)"
        elif diff == 0:
            status = "synced"
        else:
            status = "drift"
        pnl = pnl_map.get(sym, {})
        unrealized = pnl.get("unrealized")
        realized = pnl.get("realized")
        total_pnl = (
            (unrealized or 0.0) + (realized or 0.0)
            if unrealized is not None or realized is not None
            else None
        )
        rows.append(
            {
                "symbol": sym,
                "target": tgt,
                "actual": act,
                "diff": diff,
                "status": status,
                "unrealized_pnl": unrealized,
                "realized_pnl": realized,
                "total_pnl": total_pnl,
                "last_fill_utc": last_fill.get(sym),
                # Signed working-order qty, and whether it would land exactly on
                # target if it filled - so a drift with a correct order against
                # it is visibly different from an unattended one.
                "pending": (actual.get("pending") or {}).get(sym, 0),
                "pending_closes_diff": (
                    (actual.get("pending") or {}).get(sym, 0) == (tgt - act)
                    and (tgt - act) != 0
                ),
            }
        )
    return rows


def build_ig_rows(target: dict[str, Any], actual: dict[str, Any]) -> list[dict[str, Any]]:
    nonflat_targets = {
        symbol
        for symbol, direction in target["directions"].items()
        if direction != "FLAT"
    }
    symbols = sorted(nonflat_targets | set(actual["positions"]))
    rows = []
    for sym in symbols:
        tgt_dir = target["directions"].get(sym)
        act = actual["positions"].get(sym)
        act_dir = act["direction"] if act else None
        if tgt_dir is None:
            status = "unexpected position (not in target)"
        elif tgt_dir == "FLAT" and act is not None:
            status = "exit pending (target flat)"
        elif tgt_dir == "FLAT":
            status = "synced"
        elif act is None:
            status = "missing (not dealt)"
        elif int(act.get("deal_count", 1)) > 1:
            status = (
                "hedged positions" if act.get("hedged") else "stacked positions"
            )
        elif tgt_dir == act_dir:
            status = "synced"
        else:
            status = f"direction mismatch (target {tgt_dir}, actual {act_dir})"
        rows.append(
            {
                "symbol": sym,
                "target_dir": tgt_dir,
                "actual_dir": act_dir,
                "actual_size": act["size"] if act else None,
                "status": status,
                "opened_at_utc": act["created_at_utc"] if act else None,
                "pnl": act["pnl"] if act else None,
            }
        )
    return rows


# --------------------------------------------------------------------- render


def _status_icon(status: str) -> str:
    return "✅" if status == "synced" else "⚠️"


def _money_cell(value: float | None, currency: str = "$") -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else "-"
    return f"{sign}{currency}{abs(value):,.2f}"


def render_ibkr_markdown(
    target: dict[str, Any],
    actual: dict[str, Any],
    rows: list[dict[str, Any]],
    iqfeed: dict[str, dict[str, Any]],
    holding_stats: dict[str, Any] | None = None,
) -> str:
    holding_stats = holding_stats or {}
    holding_status = _holding_cache_status(holding_stats, iqfeed)
    visible_holding_stats = holding_stats if holding_status["usable"] else {}
    holding_note = str(holding_status["note"])
    timing_status = target.get("execution_timing_status") or _execution_timing_status(
        target.get("execution_timing")
    )
    lines = [
        f"**IBKR — {actual.get('account', '?')}** "
        f"(paper={actual.get('is_paper')}; target_day={target.get('target_day')}, "
        f"signal_as_of={target.get('signal_as_of_day')}; "
        f"execution_timing={target.get('execution_timing')} "
        f"[{timing_status['label']}]; "
        f"queried {actual.get('queried_at')}; "
        f"next session {next_expected_session(target.get('target_day'))}; "
        f"decision produced {_decision_age_cell(generated_at_epoch=target.get('generated_at'))}; "
        f"holding-period stats: {holding_note})",
        "",
        "| Symbol | IQFeed Signal | Target (shares) | Actual | Diff | Status | P&L | Live Quote Check | Last Fill (not \"opened\" - reconcile-and-hold may predate it) | Typical Hold when BUY (live-panel window) | Typical Hold when SELL (live-panel window) | Current Direction Set Since (model re-run) |",
        "|---|---|---:|---:|---:|---|---:|---|---|---|---|---|",
    ]
    pnl_total = 0.0
    pnl_known = False
    for row in rows:
        pnl_cell = _money_cell(row["total_pnl"])
        if row["total_pnl"] is not None:
            pnl_total += row["total_pnl"]
            pnl_known = True
        last_fill_utc = row.get("last_fill_utc")
        last_fill_cell = (
            f"{last_fill_utc} ({_age_str(last_fill_utc)} ago)"
            if last_fill_utc
            else "no fill in adapter's event log"
        )
        lines.append(
            f"| {row['symbol']} | {_iqfeed_cell(iqfeed, row['symbol'])} "
            f"| {row['target']:+d} | {row['actual']:+d} | {row['diff']:+d} "
            f"| {_status_icon(row['status'])} {row['status']} "
            f"| {pnl_cell} "
            f"| live @ {actual.get('queried_at')} "
            f"| {last_fill_cell} "
            f"| {_holding_cell(visible_holding_stats, row['symbol'], 'buy')} "
            f"| {_holding_cell(visible_holding_stats, row['symbol'], 'sell')} "
            f"| {_current_direction_cell(visible_holding_stats, row['symbol'])} |"
        )
    if pnl_known:
        lines.append(
            f"| **Total** | | | | | | **{_money_cell(pnl_total)}** | | | | | |"
        )
    lines += [
        "",
        f"Legend — IQFeed Signal: daily panel last session. Live Quote Check: "
        f"`live` = P&L "
        f"marked at the header's query time ({actual.get('queried_at')}), not cached. "
        "Last Fill: most recent fill in the ADAPTER's event log — NOT when the "
        "position was opened (it reconciles-and-holds, so a position can predate "
        "its last fill; one opened outside the adapter shows "
        "`no fill in adapter's event log`). "
        "Hold BUY/SELL: completed-run median/mean, n = fully observed episodes; "
        "L/R = left/right-censored runs excluded from those statistics. Small n makes "
        "these rough scale indicators, not reliable estimates. Direction Since: when "
        "the model last set this direction; ≤ marks a left-censored lower bound.",
    ]
    return "\n".join(lines)


def render_ig_markdown(
    target: dict[str, Any],
    actual: dict[str, Any],
    rows: list[dict[str, Any]],
    iqfeed: dict[str, dict[str, Any]],
    holding_stats: dict[str, Any] | None = None,
) -> str:
    holding_stats = holding_stats or {}
    holding_status = _holding_cache_status(holding_stats, iqfeed)
    visible_holding_stats = holding_stats if holding_status["usable"] else {}
    holding_note = str(holding_status["note"])
    lines = [
        f"**IG Index — {actual.get('account', '?')}** "
        f"(env={actual.get('environment')}; target_day={target.get('target_day')}, "
        f"snapshot_day={target.get('target_snapshot_day')}; "
        f"order_capable_plan={target.get('order_capable_plan')}; "
        f"target_vector_complete={target.get('target_vector_complete')}; "
        f"next session {next_expected_session(target.get('target_day'))}; "
        f"last plan written {_decision_age_cell(generated_at_iso=target.get('generated_at_utc'))}; "
        f"holding-period stats: {holding_note})",
        "",
        "| Symbol | Signal | Target | Actual | Status | P&L (GBP) | Opened | Hold BUY | Hold SELL | Direction Since |",
        "|---|---|---|---|---|---:|---|---|---|---|",
    ]
    pnl_total = 0.0
    pnl_known = False
    for row in rows:
        actual_desc = (
            f"{row['actual_dir']} {row['actual_size']}"
            + (
                f" ({actual['positions'][row['symbol']].get('deal_count')} deals)"
                if actual["positions"].get(row["symbol"], {}).get("deal_count", 1) > 1
                else ""
            )
            if row["actual_dir"]
            else "—"
        )
        opened = (
            f"{_short_day(str(row['opened_at_utc'])[:10])} "
            f"({_age_str(row['opened_at_utc'])})"
            if row["opened_at_utc"]
            else "—"
        )
        pnl_cell = _money_cell(row["pnl"], currency="£")
        if row["pnl"] is not None:
            pnl_total += row["pnl"]
            pnl_known = True
        fresh = iqfeed.get(row["symbol"], {})
        signal_cell = (
            f"{'🟢' if fresh.get('current') else '🔴'} {_short_day(fresh.get('last_date'))}"
            f"{'' if fresh.get('current') else ' STALE'}"
        )
        lines.append(
            f"| {row['symbol']} | {signal_cell} "
            f"| {row['target_dir'] or '—'} | {actual_desc} "
            f"| {_status_icon(row['status'])} {_short_status(row['status'])} | {pnl_cell} | {opened} "
            f"| {_compact_holding(visible_holding_stats, row['symbol'], 'buy')} "
            f"| {_compact_holding(visible_holding_stats, row['symbol'], 'sell')} "
            f"| {_compact_direction(visible_holding_stats, row['symbol'])} |"
        )
    if pnl_known:
        lines.append(
            f"| **Total** | | | | | **{_money_cell(pnl_total, currency='£')}** | | | | |"
        )
    lines += [
        "",
        "Legend — Signal: IQFeed daily panel last session. Opened: when the IG "
        "position was actually dealt (IG closes and re-opens each session, so this "
        "is a true open time). Hold BUY/SELL: completed-run median/mean, n = fully "
        "observed episodes; L/R = censored runs excluded from those statistics. "
        "Small n makes these rough scale indicators, not reliable estimates. "
        "Direction Since: when the model last set this direction; ≤ marks a bound.",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ibkr-only", action="store_true")
    parser.add_argument("--ig-only", action="store_true")
    parser.add_argument("--host", default=DEFAULT_IBKR_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_IBKR_PORT)
    parser.add_argument("--client-id", type=int, default=DEFAULT_IBKR_REPORT_CLIENT_ID)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of markdown")
    args = parser.parse_args(argv)

    do_ibkr = not args.ig_only
    do_ig = not args.ibkr_only
    holding_stats = load_holding_period_stats()

    report: dict[str, Any] = {
        "generated_at_utc": _iso_now(),
        "holding_period_stats": holding_stats,
    }
    outputs: list[str] = []
    exit_code = 0

    if do_ibkr:
        try:
            target = load_ibkr_target()
            actual = fetch_ibkr_positions(args.host, args.port, args.client_id)
            last_fill = load_ibkr_last_fill_times()
            rows = build_ibkr_rows(target, actual, last_fill)
            iqfeed = check_iqfeed_freshness(sorted({r["symbol"] for r in rows}))
            holding_status = _holding_cache_status(holding_stats, iqfeed)
            next_session = next_expected_session(target.get("target_day"))
            report["ibkr"] = {
                "target": target,
                "actual": actual,
                "rows": rows,
                "iqfeed": iqfeed,
                "holding_cache_status": holding_status,
                "next_expected_session": next_session,
            }
            if not args.json:
                outputs.append(render_ibkr_markdown(target, actual, rows, iqfeed, holding_stats))
            if any(r["status"] != "synced" for r in rows):
                exit_code = 1
            if any(not v["current"] for v in iqfeed.values()):
                exit_code = max(exit_code, 1)
            if not holding_status["usable"]:
                exit_code = max(exit_code, 1)
            if target["execution_timing_status"]["kind"] == "unknown":
                exit_code = max(exit_code, 1)
        except Exception as exc:  # noqa: BLE001
            report["ibkr_error"] = str(exc)
            outputs.append(f"**IBKR** — report failed: {exc}")
            exit_code = 2

    if do_ig:
        try:
            target = load_ig_target()
            actual = fetch_ig_positions()
            rows = build_ig_rows(target, actual)
            iqfeed = check_iqfeed_freshness(sorted({r["symbol"] for r in rows}))
            holding_status = _holding_cache_status(holding_stats, iqfeed)
            next_session = next_expected_session(target.get("target_day"))
            report["ig"] = {
                "target": target,
                "actual": actual,
                "rows": rows,
                "iqfeed": iqfeed,
                "holding_cache_status": holding_status,
                "next_expected_session": next_session,
            }
            if not args.json:
                outputs.append(render_ig_markdown(target, actual, rows, iqfeed, holding_stats))
            if any(r["status"] != "synced" for r in rows):
                exit_code = 1
            if any(not v["current"] for v in iqfeed.values()):
                exit_code = max(exit_code, 1)
            if not holding_status["usable"]:
                exit_code = max(exit_code, 1)
            if not target["order_capable_plan"] or not target["target_vector_complete"]:
                exit_code = max(exit_code, 1)
        except Exception as exc:  # noqa: BLE001
            report["ig_error"] = str(exc)
            outputs.append(f"**IG Index** — report failed: {exc}")
            exit_code = 2

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print("\n\n".join(outputs))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
