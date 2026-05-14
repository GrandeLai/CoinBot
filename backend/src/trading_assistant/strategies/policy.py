"""Position and order lifecycle controls for strategy runtime."""

from __future__ import annotations

from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import StrategyRuntimeConfig
from trading_assistant.strategies.models import OrderLifecyclePlan, StrategyBudgetDecision
from trading_assistant.strategies.registry import StrategyRegistry


class StrategyPolicy:
    """Evaluate runtime position caps and create lifecycle plans."""

    def __init__(self, config: StrategyRuntimeConfig) -> None:
        self.config = config

    def evaluate(self, strategy_name: str, opportunity: ArbitrageOpportunity, active_orders: int = 0) -> StrategyBudgetDecision:
        """Return position budget approval for one opportunity."""
        reasons: list[str] = []
        if not self._strategy_enabled(strategy_name):
            reasons.append("strategy_disabled")
        if opportunity.required_capital > self.config.max_position_value_usdt:
            reasons.append("max_position_value_usdt")
        if opportunity.required_capital > self.config.max_strategy_capital_usdt:
            reasons.append("max_strategy_capital_usdt")
        if active_orders >= self.config.max_open_orders_per_strategy:
            reasons.append("max_open_orders_per_strategy")
        return StrategyBudgetDecision(
            approved=not reasons,
            reasons=reasons,
            required_capital=opportunity.required_capital,
            max_position_value_usdt=self.config.max_position_value_usdt,
            max_strategy_capital_usdt=self.config.max_strategy_capital_usdt,
            active_orders=active_orders,
            max_open_orders_per_strategy=self.config.max_open_orders_per_strategy,
        )

    def lifecycle_plan(self) -> OrderLifecyclePlan:
        """Return cancel/reprice lifecycle instructions."""
        return OrderLifecyclePlan(
            order_ttl_seconds=self.config.order_ttl_seconds,
            cancel_after_ttl=True,
            reprice_threshold_pct=self.config.reprice_threshold_pct,
            rescan_before_reprice=True,
            actions=[
                "submit_if_risk_and_budget_approved",
                "cancel_if_unfilled_after_ttl",
                "rescan_market_before_reprice",
                "replace_only_if_new_opportunity_passes_risk_and_budget",
            ],
        )

    def _strategy_enabled(self, strategy_name: str) -> bool:
        """Return whether a strategy or compatibility alias is enabled."""
        enabled = set(self.config.enabled_strategies)
        if strategy_name in enabled:
            return True
        aliases = StrategyRegistry().aliases()
        canonical = aliases.get(strategy_name)
        if canonical and canonical in enabled:
            return True
        try:
            definition = StrategyRegistry().get(strategy_name)
        except Exception:
            return False
        return any(alias in enabled for alias in definition.aliases)
