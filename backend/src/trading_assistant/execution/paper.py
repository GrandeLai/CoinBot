"""Paper trading ledger for simulated executions."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from trading_assistant.execution.order import ExecutionResult


@dataclass
class PaperTradingLedger:
    """In-memory paper ledger for local dry-run sessions."""

    starting_cash: Decimal = Decimal("10000")
    cash_usdt: Decimal | None = None
    realized_pnl_usdt: Decimal = Decimal("0")
    trade_count: int = 0
    history: list[ExecutionResult] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.cash_usdt is None:
            self.cash_usdt = self.starting_cash

    def record(self, result: ExecutionResult) -> None:
        """Record one simulated execution."""
        self.history.append(result)
        self.trade_count += 1
        self.realized_pnl_usdt += result.net_profit
        self.cash_usdt = (self.cash_usdt or Decimal("0")) + result.net_profit - Decimal("0.01")

