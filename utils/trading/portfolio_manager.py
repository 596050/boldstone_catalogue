# portfolio_manager.py
import threading
import time
import logging
from utils.trading.market_maker import QuoteMode

logger = logging.getLogger(__name__)

class PortfolioManager:
    def __init__(self, ib, oms, market_maker):
        self.ib = ib
        self.oms = oms
        self.market_maker = market_maker
        self.running = False
        self.thread = None
        self.portfolio = {}  # {symbol: position}
        self.risk_limits = {
            "max_position_per_symbol": 500,
            "max_total_exposure": 200000,  # Example realistic limit
            "max_loss": 1000  # Example for future use
        }
        
    def start(self):
        if self.running:
            logger.warning("Portfolio Manager already running.")
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("Portfolio Manager thread started.")


    def stop(self):
        self.running = False

    def _run(self):
        while self.running:
            self.update_portfolio()
            self.check_risk_limits()
            self.adjust_market_makers()
            time.sleep(10)  # Check every minute

    def update_portfolio(self):
        try:
            broker_state = getattr(self.oms, "broker_state", None)
            if broker_state is not None:
                snapshots = broker_state.refresh_positions()
                self.portfolio = {
                    symbol: snapshot.quantity for symbol, snapshot in snapshots.items()
                }
            else:
                logger.warning("Broker-state cache unavailable; portfolio snapshot not refreshed")
        except Exception as e:
            logger.error(f"Error updating portfolio: {e}")


    def check_risk_limits(self):
        total_exposure = sum(abs(pos) for pos in self.portfolio.values())
        max_total_exposure = self.risk_limits.get("max_total_exposure", float('inf'))
        if total_exposure > max_total_exposure:
            logger.warning("Total exposure limit breached, halting Market Maker.")
            self.market_maker.stop()  # Immediately halt all market making


    def adjust_market_makers(self):
        """Apply portfolio-level quote-mode overrides without sending liquidation orders."""
        total_exposure = sum(abs(pos) for pos in self.portfolio.values())
        max_total_exposure = self.risk_limits.get("max_total_exposure", float("inf"))
        portfolio_stressed = max_total_exposure not in (0, float("inf")) and (
            total_exposure >= 0.8 * max_total_exposure
        )

        for symbol, state in self.market_maker.market_makers.items():
            position = self.portfolio.get(symbol, 0.0)
            hard_limit = self.risk_limits.get("max_position_per_symbol", float("inf"))

            override_mode = None
            override_reason = None
            quote_size_multiplier = 1.0

            if abs(position) >= hard_limit:
                override_mode = QuoteMode.HALTED
                override_reason = "portfolio_hard_limit"
                quote_size_multiplier = 0.25
            elif portfolio_stressed and position != 0:
                override_mode = QuoteMode.REDUCE_ONLY
                override_reason = "portfolio_stress"
                quote_size_multiplier = 0.5
            elif abs(position) >= (
                state.settings.max_position * state.settings.inventory_reduce_threshold_pct
            ):
                quote_size_multiplier = 0.5

            changed = self.market_maker.apply_portfolio_controls(
                symbol,
                quote_mode=override_mode,
                reason=override_reason,
                quote_size_multiplier=quote_size_multiplier,
            )
            if changed:
                logger.info(
                    "%s: Portfolio controls applied mode=%s multiplier=%s position=%s",
                    symbol,
                    override_mode.value if override_mode else "AUTO",
                    quote_size_multiplier,
                    position,
                )
