"""Read-only operator brief for strategy runtime safety and validation state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.base import utcnow
from trading_assistant.strategies.guard import StrategyRuntimeGuard
from trading_assistant.strategies.models import ExecutionMode
from trading_assistant.strategies.registry import StrategyRegistry
from trading_assistant.strategies.validation_report import StrategyValidationReportService
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class StrategyOperatorBrief:
    """Read-only operator-facing snapshot before demo or live promotion decisions."""

    strategy_name: str
    execution_mode: ExecutionMode | None
    safety: dict[str, Any]
    size_stage: dict[str, Any]
    guard: dict[str, Any]
    validation: dict[str, Any]
    recommendations: list[str] = field(default_factory=list)
    read_only: bool = True
    orders_sent: bool = False
    live_orders_sent: bool = False
    generated_at: str = field(default_factory=lambda: utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe operator brief."""
        return to_jsonable(self)


class StrategyOperatorBriefService:
    """Build a read-only brief from config, runtime guard, and journal validation evidence."""

    def __init__(self, settings: Settings, registry: StrategyRegistry | None = None) -> None:
        self.settings = settings
        self.registry = registry or StrategyRegistry()

    def brief(
        self,
        *,
        strategy_name: str = "all",
        execution_mode: ExecutionMode | None = None,
        limit: int = 50,
    ) -> StrategyOperatorBrief:
        """Return a read-only operator brief for one strategy set."""
        strategy_names = self._strategy_names(strategy_name)
        guard = StrategyRuntimeGuard(self.settings.strategy_runtime).status(
            strategy_names=strategy_names,
            execution_mode=execution_mode,
        )
        validation = StrategyValidationReportService(self.settings.strategy_runtime).report(
            execution_mode=execution_mode,
            strategy_name=strategy_name,
            limit=limit,
        ).to_dict()
        return StrategyOperatorBrief(
            strategy_name=strategy_name,
            execution_mode=execution_mode,
            safety=self._safety(),
            size_stage=self._size_stage(),
            guard=guard,
            validation=validation,
            recommendations=self._recommendations(guard, validation, execution_mode),
        )

    def _strategy_names(self, strategy_name: str) -> list[str]:
        if strategy_name == "all":
            return self.registry.names()
        return [definition.name for definition in self.registry.expand(strategy_name)]

    def _safety(self) -> dict[str, Any]:
        return to_jsonable(
            {
                "live_trading": self.settings.trading.live_trading,
                "dry_run": self.settings.trading.dry_run,
                "require_confirm_before_order": self.settings.trading.require_confirm_before_order,
                "agent_trading_enabled": self.settings.agent_trading.enabled,
                "agent_demo_orders_allowed": self.settings.agent_trading.allow_demo_orders,
                "agent_live_orders_allowed": self.settings.agent_trading.allow_live_orders,
                "validation_allow_live_canary": self.settings.strategy_runtime.validation_allow_live_canary,
            }
        )

    def _size_stage(self) -> dict[str, Any]:
        return to_jsonable(
            {
                "demo_order_size_multiplier": self.settings.strategy_runtime.demo_order_size_multiplier,
                "demo_max_order_value_usdt": self.settings.strategy_runtime.demo_max_order_value_usdt,
                "demo_strategy_size_overrides": {
                    name: override.model_dump(mode="json")
                    for name, override in self.settings.strategy_runtime.demo_strategy_size_overrides.items()
                },
            }
        )

    def _recommendations(
        self,
        guard: dict[str, Any],
        validation: dict[str, Any],
        execution_mode: ExecutionMode | None,
    ) -> list[str]:
        recommendations: list[str] = []
        if not self.settings.trading.live_trading:
            recommendations.append("live_trading_disabled")
        if not self.settings.agent_trading.allow_live_orders:
            recommendations.append("agent_live_orders_disabled")
        if not self.settings.strategy_runtime.validation_allow_live_canary:
            recommendations.append("live_canary_disabled")
        cooldown_count = sum(1 for entry in guard.get("entries", []) if entry.get("cooldown_active"))
        if cooldown_count:
            recommendations.append("wait_for_runtime_guard_cooldown")
        total = validation.get("total", {})
        executed = int(total.get("executed", 0))
        if execution_mode == "demo" and executed < self.settings.strategy_runtime.validation_min_demo_executions:
            recommendations.append("collect_more_demo_samples")
        elif execution_mode == "paper" and executed < self.settings.strategy_runtime.validation_min_local_executions:
            recommendations.append("collect_more_local_samples")
        if total.get("execution_quality_passed") is False:
            recommendations.append("review_validation_quality_failures")
        return sorted(set(recommendations))
