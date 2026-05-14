"""Deterministic offline backtest engine."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trading_assistant.backtesting.metrics import BacktestMetrics, calculate_backtest_metrics
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class BacktestResult:
    """Backtest result payload."""

    metrics: BacktestMetrics
    equity_curve: list[Decimal]
    mode: str

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


class BacktestEngine:
    """Run a local mock backtest."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def run(self) -> BacktestResult:
        """Run deterministic mock backtest using configured initial capital."""
        initial = self.settings.backtest.initial_capital_usdt
        equity_curve = [
            initial,
            initial + Decimal("25"),
            initial + Decimal("55"),
            initial + Decimal("48"),
        ]
        metrics = calculate_backtest_metrics(equity_curve, trades=3, wins=2)
        return BacktestResult(metrics=metrics, equity_curve=equity_curve, mode=self.settings.app.mode)

