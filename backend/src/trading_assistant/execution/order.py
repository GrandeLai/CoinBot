"""Order and execution result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

from trading_assistant.exchanges.base import utcnow
from trading_assistant.risk.manager import RiskDecision
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class SimulatedOrder:
    """Simulated order leg."""

    exchange: str
    symbol: str
    side: Literal["buy", "sell"]
    price: Decimal
    quantity: Decimal
    notional: Decimal
    status: Literal["simulated", "blocked"]


@dataclass(frozen=True)
class ExecutionResult:
    """Execution result for dry-run or paper trading."""

    opportunity_id: str
    status: Literal["simulated", "blocked"]
    dry_run: bool
    risk_decision: RiskDecision
    orders: list[SimulatedOrder]
    net_profit: Decimal
    message: str
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)

