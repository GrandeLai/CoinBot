"""Arbitrage opportunity domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from trading_assistant.exchanges.base import utcnow
from trading_assistant.utils.serialization import to_jsonable


@dataclass
class ArbitrageOpportunity:
    """Unified arbitrage opportunity representation."""

    opportunity_id: str
    strategy_type: str
    symbol: str
    buy_exchange: str | None
    sell_exchange: str | None
    expected_profit: Decimal
    expected_profit_pct: Decimal
    estimated_fee: Decimal
    estimated_slippage: Decimal
    required_capital: Decimal
    net_profit: Decimal
    risk_score: Decimal
    confidence: Decimal
    created_at: datetime = field(default_factory=utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(self)

