"""OKX-first long-only spot directional strategy implementations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trading_assistant.directional.indicators import (
    atr,
    bollinger_bands,
    donchian_channel,
    ema,
    percent_return,
    rsi,
    volatility_pct,
    zscore,
)
from trading_assistant.directional.models import DirectionalSignal
from trading_assistant.exchanges.base import Candle, OrderBook


MAINSTREAM_SPOT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT", "ADA/USDT"]


@dataclass(frozen=True)
class DirectionalStrategyContext:
    """Input bundle for a directional strategy."""

    symbol: str
    exchange: str
    candles: list[Candle]
    orderbook: OrderBook | None = None


class BaseDirectionalStrategy:
    """Base contract for directional signal generators."""

    name = "directional"
    stop_loss_pct = Decimal("0.80")
    take_profit_pct = Decimal("1.60")
    time_limit_minutes = 90

    def generate_signal(self, candles: list[Candle], symbol: str, exchange: str, orderbook: OrderBook | None = None) -> DirectionalSignal:
        """Generate a directional signal."""
        raise NotImplementedError

    def _signal(
        self,
        symbol: str,
        exchange: str,
        signal: str,
        confidence: Decimal,
        expected_edge_pct: Decimal,
        reason_codes: list[str],
    ) -> DirectionalSignal:
        return DirectionalSignal(
            strategy_name=self.name,
            symbol=symbol,
            exchange=exchange,
            signal=signal,  # type: ignore[arg-type]
            confidence=max(Decimal("0"), min(confidence, Decimal("1"))),
            expected_edge_pct=max(expected_edge_pct, Decimal("0")),
            stop_loss_pct=self.stop_loss_pct,
            take_profit_pct=self.take_profit_pct,
            time_limit_minutes=self.time_limit_minutes,
            reason_codes=reason_codes,
        )


class TrendBreakoutStrategy(BaseDirectionalStrategy):
    """Multi-period EMA trend and Donchian breakout strategy."""

    name = "trend-breakout"
    stop_loss_pct = Decimal("0.85")
    take_profit_pct = Decimal("1.90")
    time_limit_minutes = 120

    def generate_signal(self, candles: list[Candle], symbol: str, exchange: str, orderbook: OrderBook | None = None) -> DirectionalSignal:
        completed, ignored = _completed_candles(candles)
        if len(completed) < 35:
            return self._signal(symbol, exchange, "hold", Decimal("0.1"), Decimal("0"), ["insufficient_candles", *ignored])
        closes = [candle.close for candle in completed]
        fast = ema(closes, 12)
        slow = ema(closes, 26)
        highs, lows = donchian_channel(completed, 20)
        volumes = [candle.volume for candle in completed]
        previous_high = highs[-2]
        previous_low = lows[-2]
        latest = completed[-1]
        average_volume = sum(volumes[-21:-1], Decimal("0")) / Decimal(20)
        reasons = list(ignored)
        if latest.close > previous_high and fast[-1] > slow[-1] and latest.volume > average_volume * Decimal("1.05"):
            reasons.extend(["ema_trend", "donchian_breakout", "volume_confirmation"])
            edge = min(percent_return(previous_high, latest.close) + Decimal("0.90"), Decimal("3.00"))
            return self._signal(symbol, exchange, "buy", Decimal("0.76"), edge, reasons)
        if latest.close < fast[-1] or latest.close < previous_low:
            reasons.extend(["trend_exit"])
            return self._signal(symbol, exchange, "sell", Decimal("0.58"), Decimal("0"), reasons)
        return self._signal(symbol, exchange, "hold", Decimal("0.35"), Decimal("0"), [*reasons, "no_breakout"])


class MeanReversionSpotStrategy(BaseDirectionalStrategy):
    """Oversold spot rebound strategy with trend filter."""

    name = "mean-reversion-spot"
    stop_loss_pct = Decimal("1.10")
    take_profit_pct = Decimal("1.70")
    time_limit_minutes = 180

    def generate_signal(self, candles: list[Candle], symbol: str, exchange: str, orderbook: OrderBook | None = None) -> DirectionalSignal:
        completed, ignored = _completed_candles(candles)
        if len(completed) < 35:
            return self._signal(symbol, exchange, "hold", Decimal("0.1"), Decimal("0"), ["insufficient_candles", *ignored])
        closes = [candle.close for candle in completed]
        latest = completed[-1]
        latest_rsi = rsi(closes, 14)[-1]
        middle, _upper, lower, _bandwidth = bollinger_bands(closes, 20)
        trend = ema(closes, 50)
        not_deep_downtrend = latest.close > trend[-1] * Decimal("0.965")
        reasons = list(ignored)
        if latest_rsi < Decimal("38") and latest.close <= lower[-1] * Decimal("1.01") and not_deep_downtrend:
            reasons.extend(["rsi_oversold", "bollinger_lower_reclaim", "higher_timeframe_filter"])
            return self._signal(symbol, exchange, "buy", Decimal("0.64"), Decimal("1.25"), reasons)
        if latest_rsi > Decimal("62") or latest.close >= middle[-1]:
            reasons.append("mean_reversion_exit")
            return self._signal(symbol, exchange, "sell", Decimal("0.55"), Decimal("0"), reasons)
        return self._signal(symbol, exchange, "hold", Decimal("0.30"), Decimal("0"), [*reasons, "no_oversold_edge"])


class VolatilitySqueezeBreakoutStrategy(BaseDirectionalStrategy):
    """Volatility compression followed by confirmed breakout."""

    name = "volatility-squeeze-breakout"
    stop_loss_pct = Decimal("0.95")
    take_profit_pct = Decimal("2.20")
    time_limit_minutes = 120

    def generate_signal(self, candles: list[Candle], symbol: str, exchange: str, orderbook: OrderBook | None = None) -> DirectionalSignal:
        completed, ignored = _completed_candles(candles)
        if len(completed) < 45:
            return self._signal(symbol, exchange, "hold", Decimal("0.1"), Decimal("0"), ["insufficient_candles", *ignored])
        closes = [candle.close for candle in completed]
        latest = completed[-1]
        previous = completed[-2]
        _middle, upper, _lower, bandwidth = bollinger_bands(closes, 20)
        ranges = atr(completed, 14)
        volumes = [candle.volume for candle in completed]
        previous_bandwidth_avg = sum(bandwidth[-25:-5], Decimal("0")) / Decimal(20)
        squeeze = bandwidth[-2] < previous_bandwidth_avg * Decimal("0.75")
        range_expansion = ranges[-1] > ranges[-5] * Decimal("1.10")
        volume_expansion = zscore(latest.volume, volumes[-31:-1]) > Decimal("0.5")
        reasons = list(ignored)
        if squeeze and latest.close > max(upper[-2], previous.high) and range_expansion and volume_expansion:
            reasons.extend(["bollinger_squeeze", "breakout_confirmed", "atr_expansion", "volume_expansion"])
            return self._signal(symbol, exchange, "buy", Decimal("0.70"), Decimal("1.65"), reasons)
        return self._signal(symbol, exchange, "hold", Decimal("0.32"), Decimal("0"), [*reasons, "no_squeeze_breakout"])


class MomentumRotationStrategy(BaseDirectionalStrategy):
    """Single-symbol view of cross-sectional mainstream-coin momentum."""

    name = "momentum-rotation"
    stop_loss_pct = Decimal("1.20")
    take_profit_pct = Decimal("2.40")
    time_limit_minutes = 240

    def generate_signal(self, candles: list[Candle], symbol: str, exchange: str, orderbook: OrderBook | None = None) -> DirectionalSignal:
        completed, ignored = _completed_candles(candles)
        if len(completed) < 40:
            return self._signal(symbol, exchange, "hold", Decimal("0.1"), Decimal("0"), ["insufficient_candles", *ignored])
        closes = [candle.close for candle in completed]
        recent_return = percent_return(closes[-24], closes[-1])
        medium_return = percent_return(closes[-40], closes[-1])
        realized_volatility = volatility_pct(closes[-40:])
        if recent_return > Decimal("0.75") and medium_return > Decimal("1.25") and realized_volatility < Decimal("1.50"):
            confidence = min(Decimal("0.60") + recent_return / Decimal("20"), Decimal("0.82"))
            edge = min(recent_return / Decimal("2") + Decimal("0.80"), Decimal("3.20"))
            return self._signal(symbol, exchange, "buy", confidence, edge, [*ignored, "relative_momentum", "volatility_control"])
        return self._signal(symbol, exchange, "hold", Decimal("0.28"), Decimal("0"), [*ignored, "momentum_rank_not_selected"])


class OrderbookImbalanceScalpStrategy(BaseDirectionalStrategy):
    """Short-horizon orderbook imbalance scanner; demo disabled by default."""

    name = "orderbook-imbalance-scalp"
    stop_loss_pct = Decimal("0.35")
    take_profit_pct = Decimal("0.55")
    time_limit_minutes = 20

    def generate_signal(self, candles: list[Candle], symbol: str, exchange: str, orderbook: OrderBook | None = None) -> DirectionalSignal:
        if orderbook is None:
            return self._signal(symbol, exchange, "hold", Decimal("0.15"), Decimal("0"), ["missing_orderbook"])
        bid_depth = orderbook.depth_notional("bid", levels=3)
        ask_depth = orderbook.depth_notional("ask", levels=3)
        total_depth = bid_depth + ask_depth
        spread_pct = ((orderbook.best_ask.price - orderbook.best_bid.price) / orderbook.best_bid.price * Decimal("100")) if orderbook.best_bid.price else Decimal("100")
        imbalance = bid_depth / total_depth if total_depth else Decimal("0")
        if imbalance > Decimal("0.62") and spread_pct < Decimal("0.04"):
            return self._signal(symbol, exchange, "buy", Decimal("0.54"), Decimal("0.65"), ["bid_depth_imbalance", "tight_spread"])
        return self._signal(symbol, exchange, "hold", Decimal("0.22"), Decimal("0"), ["no_orderbook_edge"])


def strategy_for_name(name: str) -> BaseDirectionalStrategy:
    """Return a directional strategy implementation by name."""
    strategies: dict[str, BaseDirectionalStrategy] = {
        "trend-breakout": TrendBreakoutStrategy(),
        "mean-reversion-spot": MeanReversionSpotStrategy(),
        "volatility-squeeze-breakout": VolatilitySqueezeBreakoutStrategy(),
        "momentum-rotation": MomentumRotationStrategy(),
        "orderbook-imbalance-scalp": OrderbookImbalanceScalpStrategy(),
    }
    return strategies[name]


def _completed_candles(candles: list[Candle]) -> tuple[list[Candle], list[str]]:
    completed = [candle for candle in candles if candle.complete]
    ignored = ["incomplete_candle_ignored"] if len(completed) != len(candles) else []
    return completed, ignored
