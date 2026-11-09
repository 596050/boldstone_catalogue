#!/usr/bin/env python3
# fixed_run.py - Main script to run the trading system with proper integration

import argparse
import logging
import time
from ib_insync import IB
from utils.trading.order_management import OrderManagementSystem, create_stock_contract
from utils.trading.market_maker import MarketMaker, MarketMakerSettings, StrategyType
from utils.trading.portfolio_manager import PortfolioManager
from utils.trading.standalone_market_data import StandaloneMarketData
from utils.trading.market_maker_config import DEFAULT_SETTINGS, max_order_sizes
from utils.trading.logging_config import setup_logging
from utils.trading.runtime_state import RuntimeStateStore

setup_logging()
logger = logging.getLogger(__name__)

ADOPTABLE_ORDER_STATUSES = {"ApiPending", "PendingSubmit", "PreSubmitted", "Submitted"}


class StartupReconciliationError(RuntimeError):
    def __init__(self, message, components=None):
        super().__init__(message)
        self.components = components or {}


def connect_to_ib(
    host,
    port,
    client_id,
    *,
    timeout=4.0,
    attempts=1,
    retry_delay_seconds=1.0,
):
    """Connect with bounded retries, including IB's startup state handshake."""

    maximum_attempts = max(int(attempts), 1)
    for attempt in range(1, maximum_attempts + 1):
        ib = IB()
        try:
            ib.connect(
                host,
                port,
                clientId=client_id,
                timeout=max(float(timeout), 0.1),
            )
            logger.info(
                "Connected to IB (client_id=%s attempt=%d/%d)",
                client_id,
                attempt,
                maximum_attempts,
            )
            return ib
        except Exception as e:
            try:
                ib.disconnect()
            except Exception:
                pass
            logger.error(
                "Connection error (client_id=%s attempt=%d/%d): %s",
                client_id,
                attempt,
                maximum_attempts,
                e,
            )
            if attempt < maximum_attempts:
                time.sleep(max(float(retry_delay_seconds), 0.0))
    return None


def initialize_oms(ib):
    if not ib.isConnected():
        logger.error("Cannot initialize OMS: IB not connected")
        return None
    oms = OrderManagementSystem(ib, max_order_sizes)
    logger.info("Order Management System initialized")
    return oms


def initialize_market_maker(ib, oms, runtime_state_store=None):
    if not oms:
        logger.error("Cannot initialize Market Maker: OMS not initialized")
        return None
    market_maker = MarketMaker(ib, oms, runtime_state_store=runtime_state_store)
    logger.info("Market Maker initialized")
    return market_maker


def add_default_market_makers(market_maker, runtime_states=None):
    if not market_maker:
        logger.error("Cannot add market makers: Market Maker not initialized")
        return []
    symbols_to_track = []
    runtime_states = runtime_states or {}
    for symbol, settings_dict in DEFAULT_SETTINGS.items():
        try:
            normalized_settings = dict(settings_dict)
            normalized_settings["strategy_type"] = StrategyType(
                normalized_settings["strategy_type"]
            )
            settings = MarketMakerSettings.from_dict(normalized_settings)
            runtime_state = runtime_states.get(symbol)
            if market_maker.add_market_maker(settings, runtime_state=runtime_state):
                logger.info(f"Added market maker for {symbol}")
                symbols_to_track.append(
                    {
                        "symbol": symbol,
                        "exchange": settings.exchange,
                        "currency": settings.currency,
                        "primary_exchange": settings.primary_exchange,
                    }
                )
            else:
                logger.error(f"Failed to add market maker for {symbol}")
        except Exception as e:
            logger.error(f"Error adding market maker for {symbol}: {e}")
    return symbols_to_track


