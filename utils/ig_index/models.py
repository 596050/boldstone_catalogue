from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Literal, Optional


TradeAction = Literal[
    "HOLD",
    "OPEN_LONG",
    "OPEN_SHORT",
    "CLOSE_LONG",
    "CLOSE_SHORT",
]
PositionDirection = Literal["FLAT", "LONG", "SHORT"]


@dataclass(frozen=True)
class IGQuote:
    epic: str
    bid: float
    offer: float
    status: str = "UNKNOWN"
    timestamp: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.epic:
            raise ValueError("epic is required")
        if self.bid <= 0 or self.offer <= 0:
            raise ValueError("bid and offer must be positive")
        if self.bid >= self.offer:
            raise ValueError("bid must be below offer")

    @property
    def mid(self) -> float:
        return (self.bid + self.offer) / 2.0

    @property
    def spread(self) -> float:
        return self.offer - self.bid


@dataclass(frozen=True)
class PositionState:
    direction: PositionDirection = "FLAT"
    size: float = 0.0
    average_entry: Optional[float] = None
    deal_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.size < 0:
            raise ValueError("size must be non-negative")
        if self.direction == "FLAT" and self.size != 0:
            raise ValueError("flat position must have size 0")
        if self.direction != "FLAT" and self.size <= 0:
            raise ValueError("non-flat position must have positive size")

    @property
    def signed_size(self) -> float:
        if self.direction == "LONG":
            return self.size
        if self.direction == "SHORT":
            return -self.size
        return 0.0


@dataclass(frozen=True)
class TradeDecision:
    action: TradeAction
    reason: str
    size: float = 0.0
    level: Optional[float] = None
    metadata: Dict[str, float] = field(default_factory=dict)

    @property
    def is_trade(self) -> bool:
        return self.action != "HOLD"

    @property
    def opens_position(self) -> bool:
        return self.action in {"OPEN_LONG", "OPEN_SHORT"}

    @property
    def closes_position(self) -> bool:
        return self.action in {"CLOSE_LONG", "CLOSE_SHORT"}

