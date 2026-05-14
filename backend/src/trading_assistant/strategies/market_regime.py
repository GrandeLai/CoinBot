"""Candle-derived market-regime tagging for strategy evolution."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Any

from trading_assistant.config.schema import Settings
from trading_assistant.directional.indicators import ema, percent_return, volatility_pct
from trading_assistant.exchanges.base import Candle
from trading_assistant.exchanges.factory import ExchangeFactory


def classify_candle_regime(candles: list[Candle]) -> dict[str, Any]:
    """Classify a completed-candle series into a coarse market regime."""
    completed = [candle for candle in candles if candle.complete]
    ignored = len(candles) - len(completed)
    if len(completed) < 30:
        return {
            "tag": "unknown",
            "source": "candles",
            "completed_candles": len(completed),
            "ignored_incomplete_candles": ignored,
            "recent_return_pct": "0",
            "medium_return_pct": "0",
            "volatility_pct": "0",
            "ema_slope_pct": "0",
            "reasons": ["insufficient_completed_candles"],
        }
    closes = [candle.close for candle in completed]
    recent_window = min(24, len(closes) - 1)
    medium_window = min(60, len(closes) - 1)
    volatility_window = min(40, len(closes))
    recent_return = percent_return(closes[-recent_window - 1], closes[-1])
    medium_return = percent_return(closes[-medium_window - 1], closes[-1])
    realized_volatility = volatility_pct(closes[-volatility_window:])
    ema_values = ema(closes, 20)
    ema_slope = percent_return(ema_values[-10], ema_values[-1]) if len(ema_values) >= 10 else Decimal("0")
    tag = "unknown"
    reasons: list[str] = []
    if realized_volatility >= Decimal("2.50"):
        tag = "high_volatility"
        reasons.append("volatility_above_threshold")
    elif medium_return >= Decimal("1.00") and ema_slope >= Decimal("0.10"):
        tag = "trend_up"
        reasons.extend(["positive_medium_return", "ema_slope_up"])
    elif medium_return <= Decimal("-1.00") and ema_slope <= Decimal("-0.10"):
        tag = "trend_down"
        reasons.extend(["negative_medium_return", "ema_slope_down"])
    elif abs(medium_return) <= Decimal("0.75") and realized_volatility <= Decimal("1.00"):
        tag = "range"
        reasons.extend(["low_medium_return", "low_volatility"])
    else:
        reasons.append("mixed_features")
    return {
        "tag": tag,
        "source": "candles",
        "completed_candles": len(completed),
        "ignored_incomplete_candles": ignored,
        "recent_return_pct": recent_return.quantize(Decimal("0.0001")),
        "medium_return_pct": medium_return.quantize(Decimal("0.0001")),
        "volatility_pct": realized_volatility.quantize(Decimal("0.0001")),
        "ema_slope_pct": ema_slope.quantize(Decimal("0.0001")),
        "reasons": reasons,
    }


class StrategyMarketRegimeService:
    """Build a market-regime snapshot from completed exchange candles."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def snapshot(self, symbol: str | None = None, exchange: str | None = None, limit: int | None = None) -> dict[str, Any]:
        """Return regime tags for configured symbols using completed candles."""
        target_exchange = exchange or self._default_exchange()
        symbols = [symbol] if symbol else list(self.settings.directional.symbols)
        candle_limit = limit or self.settings.directional.candles_limit
        per_symbol: dict[str, dict[str, Any]] = {}
        errors: dict[str, str] = {}
        for item in symbols:
            try:
                candles = self.exchanges.get(target_exchange).get_candles(
                    item,
                    bar=self.settings.directional.bar,
                    limit=candle_limit,
                )
                per_symbol[item] = classify_candle_regime(candles)
            except Exception as exc:  # pragma: no cover - defensive per-symbol isolation
                errors[item] = f"{exc.__class__.__name__}: {exc}"
        tag_counts = Counter(str(row.get("tag", "unknown")) for row in per_symbol.values())
        dominant = tag_counts.most_common(1)[0][0] if tag_counts else "unknown"
        return {
            "tag": dominant,
            "source": "candles" if per_symbol else "none",
            "exchange": target_exchange,
            "bar": self.settings.directional.bar,
            "symbol_count": len(per_symbol),
            "sample_count": sum(int(row.get("completed_candles", 0)) for row in per_symbol.values()),
            "tag_counts": dict(tag_counts),
            "volatility": _dominant_volatility(per_symbol),
            "strategy_tags": {},
            "symbols": per_symbol,
            "errors": errors,
        }

    def _default_exchange(self) -> str:
        enabled = set(self.exchanges.list_enabled())
        if self.settings.directional.exchange in enabled:
            return self.settings.directional.exchange
        if "mock" in enabled:
            return "mock"
        return next(iter(enabled), "mock")


def _dominant_volatility(per_symbol: dict[str, dict[str, Any]]) -> str:
    labels = []
    for row in per_symbol.values():
        volatility = Decimal(str(row.get("volatility_pct", "0")))
        if volatility >= Decimal("2.50"):
            labels.append("high")
        elif volatility <= Decimal("1.00"):
            labels.append("low")
        else:
            labels.append("normal")
    counts = Counter(labels)
    return counts.most_common(1)[0][0] if counts else "unknown"
