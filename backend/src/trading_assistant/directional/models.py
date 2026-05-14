"""Domain models for long-only spot directional strategies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from trading_assistant.exchanges.base import utcnow
from trading_assistant.utils.serialization import to_jsonable


DirectionalSignalValue = Literal["buy", "sell", "hold"]
DirectionalPositionState = Literal["planned", "open_submitted", "open", "exit_submitted", "closed", "aborted"]


@dataclass(frozen=True)
class DirectionalSignal:
    """Actionable or non-actionable signal from a directional strategy."""

    strategy_name: str
    symbol: str
    exchange: str
    signal: DirectionalSignalValue
    confidence: Decimal
    expected_edge_pct: Decimal
    stop_loss_pct: Decimal
    take_profit_pct: Decimal
    time_limit_minutes: int
    reason_codes: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class DirectionalPositionLifecycle:
    """Stateful lifecycle evidence for a spot directional position."""

    strategy_name: str
    symbol: str
    exchange: str
    state: DirectionalPositionState
    entry_signal: DirectionalSignal
    exit_signal: DirectionalSignal | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    entry_price: Decimal | None = None
    exit_price: Decimal | None = None
    quantity: Decimal | None = None
    realized_pnl_usdt: Decimal = Decimal("0")
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class DirectionalBacktestResult:
    """Fee and slippage adjusted directional backtest metrics."""

    strategy_name: str
    symbol: str
    exchange: str
    total_trades: int
    wins: int
    losses: int
    win_rate_pct: Decimal
    profit_factor: Decimal
    expectancy_usdt: Decimal
    max_drawdown_pct: Decimal
    average_hold_minutes: Decimal
    gross_pnl_usdt: Decimal
    fees_usdt: Decimal
    slippage_usdt: Decimal
    net_pnl_usdt: Decimal
    account_equity_attribution: dict[str, Decimal]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(self)
