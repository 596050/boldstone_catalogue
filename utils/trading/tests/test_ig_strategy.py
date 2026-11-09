import unittest

from utils.ig_index.models import IGQuote, PositionState, TradeDecision
from utils.ig_index.risk import IGRiskManager, RiskSettings
from utils.ig_index.strategy import SpreadAwareIGStrategy, StrategySettings


class IGQuoteTests(unittest.TestCase):
    def test_mid_and_spread(self):
        quote = IGQuote(epic="IX.D.TEST.CFD.IP", bid=99.5, offer=100.5, status="TRADEABLE")
        self.assertEqual(quote.mid, 100.0)
        self.assertEqual(quote.spread, 1.0)

    def test_rejects_crossed_quote(self):
        with self.assertRaises(ValueError):
            IGQuote(epic="IX.D.TEST.CFD.IP", bid=100.5, offer=100.5)


class SpreadAwareIGStrategyTests(unittest.TestCase):
    def _strategy(self):
        return SpreadAwareIGStrategy(
            StrategySettings(
                min_samples=5,
                trade_size=1.0,
                max_abs_position=2.0,
                min_edge_points=0.5,
                spread_cost_multiplier=1.0,
                volatility_multiplier=0.0,
            )
        )

    def _warm_up(self, strategy):
        flat = PositionState()
        for _ in range(5):
            decision = strategy.on_quote(
                IGQuote(epic="IX.D.TEST.CFD.IP", bid=99.95, offer=100.05, status="TRADEABLE"),
                flat,
            )
        return decision

    def test_waits_for_warmup(self):
        strategy = self._strategy()
        decision = strategy.on_quote(
            IGQuote(epic="IX.D.TEST.CFD.IP", bid=99.95, offer=100.05, status="TRADEABLE"),
            PositionState(),
        )
        self.assertEqual(decision.action, "HOLD")
        self.assertEqual(decision.reason, "warming_up")

    def test_opens_long_when_downward_edge_clears_spread_cost(self):
        strategy = self._strategy()
        self._warm_up(strategy)

        decision = strategy.on_quote(
            IGQuote(epic="IX.D.TEST.CFD.IP", bid=98.95, offer=99.05, status="TRADEABLE"),
            PositionState(),
        )

        self.assertEqual(decision.action, "OPEN_LONG")
        self.assertEqual(decision.reason, "long_edge_clears_spread")
        self.assertEqual(decision.level, 99.05)

    def test_opens_short_when_upward_edge_clears_spread_cost(self):
        strategy = self._strategy()
        self._warm_up(strategy)

        decision = strategy.on_quote(
            IGQuote(epic="IX.D.TEST.CFD.IP", bid=100.95, offer=101.05, status="TRADEABLE"),
            PositionState(),
        )

        self.assertEqual(decision.action, "OPEN_SHORT")
        self.assertEqual(decision.reason, "short_edge_clears_spread")
        self.assertEqual(decision.level, 100.95)

    def test_holds_when_spread_cost_consumes_edge(self):
        strategy = self._strategy()
        self._warm_up(strategy)

        decision = strategy.on_quote(
            IGQuote(epic="IX.D.TEST.CFD.IP", bid=99.0, offer=100.0, status="TRADEABLE"),
            PositionState(),
        )

        self.assertEqual(decision.action, "HOLD")
        self.assertEqual(decision.reason, "edge_too_small")

    def test_closes_long_when_edge_fades(self):
        strategy = self._strategy()
        self._warm_up(strategy)

        decision = strategy.on_quote(
            IGQuote(epic="IX.D.TEST.CFD.IP", bid=99.95, offer=100.05, status="TRADEABLE"),
            PositionState(direction="LONG", size=1.0, average_entry=99.05, deal_id="D1"),
        )

        self.assertEqual(decision.action, "CLOSE_LONG")
        self.assertEqual(decision.reason, "long_edge_faded")
        self.assertEqual(decision.level, 99.95)


class IGRiskManagerTests(unittest.TestCase):
    def test_rejects_non_tradeable_market(self):
        risk = IGRiskManager(RiskSettings(max_spread_points=5.0))
        check = risk.check(
            IGQuote(epic="IX.D.TEST.CFD.IP", bid=99.95, offer=100.05, status="CLOSED"),
            PositionState(),
            TradeDecision("OPEN_LONG", "test", size=1.0),
        )
        self.assertFalse(check.accepted)
        self.assertEqual(check.reason, "market_status_CLOSED")

    def test_rejects_wide_spread(self):
        risk = IGRiskManager(RiskSettings(max_spread_points=0.5))
        check = risk.check(
            IGQuote(epic="IX.D.TEST.CFD.IP", bid=99.0, offer=100.0, status="TRADEABLE"),
            PositionState(),
            TradeDecision("OPEN_LONG", "test", size=1.0),
        )
        self.assertFalse(check.accepted)
        self.assertEqual(check.reason, "spread_too_wide")

    def test_rejects_projected_position_breach(self):
        risk = IGRiskManager(RiskSettings(max_abs_position=1.0, max_trade_size=1.0))
        check = risk.check(
            IGQuote(epic="IX.D.TEST.CFD.IP", bid=99.95, offer=100.05, status="TRADEABLE"),
            PositionState(direction="LONG", size=1.0),
            TradeDecision("OPEN_LONG", "test", size=1.0),
        )
        self.assertFalse(check.accepted)
        self.assertEqual(check.reason, "max_position_exceeded")

    def test_accepts_close_for_existing_position(self):
        risk = IGRiskManager(RiskSettings(max_abs_position=1.0, max_trade_size=1.0))
        check = risk.check(
            IGQuote(epic="IX.D.TEST.CFD.IP", bid=99.95, offer=100.05, status="TRADEABLE"),
            PositionState(direction="LONG", size=1.0, deal_id="D1"),
            TradeDecision("CLOSE_LONG", "test", size=1.0),
        )
        self.assertTrue(check.accepted)


if __name__ == "__main__":
    unittest.main()

