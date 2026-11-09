# market_maker.py
import threading
import time
import logging
import math
from enum import Enum
from typing import Dict, Optional
from ib_insync import IB
from decimal import Decimal
from utils.trading.order_management import OrderManagementSystem, OrderSide, OrderType, OrderStatus, OrderRecord, create_stock_contract
from utils.trading.shared_market_data import market_data_store

logger = logging.getLogger('MarketMaker')

def to_decimal_price(price, places=2):
    return Decimal(str(price)).quantize(Decimal('0.01'))

class StrategyType(Enum):
    BASIC_SPREAD = "BASIC_SPREAD"
    INVENTORY_SKEW = "INVENTORY_SKEW"
    DYNAMIC_SPREAD = "DYNAMIC_SPREAD"


class QuoteMode(Enum):
    NORMAL = "NORMAL"
    REDUCE_ONLY = "REDUCE_ONLY"
    HALTED = "HALTED"


class MarketMakerSettings:
    def __init__(
            self,
            symbol: str,
            exchange: str = "SMART",
            currency: str = "USD",
            primary_exchange: Optional[str] = None,
            strategy_type: StrategyType = StrategyType.BASIC_SPREAD,
            base_spread_bps: float = 20.0,
            min_spread_bps: float = 10.0,
            max_spread_bps: float = 50.0,
            quote_size: float = 10.0,
            max_position: float = 100.0,
            inventory_skew_factor: float = 0.2,
            order_timeout_seconds: float = 30.0,
            tick_size: float = 0.01,
            refresh_threshold_pct: float = 0.7,
            restart_reduce_only: bool = True,
            inventory_reduce_threshold_pct: float = 0.5,
            inventory_halt_threshold_pct: float = 0.9,
        ):
        self.symbol = symbol
        self.exchange = exchange
        self.currency = currency
        self.primary_exchange = primary_exchange
        self.strategy_type = strategy_type
        self.base_spread_bps = base_spread_bps
        self.min_spread_bps = min_spread_bps
        self.max_spread_bps = max_spread_bps
        self.quote_size = quote_size
        self.max_position = max_position
        self.inventory_skew_factor = inventory_skew_factor
        self.order_timeout_seconds = order_timeout_seconds
        self.tick_size = tick_size
        self.refresh_threshold_pct = refresh_threshold_pct
        self.restart_reduce_only = restart_reduce_only
        self.inventory_reduce_threshold_pct = inventory_reduce_threshold_pct
        self.inventory_halt_threshold_pct = inventory_halt_threshold_pct

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "currency": self.currency,
            "primary_exchange": self.primary_exchange,
            "strategy_type": self.strategy_type.value,
            "base_spread_bps": self.base_spread_bps,
            "min_spread_bps": self.min_spread_bps,
            "max_spread_bps": self.max_spread_bps,
            "quote_size": self.quote_size,
            "max_position": self.max_position,
            "inventory_skew_factor": self.inventory_skew_factor,
            "order_timeout_seconds": self.order_timeout_seconds,
            "tick_size": self.tick_size,
            "refresh_threshold_pct": self.refresh_threshold_pct,
            "restart_reduce_only": self.restart_reduce_only,
            "inventory_reduce_threshold_pct": self.inventory_reduce_threshold_pct,
            "inventory_halt_threshold_pct": self.inventory_halt_threshold_pct,
        }

    @classmethod
    def from_dict(cls, data: Dict):
        data["strategy_type"] = StrategyType(data["strategy_type"])
        return cls(**data)

