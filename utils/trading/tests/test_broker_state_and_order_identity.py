import sys
import types
import unittest
from types import SimpleNamespace


def _install_fake_ib_insync():
    if "ib_insync" in sys.modules:
        return

    fake_module = types.ModuleType("ib_insync")

    class IB:
        pass

    class Contract:
        def __init__(self, symbol=None):
            self.symbol = symbol

    class Order:
        def __init__(self):
            self.orderId = 0
            self.permId = 0
            self.orderRef = ""
            self.action = None
            self.orderType = None
            self.totalQuantity = 0
            self.tif = "DAY"
            self.lmtPrice = None
            self.auxPrice = None

    class Trade:
        def __init__(self):
            self.order = SimpleNamespace(orderId=0, permId=0)
            self.orderStatus = SimpleNamespace(
                status="Submitted", filled=0, avgFillPrice=0.0, whyHeld=None
            )
            self.contract = None

    class Stock(Contract):
        def __init__(self, symbol, exchange, currency, primaryExchange=None):
            super().__init__(symbol=symbol)
            self.exchange = exchange
            self.currency = currency
            self.primaryExchange = primaryExchange

    fake_module.IB = IB
    fake_module.Contract = Contract
    fake_module.Order = Order
    fake_module.Trade = Trade
    fake_module.Stock = Stock

    sys.modules["ib_insync"] = fake_module


_install_fake_ib_insync()

from utils.trading.broker_state import BrokerStateCache  # noqa: E402
from utils.trading.order_management import OrderManagementSystem, OrderRecord, OrderSide, OrderStatus, OrderType


class FakeEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self


class FakePosition:
    def __init__(
        self,
        symbol,
        position,
        avg_cost,
        *,
        account="",
        sec_type="STK",
        currency="USD",
        con_id=0,
    ):
        self.account = account
        self.contract = SimpleNamespace(
            symbol=symbol,
            secType=sec_type,
            currency=currency,
            conId=con_id,
            exchange="SMART",
        )
        self.position = position
        self.avgCost = avg_cost


class FakeTrade:
    def __init__(
        self,
        contract,
        order,
        status="Submitted",
        filled=0,
        avg_fill_price=0.0,
        why_held=None,
    ):
        self.contract = contract
        self.order = order
        self.orderStatus = SimpleNamespace(
            status=status,
            filled=filled,
            avgFillPrice=avg_fill_price,
            whyHeld=why_held,
        )


class FakeIB:
    def __init__(self, positions=None, open_trades=None):
        self._positions = positions or []
        self._open_trades = open_trades or []
        self._next_order_id = 100
        self.connected = True
        self.orderStatusEvent = FakeEvent()
        self.execDetailsEvent = FakeEvent()
        self.errorEvent = FakeEvent()
        self.client = SimpleNamespace(cancelOrder=lambda order_id: True)
        self.scheduled = []

    def isConnected(self):
        return self.connected

    def positions(self, account=None):
        if not account:
            return list(self._positions)
        return [
            position
            for position in self._positions
            if position.account in {"", account}
        ]

    def openTrades(self):
        return list(self._open_trades)

    def schedule(self, when, callback):
        self.scheduled.append((when, callback))

    def placeOrder(self, contract, order):
        order.orderId = self._next_order_id
        order.permId = self._next_order_id + 1000
        self._next_order_id += 1
        trade = FakeTrade(contract, order)
        self._open_trades.append(trade)
        return trade

    def cancelOrder(self, order):
        self._open_trades = [
            trade for trade in self._open_trades if trade.order.orderId != order.orderId
        ]
        return True


