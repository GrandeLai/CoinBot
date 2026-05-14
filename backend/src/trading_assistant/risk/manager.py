"""Independent risk checks for arbitrage execution."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import RiskConfig
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class RiskDecision:
    """Risk evaluation result."""

    approved: bool
    violations: list[str]
    risk_score: Decimal

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


class RiskManager:
    """Evaluate opportunities against configured risk limits."""

    def __init__(self, config: RiskConfig) -> None:
        self.config = config

    def evaluate(self, opportunity: ArbitrageOpportunity, exchange_available: bool = True) -> RiskDecision:
        """Return approval decision and named violations."""
        violations: list[str] = []
        if not exchange_available:
            violations.append("exchange_unavailable")
        if opportunity.required_capital > self.config.max_order_value_usdt:
            violations.append("max_order_value_usdt")
        if opportunity.required_capital > self.config.max_position_exposure_usdt:
            violations.append("max_position_exposure_usdt")
        if opportunity.net_profit < Decimal("0"):
            violations.append("negative_net_profit")
        net_profit_pct = Decimal("0")
        if opportunity.required_capital > 0:
            net_profit_pct = (opportunity.net_profit / opportunity.required_capital) * Decimal("100")
        if net_profit_pct < self.config.min_net_profit_pct:
            violations.append("min_net_profit_pct")
        if opportunity.estimated_slippage > opportunity.required_capital * (self.config.max_slippage_pct / Decimal("100")):
            violations.append("max_slippage_pct")
        if opportunity.symbol in self.config.symbol_blacklist:
            violations.append("symbol_blacklist")
        if opportunity.buy_exchange in self.config.exchange_blacklist or opportunity.sell_exchange in self.config.exchange_blacklist:
            violations.append("exchange_blacklist")
        return RiskDecision(
            approved=not violations,
            violations=violations,
            risk_score=max(opportunity.risk_score, Decimal("0")),
        )
