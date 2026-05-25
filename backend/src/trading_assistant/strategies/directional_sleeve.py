"""Read-only directional sleeve promotion status."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from trading_assistant.config.schema import Settings
from trading_assistant.strategies.guard import StrategyRuntimeGuard
from trading_assistant.strategies.models import ExecutionMode, StrategyDefinition
from trading_assistant.strategies.registry import StrategyRegistry
from trading_assistant.strategies.validation_report import StrategyValidationAggregate, StrategyValidationReportService
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class DirectionalSleeveStrategyStatus:
    """Promotion status for one long-only directional strategy."""

    strategy_name: str
    demo_supported: bool
    demo_enabled: bool
    live_supported: bool
    stage: str
    validation_executed: int
    validation_win_rate_pct: Decimal
    validation_net_profit_usdt: Decimal
    validation_max_drawdown_usdt: Decimal
    execution_quality_passed: bool
    guard_cooldown_active: bool
    max_order_value_usdt: Decimal
    reasons: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe status."""
        return to_jsonable(self)


@dataclass(frozen=True)
class DirectionalSleeveStatusReport:
    """Read-only directional sleeve report."""

    execution_mode: ExecutionMode | None
    limit: int
    strategies: list[DirectionalSleeveStrategyStatus]
    summary: dict[str, Any]
    guardrails: list[str]
    read_only: bool = True
    orders_sent: bool = False
    live_orders_sent: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report."""
        return to_jsonable(
            {
                "execution_mode": self.execution_mode,
                "limit": self.limit,
                "strategies": [row.to_dict() for row in self.strategies],
                "summary": self.summary,
                "guardrails": self.guardrails,
                "read_only": self.read_only,
                "orders_sent": self.orders_sent,
                "live_orders_sent": self.live_orders_sent,
            }
        )


class DirectionalSleeveStatusService:
    """Report directional sleeve promotion rules without trading."""

    def __init__(self, settings: Settings, registry: StrategyRegistry | None = None) -> None:
        self.settings = settings
        self.registry = registry or StrategyRegistry()

    def status(
        self,
        execution_mode: ExecutionMode | None = None,
        limit: int = 50,
    ) -> DirectionalSleeveStatusReport:
        """Return directional sleeve status for all directional strategies."""
        requested_limit = max(limit, 1)
        definitions = self.registry.expand("directional-all")
        names = [definition.name for definition in definitions]
        validation = StrategyValidationReportService(self.settings.strategy_runtime).report(
            execution_mode=execution_mode,
            strategy_name="directional-all",
            limit=requested_limit,
        )
        guard = StrategyRuntimeGuard(self.settings.strategy_runtime).status(
            strategy_names=names,
            execution_mode=execution_mode,
        )
        rows = [
            self._row(
                definition=definition,
                aggregate=validation.by_strategy.get(definition.name),
                guard_entry=_guard_entry_for(definition.name, guard.get("entries", [])),
                execution_mode=execution_mode,
            )
            for definition in definitions
        ]
        return DirectionalSleeveStatusReport(
            execution_mode=execution_mode,
            limit=requested_limit,
            strategies=rows,
            summary=_summary(rows, self.settings),
            guardrails=[
                "read_only_no_orders",
                "directional_live_trading_not_supported",
                "small_sleeve_only",
                "demo_window_gates_remain_authoritative",
                "managed_exits_only_after_position_open",
            ],
        )

    def _row(
        self,
        *,
        definition: StrategyDefinition,
        aggregate: StrategyValidationAggregate | None,
        guard_entry: dict[str, Any] | None,
        execution_mode: ExecutionMode | None,
    ) -> DirectionalSleeveStrategyStatus:
        """Return one strategy sleeve row."""
        aggregate = aggregate or StrategyValidationAggregate(strategy_name=definition.name)
        demo_enabled = definition.name in self.settings.directional.demo_enabled_strategies
        cooldown_active = bool(guard_entry and guard_entry.get("cooldown_active"))
        required_executions = (
            self.settings.strategy_runtime.validation_min_demo_executions
            if execution_mode == "demo"
            else self.settings.strategy_runtime.validation_min_local_executions
        )
        stage, reasons = _stage(
            definition=definition,
            demo_enabled=demo_enabled,
            cooldown_active=cooldown_active,
            aggregate=aggregate,
            required_executions=required_executions,
            min_win_rate_pct=self.settings.strategy_runtime.validation_min_win_rate_pct,
            min_net_profit_usdt=self.settings.strategy_runtime.validation_min_net_profit_usdt,
        )
        return DirectionalSleeveStrategyStatus(
            strategy_name=definition.name,
            demo_supported=definition.demo_supported,
            demo_enabled=demo_enabled,
            live_supported=False,
            stage=stage,
            validation_executed=aggregate.executed,
            validation_win_rate_pct=aggregate.win_rate_pct,
            validation_net_profit_usdt=aggregate.realized_net_profit_usdt,
            validation_max_drawdown_usdt=aggregate.max_drawdown_usdt,
            execution_quality_passed=aggregate.execution_quality_passed,
            guard_cooldown_active=cooldown_active,
            max_order_value_usdt=self.settings.directional.demo_max_order_value_usdt,
            reasons=reasons,
            recommended_actions=_actions(stage),
        )


def _stage(
    *,
    definition: StrategyDefinition,
    demo_enabled: bool,
    cooldown_active: bool,
    aggregate: StrategyValidationAggregate,
    required_executions: int,
    min_win_rate_pct: Decimal,
    min_net_profit_usdt: Decimal,
) -> tuple[str, list[str]]:
    """Return promotion stage and reasons."""
    reasons: list[str] = []
    if not definition.demo_supported or not demo_enabled:
        reasons.append("directional_demo_not_enabled_for_strategy")
        return "paper_only", reasons
    if cooldown_active:
        reasons.append("runtime_guard_cooldown")
        return "blocked_runtime_guard", reasons
    if aggregate.executed < required_executions:
        reasons.append("insufficient_validation_samples")
        return "collect_more_samples", reasons
    if not aggregate.execution_quality_passed:
        reasons.append("validation_quality_failures")
        return "watchlist", reasons
    if aggregate.realized_net_profit_usdt <= min_net_profit_usdt:
        reasons.append("validation_net_profit_below_minimum")
        return "watchlist", reasons
    if aggregate.win_rate_pct < min_win_rate_pct:
        reasons.append("validation_win_rate_below_minimum")
        return "watchlist", reasons
    reasons.append("standard_demo_gates_still_required")
    return "demo_eligible_after_standard_gates", reasons


def _actions(stage: str) -> list[str]:
    """Return conservative action hints for a sleeve stage."""
    if stage == "demo_eligible_after_standard_gates":
        return ["use_demo_window_only_after_operator_brief", "keep_directional_size_caps"]
    if stage == "collect_more_samples":
        return ["collect_more_paper_samples"]
    if stage == "blocked_runtime_guard":
        return ["wait_for_runtime_guard_cooldown"]
    if stage == "paper_only":
        return ["keep_paper_only"]
    return ["keep_watchlist_until_validation_improves"]


def _summary(rows: list[DirectionalSleeveStrategyStatus], settings: Settings) -> dict[str, Any]:
    """Return aggregate directional sleeve summary."""
    return {
        "strategy_count": len(rows),
        "demo_enabled_strategy_count": sum(1 for row in rows if row.demo_enabled),
        "demo_eligible_count": sum(1 for row in rows if row.stage == "demo_eligible_after_standard_gates"),
        "paper_only_count": sum(1 for row in rows if row.stage == "paper_only"),
        "directional_live_supported": False,
        "max_position_value_usdt": settings.directional.max_position_value_usdt,
        "total_max_exposure_usdt": settings.directional.total_max_exposure_usdt,
        "demo_max_order_value_usdt": settings.directional.demo_max_order_value_usdt,
        "single_trade_risk_equity_pct": settings.directional.single_trade_risk_equity_pct,
        "daily_loss_pct": settings.directional.daily_loss_pct,
    }


def _guard_entry_for(strategy_name: str, entries: Any) -> dict[str, Any] | None:
    """Return guard entry for one strategy."""
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("strategy_name") == strategy_name:
            return entry
    return None
