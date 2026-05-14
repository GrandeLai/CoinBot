"""Live broker execution service guarded by agent readiness checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Protocol

from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import Settings
from trading_assistant.exceptions import SafetyError
from trading_assistant.execution.live_agent import AgentLiveTradingGate
from trading_assistant.exchanges.base import utcnow
from trading_assistant.risk.manager import RiskDecision
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class LiveOrderReceipt:
    """Receipt returned after submitting one live broker order."""

    exchange: str
    order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    market: str
    order_type: str
    status: str
    submitted_quantity: Decimal
    submitted_price: Decimal | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveExecutionResult:
    """Result for a guarded live execution attempt."""

    opportunity_id: str
    status: Literal["submitted"]
    live_orders_sent: bool
    orders: list[LiveOrderReceipt]
    message: str
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


class LiveBroker(Protocol):
    """Protocol for real broker dispatch implementations."""

    def execute(self, opportunity: ArbitrageOpportunity) -> LiveExecutionResult:
        """Submit live orders for an already-approved opportunity."""


class AgentLiveExecutionService:
    """Execute an opportunity through a live broker after agent gates pass."""

    def __init__(self, settings: Settings, broker: LiveBroker) -> None:
        self.settings = settings
        self.broker = broker

    def execute(self, opportunity: ArbitrageOpportunity, risk_decision: RiskDecision) -> LiveExecutionResult:
        """Run readiness checks, audit the decision, then submit live orders."""
        gate = AgentLiveTradingGate(self.settings)
        readiness = gate.evaluate(opportunity, risk_decision)
        if self.settings.agent_trading.audit_log_path.strip():
            gate.append_audit_event(
                {
                    "event": "agent_execute_live_requested",
                    "opportunity_id": opportunity.opportunity_id,
                    "ready": readiness.ready,
                    "reasons": readiness.reasons,
                }
            )
        if not readiness.ready:
            raise SafetyError(f"autonomous live trading blocked: {', '.join(readiness.reasons)}")

        result = self.broker.execute(opportunity)
        if self.settings.agent_trading.audit_log_path.strip():
            gate.append_audit_event(
                {
                    "event": "agent_execute_live_submitted",
                    "opportunity_id": opportunity.opportunity_id,
                    "order_ids": [order.order_id for order in result.orders],
                    "live_orders_sent": result.live_orders_sent,
                }
            )
        return result
