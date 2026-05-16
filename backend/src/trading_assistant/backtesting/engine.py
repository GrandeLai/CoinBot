"""Read-only backtest and walk-forward validation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from trading_assistant.backtesting.metrics import BacktestMetrics, calculate_backtest_metrics
from trading_assistant.config.schema import Settings
from trading_assistant.directional.backtest import DirectionalBacktestEngine
from trading_assistant.directional.models import DirectionalBacktestResult
from trading_assistant.directional.strategies import strategy_for_name
from trading_assistant.exchanges.base import Candle
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class BacktestResult:
    """Backtest result payload."""

    metrics: BacktestMetrics
    equity_curve: list[Decimal]
    mode: str
    read_only: bool = True
    orders_sent: bool = False
    live_orders_sent: bool = False
    strategy_name: str = "trend-breakout"
    symbol: str = "BTC/USDT"
    exchange: str = "mock"
    bar: str = "15m"
    candle_count: int = 0
    fill_model: dict[str, object] = field(default_factory=dict)
    directional_result: DirectionalBacktestResult | None = None

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class WalkForwardWindow:
    """One expanding train and forward validation backtest window."""

    index: int
    train_candle_count: int
    validation_candle_count: int
    train_result: DirectionalBacktestResult | None
    validation_result: DirectionalBacktestResult | None
    accepted: bool
    reasons: list[str]

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class WalkForwardReport:
    """Read-only walk-forward validation report."""

    strategy_name: str
    symbol: str
    exchange: str
    bar: str
    read_only: bool
    orders_sent: bool
    live_orders_sent: bool
    windows: list[WalkForwardWindow]
    summary: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class BiasCheckReport:
    """No-order diagnostics for obvious backtest bias risks."""

    strategy_name: str
    symbol: str
    exchange: str
    bar: str
    read_only: bool
    orders_sent: bool
    live_orders_sent: bool
    passed: bool
    checks: list[dict[str, object]]
    reasons: list[str]

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


class BacktestEngine:
    """Run read-only local backtest validation."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def run(
        self,
        strategy_name: str | None = None,
        symbol: str | None = None,
        exchange: str | None = None,
        bar: str | None = None,
        limit: int | None = None,
    ) -> BacktestResult:
        """Run a fee/slippage-adjusted completed-candle backtest."""
        target_strategy = strategy_name or self.settings.backtest.strategy
        target_symbol = symbol or self.settings.backtest.symbol
        target_exchange = exchange or self.settings.backtest.exchange
        target_bar = bar or self.settings.backtest.bar
        candles = self._completed_candles(target_exchange, target_symbol, target_bar, limit)
        directional = self._directional_backtest(target_strategy, target_symbol, target_exchange, candles)
        initial = self.settings.backtest.initial_capital_usdt
        net_pnl = directional.net_pnl_usdt if directional is not None else Decimal("0")
        equity_curve = [initial, initial + net_pnl]
        metrics = calculate_backtest_metrics(
            equity_curve,
            trades=directional.total_trades if directional is not None else 0,
            wins=directional.wins if directional is not None else 0,
        )
        return BacktestResult(
            metrics=metrics,
            equity_curve=equity_curve,
            mode=self.settings.app.mode,
            strategy_name=target_strategy,
            symbol=target_symbol,
            exchange=target_exchange,
            bar=target_bar,
            candle_count=len(candles),
            fill_model=self._fill_model(),
            directional_result=directional,
        )

    def walk_forward(
        self,
        strategy_name: str | None = None,
        symbol: str | None = None,
        exchange: str | None = None,
        bar: str | None = None,
        limit: int | None = None,
        windows: int | None = None,
    ) -> WalkForwardReport:
        """Run expanding train and forward validation windows."""
        target_strategy = strategy_name or self.settings.backtest.strategy
        target_symbol = symbol or self.settings.backtest.symbol
        target_exchange = exchange or self.settings.backtest.exchange
        target_bar = bar or self.settings.backtest.bar
        window_count = windows or self.settings.backtest.walk_forward_windows
        candles = self._completed_candles(target_exchange, target_symbol, target_bar, limit)
        segments = _walk_forward_segments(len(candles), window_count)
        rows: list[WalkForwardWindow] = []
        for index, (train_end, validation_end) in enumerate(segments, start=1):
            train_candles = candles[:train_end]
            validation_candles = candles[train_end:validation_end]
            train = self._directional_backtest(target_strategy, target_symbol, target_exchange, train_candles)
            validation = self._directional_backtest(target_strategy, target_symbol, target_exchange, validation_candles)
            reasons = _window_reasons(validation, self.settings.backtest.min_window_trades)
            rows.append(
                WalkForwardWindow(
                    index=index,
                    train_candle_count=len(train_candles),
                    validation_candle_count=len(validation_candles),
                    train_result=train,
                    validation_result=validation,
                    accepted=not reasons,
                    reasons=reasons,
                )
            )
        accepted = sum(1 for row in rows if row.accepted)
        return WalkForwardReport(
            strategy_name=target_strategy,
            symbol=target_symbol,
            exchange=target_exchange,
            bar=target_bar,
            read_only=True,
            orders_sent=False,
            live_orders_sent=False,
            windows=rows,
            summary={
                "window_count": len(rows),
                "accepted_windows": accepted,
                "acceptance_rate_pct": _percent(Decimal(accepted), Decimal(len(rows))) if rows else Decimal("0"),
                "min_window_trades": self.settings.backtest.min_window_trades,
            },
        )

    def bias_check(
        self,
        strategy_name: str | None = None,
        symbol: str | None = None,
        exchange: str | None = None,
        bar: str | None = None,
        limit: int | None = None,
    ) -> BiasCheckReport:
        """Return deterministic no-lookahead and completed-candle diagnostics."""
        target_strategy = strategy_name or self.settings.backtest.strategy
        target_symbol = symbol or self.settings.backtest.symbol
        target_exchange = exchange or self.settings.backtest.exchange
        target_bar = bar or self.settings.backtest.bar
        candles = self._completed_candles(target_exchange, target_symbol, target_bar, limit)
        checks = [
            _check("completed_candles_only", all(candle.complete for candle in candles), {"candle_count": len(candles)}),
            _check("warmup_window_enforced", len(candles) >= 31, {"minimum_candles": 31, "candle_count": len(candles)}),
            self._prefix_replay_check(target_strategy, target_symbol, target_exchange, candles),
        ]
        reasons = [str(check["name"]) for check in checks if not bool(check["passed"])]
        return BiasCheckReport(
            strategy_name=target_strategy,
            symbol=target_symbol,
            exchange=target_exchange,
            bar=target_bar,
            read_only=True,
            orders_sent=False,
            live_orders_sent=False,
            passed=not reasons,
            checks=checks,
            reasons=reasons,
        )

    def _completed_candles(self, exchange: str, symbol: str, bar: str, limit: int | None) -> list[Candle]:
        """Return completed candles ordered oldest to newest."""
        adapter = self.exchanges.get(exchange)
        candle_limit = limit or self.settings.backtest.candles_limit
        return [candle for candle in adapter.get_candles(symbol, bar=bar, limit=candle_limit) if candle.complete]

    def _directional_backtest(
        self,
        strategy_name: str,
        symbol: str,
        exchange: str,
        candles: list[Candle],
    ) -> DirectionalBacktestResult | None:
        """Run directional strategy backtests for supported strategy names."""
        try:
            strategy_for_name(strategy_name)
        except ValueError:
            return None
        return DirectionalBacktestEngine(
            notional_usdt=self.settings.directional.max_position_value_usdt,
            fee_pct=self.settings.backtest.fee_pct,
            slippage_pct=self.settings.backtest.slippage_pct,
        ).run(strategy_name, symbol, exchange, candles)

    def _fill_model(self) -> dict[str, object]:
        """Return the local simulation assumptions."""
        return {
            "completed_candles_only": True,
            "entry_price": "next_bar_open_plus_slippage",
            "exit_price": "barrier_or_close_minus_slippage",
            "fee_pct": self.settings.backtest.fee_pct,
            "slippage_pct": self.settings.backtest.slippage_pct,
            "partial_fills": "not_modeled",
            "orders_sent": False,
            "live_orders_sent": False,
        }

    def _prefix_replay_check(
        self,
        strategy_name: str,
        symbol: str,
        exchange: str,
        candles: list[Candle],
    ) -> dict[str, object]:
        """Check deterministic signal replay over historical prefixes."""
        try:
            strategy = strategy_for_name(strategy_name)
        except ValueError:
            return _check("prefix_replay_stable", False, {"reason": "unsupported_strategy"})
        replayed = 0
        for end in range(31, len(candles) + 1):
            prefix = candles[:end]
            first = strategy.generate_signal(prefix, symbol=symbol, exchange=exchange)
            second = strategy.generate_signal(prefix, symbol=symbol, exchange=exchange)
            if (
                first.signal != second.signal
                or first.confidence != second.confidence
                or first.expected_edge_pct != second.expected_edge_pct
                or first.stop_loss_pct != second.stop_loss_pct
                or first.take_profit_pct != second.take_profit_pct
                or first.time_limit_minutes != second.time_limit_minutes
                or first.reason_codes != second.reason_codes
            ):
                return _check("prefix_replay_stable", False, {"prefix_end": end})
            replayed += 1
        return _check("prefix_replay_stable", replayed > 0, {"prefixes_replayed": replayed})


