"""Lightweight Decimal-based indicators for spot directional strategies."""

from __future__ import annotations

from decimal import Decimal

from trading_assistant.exchanges.base import Candle


def ema(values: list[Decimal], period: int) -> list[Decimal]:
    """Return exponential moving average values."""
    if not values:
        return []
    alpha = Decimal("2") / Decimal(period + 1)
    result: list[Decimal] = []
    current = values[0]
    for value in values:
        current = value if not result else (value * alpha) + (current * (Decimal("1") - alpha))
        result.append(current)
    return result


def rsi(values: list[Decimal], period: int = 14) -> list[Decimal]:
    """Return RSI values using Wilder-style rolling averages."""
    if not values:
        return []
    result: list[Decimal] = [Decimal("50")]
    avg_gain = Decimal("0")
    avg_loss = Decimal("0")
    for index in range(1, len(values)):
        change = values[index] - values[index - 1]
        gain = max(change, Decimal("0"))
        loss = abs(min(change, Decimal("0")))
        if index <= period:
            avg_gain += gain / Decimal(period)
            avg_loss += loss / Decimal(period)
        else:
            avg_gain = ((avg_gain * Decimal(period - 1)) + gain) / Decimal(period)
            avg_loss = ((avg_loss * Decimal(period - 1)) + loss) / Decimal(period)
        if index < period:
            result.append(Decimal("50"))
        elif avg_loss == 0:
            result.append(Decimal("100"))
        else:
            rs = avg_gain / avg_loss
            result.append(Decimal("100") - (Decimal("100") / (Decimal("1") + rs)))
    return result


def atr(candles: list[Candle], period: int = 14) -> list[Decimal]:
    """Return average true range values."""
    if not candles:
        return []
    true_ranges: list[Decimal] = []
    for index, candle in enumerate(candles):
        if index == 0:
            true_ranges.append(candle.high - candle.low)
            continue
        previous_close = candles[index - 1].close
        true_ranges.append(max(candle.high - candle.low, abs(candle.high - previous_close), abs(candle.low - previous_close)))
    return simple_moving_average(true_ranges, period)


def bollinger_bands(values: list[Decimal], period: int = 20, stddev_multiplier: Decimal = Decimal("2")) -> tuple[list[Decimal], list[Decimal], list[Decimal], list[Decimal]]:
    """Return Bollinger middle, upper, lower, and bandwidth series."""
    middle = simple_moving_average(values, period)
    upper: list[Decimal] = []
    lower: list[Decimal] = []
    bandwidth: list[Decimal] = []
    for index, average in enumerate(middle):
        window = values[max(0, index - period + 1) : index + 1]
        deviation = _stddev(window)
        up = average + deviation * stddev_multiplier
        lo = average - deviation * stddev_multiplier
        upper.append(up)
        lower.append(lo)
        bandwidth.append(((up - lo) / average * Decimal("100")) if average else Decimal("0"))
    return middle, upper, lower, bandwidth


def donchian_channel(candles: list[Candle], period: int = 20) -> tuple[list[Decimal], list[Decimal]]:
    """Return Donchian high and low series."""
    highs: list[Decimal] = []
    lows: list[Decimal] = []
    for index, _ in enumerate(candles):
        window = candles[max(0, index - period + 1) : index + 1]
        highs.append(max(candle.high for candle in window))
        lows.append(min(candle.low for candle in window))
    return highs, lows


def simple_moving_average(values: list[Decimal], period: int) -> list[Decimal]:
    """Return simple moving average values."""
    result: list[Decimal] = []
    for index, _ in enumerate(values):
        window = values[max(0, index - period + 1) : index + 1]
        result.append(sum(window, Decimal("0")) / Decimal(len(window)))
    return result


def percent_return(first: Decimal, last: Decimal) -> Decimal:
    """Return percent return from first to last."""
    if first == 0:
        return Decimal("0")
    return ((last - first) / first) * Decimal("100")


def volatility_pct(values: list[Decimal]) -> Decimal:
    """Return close-to-close volatility as a percent standard deviation."""
    returns = [percent_return(values[index - 1], values[index]) for index in range(1, len(values)) if values[index - 1] != 0]
    return _stddev(returns)


def zscore(value: Decimal, values: list[Decimal]) -> Decimal:
    """Return z-score for one value against a sample."""
    if not values:
        return Decimal("0")
    deviation = _stddev(values)
    if deviation == 0:
        return Decimal("0")
    average = sum(values, Decimal("0")) / Decimal(len(values))
    return (value - average) / deviation


def _stddev(values: list[Decimal]) -> Decimal:
    if len(values) <= 1:
        return Decimal("0")
    average = sum(values, Decimal("0")) / Decimal(len(values))
    variance = sum(((value - average) ** 2 for value in values), Decimal("0")) / Decimal(len(values))
    return variance.sqrt()
