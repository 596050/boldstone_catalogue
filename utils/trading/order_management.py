# order_management.py - Order Management System for Interactive Brokers
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from ib_insync import IB, Order, Contract, Trade
from decimal import Decimal
import queue
import time
import uuid
import logging
from utils.trading.broker_state import BrokerStateCache
from utils.trading.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

def to_decimal_price(price, places=2):
    return Decimal(str(price)).quantize(Decimal('0.01'))

class OrderSide:
    BUY = "BUY"
    SELL = "SELL"

class OrderType:
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP LMT"

class OrderStatus:
    PENDING_NEW = "PENDING_NEW"
    NEW = "NEW"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    INACTIVE = "INACTIVE"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    ERROR = "ERROR"


class OrderCancellationConfirmationError(RuntimeError):
    """Raised when broker-side working-order cancellation is not confirmed."""

    def __init__(self, message: str, summary: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.summary = dict(summary or {})

class OrderRecord:
    def __init__(
        self,
        contract: Contract,
        order_side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "DAY",
        ib_order_id: Optional[int] = None,
        perm_id: Optional[int] = None,
        order_ref: Optional[str] = None,
        internal_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        role: Optional[str] = None,
        tags: Optional[Dict] = None
    ):
        self.internal_id = internal_id or str(uuid.uuid4())
        self.contract = contract
        self.order_side = order_side
        self.order_type = order_type
        self.quantity = quantity
        self.price = price
        self.stop_price = stop_price
        self.time_in_force = time_in_force
        self.ib_order_id = ib_order_id
        self.perm_id = perm_id
        self.order_ref = order_ref
        self.role = role or "manual"
        self.ib_order = None
        self.ib_trade = None
        self.status = OrderStatus.PENDING_NEW
        self.filled_quantity = 0
        self.average_fill_price = 0
        self.error_message = None
        self.created_at = datetime.now()
        self.submitted_at = None
        self.last_updated_at = self.created_at
        self.parent_id = parent_id
        self.tags = dict(tags or {})

    def update_from_ib_order_status(self, status: str, filled: float, avg_fill_price: float, whyHeld: str = None):
        if status in ["ApiPending", "PendingSubmit"]:
            self.status = OrderStatus.PENDING_NEW
            if self.submitted_at is None:
                self.submitted_at = datetime.now()
        elif status in ["Submitted", "PreSubmitted", "PendingCancel"]:
            self.status = OrderStatus.NEW
            if self.submitted_at is None:
                self.submitted_at = datetime.now()
        elif status == "Filled" and filled >= self.quantity:
            self.status = OrderStatus.FILLED
        elif status == "Filled" and filled < self.quantity:
            self.status = OrderStatus.PARTIALLY_FILLED
        elif status in ["Cancelled", "ApiCancelled"]:
            self.status = OrderStatus.CANCELLED
        elif status == "Inactive":
            self.status = OrderStatus.INACTIVE
            self.error_message = whyHeld
        self.filled_quantity = filled
        if avg_fill_price != 0:
            self.average_fill_price = avg_fill_price
        self.last_updated_at = datetime.now()

    def to_dict(self):
        return {
            "internal_id": self.internal_id,
            "ib_order_id": self.ib_order_id,
            "perm_id": self.perm_id,
            "order_ref": self.order_ref,
            "role": self.role,
            "symbol": self.contract.symbol if self.contract else None,
            "side": self.order_side,
            "type": self.order_type,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "time_in_force": self.time_in_force,
            "status": self.status,
            "filled_quantity": self.filled_quantity,
            "average_fill_price": self.average_fill_price,
            "created_at": self.created_at.isoformat(),
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "last_updated_at": self.last_updated_at.isoformat(),
            "parent_id": self.parent_id,
            "tags": self.tags,
            "error_message": self.error_message
        }

    def __str__(self):
        return f"Order({self.internal_id[:8]}, {self.contract.symbol}, {self.order_side}, {self.quantity} @ {self.price}, Status: {self.status})"

class MainThreadOrderQueue:
    def __init__(self, ib):
        self.ib = ib
        self.queue = queue.Queue()
        self.is_running = True
        self._state_lock = threading.Lock()
        self._schedule_next()

    def add_task(self, task_callable):
        with self._state_lock:
            if not self.is_running:
                return False
            self.queue.put(task_callable)
        #logger.info(f"Task added to queue. Current size: {self.queue.qsize()}")
        return True

    def _process_queue(self):
        #logger.debug(f"Processing order queue, size: {self.queue.qsize()}")
        tasks_processed = 0
        while tasks_processed < 10:
            try:
                task_callable = self.queue.get_nowait()
            except queue.Empty:
                break
            try:
                result = task_callable()
                #logger.info(f"Task executed successfully: {result}")
            except Exception as e:
                logger.error(f"Error executing task from queue: {e}")
            tasks_processed += 1
            self.queue.task_done()
        self._schedule_next()

    def _schedule_next(self):
        with self._state_lock:
            is_running = self.is_running
        if is_running:
            next_run = datetime.now() + timedelta(seconds=0.1)
            self.ib.schedule(next_run, self._process_queue)

    def shutdown(self, *, discard_pending: bool = True):
        with self._state_lock:
            self.is_running = False
        discarded = 0
        if discard_pending:
            while True:
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    break
                else:
                    discarded += 1
                    self.queue.task_done()
        return discarded

class OrderManagementSystem:
    def __init__(
        self,
        ib: IB,
        max_order_size: Dict[str, float] = None,
        broker_state: Optional[BrokerStateCache] = None,
        account: Optional[str] = None,
        position_security_type: Optional[str] = None,
        position_currency: Optional[str] = None,
        reject_unsupported_contracts: bool = False,
    ):
        self.ib = ib
        self.account = account
        self.orders: Dict[str, OrderRecord] = {}
        self.ib_order_map: Dict[int, str] = {}
        self.ib_perm_id_map: Dict[int, str] = {}
        self.order_ref_map: Dict[str, str] = {}
        self.max_order_size = max_order_size or {}
        self.default_max_order_size = 500
        self.broker_state = broker_state or BrokerStateCache(
            ib,
            account=account,
            security_type=position_security_type,
            currency=position_currency,
            reject_unsupported_contracts=reject_unsupported_contracts,
        )
        self.status_callbacks = []
        self.fill_callbacks = []
        self.error_callbacks = []
        self.order_lock = threading.Lock()
        self._register_ib_callbacks()
        self.initialize_main_thread_queue()

    def _register_ib_callbacks(self):
        self.ib.orderStatusEvent += self._handle_order_status
        self.ib.execDetailsEvent += self._handle_execution
        self.ib.errorEvent += self._handle_error

    def _handle_order_status(self, trade: Trade):
        self.broker_state.remember_trade(trade)
        order_record = None
        callbacks = ()
        with self.order_lock:
            order_record = self._get_order_record_for_trade_locked(trade)
            if order_record:
                self._capture_broker_identity_locked(order_record, trade)
                order_record.update_from_ib_order_status(
                    trade.orderStatus.status,
                    trade.orderStatus.filled,
                    trade.orderStatus.avgFillPrice,
                    trade.orderStatus.whyHeld
                )
                callbacks = tuple(self.status_callbacks)
        # Callbacks may persist market-maker state and therefore acquire the
        # market-maker lock.  Never invoke them while holding ``order_lock``:
        # the producer takes those locks in the opposite order while routing.
        for callback in callbacks:
            try:
                callback(order_record)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    def _handle_execution(self, trade: Trade, fill):
        self.broker_state.remember_trade(trade)
        order_record = None
        callbacks = ()
        with self.order_lock:
            order_record = self._get_order_record_for_trade_locked(trade)
            if order_record:
                self._capture_broker_identity_locked(order_record, trade)
                order_record.filled_quantity = trade.orderStatus.filled
                order_record.average_fill_price = trade.orderStatus.avgFillPrice
                order_record.last_updated_at = datetime.now()
                order_record.status = OrderStatus.FILLED if trade.orderStatus.filled >= order_record.quantity else OrderStatus.PARTIALLY_FILLED
                callbacks = tuple(self.fill_callbacks)
        for callback in callbacks:
            try:
                callback(order_record, fill)
            except Exception as e:
                logger.error(f"Error in fill callback: {e}")

    def _handle_error(self, reqId, errorCode, errorString, contract):
        order_record = None
        callbacks = ()
        with self.order_lock:
            if reqId > 0 and reqId in self.ib_order_map:
                order_record = self.orders.get(self.ib_order_map[reqId])
                if order_record:
                    order_record.error_message = f"{errorCode}: {errorString}"
                    if errorCode in [104, 105, 106, 107, 109, 110, 111, 113, 114, 115, 116, 117, 118, 119, 120]:
                        order_record.status = OrderStatus.REJECTED
                    callbacks = tuple(self.error_callbacks)
        for callback in callbacks:
            try:
                callback(order_record, errorCode, errorString)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")

    def _check_risk_limits(self, contract: Contract, quantity: float, price: Optional[float] = None):
        symbol = contract.symbol
        max_size = self.max_order_size.get(symbol, self.default_max_order_size)
        if quantity > max_size:
            return False, f"Order size ({quantity}) exceeds maximum ({max_size}) for {symbol}"
        return True, ""

    def create_order(self, contract: Contract, order_side: str, order_type: str, quantity: float, price: Optional[float] = None, stop_price: Optional[float] = None, time_in_force: str = "DAY", tags: Optional[Dict] = None):
        symbol = contract.symbol

        pos_qty = self.broker_state.get_position_quantity(symbol, refresh=True)

        proposed_position = pos_qty + quantity if order_side == OrderSide.BUY else pos_qty - quantity
        
        max_position = self.max_order_size.get(symbol, self.default_max_order_size)
        if abs(proposed_position) > max_position:
            #logger.error(f"Position limit exceeded for {symbol}. Current: {pos_qty}, Proposed: {proposed_position}, Max Allowed: {max_position}")
            return None

        is_valid, reason = self._check_risk_limits(contract, quantity, price)
        if not is_valid:
            logger.error(f"Order failed risk check: {reason}")
            return None

        normalized_tags = dict(tags or {})
        role = self._normalize_role(order_side, normalized_tags)
        order_record = OrderRecord(
            contract,
            order_side,
            order_type,
            quantity,
            price,
            stop_price,
            time_in_force,
            order_ref=None,
            role=role,
            tags=normalized_tags,
        )
        order_record.order_ref = self._build_order_ref(order_record)

        with self.order_lock:
            self._index_order_record_locked(order_record)

        return order_record


    def submit_order(self, order_record: OrderRecord):
        if not self.ib.isConnected():
            logger.error("Cannot submit order: IB not connected")
            order_record.status = OrderStatus.ERROR
            order_record.error_message = "IB not connected"
            return False
        ib_order = self._build_ib_order(order_record)
        try:
            trade = self.ib.placeOrder(order_record.contract, ib_order)
            order_record.ib_order = ib_order
            order_record.ib_trade = trade
            order_record.status = OrderStatus.NEW
            order_record.submitted_at = datetime.now()
            order_record.last_updated_at = datetime.now()
            with self.order_lock:
                self._capture_broker_identity_locked(order_record, trade)
            self.broker_state.remember_trade(trade)
            return True
        except Exception as e:
            logger.error(f"Error submitting order: {e}")
            order_record.status = OrderStatus.ERROR
            order_record.error_message = str(e)
            return False

    def cancel_order(self, order_id: str):
        with self.order_lock:
            order_record = self.orders.get(order_id)
            if not order_record:
                logger.error(f"Order {order_id} not found")
                return False
            if order_record.status not in [OrderStatus.PENDING_NEW, OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]:
                logger.error(f"Cannot cancel order in {order_record.status} status")
                return False
            if not order_record.ib_trade:
                logger.error(f"Order {order_id} has no IB trade object")
                return False
        try:
            self.ib.cancelOrder(order_record.ib_order)
            return True
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    def initialize_main_thread_queue(self):
        self.main_thread_queue = MainThreadOrderQueue(self.ib)
        logger.info("Main thread order queue initialized")

    def submit_order_truly_safe(self, order_record: OrderRecord) -> bool:
        if not hasattr(self, 'main_thread_queue'):
            self.initialize_main_thread_queue()
        if not self.ib.isConnected():
            order_record.status = OrderStatus.ERROR
            order_record.error_message = "IB not connected"
            return False
        ib_order = self._build_ib_order(order_record)

        def submit_task():
            try:
                trade = self.ib.placeOrder(order_record.contract, ib_order)
                order_record.ib_order = ib_order
                order_record.ib_trade = trade
                order_record.status = OrderStatus.NEW
                order_record.submitted_at = datetime.now()
                order_record.last_updated_at = datetime.now()
                with self.order_lock:
                    self._capture_broker_identity_locked(order_record, trade)
                self.broker_state.remember_trade(trade)
                logger.info(f"Order submitted: {order_record.order_side} {order_record.quantity} {order_record.contract.symbol}@{order_record.price} {order_record.price * order_record.quantity}")
            except Exception as e:
                order_record.status = OrderStatus.ERROR
                order_record.error_message = str(e)
                logger.error(f"Order submission error: {e}")

        if not self.main_thread_queue.add_task(submit_task):
            order_record.status = OrderStatus.ERROR
            order_record.error_message = "order queue is shutting down"
            logger.error("Cannot queue order submission: OMS is shutting down")
            return False
        order_record.status = OrderStatus.PENDING_NEW
        return True

    def cancel_order_truly_safe(self, order_id):
        if not hasattr(self, 'main_thread_queue'):
            self.initialize_main_thread_queue()
        with self.order_lock:
            order_record = self.orders.get(order_id)
            if not order_record:
                logger.error(f"Order {order_id} not found")
                return False
            if order_record.status not in [OrderStatus.PENDING_NEW, OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]:
                logger.error(f"Cannot cancel order in {order_record.status} status")
                return False
            if not order_record.ib_order_id:
                logger.error(f"Order {order_id} has no IB order ID")
                return False
        try:
            def execute_cancel():
                try:
                    self.ib.client.cancelOrder(order_record.ib_order_id)
                    logger.info(f"Order {order_id} cancelled")
                    return True
                except Exception as e:
                    logger.error(f"Error cancelling order in main thread: {e}")
                    return False
            if not self.main_thread_queue.add_task(execute_cancel):
                logger.error("Cannot queue order cancellation: OMS is shutting down")
                return False
            return True
        except Exception as e:
            logger.error(f"Error queuing cancel: {e}")
            return False

    def shutdown(self, *, discard_pending: bool = True):
        if hasattr(self, 'main_thread_queue'):
            return self.main_thread_queue.shutdown(discard_pending=discard_pending)
        return 0

    def cancel_market_maker_orders_and_confirm(
        self,
        *,
        timeout_seconds: float = 10.0,
        poll_interval: float = 0.1,
        pre_discarded_queued_tasks: int = 0,
    ) -> Dict[str, Any]:
        """Synchronously cancel every broker-visible MM order and prove none remain.

        Pending local queue tasks are discarded before the broker snapshot, so a
        delayed submission cannot race behind the shutdown cancellation barrier.
        Manual/non-market-maker orders are deliberately outside this scope.
        """

        started_at = time.time()
        discarded_tasks = int(pre_discarded_queued_tasks) + self.shutdown(
            discard_pending=True
        )
        summary: Dict[str, Any] = {
            "started_at": started_at,
            "finished_at": None,
            "discarded_queued_tasks": discarded_tasks,
            "cancel_requested_order_refs": [],
            "cancel_failed_order_refs": [],
            "remaining_order_refs": [],
            "confirmed": False,
        }
        if not self.ib.isConnected():
            raise OrderCancellationConfirmationError(
                "Cannot confirm market-maker order cancellation: IBKR is disconnected",
                summary,
            )

        def broker_market_maker_orders():
            request_open_orders = getattr(self.ib, "reqOpenOrders", None)
            if callable(request_open_orders):
                try:
                    request_open_orders()
                except Exception as exc:
                    raise OrderCancellationConfirmationError(
                        f"IBKR open-order refresh failed during shutdown: {exc}",
                        summary,
                    ) from exc
            snapshots = self.list_open_market_maker_orders(refresh=True)
            refresh_error = getattr(self.broker_state, "last_open_orders_error", None)
            if refresh_error:
                raise OrderCancellationConfirmationError(
                    "Broker open-order snapshot failed during shutdown: "
                    + str(refresh_error),
                    summary,
                )
            return snapshots

        snapshots = broker_market_maker_orders()
        for snapshot in snapshots:
            success, message = self.cancel_open_order_snapshot(snapshot)
            if success:
                summary["cancel_requested_order_refs"].append(message)
                logger.info("Shutdown cancellation requested for %s", message)
            else:
                summary["cancel_failed_order_refs"].append(message)

        if summary["cancel_failed_order_refs"]:
            summary["finished_at"] = time.time()
            raise OrderCancellationConfirmationError(
                "Failed to request shutdown cancellation for: "
                + "; ".join(summary["cancel_failed_order_refs"]),
                summary,
            )

        deadline = time.monotonic() + max(float(timeout_seconds), 0.0)
        poll = max(float(poll_interval), 0.0)
        while True:
            remaining = broker_market_maker_orders()
            remaining_refs = [
                snapshot.order_ref or f"order_id={snapshot.order_id}"
                for snapshot in remaining
            ]
            summary["remaining_order_refs"] = remaining_refs
            if not remaining_refs:
                summary["confirmed"] = True
                summary["finished_at"] = time.time()
                logger.info(
                    "Shutdown order barrier confirmed: cancelled=%d discarded_queue_tasks=%d",
                    len(summary["cancel_requested_order_refs"]),
                    discarded_tasks,
                )
                return summary
            if time.monotonic() >= deadline:
                summary["finished_at"] = time.time()
                raise OrderCancellationConfirmationError(
                    "Timed out waiting for broker cancellation confirmation: "
                    + ", ".join(remaining_refs),
                    summary,
                )
            wait_seconds = min(poll, max(0.0, deadline - time.monotonic()))
            broker_sleep = getattr(self.ib, "sleep", None)
            if callable(broker_sleep):
                broker_sleep(wait_seconds)
            else:
                time.sleep(wait_seconds)

    def register_status_callback(self, callback: Callable[[OrderRecord], None]):
        self.status_callbacks.append(callback)

    def register_fill_callback(self, callback: Callable[[OrderRecord, Any], None]):
        self.fill_callbacks.append(callback)

    def register_error_callback(self, callback: Callable[[OrderRecord, int, str], None]):
        self.error_callbacks.append(callback)

    def set_max_order_size(self, symbol: str, max_size: float):
        self.max_order_size[symbol] = max_size

    def find_order_by_order_ref(self, order_ref: str) -> Optional[OrderRecord]:
        with self.order_lock:
            internal_id = self.order_ref_map.get(order_ref)
            return self.orders.get(internal_id) if internal_id else None

    def list_open_market_maker_orders(self, refresh: bool = True):
        snapshots = self.broker_state.get_open_orders(refresh=refresh)
        return [
            snapshot
            for snapshot in snapshots
            if self._is_quote_role(snapshot.role)
        ]

    def cancel_open_market_maker_orders(
        self, symbol: Optional[str] = None, refresh: bool = True
    ) -> Dict[str, List[str]]:
        snapshots = self.list_open_market_maker_orders(refresh=refresh)
        if symbol is not None:
            snapshots = [snapshot for snapshot in snapshots if snapshot.symbol == symbol]

        cancelled = []
        failed = []
        for snapshot in snapshots:
            success, message = self.cancel_open_order_snapshot(snapshot)
            if success:
                cancelled.append(message)
            else:
                failed.append(message)
        return {"cancelled": cancelled, "failed": failed}

    def cancel_open_order_snapshot(self, snapshot):
        order = getattr(snapshot.trade, "order", None)
        order_ref = snapshot.order_ref or f"order_id={snapshot.order_id}"
        try:
            if order is not None and hasattr(self.ib, "cancelOrder"):
                self.ib.cancelOrder(order)
            elif snapshot.order_id is not None and hasattr(self.ib, "client"):
                self.ib.client.cancelOrder(snapshot.order_id)
            else:
                raise RuntimeError("No cancel path available for broker order")
            return True, order_ref
        except Exception as exc:
            return False, f"{order_ref}: {exc}"

    def adopt_open_trade(self, trade: Trade, role: Optional[str] = None) -> Optional[OrderRecord]:
        contract = getattr(trade, "contract", None)
        order = getattr(trade, "order", None)
        if contract is None or order is None:
            return None

        order_ref = getattr(order, "orderRef", None)
        tags = {
            "symbol": getattr(contract, "symbol", None),
            "role": role or self._role_from_order_ref(order_ref),
            "market_maker": self._is_quote_role(
                role or self._role_from_order_ref(order_ref)
            ),
        }
        order_record = OrderRecord(
            contract=contract,
            order_side=getattr(order, "action", None),
            order_type=getattr(order, "orderType", None),
            quantity=getattr(order, "totalQuantity", 0),
            price=getattr(order, "lmtPrice", None),
            stop_price=getattr(order, "auxPrice", None),
            time_in_force=getattr(order, "tif", "DAY"),
            ib_order_id=getattr(order, "orderId", None),
            perm_id=getattr(order, "permId", None),
            order_ref=order_ref,
            role=tags["role"],
            tags=tags,
        )
        order_record.ib_order = order
        order_record.ib_trade = trade
        order_status = getattr(trade, "orderStatus", None)
        if order_status is not None:
            order_record.update_from_ib_order_status(
                getattr(order_status, "status", "Submitted"),
                getattr(order_status, "filled", 0),
                getattr(order_status, "avgFillPrice", 0),
                getattr(order_status, "whyHeld", None),
            )

        with self.order_lock:
            self._index_order_record_locked(order_record)
        self.broker_state.remember_trade(trade)
        return order_record

    def _normalize_role(self, order_side: str, tags: Dict[str, Any]) -> str:
        explicit_role = tags.get("role")
        if explicit_role:
            return explicit_role
        if tags.get("market_maker"):
            return "market_maker_bid" if order_side == OrderSide.BUY else "market_maker_ask"
        return "manual"

    def _role_from_order_ref(self, order_ref: Optional[str]) -> Optional[str]:
        if not order_ref:
            return None
        for token in order_ref.split("|"):
            if token.startswith("role="):
                return token.split("=", 1)[1]
        return None

    def _build_order_ref(self, order_record: OrderRecord) -> str:
        prefix = "mm" if self._is_quote_role(order_record.role) else "oms"
        symbol = order_record.contract.symbol if order_record.contract else "UNKNOWN"
        return (
            f"{prefix}|symbol={symbol}|role={order_record.role}|internal_id={order_record.internal_id}"
        )

    def _is_quote_role(self, role: Optional[str]) -> bool:
        if not role:
            return False
        return role.startswith("market_maker") or role.startswith(
            "inventory_reduce_only"
        )

    def _build_ib_order(self, order_record: OrderRecord):
        ib_order = Order()
        ib_order.action = order_record.order_side
        ib_order.orderType = order_record.order_type
        ib_order.totalQuantity = order_record.quantity
        ib_order.tif = order_record.time_in_force
        if hasattr(ib_order, "orderRef"):
            ib_order.orderRef = order_record.order_ref
        if self.account:
            ib_order.account = self.account
        if order_record.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
            ib_order.lmtPrice = float(to_decimal_price(order_record.price))
        if order_record.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
            ib_order.auxPrice = float(to_decimal_price(order_record.stop_price))
        return ib_order

    def _index_order_record_locked(self, order_record: OrderRecord):
        self.orders[order_record.internal_id] = order_record
        if order_record.ib_order_id is not None:
            self.ib_order_map[order_record.ib_order_id] = order_record.internal_id
        if order_record.perm_id is not None:
            self.ib_perm_id_map[order_record.perm_id] = order_record.internal_id
        if order_record.order_ref:
            self.order_ref_map[order_record.order_ref] = order_record.internal_id

    def _capture_broker_identity_locked(self, order_record: OrderRecord, trade: Trade):
        order = getattr(trade, "order", None)
        if order is None:
            return
        order_record.ib_order_id = getattr(order, "orderId", order_record.ib_order_id)
        order_record.perm_id = getattr(order, "permId", order_record.perm_id)
        order_record.order_ref = getattr(order, "orderRef", order_record.order_ref)
        self._index_order_record_locked(order_record)

    def _get_order_record_for_trade_locked(self, trade: Trade) -> Optional[OrderRecord]:
        order = getattr(trade, "order", None)
        if order is None:
            return None

        order_id = getattr(order, "orderId", None)
        if order_id in self.ib_order_map:
            return self.orders.get(self.ib_order_map[order_id])

        perm_id = getattr(order, "permId", None)
        if perm_id in self.ib_perm_id_map:
            return self.orders.get(self.ib_perm_id_map[perm_id])

        order_ref = getattr(order, "orderRef", None)
        if order_ref in self.order_ref_map:
            return self.orders.get(self.order_ref_map[order_ref])

        return None

def create_stock_contract(symbol, exchange='SMART', currency='USD', primary_exchange=None):
    from ib_insync import Stock
    contract = Stock(symbol, exchange, currency)
    if primary_exchange:
        contract.primaryExchange = primary_exchange
    return contract
