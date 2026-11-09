from dataclasses import dataclass
from typing import Tuple

from utils.ig_index.models import IGQuote, PositionState, TradeDecision


@dataclass(frozen=True)
class RiskSettings:
    max_spread_points: float = 5.0
    max_abs_position: float = 1.0
    max_trade_size: float = 1.0
    tradeable_statuses: Tuple[str, ...] = ("TRADEABLE",)


@dataclass(frozen=True)
class RiskCheck:
    accepted: bool
    reason: str


class IGRiskManager:
    def __init__(self, settings: RiskSettings) -> None:
        if settings.max_spread_points <= 0:
            raise ValueError("max_spread_points must be positive")
        if settings.max_abs_position <= 0:
            raise ValueError("max_abs_position must be positive")
        if settings.max_trade_size <= 0:
            raise ValueError("max_trade_size must be positive")
        self.settings = settings

    def check(
        self,
        quote: IGQuote,
        position: PositionState,
        decision: TradeDecision,
    ) -> RiskCheck:
        if decision.action == "HOLD":
            return RiskCheck(True, "hold")

        if quote.status not in self.settings.tradeable_statuses:
            return RiskCheck(False, f"market_status_{quote.status}")

        if quote.spread > self.settings.max_spread_points:
            return RiskCheck(False, "spread_too_wide")

        if decision.size <= 0:
            return RiskCheck(False, "non_positive_size")

        if decision.size > self.settings.max_trade_size:
            return RiskCheck(False, "trade_size_too_large")

        if decision.opens_position:
            projected = position.signed_size
            if decision.action == "OPEN_LONG":
                projected += decision.size
            elif decision.action == "OPEN_SHORT":
                projected -= decision.size
            if abs(projected) > self.settings.max_abs_position:
                return RiskCheck(False, "max_position_exceeded")

        if decision.closes_position:
            if position.direction == "FLAT":
                return RiskCheck(False, "no_position_to_close")
            if decision.size > position.size:
                return RiskCheck(False, "close_size_exceeds_position")

        return RiskCheck(True, "accepted")

