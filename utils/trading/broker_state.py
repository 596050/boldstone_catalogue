import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PositionSnapshot:
    symbol: str
    quantity: float
    avg_cost: Optional[float]
    contract: object
    updated_at: float


@dataclass
class OpenOrderSnapshot:
    order_id: Optional[int]
    perm_id: Optional[int]
    order_ref: Optional[str]
    symbol: str
    side: Optional[str]
    quantity: float
    limit_price: Optional[float]
    status: Optional[str]
    role: Optional[str]
    contract: object
    trade: object
    updated_at: float = field(default_factory=time.time)


def parse_order_ref(order_ref: Optional[str]) -> Dict[str, str]:
    if not order_ref:
        return {}

    parsed = {}
    for token in order_ref.split("|"):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        parsed[key] = value
    return parsed


class BrokerStateCache:
    def __init__(
        self,
        ib,
        *,
        account: Optional[str] = None,
        security_type: Optional[str] = None,
        currency: Optional[str] = None,
        reject_unsupported_contracts: bool = False,
    ):
        self.ib = ib
        self.account = account
        self.security_type = security_type.upper() if security_type else None
        self.currency = currency.upper() if currency else None
        self.reject_unsupported_contracts = reject_unsupported_contracts
        self.lock = threading.Lock()
        self.positions: Dict[str, PositionSnapshot] = {}
        self.open_orders_by_key: Dict[str, OpenOrderSnapshot] = {}
        self.open_orders_by_id: Dict[int, OpenOrderSnapshot] = {}
        self.open_orders_by_perm_id: Dict[int, OpenOrderSnapshot] = {}
        self.open_orders_by_ref: Dict[str, OpenOrderSnapshot] = {}
        self.last_positions_refresh = 0.0
        self.last_open_orders_refresh = 0.0
        self.ready = False
        self.last_ready_at = 0.0
        self.last_positions_error: Optional[str] = None
        self.last_open_orders_error: Optional[str] = None

    def _account_matches(self, value: object) -> bool:
        if not self.account:
            return True
        candidate = str(value or "")
        # IB may leave account blank on an order when the connection manages
        # exactly one account. Positions are already requested with the exact
        # account filter when configured.
        return candidate in {"", self.account}

    def _contract_matches(self, contract: object) -> bool:
        if self.security_type:
            actual = str(getattr(contract, "secType", "") or "").upper()
            if actual != self.security_type:
                return False
        if self.currency:
            actual = str(getattr(contract, "currency", "") or "").upper()
            if actual != self.currency:
                return False
        return True

    @staticmethod
    def _contract_identity(contract: object) -> tuple:
        con_id = getattr(contract, "conId", None)
        if con_id not in (None, 0):
            return ("conId", int(con_id))
        return (
            str(getattr(contract, "symbol", "") or "").upper(),
            str(getattr(contract, "secType", "") or "").upper(),
            str(getattr(contract, "currency", "") or "").upper(),
            str(getattr(contract, "exchange", "") or "").upper(),
        )

    def refresh_positions(self) -> Dict[str, PositionSnapshot]:
        try:
            raw_positions = (
                self.ib.positions(account=self.account)
                if self.account
                else self.ib.positions()
            )
        except Exception as exc:
            with self.lock:
                self.last_positions_error = str(exc)
                self.ready = False
            return self.snapshot_positions()

        refreshed: Dict[str, PositionSnapshot] = {}
        identities: Dict[str, tuple] = {}
        now = time.time()
        for position in raw_positions:
            contract = getattr(position, "contract", None)
            if not self._account_matches(getattr(position, "account", None)):
                continue
            if not self._contract_matches(contract):
                if (
                    self.reject_unsupported_contracts
                    and abs(float(getattr(position, "position", 0.0))) > 1e-12
                ):
                    with self.lock:
                        self.last_positions_error = (
                            "unsupported position contract in configured account: "
                            f"{contract!r}"
                        )
                        self.ready = False
                        return dict(self.positions)
                continue
            symbol = getattr(contract, "symbol", None)
            if not symbol:
                continue
            symbol = str(symbol).upper()
            identity = self._contract_identity(contract)
            if symbol in identities and identities[symbol] != identity:
                with self.lock:
                    self.last_positions_error = (
                        f"multiple position contracts share symbol {symbol}: "
                        f"{identities[symbol]!r} vs {identity!r}"
                    )
                    self.ready = False
                    return dict(self.positions)
            identities[symbol] = identity
            refreshed[symbol] = PositionSnapshot(
                symbol=symbol,
                quantity=getattr(position, "position", 0.0),
                avg_cost=getattr(position, "avgCost", None),
                contract=contract,
                updated_at=now,
            )

        with self.lock:
            self.positions = refreshed
            self.last_positions_refresh = now
            self.last_positions_error = None
        return self.snapshot_positions()

    def snapshot_positions(self) -> Dict[str, PositionSnapshot]:
        with self.lock:
            return dict(self.positions)

    def get_position(self, symbol: str, refresh: bool = False) -> Optional[PositionSnapshot]:
        if refresh:
            self.refresh_positions()
        with self.lock:
            return self.positions.get(symbol)

    def get_position_quantity(self, symbol: str, refresh: bool = False) -> float:
        snapshot = self.get_position(symbol, refresh=refresh)
        return snapshot.quantity if snapshot else 0.0

    def get_position_avg_cost(self, symbol: str, refresh: bool = False) -> Optional[float]:
        snapshot = self.get_position(symbol, refresh=refresh)
        return snapshot.avg_cost if snapshot else None

    def refresh_open_orders(self) -> List[OpenOrderSnapshot]:
        if not hasattr(self.ib, "openTrades"):
            with self.lock:
                self.last_open_orders_error = None
            return self.get_open_orders()

        try:
            raw_trades = self.ib.openTrades()
        except Exception as exc:
            with self.lock:
                self.last_open_orders_error = str(exc)
                self.ready = False
            return self.get_open_orders()

        snapshots = {}
        order_id_index = {}
        perm_id_index = {}
        ref_index = {}
        now = time.time()

        for trade in raw_trades:
            order = getattr(trade, "order", None)
            contract = getattr(trade, "contract", None)
            if not self._account_matches(getattr(order, "account", None)):
                continue
            if not self._contract_matches(contract):
                if self.reject_unsupported_contracts:
                    with self.lock:
                        self.last_open_orders_error = (
                            "unsupported working-order contract in configured account: "
                            f"{contract!r}"
                        )
                        self.ready = False
                        return list(self.open_orders_by_key.values())
                continue
            snapshot = self._snapshot_from_trade(trade, now=now)
            if not snapshot:
                continue
            snapshots[self._snapshot_key(snapshot)] = snapshot
            if snapshot.order_id is not None:
                order_id_index[snapshot.order_id] = snapshot
            if snapshot.perm_id is not None:
                perm_id_index[snapshot.perm_id] = snapshot
            if snapshot.order_ref:
                ref_index[snapshot.order_ref] = snapshot

        with self.lock:
            self.open_orders_by_key = snapshots
            self.open_orders_by_id = order_id_index
            self.open_orders_by_perm_id = perm_id_index
            self.open_orders_by_ref = ref_index
            self.last_open_orders_refresh = now
            self.last_open_orders_error = None
        return self.get_open_orders()

    def warmup(self) -> bool:
        self.refresh_positions()
        self.refresh_open_orders()
        now = time.time()
        with self.lock:
            success = self.last_positions_error is None and self.last_open_orders_error is None
            self.ready = success
            if success:
                self.last_ready_at = now
            return success

    def remember_trade(self, trade):
        snapshot = self._snapshot_from_trade(trade)
        if not snapshot:
            return None

        final_statuses = {"Cancelled", "Filled", "ApiCancelled"}
        if snapshot.status in final_statuses:
            self.remove_open_order(
                order_id=snapshot.order_id,
                perm_id=snapshot.perm_id,
                order_ref=snapshot.order_ref,
            )
            return snapshot

        with self.lock:
            self.open_orders_by_key[self._snapshot_key(snapshot)] = snapshot
            if snapshot.order_id is not None:
                self.open_orders_by_id[snapshot.order_id] = snapshot
            if snapshot.perm_id is not None:
                self.open_orders_by_perm_id[snapshot.perm_id] = snapshot
            if snapshot.order_ref:
                self.open_orders_by_ref[snapshot.order_ref] = snapshot
            self.last_open_orders_refresh = snapshot.updated_at
        return snapshot

    def remove_open_order(
        self,
        order_id: Optional[int] = None,
        perm_id: Optional[int] = None,
        order_ref: Optional[str] = None,
    ):
        with self.lock:
            snapshot = None
            if order_id is not None:
                snapshot = self.open_orders_by_id.pop(order_id, None)
            if snapshot is None and perm_id is not None:
                snapshot = self.open_orders_by_perm_id.pop(perm_id, None)
            if snapshot is None and order_ref:
                snapshot = self.open_orders_by_ref.pop(order_ref, None)
            if snapshot is None:
                return
            self.open_orders_by_key.pop(self._snapshot_key(snapshot), None)
            if snapshot.order_id is not None:
                self.open_orders_by_id.pop(snapshot.order_id, None)
            if snapshot.perm_id is not None:
                self.open_orders_by_perm_id.pop(snapshot.perm_id, None)
            if snapshot.order_ref:
                self.open_orders_by_ref.pop(snapshot.order_ref, None)

    def get_open_orders(
        self, symbol: Optional[str] = None, refresh: bool = False
    ) -> List[OpenOrderSnapshot]:
        if refresh:
            self.refresh_open_orders()
        with self.lock:
            orders = list(self.open_orders_by_key.values())
        if symbol is None:
            return orders
        return [snapshot for snapshot in orders if snapshot.symbol == symbol]

    def get_open_order_by_ref(
        self, order_ref: str, refresh: bool = False
    ) -> Optional[OpenOrderSnapshot]:
        if refresh:
            self.refresh_open_orders()
        with self.lock:
            return self.open_orders_by_ref.get(order_ref)

    def _snapshot_from_trade(self, trade, now: Optional[float] = None) -> Optional[OpenOrderSnapshot]:
        contract = getattr(trade, "contract", None)
        order = getattr(trade, "order", None)
        order_status = getattr(trade, "orderStatus", None)
        symbol = getattr(contract, "symbol", None)
        if (
            not symbol
            or order is None
            or not self._account_matches(getattr(order, "account", None))
            or not self._contract_matches(contract)
        ):
            return None

        order_ref = getattr(order, "orderRef", None)
        parsed_ref = parse_order_ref(order_ref)
        limit_price = getattr(order, "lmtPrice", None)
        if limit_price in ("", 0):
            limit_price = None

        return OpenOrderSnapshot(
            order_id=getattr(order, "orderId", None),
            perm_id=getattr(order, "permId", None),
            order_ref=order_ref,
            symbol=symbol,
            side=getattr(order, "action", None),
            quantity=getattr(order, "totalQuantity", 0),
            limit_price=limit_price,
            status=getattr(order_status, "status", None),
            role=parsed_ref.get("role"),
            contract=contract,
            trade=trade,
            updated_at=now or time.time(),
        )

    def _snapshot_key(self, snapshot: OpenOrderSnapshot) -> str:
        if snapshot.perm_id not in (None, 0):
            return f"perm_id:{snapshot.perm_id}"
        if snapshot.order_ref:
            return f"order_ref:{snapshot.order_ref}"
        if snapshot.order_id is not None:
            return f"order_id:{snapshot.order_id}"
        return f"trade:{id(snapshot.trade)}"
