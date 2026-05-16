"""Strategy runtime domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from trading_assistant.exchanges.base import utcnow
from trading_assistant.utils.serialization import to_jsonable


ExecutionMode = Literal["paper", "demo"]
StrategyDecision = Literal["executed", "blocked", "skipped"]
StrategyStatus = Literal["active", "deferred"]
StrategyRiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class StrategyDefinition:
    """Registered production strategy definition."""

    name: str
    scanner_type: str
    description: str
    category: str = "arbitrage"
    required_markets: list[str] = field(default_factory=list)
    risk_level: StrategyRiskLevel = "medium"
    status: StrategyStatus = "active"
    aliases: list[str] = field(default_factory=list)
    default_execution_mode: ExecutionMode = "paper"
    paper_supported: bool = True
    demo_supported: bool = False
    live_supported: bool = False
    execution_alias: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe strategy definition."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyBudgetDecision:
    """Position and capital budget decision."""

    approved: bool
    reasons: list[str]
    required_capital: Decimal
    max_position_value_usdt: Decimal
    max_strategy_capital_usdt: Decimal
    active_orders: int
    projected_open_orders: int
    max_open_orders_per_strategy: int
    active_capital_usdt: Decimal = Decimal("0")
    projected_strategy_capital_usdt: Decimal = Decimal("0")

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe budget decision."""
        return to_jsonable(self)


@dataclass(frozen=True)
class OrderLifecyclePlan:
    """Order lifecycle instructions for autonomous strategy execution."""

    order_ttl_seconds: int
    cancel_after_ttl: bool
    reprice_threshold_pct: Decimal
    rescan_before_reprice: bool
    actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe lifecycle plan."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyCycleResult:
    """One strategy decision within one runtime cycle."""

    cycle: int
    strategy_name: str
    decision: StrategyDecision
    execution_mode: ExecutionMode
    opportunities_found: int
    selected_opportunity_id: str | None
    risk_approved: bool
    risk_reasons: list[str]
    budget: StrategyBudgetDecision | None
    lifecycle: OrderLifecyclePlan | None
    execution: dict[str, Any] | None
    net_profit: Decimal
    message: str
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe cycle result."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyRunResult:
    """Result for a bounded or long-running strategy run."""

    completed: bool
    strategy_name: str
    execution_mode: ExecutionMode
    cycles_completed: int
    results: list[StrategyCycleResult]
    journal_path: str
    summary: str
    stopped_reason: str | None = None
    demo_cumulative_net_pnl: Decimal | None = None
    demo_max_drawdown_usdt: Decimal | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe run result."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyStats:
    """Review statistics for one strategy."""

    strategy_name: str
    total: int = 0
    executed: int = 0
    blocked: int = 0
    skipped: int = 0
    wins: int = 0
    losses: int = 0
    net_profit: Decimal = Decimal("0")
    win_rate_pct: Decimal = Decimal("0")

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe review stats."""
        return to_jsonable(self)


@dataclass(frozen=True)
class LearningSuggestion:
    """Conservative advisory learning output."""

    strategy_name: str
    action: str
    reason: str
    severity: Literal["info", "warning"]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe learning suggestion."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyReviewReport:
    """Post-run strategy review report."""

    total_events: int
    strategy_stats: dict[str, StrategyStats]
    suggestions: list[LearningSuggestion]
    journal_path: str

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe review report."""
        return to_jsonable(self)