class BrokerStateTests(unittest.TestCase):
    def test_refresh_positions_captures_quantity_and_avg_cost(self):
        fake_ib = FakeIB(
            positions=[
                FakePosition("AAPL", 25.0, 199.5),
                FakePosition("MSFT", -10.0, 410.25),
            ]
        )
        broker_state = BrokerStateCache(fake_ib)

        snapshots = broker_state.refresh_positions()

        self.assertEqual(snapshots["AAPL"].quantity, 25.0)
        self.assertEqual(snapshots["AAPL"].avg_cost, 199.5)
        self.assertEqual(snapshots["MSFT"].quantity, -10.0)
        self.assertEqual(snapshots["MSFT"].avg_cost, 410.25)

    def test_account_scoped_stock_cache_rejects_same_symbol_option(self):
        fake_ib = FakeIB(
            positions=[
                FakePosition(
                    "PFE", 395.0, 25.0, account="DU1", con_id=1
                ),
                FakePosition(
                    "PFE",
                    1.0,
                    2.0,
                    account="DU1",
                    sec_type="OPT",
                    con_id=2,
                ),
            ]
        )
        broker_state = BrokerStateCache(
            fake_ib,
            account="DU1",
            security_type="STK",
            currency="USD",
            reject_unsupported_contracts=True,
        )

        snapshots = broker_state.refresh_positions()

        self.assertEqual(snapshots, {})
        self.assertIn("unsupported position contract", broker_state.last_positions_error)

    def test_refresh_open_orders_parses_market_maker_role_from_order_ref(self):
        order = SimpleNamespace(
            orderId=101,
            permId=1101,
            orderRef="mm|symbol=AAPL|role=market_maker_bid|internal_id=test-order",
            action="BUY",
            totalQuantity=25,
            lmtPrice=200.0,
        )
        trade = FakeTrade(SimpleNamespace(symbol="AAPL"), order)
        fake_ib = FakeIB(open_trades=[trade])
        broker_state = BrokerStateCache(fake_ib)

        snapshots = broker_state.refresh_open_orders()

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].symbol, "AAPL")
        self.assertEqual(snapshots[0].role, "market_maker_bid")
        self.assertEqual(
            broker_state.get_open_order_by_ref(order.orderRef).order_id, 101
        )

    def test_refresh_open_orders_keeps_inventory_reduce_only_roles_reconcilable(self):
        order = SimpleNamespace(
            orderId=102,
            permId=1102,
            orderRef="mm|symbol=AAPL|role=inventory_reduce_only_ask|internal_id=test-order",
            action="SELL",
            totalQuantity=10,
            lmtPrice=201.0,
        )
        trade = FakeTrade(SimpleNamespace(symbol="AAPL"), order)
        fake_ib = FakeIB(open_trades=[trade])
        broker_state = BrokerStateCache(fake_ib)

        snapshots = broker_state.refresh_open_orders()

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].role, "inventory_reduce_only_ask")

    def test_refresh_open_orders_preserves_multiple_unbound_orders(self):
        order_one = SimpleNamespace(
            orderId=0,
            permId=2101,
            orderRef="mm|symbol=AAPL|role=market_maker_bid|internal_id=unbound-1",
            action="BUY",
            totalQuantity=10,
            lmtPrice=200.0,
        )
        order_two = SimpleNamespace(
            orderId=0,
            permId=2102,
            orderRef="mm|symbol=AAPL|role=market_maker_ask|internal_id=unbound-2",
            action="SELL",
            totalQuantity=10,
            lmtPrice=201.0,
        )
        fake_ib = FakeIB(
            open_trades=[
                FakeTrade(SimpleNamespace(symbol="AAPL"), order_one),
                FakeTrade(SimpleNamespace(symbol="AAPL"), order_two),
            ]
        )
        broker_state = BrokerStateCache(fake_ib)

        snapshots = broker_state.refresh_open_orders()

        self.assertEqual(len(snapshots), 2)
        self.assertEqual(
            {
                snapshot.order_ref
                for snapshot in snapshots
            },
            {
                "mm|symbol=AAPL|role=market_maker_bid|internal_id=unbound-1",
                "mm|symbol=AAPL|role=market_maker_ask|internal_id=unbound-2",
            },
        )

    def test_remember_trade_keeps_inactive_orders_visible_for_reconciliation(self):
        fake_ib = FakeIB()
        broker_state = BrokerStateCache(fake_ib)
        order = SimpleNamespace(
            orderId=103,
            permId=1103,
            orderRef="mm|symbol=AAPL|role=market_maker_bid|internal_id=inactive-order",
            action="BUY",
            totalQuantity=10,
            lmtPrice=199.0,
        )
        trade = FakeTrade(SimpleNamespace(symbol="AAPL"), order, status="Inactive")

        broker_state.remember_trade(trade)

        self.assertEqual(len(broker_state.get_open_orders()), 1)
        self.assertEqual(broker_state.get_open_orders()[0].status, "Inactive")

    def test_remember_trade_removes_api_cancelled_orders_from_cache(self):
        order = SimpleNamespace(
            orderId=104,
            permId=1104,
            orderRef="mm|symbol=AAPL|role=market_maker_bid|internal_id=api-cancelled",
            action="BUY",
            totalQuantity=10,
            lmtPrice=199.0,
        )
        trade = FakeTrade(SimpleNamespace(symbol="AAPL"), order, status="Submitted")
        fake_ib = FakeIB(open_trades=[trade])
        broker_state = BrokerStateCache(fake_ib)
        broker_state.refresh_open_orders()

        trade.orderStatus.status = "ApiCancelled"
        broker_state.remember_trade(trade)

        self.assertEqual(broker_state.get_open_orders(), [])


class OrderStatusMappingTests(unittest.TestCase):
    def test_order_record_maps_documented_ib_pending_and_cancelled_states(self):
        order_record = OrderRecord(
            contract=SimpleNamespace(symbol="AAPL"),
            order_side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=25.0,
            price=200.0,
        )

        order_record.update_from_ib_order_status("PendingSubmit", 0, 0.0)
        self.assertEqual(order_record.status, OrderStatus.PENDING_NEW)

        order_record.update_from_ib_order_status("ApiCancelled", 0, 0.0)
        self.assertEqual(order_record.status, OrderStatus.CANCELLED)

    def test_order_record_marks_inactive_orders_explicitly(self):
        order_record = OrderRecord(
            contract=SimpleNamespace(symbol="AAPL"),
            order_side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=25.0,
            price=200.0,
        )

        order_record.update_from_ib_order_status(
            "Inactive",
            0,
            0.0,
            "order held while exchange closed",
        )

        self.assertEqual(order_record.status, OrderStatus.INACTIVE)
        self.assertEqual(order_record.error_message, "order held while exchange closed")


