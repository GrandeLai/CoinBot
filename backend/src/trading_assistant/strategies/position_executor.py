"""Read-only triple-barrier position simulation and exit optimization."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.base import Candle
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class PositionExitResult:
    """Read-only simulated position exit result."""

    strategy_name: str
    symbol: str
    read_only: bool
    orders_sent: bool
    live_orders_sent: bool
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    bars_held: int
    exit_reason: str
    gross_pnl_usdt: Decimal
    fee_usdt: Decimal
    net_pnl_usdt: Decimal
    max_drawdown_usdt: Decimal
    take_profit_pct: Decimal
    stop_loss_pct: Decimal
    trailing_stop_pct: Decimal
    time_limit_bars: int

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class ExitParameterCandidate:
    """Ranked triple-barrier parameter proposal."""

    take_profit_pct: Decimal
    stop_loss_pct: Decimal
    trailing_stop_pct: Decimal
    time_limit_bars: int
    score: Decimal
    net_pnl_usdt: Decimal
    max_drawdown_usdt: Decimal
    exit_reason: str
    reasons: list[str]

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class ExitOptimizationReport:
    """Read-only exit optimization report."""

    strategy_name: str
    symbol: str
    exchange: str
    read_only: bool
    orders_sent: bool
    live_orders_sent: bool
    candidates: list[ExitParameterCandidate]
    best_position: PositionExitResult | None

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


class TripleBarrierPositionExecutor:
    """Simulate a long-only position using take-profit, stop-loss, trailing, and time barriers."""

    def simulate_long(
        self,
        *,
        strategy_name: str,
        symbol: str,
        entry_price: Decimal,
        quantity: Decimal,
        candles: list[Candle],
        take_profit_pct: Decimal,
        stop_loss_pct: Decimal,
        trailing_stop_pct: Decimal,
        time_limit_bars: int,
        fee_pct: Decimal,
    ) -> PositionExitResult:
        """Return a deterministic read-only long-position exit simulation."""
        completed = [candle for candle in candles if candle.complete]
        simulation_candles = completed[1:] if len(completed) > 1 else completed
        take_profit_price = entry_price * (Decimal("1") + take_profit_pct / Decimal("100"))
        stop_loss_price = entry_price * (Decimal("1") - stop_loss_pct / Decimal("100"))
        highest_price = entry_price
        worst_unrealized = Decimal("0")
        exit_price = entry_price
        exit_reason = "no_candles"
        bars_held = 0

        for index, candle in enumerate(simulation_candles, start=1):
            bars_held = index
            highest_price = max(highest_price, candle.high)
            worst_unrealized = min(worst_unrealized, (candle.low - entry_price) * quantity)
            trailing_price = highest_price * (Decimal("1") - trailing_stop_pct / Decimal("100"))
            if candle.low <= stop_loss_price:
                exit_price = stop_loss_price
                exit_reason = "stop_loss"
                break
            if candle.high >= take_profit_price:
                exit_price = take_profit_price
                exit_reason = "take_profit"
                break
            if trailing_stop_pct > 0 and highest_price > entry_price and candle.low <= trailing_price:
                exit_price = trailing_price
                exit_reason = "trailing_stop"
                break
            if index >= time_limit_bars:
                exit_price = candle.close
                exit_reason = "time_limit"
                break
        else:
            if simulation_candles:
                exit_price = simulation_candles[-1].close
                exit_reason = "end_of_data"

        gross_pnl = (exit_price - entry_price) * quantity
        fee = (entry_price * quantity + exit_price * quantity) * fee_pct
        net_pnl = gross_pnl - fee
        return PositionExitResult(
            strategy_name=strategy_name,
            symbol=symbol,
            read_only=True,
            orders_sent=False,
            live_orders_sent=False,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            bars_held=bars_held,
            exit_reason=exit_reason,
            gross_pnl_usdt=gross_pnl,
            fee_usdt=fee,
            net_pnl_usdt=net_pnl,
            max_drawdown_usdt=abs(worst_unrealized),
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct,
            trailing_stop_pct=trailing_stop_pct,
            time_limit_bars=time_limit_bars,
        )


class ExitOptimizerService:
    """Generate read-only triple-barrier exit proposals from recent candles."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges
        self.executor = TripleBarrierPositionExecutor()

    def optimize(self, strategy_name: str, symbol: str, exchange: str = "mock") -> ExitOptimizationReport:
        """Return ranked exit parameter candidates without changing config or sending orders."""
        candles = self._candles(exchange, symbol)
        candidates: list[tuple[ExitParameterCandidate, PositionExitResult]] = []
        if len(candles) < 2:
            return ExitOptimizationReport(
                strategy_name=strategy_name,
                symbol=symbol,
                exchange=exchange,
                read_only=True,
                orders_sent=False,
                live_orders_sent=False,
                candidates=[],
                best_position=None,
            )
        entry_price = candles[0].close
        quantity = _quantity_for_notional(self.settings.strategy_runtime.max_position_value_usdt, entry_price)
        for take_profit in self.settings.exit_optimization.take_profit_candidates_pct:
            for stop_loss in self.settings.exit_optimization.stop_loss_candidates_pct:
                for trailing_stop in self.settings.exit_optimization.trailing_stop_candidates_pct:
                    for time_limit in self.settings.exit_optimization.time_limit_candidates_bars:
                        position = self.executor.simulate_long(
                            strategy_name=strategy_name,
                            symbol=symbol,
                            entry_price=entry_price,
                            quantity=quantity,
                            candles=candles,
                            take_profit_pct=take_profit,
                            stop_loss_pct=stop_loss,
                            trailing_stop_pct=trailing_stop,
                            time_limit_bars=time_limit,
                            fee_pct=self.settings.directional.fee_pct,
                        )
                        score = position.net_pnl_usdt - (position.max_drawdown_usdt * Decimal("0.25"))
                        candidates.append(
                            (
                                ExitParameterCandidate(
                                    take_profit_pct=take_profit,
                                    stop_loss_pct=stop_loss,
                                    trailing_stop_pct=trailing_stop,
                                    time_limit_bars=time_limit,
                                    score=score,
                                    net_pnl_usdt=position.net_pnl_usdt,
                                    max_drawdown_usdt=position.max_drawdown_usdt,
                                    exit_reason=position.exit_reason,
                                    reasons=_candidate_reasons(position),
                                ),
                                position,
                            )
                        )
        candidates.sort(key=lambda item: item[0].score, reverse=True)
        top = candidates[: self.settings.exit_optimization.max_candidates]
        return ExitOptimizationReport(
            strategy_name=strategy_name,
            symbol=symbol,
            exchange=exchange,
            read_only=True,
            orders_sent=False,
            live_orders_sent=False,
            candidates=[candidate for candidate, _position in top],
            best_position=top[0][1] if top else None,
        )

    def position_report(self, strategy_name: str, symbol: str, exchange: str = "mock") -> PositionExitResult:
        """Return the best current read-only position simulation."""
        report = self.optimize(strategy_name=strategy_name, symbol=symbol, exchange=exchange)
        if report.best_position is not None:
            return report.best_position
        ticker = self.exchanges.get(exchange).get_ticker(symbol)
        return self.executor.simulate_long(
            strategy_name=strategy_name,
            symbol=ticker.symbol,
            entry_price=ticker.last,
            quantity=_quantity_for_notional(self.settings.strategy_runtime.max_position_value_usdt, ticker.last),
            candles=[],
            take_profit_pct=self.settings.exit_optimization.take_profit_candidates_pct[0],
            stop_loss_pct=self.settings.exit_optimization.stop_loss_candidates_pct[0],
            trailing_stop_pct=self.settings.exit_optimization.trailing_stop_candidates_pct[0],
            time_limit_bars=self.settings.exit_optimization.time_limit_candidates_bars[0],
            fee_pct=self.settings.directional.fee_pct,
        )

    def _candles(self, exchange: str, symbol: str) -> list[Candle]:
        adapter = self.exchanges.get(exchange)
        return [
            candle
            for candle in adapter.get_candles(
                symbol,
                bar=self.settings.universe.bar,
                limit=max(self.settings.universe.candles_limit, max(self.settings.exit_optimization.time_limit_candidates_bars) + 2),
            )
            if candle.complete
        ]


def _quantity_for_notional(notional: Decimal, price: Decimal) -> Decimal:
    """Return base quantity for a quote notional."""
    if price <= 0:
        return Decimal("0")
    return notional / price


def _candidate_reasons(position: PositionExitResult) -> list[str]:
    """Return compact explanation codes for a candidate."""
    reasons = [f"exit:{position.exit_reason}"]
    if position.net_pnl_usdt > 0:
        reasons.append("positive_net_pnl")
    else:
        reasons.append("non_positive_net_pnl")
    if position.max_drawdown_usdt > 0:
        reasons.append("drawdown_observed")
    return reasons