def warm_broker_state_cache(oms):
    broker_state = getattr(oms, "broker_state", None)
    if broker_state is None:
        logger.warning("OMS has no broker-state cache; startup warmup skipped")
        return None

    if not broker_state.warmup():
        position_error = broker_state.last_positions_error or "unknown position refresh failure"
        order_error = broker_state.last_open_orders_error or "unknown open-order refresh failure"
        raise StartupReconciliationError(
            f"Broker-state warmup failed: positions={position_error}; open_orders={order_error}"
        )

    positions = broker_state.snapshot_positions()
    open_orders = broker_state.get_open_orders(refresh=False)
    logger.info(
        "Broker-state cache warmed with %d positions and %d open orders",
        len(positions),
        len(open_orders),
    )
    for symbol, snapshot in sorted(positions.items()):
        logger.info(
            "%s: Broker snapshot position=%s avg_cost=%s updated_at=%s",
            symbol,
            snapshot.quantity,
            snapshot.avg_cost,
            snapshot.updated_at,
        )
    return broker_state


def initialize_runtime_state_store(path: str = ".runtime/market_maker_state.json"):
    store = RuntimeStateStore(path=path)
    logger.info("Runtime state store initialized at %s", store.path)
    return store


def _snapshot_side_key(snapshot):
    role = snapshot.role or ""
    if role.endswith("_bid"):
        return "bid"
    if role.endswith("_ask"):
        return "ask"
    side = (snapshot.side or "").upper()
    if side == "BUY":
        return "bid"
    if side == "SELL":
        return "ask"
    return None


def reconcile_startup_orders(
    oms,
    market_maker=None,
    runtime_states=None,
    timeout_seconds=10.0,
    poll_interval=0.25,
):
    summary = {
        "started_at": time.time(),
        "finished_at": None,
        "adopted_order_refs": [],
        "cancelled_order_refs": [],
        "cancellation_reasons": [],
        "adopted_count": 0,
        "cancelled_count": 0,
    }
    runtime_states = runtime_states or {}
    logger.info("Startup reconciliation started")

    snapshots = oms.list_open_market_maker_orders(refresh=True)
    if not snapshots:
        logger.info("No live market-maker orders found during startup reconciliation")
        summary["finished_at"] = time.time()
        if market_maker is not None:
            market_maker.set_startup_reconciliation_summary(summary)
            market_maker.persist_runtime_state()
        return summary

    cancellations = []
    adopted_refs = set()

    if market_maker is None:
        cancellations = [(snapshot, "cancel_and_rebuild") for snapshot in snapshots]
    else:
        grouped = {}
        for snapshot in snapshots:
            state = market_maker.market_makers.get(snapshot.symbol)
            side_key = _snapshot_side_key(snapshot)
            if state is None:
                cancellations.append((snapshot, "orphaned_symbol"))
                continue
            if side_key is None:
                cancellations.append((snapshot, "unknown_side"))
                continue
            if snapshot.status not in ADOPTABLE_ORDER_STATUSES:
                cancellations.append((snapshot, "not_active"))
                continue

            wants_bid, wants_ask = state.desired_quote_sides()
            if (side_key == "bid" and not wants_bid) or (
                side_key == "ask" and not wants_ask
            ):
                cancellations.append((snapshot, "inconsistent_side"))
                continue

            grouped.setdefault((snapshot.symbol, side_key), []).append(snapshot)

        for (symbol, side_key), group in grouped.items():
            tracked_key = f"tracked_{side_key}_order_ref"
            tracked_ref = runtime_states.get(symbol, {}).get(tracked_key)
            chosen_snapshot = None

            if tracked_ref:
                matches = [snapshot for snapshot in group if snapshot.order_ref == tracked_ref]
                if len(matches) == 1:
                    chosen_snapshot = matches[0]

            if chosen_snapshot is None and len(group) == 1:
                chosen_snapshot = group[0]

            if chosen_snapshot is None:
                cancellations.extend((snapshot, "ambiguous_side") for snapshot in group)
                continue

            adopted_order = market_maker.adopt_open_order_snapshot(chosen_snapshot)
            if adopted_order is None:
                cancellations.append((chosen_snapshot, "adoption_failed"))
                continue

            adopted_refs.add(chosen_snapshot.order_ref or f"order_id={chosen_snapshot.order_id}")
            summary["adopted_order_refs"].append(
                chosen_snapshot.order_ref or f"order_id={chosen_snapshot.order_id}"
            )
            for snapshot in group:
                if snapshot is not chosen_snapshot:
                    cancellations.append((snapshot, "duplicate_side"))

    failed = []
    for snapshot, reason in cancellations:
        success, message = oms.cancel_open_order_snapshot(snapshot)
        if success:
            summary["cancelled_order_refs"].append(message)
            summary["cancellation_reasons"].append({"order_ref": message, "reason": reason})
            logger.info("Startup reconciliation cancelled %s (%s)", message, reason)
        else:
            failed.append(message)

    if failed:
        raise StartupReconciliationError(
            "Failed to reconcile existing market-maker orders: " + "; ".join(failed)
        )

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        remaining = oms.list_open_market_maker_orders(refresh=True)
        remaining_refs = {
            snapshot.order_ref or f"order_id={snapshot.order_id}" for snapshot in remaining
        }
        unresolved = remaining_refs - adopted_refs
        if not unresolved:
            summary["adopted_count"] = len(summary["adopted_order_refs"])
            summary["cancelled_count"] = len(summary["cancelled_order_refs"])
            summary["finished_at"] = time.time()
            logger.info(
                "Startup reconciliation finished: adopted=%d cancelled=%d",
                summary["adopted_count"],
                summary["cancelled_count"],
            )
            if market_maker is not None:
                market_maker.set_startup_reconciliation_summary(summary)
                market_maker.persist_runtime_state()
            return summary
        time.sleep(poll_interval)

    remaining_refs = [
        snapshot.order_ref or f"order_id={snapshot.order_id}"
        for snapshot in oms.list_open_market_maker_orders(refresh=True)
        if (snapshot.order_ref or f"order_id={snapshot.order_id}") not in adopted_refs
    ]
    raise StartupReconciliationError(
        "Timed out waiting for market-maker orders to clear during reconciliation: "
        + ", ".join(remaining_refs)
    )