class DurableOrderIdentityTests(unittest.TestCase):
    def test_configured_account_is_pinned_on_every_broker_order(self):
        fake_ib = FakeIB(positions=[FakePosition("AAPL", 0.0, None, account="DU1")])
        oms = OrderManagementSystem(
            fake_ib,
            max_order_size={"AAPL": 125.0},
            account="DU1",
        )
        order_record = oms.create_order(
            contract=SimpleNamespace(symbol="AAPL"),
            order_side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=25.0,
            price=200.0,
        )

        ib_order = oms._build_ib_order(order_record)

        self.assertEqual(ib_order.account, "DU1")

    def test_create_order_assigns_market_maker_role_and_durable_order_ref(self):
        fake_ib = FakeIB(positions=[FakePosition("AAPL", 0.0, None)])
        oms = OrderManagementSystem(fake_ib, max_order_size={"AAPL": 125.0})

        order_record = oms.create_order(
            contract=SimpleNamespace(symbol="AAPL"),
            order_side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=25.0,
            price=200.0,
            tags={"market_maker": True, "symbol": "AAPL", "role": "market_maker_bid"},
        )

        self.assertIsNotNone(order_record)
        self.assertEqual(order_record.role, "market_maker_bid")
        self.assertTrue(order_record.order_ref.startswith("mm|symbol=AAPL|role=market_maker_bid|"))

    def test_submit_order_tracks_perm_id_and_market_maker_open_order(self):
        fake_ib = FakeIB(positions=[FakePosition("AAPL", 0.0, None)])
        oms = OrderManagementSystem(fake_ib, max_order_size={"AAPL": 125.0})

        order_record = oms.create_order(
            contract=SimpleNamespace(symbol="AAPL"),
            order_side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=25.0,
            price=200.0,
            tags={"market_maker": True, "symbol": "AAPL", "role": "market_maker_bid"},
        )

        submitted = oms.submit_order(order_record)

        self.assertTrue(submitted)
        self.assertEqual(order_record.ib_order_id, 100)
        self.assertEqual(order_record.perm_id, 1100)
        self.assertEqual(oms.find_order_by_order_ref(order_record.order_ref), order_record)
        open_orders = oms.list_open_market_maker_orders(refresh=False)
        self.assertEqual(len(open_orders), 1)
        self.assertEqual(open_orders[0].order_ref, order_record.order_ref)

    def test_cancel_order_allows_pending_new_status(self):
        fake_ib = FakeIB(positions=[FakePosition("AAPL", 0.0, None)])
        oms = OrderManagementSystem(fake_ib, max_order_size={"AAPL": 125.0})

        order_record = oms.create_order(
            contract=SimpleNamespace(symbol="AAPL"),
            order_side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=25.0,
            price=200.0,
            tags={"market_maker": True, "symbol": "AAPL", "role": "market_maker_bid"},
        )
        oms.submit_order(order_record)
        order_record.status = OrderStatus.PENDING_NEW

        cancelled = oms.cancel_order(order_record.internal_id)

        self.assertTrue(cancelled)

    def test_list_open_market_maker_orders_includes_inventory_reduce_only_roles(self):
        fake_ib = FakeIB()
        oms = OrderManagementSystem(fake_ib, max_order_size={"AAPL": 125.0})
        order = SimpleNamespace(
            orderId=151,
            permId=1151,
            orderRef="mm|symbol=AAPL|role=inventory_reduce_only_bid|internal_id=external-order",
            action="BUY",
            orderType="LMT",
            totalQuantity=10.0,
            tif="DAY",
            lmtPrice=199.0,
            auxPrice=None,
        )
        trade = FakeTrade(SimpleNamespace(symbol="AAPL"), order)

        oms.adopt_open_trade(trade)

        open_orders = oms.list_open_market_maker_orders(refresh=False)
        self.assertEqual(len(open_orders), 1)
        self.assertEqual(open_orders[0].role, "inventory_reduce_only_bid")

    def test_adopt_open_trade_indexes_existing_order_by_order_ref(self):
        fake_ib = FakeIB()
        oms = OrderManagementSystem(fake_ib, max_order_size={"AAPL": 125.0})
        order = SimpleNamespace(
            orderId=150,
            permId=1150,
            orderRef="mm|symbol=AAPL|role=market_maker_ask|internal_id=external-order",
            action="SELL",
            orderType="LMT",
            totalQuantity=25.0,
            tif="DAY",
            lmtPrice=201.0,
            auxPrice=None,
        )
        trade = FakeTrade(SimpleNamespace(symbol="AAPL"), order)

        adopted = oms.adopt_open_trade(trade)

        self.assertIsNotNone(adopted)
        self.assertEqual(adopted.role, "market_maker_ask")
        self.assertEqual(oms.find_order_by_order_ref(order.orderRef), adopted)


if __name__ == "__main__":
    unittest.main()