class MarketMakerState:
    def __init__(self, settings: MarketMakerSettings, contract):
        self.settings = settings
        self.contract = contract
        self.current_position = 0.0
        self.bid_order_id = None
        self.ask_order_id = None
        self.last_bid = None
        self.last_ask = None
        self.last_bid_size = None
        self.last_ask_size = None
        self.last_mid = None
        self.last_quoted_mid = None
        self.last_quote_time = 0.0
        self.last_position_sync_time = 0.0
        self.consecutive_data_failures = 0
        self.position_avg_price = None
        self.cooldown_until = 0
        self.quote_mode = QuoteMode.NORMAL
        self.quote_mode_reason = "flat"
        self.override_quote_mode = None
        self.override_quote_mode_reason = None
        self.startup_reduce_only = False
        self.missing_avg_cost = False
        self.tracked_bid_order_ref = None
        self.tracked_ask_order_ref = None
        self.quote_size_multiplier = 1.0

    def update_market_data(
        self,
        bid: Optional[float],
        ask: Optional[float],
        bid_size: Optional[float] = None,
        ask_size: Optional[float] = None,
    ):
        if bid is None or ask is None or math.isnan(bid) or math.isnan(ask) or bid <= 0 or ask <= 0 or bid >= ask:
            return False
        self.last_bid = bid
        self.last_ask = ask
        self.last_bid_size = bid_size
        self.last_ask_size = ask_size
        if bid_size and ask_size and bid_size > 0 and ask_size > 0:
            # Microprice: when ask is thin (small ask_size), the term bid_size*ask
            # dominates and the fair value sits closer to ask — reflecting the
            # higher probability that the next trade lifts the offer.
            self.last_mid = (bid_size * ask + ask_size * bid) / (bid_size + ask_size)
        else:
            self.last_mid = (bid + ask) / 2
        return True

    def desired_quote_sides(self):
        if self.quote_mode == QuoteMode.HALTED:
            return False, False
        if self.quote_mode == QuoteMode.REDUCE_ONLY:
            if self.current_position > 0:
                return False, True
            if self.current_position < 0:
                return True, False
        return True, True

    def should_refresh_quotes(self):
        wants_bid, wants_ask = self.desired_quote_sides()
        has_bid = self.bid_order_id is not None
        has_ask = self.ask_order_id is not None
        if not wants_bid and not wants_ask and not has_bid and not has_ask:
            return False
        if wants_bid != has_bid or wants_ask != has_ask:
            return True
        if time.time() - self.last_quote_time > self.settings.order_timeout_seconds:
            return True
        threshold = self.settings.refresh_threshold_pct / 100.0
        if (self.last_mid is not None and self.last_quoted_mid is not None and 
            abs(self.last_mid - self.last_quoted_mid) / self.last_quoted_mid >= threshold):
            return True
        return False

    def calculate_quote_prices(self):
        if self.last_mid is None or math.isnan(self.last_mid):
            logger.warning(f"{self.contract.symbol}: Invalid mid-price, cannot calculate quotes.")
            return None, None

        mid_price = self.last_mid
        base_spread = self.settings.base_spread_bps / 10000.0 * mid_price
        min_spread = self.settings.min_spread_bps / 10000.0 * mid_price
        max_spread = self.settings.max_spread_bps / 10000.0 * mid_price

        if self.settings.strategy_type == StrategyType.BASIC_SPREAD:
            bid_price = mid_price - base_spread / 2
            ask_price = mid_price + base_spread / 2

        elif self.settings.strategy_type == StrategyType.INVENTORY_SKEW:
            # Adjust the mid-price based on inventory skew
            position_ratio = self.current_position / self.settings.max_position
            inventory_skew = position_ratio * self.settings.inventory_skew_factor * mid_price
            skewed_mid = mid_price - inventory_skew
            bid_price = skewed_mid - base_spread / 2
            ask_price = skewed_mid + base_spread / 2

        elif self.settings.strategy_type == StrategyType.DYNAMIC_SPREAD:
            # Simple implementation: widen spread based on volatility (mocked here)
            # In a real scenario, you'd fetch market volatility or order book depth
            volatility_factor = 1.5  # Example factor for simplicity
            dynamic_spread = min(max(base_spread * volatility_factor, min_spread), max_spread)
            bid_price = mid_price - dynamic_spread / 2
            ask_price = mid_price + dynamic_spread / 2

        else:
            logger.error(f"{self.contract.symbol}: Unknown strategy type {self.settings.strategy_type}.")
            return None, None

        # Ensure spread adheres to min/max constraints
        actual_spread = ask_price - bid_price
        if actual_spread < min_spread:
            adjustment = (min_spread - actual_spread) / 2
            bid_price -= adjustment
            ask_price += adjustment
        elif actual_spread > max_spread:
            adjustment = (actual_spread - max_spread) / 2
            bid_price += adjustment
            ask_price -= adjustment

        # Round prices to the nearest tick size
        tick = self.settings.tick_size
        bid_price = float(to_decimal_price(round(bid_price / tick) * tick))
        ask_price = float(to_decimal_price(round(ask_price / tick) * tick))

        # NBBO cap: never quote outside the inside market. Without this our
        # quotes sit behind the NBBO when our configured spread is wider than
        # the natural book — and we never get filled.
        if self.last_bid is not None:
            bid_price = max(bid_price, self.last_bid)
        if self.last_ask is not None:
            ask_price = min(ask_price, self.last_ask)

        # Ensure bid < ask by at least tick size. If the NBBO cap collapsed our
        # quote, fall back to joining the inside market on both sides.
        if ask_price - bid_price < tick:
            if (
                self.last_bid is not None
                and self.last_ask is not None
                and self.last_ask - self.last_bid >= tick
            ):
                bid_price = self.last_bid
                ask_price = self.last_ask
            else:
                ask_price = bid_price + tick

        logger.debug(f"{self.contract.symbol}: Calculated bid={bid_price}, ask={ask_price} using strategy {self.settings.strategy_type}.")
        return bid_price, ask_price


    def calculate_quote_sizes(self):
        base_quote_size = self.settings.quote_size * self.quote_size_multiplier
        buy_size = sell_size = base_quote_size

        # Adjust based on current position
        if self.settings.strategy_type == StrategyType.INVENTORY_SKEW:
            position_ratio = self.current_position / self.settings.max_position
            buy_size = max(base_quote_size * (1 - position_ratio), 1)
            sell_size = max(base_quote_size * (1 + position_ratio), 1)

        # Ensure we never exceed max_position limits
        if self.current_position + buy_size > self.settings.max_position:
            buy_size = max(self.settings.max_position - self.current_position, 0)

        if self.current_position - sell_size < -self.settings.max_position:
            sell_size = max(self.current_position + self.settings.max_position, 0)

        # Ensure sizes are integers and at least 1 if possible, else 0
        buy_size = int(max(round(buy_size), 0))
        sell_size = int(max(round(sell_size), 0))

        # Prevent quoting on the side where no shares should be added
        if self.current_position >= self.settings.max_position:
            buy_size = 0
        if self.current_position <= -self.settings.max_position:
            sell_size = 0
        return buy_size, sell_size


