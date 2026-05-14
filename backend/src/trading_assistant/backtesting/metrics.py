"""Backtest metric calculations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class BacktestMetrics:
    """Core backtest metrics."""

    initial_equity: Decimal
    final_equity: Decimal
    total_return_pct: Decimal
    max_drawdown_pct: Decimal
    trades: int
    win_rate_pct: Decimal

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


def calculate_backtest_metrics(equity_curve: list[Decimal], trades: int, wins: int) -> BacktestMetrics:
    """Calculate simple deterministic backtest metrics."""
    if not equity_curve:
        equity_curve = [Decimal("0")]
    initial = equity_curve[0]
    final = equity_curve[-1]
    total_return = Decimal("0") if initial == 0 else ((final - initial) / initial) * Decimal("100")
    peak = equity_curve[0]
    max_drawdown = Decimal("0")
    for value in equity_curve:
        peak = max(peak, value)
        if peak:
            drawdown = ((peak - value) / peak) * Decimal("100")
            max_drawdown = max(max_drawdown, drawdown)
    win_rate = Decimal("0") if trades == 0 else (Decimal(wins) / Decimal(trades)) * Decimal("100")
    return BacktestMetrics(
        initial_equity=initial,
        final_equity=final,
        total_return_pct=total_return.quantize(Decimal("0.01")),
        max_drawdown_pct=max_drawdown.quantize(Decimal("0.01")),
        trades=trades,
        win_rate_pct=win_rate.quantize(Decimal("0.01")),
    )