def initialize_market_data(
    ib,
    symbols_to_track,
    *,
    require_live=False,
    live_preflight_timeout=5.0,
):
    symbols_to_track = list(symbols_to_track)
    standalone_md = StandaloneMarketData(ib)
    try:
        if require_live and not symbols_to_track:
            raise RuntimeError("live market-data preflight requires at least one symbol")

        for index, symbol_info in enumerate(symbols_to_track):
            contract = create_stock_contract(
                symbol=symbol_info["symbol"],
                exchange=symbol_info.get("exchange", "SMART"),
                currency=symbol_info.get("currency", "USD"),
                primary_exchange=symbol_info.get("primary_exchange"),
            )
            standalone_md.request_market_data(contract)
            # Prove entitlement and a usable live NBBO on one representative
            # symbol before opening the remaining 95 subscriptions or starting
            # the market maker. Venue-specific gaps still fail closed per symbol
            # in the execution loop.
            if require_live and index == 0:
                standalone_md.require_live_quote(
                    symbol_info["symbol"], timeout_seconds=live_preflight_timeout
                )
        return standalone_md
    except Exception:
        standalone_md.shutdown()
        raise


def bootstrap_runtime(ib, runtime_state_store=None):
    components = {
        "oms": None,
        "market_maker": None,
        "portfolio_manager": None,
        "standalone_md": None,
        "runtime_state_store": None,
    }
    runtime_state_store = runtime_state_store or initialize_runtime_state_store()
    runtime_states = runtime_state_store.load_symbol_states()
    components["runtime_state_store"] = runtime_state_store

    oms = initialize_oms(ib)
    if not oms:
        raise StartupReconciliationError("OMS failed to initialize", components)
    components["oms"] = oms

    try:
        warm_broker_state_cache(oms)
    except StartupReconciliationError as exc:
        raise StartupReconciliationError(str(exc), components) from exc

    market_maker = initialize_market_maker(
        ib, oms, runtime_state_store=runtime_state_store
    )
    if not market_maker:
        raise StartupReconciliationError("Market maker failed to initialize", components)
    components["market_maker"] = market_maker

    symbols_to_track = add_default_market_makers(
        market_maker, runtime_states=runtime_states
    )
    try:
        reconcile_startup_orders(
            oms,
            market_maker=market_maker,
            runtime_states=runtime_states,
        )
    except StartupReconciliationError as exc:
        raise StartupReconciliationError(str(exc), components) from exc

    portfolio_manager = PortfolioManager(ib, oms, market_maker)
    portfolio_manager.start()
    logger.info("Portfolio Manager started")
    components["portfolio_manager"] = portfolio_manager

    standalone_md = initialize_market_data(ib, symbols_to_track)
    components["standalone_md"] = standalone_md

    if not market_maker.start():
        raise StartupReconciliationError("Market maker failed to start", components)
    logger.info("Market maker started")

    return components


