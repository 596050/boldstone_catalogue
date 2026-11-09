import math
from dataclasses import dataclass
from typing import Optional

from utils.ig_index.models import IGQuote, PositionState, TradeDecision


@dataclass(frozen=True)
class StrategySettings:
    trade_size: float = 1.0
    max_abs_position: float = 1.0
    min_samples: int = 20
    fair_value_alpha: float = 0.05
    volatility_alpha: float = 0.10
    min_edge_points: float = 1.0
    spread_cost_multiplier: float = 1.5
    volatility_multiplier: float = 1.0
    exit_edge_points: float = 0.0
    stop_loss_points: float = 20.0
    take_profit_points: float = 10.0
    allow_long: bool = True
    allow_short: bool = True


class SpreadAwareIGStrategy:
    """Directional IG strategy that treats IG's spread as a trading cost.

    This is not a passive market maker. It opens at IG's offer when long, opens
    at IG's bid when short, and requires estimated edge to clear that cost.
    """

    def __init__(self, settings: StrategySettings) -> None:
        if settings.trade_size <= 0:
            raise ValueError("trade_size must be positive")
        if settings.max_abs_position <= 0:
            raise ValueError("max_abs_position must be positive")
        if not 0 < settings.fair_value_alpha <= 1:
            raise ValueError("fair_value_alpha must be in (0, 1]")
        if not 0 < settings.volatility_alpha <= 1:
            raise ValueError("volatility_alpha must be in (0, 1]")
        self.settings = settings
        self._fair_mid: Optional[float] = None
        self._last_mid: Optional[float] = None
        self._variance: float = 0.0
        self.samples: int = 0

    @property
    def fair_mid(self) -> Optional[float]:
        return self._fair_mid

    @property
    def volatility_points(self) -> float:
        return math.sqrt(max(self._variance, 0.0))

    def on_quote(self, quote: IGQuote, position: PositionState) -> TradeDecision:
        decision = self._decide(quote, position)
        self._observe(quote)
        return decision

    def _observe(self, quote: IGQuote) -> None:
        mid = quote.mid
        if self._fair_mid is None:
            self._fair_mid = mid
            self._last_mid = mid
            self.samples = 1
            return

        change = mid - (self._last_mid if self._last_mid is not None else mid)
        self._variance = (
            (1.0 - self.settings.volatility_alpha) * self._variance
            + self.settings.volatility_alpha * change * change
        )
        self._fair_mid = (
            (1.0 - self.settings.fair_value_alpha) * self._fair_mid
            + self.settings.fair_value_alpha * mid
        )
        self._last_mid = mid
        self.samples += 1

    def _required_edge(self, quote: IGQuote) -> float:
        return max(
            self.settings.min_edge_points,
            quote.spread * self.settings.spread_cost_multiplier
            + self.volatility_points * self.settings.volatility_multiplier,
        )

    def _remaining_open_size(self, position: PositionState) -> float:
        return max(self.settings.max_abs_position - abs(position.signed_size), 0.0)

    def _decide(self, quote: IGQuote, position: PositionState) -> TradeDecision:
        if self._fair_mid is None or self.samples < self.settings.min_samples:
            return TradeDecision("HOLD", "warming_up")

        edge_long = self._fair_mid - quote.mid
        edge_short = quote.mid - self._fair_mid
        required_edge = self._required_edge(quote)
        common_meta = {
            "fair_mid": self._fair_mid,
            "mid": quote.mid,
            "spread": quote.spread,
            "required_edge": required_edge,
            "volatility_points": self.volatility_points,
        }

        if position.direction == "LONG":
            close = self._long_close_decision(quote, position, edge_long, common_meta)
            if close:
                return close
            return TradeDecision("HOLD", "holding_long", metadata=common_meta)

        if position.direction == "SHORT":
            close = self._short_close_decision(quote, position, edge_short, common_meta)
            if close:
                return close
            return TradeDecision("HOLD", "holding_short", metadata=common_meta)

        size = min(self.settings.trade_size, self._remaining_open_size(position))
        if size <= 0:
            return TradeDecision("HOLD", "max_position_reached", metadata=common_meta)

        if self.settings.allow_long and edge_long >= required_edge:
            return TradeDecision(
                "OPEN_LONG",
                "long_edge_clears_spread",
                size=size,
                level=quote.offer,
                metadata={**common_meta, "edge": edge_long},
            )

        if self.settings.allow_short and edge_short >= required_edge:
            return TradeDecision(
                "OPEN_SHORT",
                "short_edge_clears_spread",
                size=size,
                level=quote.bid,
                metadata={**common_meta, "edge": edge_short},
            )

        return TradeDecision("HOLD", "edge_too_small", metadata=common_meta)

    def _long_close_decision(
        self,
        quote: IGQuote,
        position: PositionState,
        edge_long: float,
        metadata: dict,
    ) -> Optional[TradeDecision]:
        pnl_points = None
        if position.average_entry is not None:
            pnl_points = quote.bid - position.average_entry
            if pnl_points <= -self.settings.stop_loss_points:
                return TradeDecision(
                    "CLOSE_LONG",
                    "long_stop_loss",
                    size=position.size,
                    level=quote.bid,
                    metadata={**metadata, "pnl_points": pnl_points},
                )
            if pnl_points >= self.settings.take_profit_points:
                return TradeDecision(
                    "CLOSE_LONG",
                    "long_take_profit",
                    size=position.size,
                    level=quote.bid,
                    metadata={**metadata, "pnl_points": pnl_points},
                )

        if edge_long <= self.settings.exit_edge_points:
            meta = {**metadata}
            if pnl_points is not None:
                meta["pnl_points"] = pnl_points
            return TradeDecision(
                "CLOSE_LONG",
                "long_edge_faded",
                size=position.size,
                level=quote.bid,
                metadata=meta,
            )
        return None

    def _short_close_decision(
        self,
        quote: IGQuote,
        position: PositionState,
        edge_short: float,
        metadata: dict,
    ) -> Optional[TradeDecision]:
        pnl_points = None
        if position.average_entry is not None:
            pnl_points = position.average_entry - quote.offer
            if pnl_points <= -self.settings.stop_loss_points:
                return TradeDecision(
                    "CLOSE_SHORT",
                    "short_stop_loss",
                    size=position.size,
                    level=quote.offer,
                    metadata={**metadata, "pnl_points": pnl_points},
                )
            if pnl_points >= self.settings.take_profit_points:
                return TradeDecision(
                    "CLOSE_SHORT",
                    "short_take_profit",
                    size=position.size,
                    level=quote.offer,
                    metadata={**metadata, "pnl_points": pnl_points},
                )

        if edge_short <= self.settings.exit_edge_points:
            meta = {**metadata}
            if pnl_points is not None:
                meta["pnl_points"] = pnl_points
            return TradeDecision(
                "CLOSE_SHORT",
                "short_edge_faded",
                size=position.size,
                level=quote.offer,
                metadata=meta,
            )
        return None

