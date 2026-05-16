"""Read-only market universe and regime routing services."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.base import Candle
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.utils.serialization import to_jsonable


MarketRegime = Literal["trend", "range", "carry", "avoid", "illiquid"]


@dataclass(frozen=True)
class UniverseSymbolReport:
    """Read-only liquidity and regime report for one symbol."""

    symbol: str
    accepted: bool
    regime: MarketRegime
    reasons: list[str]
    spread_pct: Decimal
    bid_depth_usdt: Decimal
    ask_depth_usdt: Decimal
    volume_24h_usdt: Decimal
    return_pct: Decimal
    volatility_pct: Decimal

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyUniverseReport:
    """Read-only universe report for one exchange."""

    exchange: str
    read_only: bool
    orders_sent: bool
    live_orders_sent: bool
    accepted_symbols: list[str]
    rejected_symbols: list[str]
    symbols: list[UniverseSymbolReport]

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


class StrategyUniverseService:
    """Score symbols and classify market regimes without sending orders."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def report(self, exchange: str = "mock") -> StrategyUniverseReport:
        """Return a read-only universe report for configured symbols."""
        rows = [self.symbol_report(exchange=exchange, symbol=symbol) for symbol in self._symbols(exchange)]
        return StrategyUniverseReport(
            exchange=exchange,
            read_only=True,
            orders_sent=False,
            live_orders_sent=False,
            accepted_symbols=[row.symbol for row in rows if row.accepted],
            rejected_symbols=[row.symbol for row in rows if not row.accepted],
            symbols=rows,
        )

    def symbol_report(self, *, exchange: str = "mock", symbol: str) -> UniverseSymbolReport:
        """Return liquidity and regime evidence for one symbol."""
        adapter = self.exchanges.get(exchange)
        try:
            ticker = adapter.get_ticker(symbol)
            orderbook = adapter.get_orderbook(symbol)
            candles = adapter.get_candles(
                ticker.symbol,
                bar=self.settings.universe.bar,
                limit=self.settings.universe.candles_limit,
            )
        except Exception as exc:
            return UniverseSymbolReport(
                symbol=symbol,
                accepted=False,
                regime="avoid",
                reasons=[f"market_data_error:{_compact_error(exc)}"],
                spread_pct=Decimal("0"),
                bid_depth_usdt=Decimal("0"),
                ask_depth_usdt=Decimal("0"),
                volume_24h_usdt=Decimal("0"),
                return_pct=Decimal("0"),
                volatility_pct=Decimal("0"),
            )

        mid = (ticker.bid + ticker.ask) / Decimal("2")
        spread_pct = _pct(ticker.ask - ticker.bid, mid)
        bid_depth = max(orderbook.depth_notional("bid"), Decimal("0"))
        ask_depth = max(orderbook.depth_notional("ask"), Decimal("0"))
        depth = min(bid_depth, ask_depth)
        volume_24h = ticker.volume * ticker.last
        completed = [candle for candle in candles if candle.complete]
        return_pct = _return_pct(completed)
        volatility = _average_abs_return_pct(completed)
        reasons: list[str] = []
        if spread_pct > self.settings.universe.max_spread_pct:
            reasons.append("spread_above_maximum")
        if volume_24h < self.settings.universe.min_24h_volume_usdt:
            reasons.append("volume_below_minimum")
        if depth < self.settings.universe.min_depth_usdt:
            reasons.append("depth_below_minimum")
        accepted = not reasons
        regime = _classify_regime(
            accepted=accepted,
            reasons=reasons,
            return_pct=return_pct,
            volatility_pct=volatility,
            trend_threshold=self.settings.universe.trend_return_threshold_pct,
            range_threshold=self.settings.universe.range_volatility_max_pct,
        )
        return UniverseSymbolReport(
            symbol=ticker.symbol,
            accepted=accepted,
            regime=regime,
            reasons=reasons,
            spread_pct=spread_pct,
            bid_depth_usdt=bid_depth,
            ask_depth_usdt=ask_depth,
            volume_24h_usdt=volume_24h,
            return_pct=return_pct,
            volatility_pct=volatility,
        )

    def _symbols(self, exchange: str) -> list[str]:
        configured = list(self.settings.universe.symbols)
        if configured:
            return configured
        return self.exchanges.get(exchange).list_symbols()


def _classify_regime(
    *,
    accepted: bool,
    reasons: list[str],
    return_pct: Decimal,
    volatility_pct: Decimal,
    trend_threshold: Decimal,
    range_threshold: Decimal,
) -> MarketRegime:
    """Classify a symbol into a coarse trading regime."""
    if not accepted:
        if any(reason in reasons for reason in ("spread_above_maximum", "volume_below_minimum", "depth_below_minimum")):
            return "illiquid"
        return "avoid"
    if abs(return_pct) >= trend_threshold:
        return "trend"
    if volatility_pct <= range_threshold:
        return "range"
    return "carry"


def _return_pct(candles: list[Candle]) -> Decimal:
    """Return percent move from first to last completed candle."""
    if len(candles) < 2:
        return Decimal("0")
    return _pct(candles[-1].close - candles[0].close, candles[0].close)


def _average_abs_return_pct(candles: list[Candle]) -> Decimal:
    """Return average absolute close-to-close percent move."""
    if len(candles) < 2:
        return Decimal("0")
    moves = [
        abs(_pct(candles[index].close - candles[index - 1].close, candles[index - 1].close))
        for index in range(1, len(candles))
    ]
    return sum(moves, Decimal("0")) / Decimal(len(moves))


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Return a Decimal percentage, guarding division by zero."""
    if denominator == 0:
        return Decimal("0")
    return (numerator / denominator) * Decimal("100")


def _compact_error(exc: Exception) -> str:
    """Return a bounded one-line error."""
    return f"{exc.__class__.__name__}: {exc}".replace("\n", " ")[:180]
