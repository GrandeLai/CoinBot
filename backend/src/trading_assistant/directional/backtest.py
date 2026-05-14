"""Local backtesting for long-only spot directional strategies."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trading_assistant.directional.models import DirectionalBacktestResult
from trading_assistant.directional.strategies import strategy_for_name
from trading_assistant.exchanges.base import Candle


@dataclass
class _OpenTrade:
    entry_price: Decimal
    quantity: Decimal
    entry_index: int
    take_profit_price: Decimal
    stop_loss_price: Decimal
    time_limit_bars: int


class DirectionalBacktestEngine:
    """Backtest directional strategies using only completed historical candles."""

    def __init__(
        self,
        *,
        notional_usdt: Decimal = Decimal("100"),
        fee_pct: Decimal = Decimal("0.001"),
        slippage_pct: Decimal = Decimal("0.0005"),
    ) -> None:
        self.notional_usdt = notional_usdt
        self.fee_pct = fee_pct
        self.slippage_pct = slippage_pct

    def run(
        self,
        strategy_name: str,
        symbol: str,
        exchange: str,
        candles: list[Candle],
    ) -> DirectionalBacktestResult:
        """Run a no-lookahead long-only backtest."""
        completed = [candle for candle in candles if candle.complete]
        strategy = strategy_for_name(strategy_name)
        trade_pnls: list[Decimal] = []
        hold_bars: list[int] = []
        fees = Decimal("0")
        slippage = Decimal("0")
        equity = Decimal("0")
        peak = Decimal("0")
        max_drawdown = Decimal("0")
        open_trade: _OpenTrade | None = None
        start_index = 50 if len(completed) > 60 else 30
        for index in range(start_index, len(completed)):
            candle = completed[index]
            if open_trade is None:
                signal = strategy.generate_signal(completed[:index], symbol=symbol, exchange=exchange)
                if signal.signal != "buy":
                    continue
                entry_price = candle.open * (Decimal("1") + self.slippage_pct)
                quantity = self.notional_usdt / entry_price if entry_price else Decimal("0")
                open_trade = _OpenTrade(
                    entry_price=entry_price,
                    quantity=quantity,
                    entry_index=index,
                    take_profit_price=entry_price * (Decimal("1") + signal.take_profit_pct / Decimal("100")),
                    stop_loss_price=entry_price * (Decimal("1") - signal.stop_loss_pct / Decimal("100")),
                    time_limit_bars=max(signal.time_limit_minutes // 15, 1),
                )
                fees += self.notional_usdt * self.fee_pct
                slippage += self.notional_usdt * self.slippage_pct
                continue
            exit_price: Decimal | None = None
            if candle.low <= open_trade.stop_loss_price:
                exit_price = open_trade.stop_loss_price * (Decimal("1") - self.slippage_pct)
            elif candle.high >= open_trade.take_profit_price:
                exit_price = open_trade.take_profit_price * (Decimal("1") - self.slippage_pct)
            elif index - open_trade.entry_index >= open_trade.time_limit_bars:
                exit_price = candle.close * (Decimal("1") - self.slippage_pct)
            else:
                signal = strategy.generate_signal(completed[: index + 1], symbol=symbol, exchange=exchange)
                if signal.signal == "sell":
                    exit_price = candle.close * (Decimal("1") - self.slippage_pct)
            if exit_price is None:
                continue
            gross = (exit_price - open_trade.entry_price) * open_trade.quantity
            exit_notional = exit_price * open_trade.quantity
            exit_fee = exit_notional * self.fee_pct
            trade_pnl = gross - exit_fee
            fees += exit_fee
            slippage += exit_notional * self.slippage_pct
            trade_pnls.append(trade_pnl)
            hold_bars.append(index - open_trade.entry_index)
            equity += trade_pnl
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
            open_trade = None
        if open_trade is not None:
            final = completed[-1].close * (Decimal("1") - self.slippage_pct)
            gross = (final - open_trade.entry_price) * open_trade.quantity
            exit_notional = final * open_trade.quantity
            exit_fee = exit_notional * self.fee_pct
            trade_pnl = gross - exit_fee
            fees += exit_fee
            slippage += exit_notional * self.slippage_pct
            trade_pnls.append(trade_pnl)
            hold_bars.append(len(completed) - 1 - open_trade.entry_index)
            equity += trade_pnl
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
        return _result(strategy_name, symbol, exchange, trade_pnls, hold_bars, fees, slippage, max_drawdown, self.notional_usdt)


def _result(
    strategy_name: str,
    symbol: str,
    exchange: str,
    trade_pnls: list[Decimal],
    hold_bars: list[int],
    fees: Decimal,
    slippage: Decimal,
    max_drawdown: Decimal,
    notional: Decimal,
) -> DirectionalBacktestResult:
    wins = [pnl for pnl in trade_pnls if pnl > 0]
    losses = [pnl for pnl in trade_pnls if pnl <= 0]
    net = sum(trade_pnls, Decimal("0"))
    gross_wins = sum(wins, Decimal("0"))
    gross_losses = abs(sum(losses, Decimal("0")))
    profit_factor = Decimal("999") if gross_wins > 0 and gross_losses == 0 else (gross_wins / gross_losses if gross_losses else Decimal("0"))
    total = len(trade_pnls)
    win_rate = (Decimal(len(wins)) / Decimal(total) * Decimal("100")).quantize(Decimal("0.01")) if total else Decimal("0")
    expectancy = (net / Decimal(total)).quantize(Decimal("0.000001")) if total else Decimal("0")
    drawdown_pct = (max_drawdown / notional * Decimal("100")).quantize(Decimal("0.0001")) if notional else Decimal("0")
    avg_hold = (Decimal(sum(hold_bars)) * Decimal("15") / Decimal(len(hold_bars))).quantize(Decimal("0.01")) if hold_bars else Decimal("0")
    return DirectionalBacktestResult(
        strategy_name=strategy_name,
        symbol=symbol,
        exchange=exchange,
        total_trades=total,
        wins=len(wins),
        losses=len(losses),
        win_rate_pct=win_rate,
        profit_factor=profit_factor.quantize(Decimal("0.01")),
        expectancy_usdt=expectancy,
        max_drawdown_pct=drawdown_pct,
        average_hold_minutes=avg_hold,
        gross_pnl_usdt=(net + fees).quantize(Decimal("0.000001")),
        fees_usdt=fees.quantize(Decimal("0.000001")),
        slippage_usdt=slippage.quantize(Decimal("0.000001")),
        net_pnl_usdt=net.quantize(Decimal("0.000001")),
        account_equity_attribution={
            "strategy_pnl_usdt": net.quantize(Decimal("0.000001")),
            "account_mark_to_market_delta_usdt": Decimal("0"),
            "external_cashflow_gap_usdt": Decimal("0"),
        },
    )