def cleanup(ib, oms, market_maker, standalone_md, portfolio_manager=None):
    logger.info("Cleaning up resources...")
    if oms:
        oms.shutdown()
    if portfolio_manager:
        try:
            portfolio_manager.stop()
            logger.info("Portfolio manager stopped")
        except Exception as e:
            logger.error(f"Error stopping portfolio manager: {e}")
    if market_maker:
        try:
            market_maker.stop()
            market_maker.persist_runtime_state()
            logger.info("Market maker stopped")
        except Exception as e:
            logger.error(f"Error stopping market maker: {e}")
    if standalone_md:
        standalone_md.shutdown()
        logger.info("Market data subscriptions cancelled")
    if ib.isConnected():
        try:
            ib.disconnect()
            logger.info("Disconnected from IB")
        except Exception as e:
            logger.error(f"Error disconnecting from IB: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trading System")
    # parser.add_argument('--host', type=str, default='host.docker.internal', help='IB TWS/Gateway host')
    # #parser.add_argument('--host', type=str, default='host.docker.internal', help='IB TWS/Gateway host')
    # parser.add_argument('--host', type=str, default='192.168.5.39', help='IB TWS/Gateway host')
    # parser.add_argument('--host', type=str, default='host.docker.internal', help='IB TWS/Gateway host')
    parser.add_argument(
        "--host", type=str, default="localhost", help="IB TWS/Gateway host"
    )
    # parser.add_argument('--host', type=str, default='192.168.5.39', help='IB TWS/Gateway host')
    parser.add_argument("--port", type=int, default=7497, help="IB TWS/Gateway port")
    parser.add_argument("--client-id", type=int, default=0, help="IB client ID")
    parser.add_argument(
        "--runtime-state-path",
        type=str,
        default=".runtime/market_maker_state.json",
        help="Path to persisted runtime state JSON",
    )
    args = parser.parse_args()

    ib = connect_to_ib(args.host, args.port, args.client_id)
    if not ib:
        logger.error("Failed to connect to IB. Exiting.")
        exit(1)

    ib.reqMarketDataType(3)

    oms = None
    market_maker = None
    standalone_md = None
    portfolio_manager = None
    runtime_state_store = initialize_runtime_state_store(args.runtime_state_path)
    try:
        components = bootstrap_runtime(ib, runtime_state_store=runtime_state_store)
        oms = components["oms"]
        market_maker = components["market_maker"]
        standalone_md = components["standalone_md"]
        portfolio_manager = components["portfolio_manager"]
    except StartupReconciliationError as e:
        components = e.components
        oms = components.get("oms", oms)
        market_maker = components.get("market_maker", market_maker)
        standalone_md = components.get("standalone_md", standalone_md)
        portfolio_manager = components.get("portfolio_manager", portfolio_manager)
        logger.error(f"Startup reconciliation failed. Exiting: {e}")
        cleanup(ib, oms, market_maker, standalone_md, portfolio_manager)
        exit(1)

    try:
        logger.info("Running IB event loop indefinitely. Press Ctrl+C to stop.")
        ib.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    finally:
        cleanup(ib, oms, market_maker, standalone_md, portfolio_manager)
