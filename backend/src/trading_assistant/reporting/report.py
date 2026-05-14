"""Daily report generator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from trading_assistant.arbitrage.scanner import ArbitrageScanner
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.base import utcnow
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class AssistantReport:
    """Generated assistant report."""

    report_type: str
    generated_at: datetime
    sections: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report payload."""
        return {
            "type": self.report_type,
            "generated_at": self.generated_at.isoformat(),
            "sections": to_jsonable(self.sections),
        }


class ReportGenerator:
    """Generate local assistant reports."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def generate(self, report_type: str = "daily") -> AssistantReport:
        """Generate a report for configured mock state."""
        if report_type != "daily":
            raise ValueError(f"Unsupported report type: {report_type}")
        scanner = ArbitrageScanner(self.settings, self.exchanges)
        opportunities = scanner.scan("cross-exchange", symbol="BTC/USDT")
        return AssistantReport(
            report_type="daily",
            generated_at=utcnow(),
            sections={
                "safety": {
                    "mode": self.settings.app.mode,
                    "dry_run": self.settings.trading.dry_run,
                    "live_trading": self.settings.trading.live_trading,
                    "exchange_credentials": {
                        name: config.redacted_credentials() for name, config in self.settings.exchanges.items()
                    },
                },
                "arbitrage": {
                    "opportunity_count": len(opportunities),
                    "top_opportunities": [opportunity.to_dict() for opportunity in opportunities[:3]],
                },
                "risk": self.settings.risk.model_dump(mode="json"),
            },
        )