class MarketMaker:
    def __init__(self, ib: IB, oms: OrderManagementSystem, runtime_state_store=None):
        self.ib = ib
        self.oms = oms
        self.market_makers: Dict[str, MarketMakerState] = {}
        self.running = False
        # Separate from ``running`` so direct/offline quote tests remain
        # usable while shutdown can establish an immediate no-new-entry gate.
        self._order_entry_enabled = True
        self.check_interval = 0.8  # Adjusted to 1 second
        self.main_thread = None
        # Position synchronization and fill/error callbacks can persist a
        # runtime snapshot while the outer market-maker loop already holds
        # this lock.  Persistence takes the same lock through
        # ``get_runtime_state_snapshot``; a plain Lock therefore deadlocks the
        # first synchronized pass.  RLock preserves mutual exclusion while
        # allowing that intentional same-thread nesting.
        self.lock = threading.RLock()
        self.logger = logger
        self.runtime_state_store = runtime_state_store
        self.startup_reconciliation = {
            "started_at": None,
            "finished_at": None,
            "adopted_order_refs": [],
            "cancelled_order_refs": [],
            "cancellation_reasons": [],
            "adopted_count": 0,
            "cancelled_count": 0,
        }
        self.oms.register_status_callback(self._handle_order_status)
        self.oms.register_fill_callback(self._handle_execution)
        self.oms.register_error_callback(self._handle_order_error)

    def set_runtime_state_store(self, runtime_state_store):
        self.runtime_state_store = runtime_state_store

    def set_startup_reconciliation_summary(self, summary: Dict):
        self.startup_reconciliation = dict(summary or {})

    def _apply_runtime_state(self, state: MarketMakerState, runtime_state: Optional[Dict] = None):
        if not runtime_state:
            return
        if "cooldown_until" in runtime_state:
            state.cooldown_until = runtime_state["cooldown_until"] or 0
        if "last_quoted_mid" in runtime_state:
            state.last_quoted_mid = runtime_state["last_quoted_mid"]
        if "last_quote_time" in runtime_state:
            state.last_quote_time = runtime_state["last_quote_time"] or 0
        if "tracked_bid_order_ref" in runtime_state:
            state.tracked_bid_order_ref = runtime_state["tracked_bid_order_ref"]
        if "tracked_ask_order_ref" in runtime_state:
            state.tracked_ask_order_ref = runtime_state["tracked_ask_order_ref"]
        stored_quote_mode = runtime_state.get("quote_mode")
        if stored_quote_mode == QuoteMode.HALTED.value:
            state.override_quote_mode = QuoteMode.HALTED
            state.override_quote_mode_reason = runtime_state.get("quote_mode_reason") or "persisted_halt"

    def _update_quote_mode(self, state: MarketMakerState):
        previous_mode = state.quote_mode
        previous_reason = state.quote_mode_reason

        if state.current_position == 0:
            state.startup_reduce_only = False
            state.missing_avg_cost = False

        if state.override_quote_mode is not None:
            state.quote_mode = state.override_quote_mode
            state.quote_mode_reason = state.override_quote_mode_reason or "override"
        elif state.current_position == 0:
            state.quote_mode = QuoteMode.NORMAL
            state.quote_mode_reason = "flat"
        elif state.missing_avg_cost:
            state.quote_mode = QuoteMode.REDUCE_ONLY
            state.quote_mode_reason = "missing_avg_cost"
        elif state.startup_reduce_only:
            state.quote_mode = QuoteMode.REDUCE_ONLY
            state.quote_mode_reason = "restart_inventory"
        elif abs(state.current_position) >= (
            state.settings.max_position * state.settings.inventory_halt_threshold_pct
        ):
            state.quote_mode = QuoteMode.REDUCE_ONLY
            state.quote_mode_reason = "inventory_halt_threshold"
        elif abs(state.current_position) >= (
            state.settings.max_position * state.settings.inventory_reduce_threshold_pct
        ):
            state.quote_mode = QuoteMode.REDUCE_ONLY
            state.quote_mode_reason = "inventory_reduce_threshold"
        else:
            state.quote_mode = QuoteMode.NORMAL
            state.quote_mode_reason = "normal"

        if (
            state.quote_mode != previous_mode
            or state.quote_mode_reason != previous_reason
        ):
            self.logger.info(
                "%s: Quote mode -> %s (%s), position=%s avg_cost=%s",
                state.contract.symbol,
                state.quote_mode.value,
                state.quote_mode_reason,
                state.current_position,
                state.position_avg_price,
            )

    def _hydrate_state_from_snapshot(
        self,
        state: MarketMakerState,
        snapshot,
        startup: bool = False,
        runtime_state: Optional[Dict] = None,
    ):
        if snapshot is None:
            self._apply_runtime_state(state, runtime_state)
            self._update_quote_mode(state)
            return

        previously_missing_avg_cost = state.missing_avg_cost
        state.current_position = snapshot.quantity
        state.last_position_sync_time = snapshot.updated_at

        if snapshot.quantity == 0:
            state.position_avg_price = None
            state.missing_avg_cost = False
            state.startup_reduce_only = False
        else:
            if snapshot.avg_cost is not None:
                state.position_avg_price = snapshot.avg_cost
                state.missing_avg_cost = False
            else:
                state.position_avg_price = None
                state.missing_avg_cost = True
                if not previously_missing_avg_cost:
                    self.logger.warning(
                        "%s: Missing average cost from broker, forcing reduce-only quoting",
                        state.contract.symbol,
                    )

            if startup and state.settings.restart_reduce_only:
                state.startup_reduce_only = True

        self._apply_runtime_state(state, runtime_state)
        self._update_quote_mode(state)

    def _sync_position_from_broker(self, state: MarketMakerState, refresh: bool = False):
        broker_state = getattr(self.oms, "broker_state", None)
        if broker_state is None:
            return
        snapshot = broker_state.get_position(state.contract.symbol, refresh=refresh)
        if snapshot is not None:
            self._hydrate_state_from_snapshot(state, snapshot, startup=False)
            self._persist_runtime_state()

    def _quote_role(self, side: str, state: MarketMakerState) -> str:
        if state.quote_mode == QuoteMode.REDUCE_ONLY:
            return (
                "inventory_reduce_only_bid"
                if side == OrderSide.BUY
                else "inventory_reduce_only_ask"
        )
        return "market_maker_bid" if side == OrderSide.BUY else "market_maker_ask"

    def _side_key_for_role(self, role: Optional[str], side: Optional[str] = None):
        if role:
            if role.endswith("_bid"):
                return "bid"
            if role.endswith("_ask"):
                return "ask"
        normalized_side = (side or "").upper()
        if normalized_side == "BUY":
            return "bid"
        if normalized_side == "SELL":
            return "ask"
        return None

    def _set_tracked_order(self, state: MarketMakerState, side_key: Optional[str], order_record):
        order_ref = getattr(order_record, "order_ref", None)
        if side_key == "bid":
            state.bid_order_id = order_record.internal_id
            state.tracked_bid_order_ref = order_ref
        elif side_key == "ask":
            state.ask_order_id = order_record.internal_id
            state.tracked_ask_order_ref = order_ref

    def _clear_tracked_order(self, state: MarketMakerState, side_key: Optional[str]):
        if side_key == "bid":
            state.bid_order_id = None
            state.tracked_bid_order_ref = None
        elif side_key == "ask":
            state.ask_order_id = None
            state.tracked_ask_order_ref = None

    def adopt_open_order_snapshot(self, snapshot):
        symbol = snapshot.symbol
        state = self.market_makers.get(symbol)
        if state is None:
            return None

        order_record = self.oms.find_order_by_order_ref(snapshot.order_ref)
        if order_record is None:
            order_record = self.oms.adopt_open_trade(snapshot.trade, role=snapshot.role)
        if order_record is None:
            return None

        side_key = self._side_key_for_role(snapshot.role, snapshot.side)
        self._set_tracked_order(state, side_key, order_record)
        state.last_quote_time = max(state.last_quote_time, snapshot.updated_at)
        self.logger.info(
            "%s: Adopted startup %s order %s status=%s",
            symbol,
            side_key or "unknown-side",
            order_record.order_ref,
            snapshot.status,
        )
        self._persist_runtime_state()
        return order_record

    def get_runtime_state_snapshot(self):
        with self.lock:
            symbols = {
                symbol: {
                    "cooldown_until": state.cooldown_until,
                    "last_quoted_mid": state.last_quoted_mid,
                    "last_quote_time": state.last_quote_time,
                    "quote_mode": state.quote_mode.value,
                    "quote_mode_reason": state.quote_mode_reason,
                    "tracked_bid_order_ref": state.tracked_bid_order_ref,
                    "tracked_ask_order_ref": state.tracked_ask_order_ref,
                }
                for symbol, state in self.market_makers.items()
            }
        return symbols

    def _persist_runtime_state(self):
        if self.runtime_state_store is None:
            return
        try:
            self.runtime_state_store.save_symbol_states(self.get_runtime_state_snapshot())
        except Exception as exc:
            self.logger.error("Failed to persist runtime state: %s", exc)

    def persist_runtime_state(self):
        self._persist_runtime_state()

    def get_status(self):
        now = time.time()
        with self.lock:
            market_makers = {
                symbol: {
                    "symbol": symbol,
                    "running": self.running,
                    "position": state.current_position,
                    "position_avg_price": state.position_avg_price,
                    "last_bid": state.last_bid,
                    "last_ask": state.last_ask,
                    "last_mid": state.last_mid,
                    "last_quoted_mid": state.last_quoted_mid,
                    "last_quote_time": state.last_quote_time,
                    "cooldown_until": state.cooldown_until,
                    "cooldown_active": now < state.cooldown_until,
                    "quote_mode": state.quote_mode.value,
                    "quote_mode_reason": state.quote_mode_reason,
                    "missing_avg_cost": state.missing_avg_cost,
                    "tracked_bid_order_ref": state.tracked_bid_order_ref,
                    "tracked_ask_order_ref": state.tracked_ask_order_ref,
                    "quote_size_multiplier": state.quote_size_multiplier,
                    "consecutive_data_failures": state.consecutive_data_failures,
                    "settings": state.settings.to_dict(),
                }
                for symbol, state in self.market_makers.items()
            }
        return {
            "running": self.running,
            "check_interval": self.check_interval,
            "startup_reconciliation": dict(self.startup_reconciliation),
            "market_makers": market_makers,
        }

    def apply_portfolio_controls(
        self,
        symbol: str,
        quote_mode: Optional[QuoteMode] = None,
        reason: Optional[str] = None,
        quote_size_multiplier: Optional[float] = None,
    ):
        state = self.market_makers.get(symbol)
        if state is None:
            return False

        changed = False
        if quote_mode != state.override_quote_mode:
            state.override_quote_mode = quote_mode
            state.override_quote_mode_reason = reason
            changed = True
        elif quote_mode is not None and reason != state.override_quote_mode_reason:
            state.override_quote_mode_reason = reason
            changed = True

        if quote_size_multiplier is not None:
            normalized_multiplier = max(float(quote_size_multiplier), 0.1)
            if normalized_multiplier != state.quote_size_multiplier:
                state.quote_size_multiplier = normalized_multiplier
                changed = True

        if changed:
            self._update_quote_mode(state)
            self._persist_runtime_state()
        return changed

    def _handle_order_status(self, order_record: OrderRecord):
        if not order_record.tags.get("market_maker", False):
            return
        symbol = order_record.tags.get("symbol")
        if symbol not in self.market_makers:
            return
        state = self.market_makers[symbol]
        role = order_record.tags.get("role") or order_record.role
        side_key = self._side_key_for_role(role, order_record.order_side)
        if order_record.status in [
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.ERROR,
            OrderStatus.FILLED,
            OrderStatus.EXPIRED,
        ]:
            if side_key == "bid" and state.bid_order_id == order_record.internal_id:
                self._clear_tracked_order(state, "bid")
            if side_key == "ask" and state.ask_order_id == order_record.internal_id:
                self._clear_tracked_order(state, "ask")
            self._persist_runtime_state()

    
    def is_realized_loss(self, fill, state: MarketMakerState):
        """
        Determine if the executed trade results in a realized loss.
        """
        fill_side = fill.execution.side  # 'BOT' or 'SLD'
        fill_price = fill.execution.price

        # Selling a long position at a price lower than entry is a loss
        if fill_side == 'SLD' and state.position_avg_price is not None:
            if fill_price < state.position_avg_price:
                return True

        # Buying back a short position at a higher price than entry is a loss
        elif fill_side == 'BOT' and state.position_avg_price is not None and state.current_position < 0:
            if fill_price > state.position_avg_price:
                return True

        return False



    def _handle_execution(self, order_record: OrderRecord, fill):
        if not order_record.tags.get("market_maker", False):
            return

        symbol = order_record.tags.get("symbol")
        state = self.market_makers.get(symbol)

        if not state:
            return

        fill_qty = fill.execution.shares
        fill_price = fill.execution.price
        fill_side = fill.execution.side  # 'BOT' or 'SLD'

        if fill_side == 'BOT':
            # Update average entry price for buys
            if state.current_position >= 0:
                total_cost = (state.position_avg_price or 0) * state.current_position
                total_cost += fill_price * fill_qty
                state.current_position += fill_qty
                state.position_avg_price = total_cost / state.current_position
            else:
                state.current_position += fill_qty
                if state.current_position == 0:
                    state.position_avg_price = None
        elif fill_side == 'SLD':
            if state.current_position <= 0:
                total_cost = (state.position_avg_price or 0) * abs(state.current_position)
                total_cost += fill_price * fill_qty
                state.current_position -= fill_qty
                state.position_avg_price = total_cost / abs(state.current_position)
            else:
                state.current_position -= fill_qty
                if state.current_position == 0:
                    state.position_avg_price = None

        if self.is_realized_loss(fill, state):
            state.cooldown_until = time.time() + 300  # 5-minute cooldown
            logger.info(f"{symbol}: Realized loss detected. Entering cooldown for 5 minutes.")

        if state.current_position == 0:
            state.startup_reduce_only = False
            state.missing_avg_cost = False
            state.quote_size_multiplier = 1.0
        self._update_quote_mode(state)
        self._persist_runtime_state()

    def _handle_order_error(self, order_record: OrderRecord, error_code: int, error_message: str):
        if not order_record.tags.get("market_maker", False):
            return
        symbol = order_record.tags.get("symbol")
        if symbol not in self.market_makers:
            return
        state = self.market_makers[symbol]
        role = order_record.tags.get("role") or order_record.role
        side_key = self._side_key_for_role(role, order_record.order_side)
        # A cancellation/error for an old order can arrive after its
        # replacement has been tracked. Never let that stale callback clear
        # the replacement and make the next loop submit a duplicate.
        if side_key == "bid" and state.bid_order_id == order_record.internal_id:
            self._clear_tracked_order(state, "bid")
        if side_key == "ask" and state.ask_order_id == order_record.internal_id:
            self._clear_tracked_order(state, "ask")
        self._persist_runtime_state()

    def add_market_maker(self, settings: MarketMakerSettings, runtime_state: Optional[Dict] = None):
        symbol = settings.symbol
        if symbol in self.market_makers:
            self.logger.warning(f"Market maker for {symbol} already exists")
            return False
        contract = create_stock_contract(symbol=symbol, exchange=settings.exchange, currency=settings.currency, primary_exchange=settings.primary_exchange)
        try:
            qualified_contracts = self.ib.qualifyContracts(contract)
            if not qualified_contracts:
                self.logger.error(f"Failed to qualify contract for {symbol}")
                return False
            contract = qualified_contracts[0]
        except Exception as e:
            self.logger.error(f"Error qualifying contract for {symbol}: {e}")
            return False
        state = MarketMakerState(settings, contract)
        try:
            broker_state = getattr(self.oms, "broker_state", None)
            if broker_state is not None:
                snapshot = broker_state.get_position(symbol, refresh=True)
                self._hydrate_state_from_snapshot(
                    state, snapshot, startup=True, runtime_state=runtime_state
                )
                if snapshot is not None:
                    self.logger.info(
                        "%s: Hydrated startup position=%s avg_cost=%s quote_mode=%s",
                        symbol,
                        snapshot.quantity,
                        snapshot.avg_cost,
                        state.quote_mode.value,
                    )
            else:
                self._apply_runtime_state(state, runtime_state)
                self._update_quote_mode(state)
        except Exception as e:
            self.logger.warning(f"Could not get positions for {symbol}: {e}")
        with self.lock:
            self.market_makers[symbol] = state
        self.logger.info(f"Added market maker for {symbol}")
        self._persist_runtime_state()
        return True

    def start(self):
        if self.running or not self.ib.isConnected():
            return False
        self._order_entry_enabled = True
        self.running = True
        self.main_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.main_thread.start()
        self.logger.info("Market maker started")
        return True

    def stop(self, *, cancel_orders: bool = True):
        self._order_entry_enabled = False
        if not self.running:
            return False
        self.running = False
        if self.main_thread:
            self.main_thread.join(timeout=5)
            self.main_thread = None
        if cancel_orders:
            for symbol in list(self.market_makers.keys()):
                self._cancel_all_orders(symbol)
        self._persist_runtime_state()
        self.logger.info("Market maker stopped")
        return True

    def clear_tracked_orders_after_broker_confirmation(self):
        """Clear local order references only after a broker-empty barrier passes."""

        with self.lock:
            for state in self.market_makers.values():
                self._clear_tracked_order(state, "bid")
                self._clear_tracked_order(state, "ask")
        self._persist_runtime_state()

    def _run_loop(self):
        while self.running:
            try:
                with self.lock:
                    for symbol, state in list(self.market_makers.items()):
                        if not self.running:
                            break
                        current_time = time.time()
                        if current_time - state.last_position_sync_time > 250:  # Sync every 5 minutes
                            self._sync_position_from_broker(state, refresh=True)
                        market_data = market_data_store.get_data(symbol)
                        if market_data and state.update_market_data(market_data.get('bid'), market_data.get('ask')):
                            state.consecutive_data_failures = 0
                            if state.should_refresh_quotes():
                                self._refresh_quotes(symbol, state)
                        else:
                            state.consecutive_data_failures += 1
                            if state.consecutive_data_failures > 10:
                                self.logger.warning(f"No valid market data for {symbol} for {state.consecutive_data_failures} iterations")
            except Exception as e:
                self.logger.error(f"Error in market maker loop: {e}")
            time.sleep(self.check_interval)

    def _refresh_quotes(self, symbol: str, state: MarketMakerState):
        if not self._order_entry_enabled:
            return
        self._update_quote_mode(state)
        if state.quote_mode == QuoteMode.HALTED:
            self._cancel_all_orders(symbol)
            logger.info(f"{symbol}: Quoting halted, no orders placed.")
            return

        if state.last_mid is None or math.isnan(state.last_mid) or state.last_mid <= 0:
            logger.warning(f"{symbol}: Invalid mid-price, skipping quotes.")
            return
        
        if time.time() < state.cooldown_until:
            logger.info(f"{symbol}: Currently in cooldown, no quotes placed.")
            return

        self._cancel_all_orders(symbol)
        time.sleep(0.2)
        if not self._order_entry_enabled:
            return

        bid_price, ask_price = state.calculate_quote_prices()

        if bid_price is None or ask_price is None:
            logger.warning(f"{symbol}: Failed to calculate quote prices.")
            return

        bid_size, ask_size = state.calculate_quote_sizes()
        wants_bid, wants_ask = state.desired_quote_sides()
        min_dollar_value = 4000.0

        if bid_size == 0 or bid_size * bid_price < min_dollar_value:
            bid_size = 0

        if ask_size == 0 or ask_size * ask_price < min_dollar_value:
            ask_size = 0

        # NOTE: removed the "avoid small loss" gates here. A market maker MUST
        # be willing to take small losses to clear inventory — refusing to exit
        # in the −0.5% to +0.15% band turned the bot into an accidental
        # directional trader that accumulated inventory in trending markets.
        # Inventory skew + NBBO cap on calculate_quote_prices() are the right
        # mechanisms to incentivize exits, not a hard size-zero gate.

        if not wants_bid:
            bid_size = 0
        if not wants_ask:
            ask_size = 0

        if bid_size > 0:
            bid_role = self._quote_role(OrderSide.BUY, state)
            bid_order = self.oms.create_order(
                contract=state.contract,
                order_side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=bid_size,
                price=bid_price,
                tags={"market_maker": True, "symbol": symbol, "role": bid_role}
            )
            if bid_order and self.oms.submit_order_truly_safe(bid_order):
                self._set_tracked_order(state, "bid", bid_order)
                logger.info(f"{symbol}: Bid order submitted: {bid_size} @ {bid_price}")

        if ask_size > 0:
            ask_role = self._quote_role(OrderSide.SELL, state)
            ask_order = self.oms.create_order(
                contract=state.contract,
                order_side=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                quantity=ask_size,
                price=ask_price,
                tags={"market_maker": True, "symbol": symbol, "role": ask_role}
            )
            if ask_order and self.oms.submit_order_truly_safe(ask_order):
                self._set_tracked_order(state, "ask", ask_order)
                logger.info(f"{symbol}: Ask order submitted: {ask_size} @ {ask_price}")

        state.last_quote_time = time.time()
        state.last_quoted_mid = state.last_mid
        self._persist_runtime_state()

    def _cancel_all_orders(
        self,
        symbol: str,
        *,
        persist: bool = True,
        clear_tracked: bool = True,
    ):
        state = self.market_makers.get(symbol)
        if not state:
            return
        if state.bid_order_id:
            self.oms.cancel_order_truly_safe(state.bid_order_id)
            if clear_tracked:
                self._clear_tracked_order(state, "bid")
        if state.ask_order_id:
            self.oms.cancel_order_truly_safe(state.ask_order_id)
            if clear_tracked:
                self._clear_tracked_order(state, "ask")
        if persist:
            self._persist_runtime_state()