def _walk_forward_segments(candle_count: int, windows: int) -> list[tuple[int, int]]:
    """Return expanding train end and validation end indexes."""
    if candle_count <= 0:
        return []
    window_count = max(windows, 1)
    segment = max(candle_count // (window_count + 1), 1)
    segments: list[tuple[int, int]] = []
    for index in range(window_count):
        train_end = min(segment * (index + 1), candle_count)
        validation_end = min(segment * (index + 2), candle_count)
        if validation_end <= train_end:
            break
        segments.append((train_end, validation_end))
    return segments


def _window_reasons(result: DirectionalBacktestResult | None, min_trades: int) -> list[str]:
    """Return walk-forward rejection reasons."""
    if result is None:
        return ["unsupported_strategy"]
    reasons: list[str] = []
    if result.total_trades < min_trades:
        reasons.append(f"validation_trades_below_minimum:{result.total_trades}<{min_trades}")
    return reasons


def _check(name: str, passed: bool, details: dict[str, object]) -> dict[str, object]:
    """Return a bias-check row."""
    return {"name": name, "passed": passed, "details": details}


def _percent(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Return a quantized percentage."""
    if denominator == 0:
        return Decimal("0")
    return ((numerator / denominator) * Decimal("100")).quantize(Decimal("0.01"))
