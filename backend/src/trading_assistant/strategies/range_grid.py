"""Paper-only range-grid strategy scanner."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from trading_assistant.arbitrage.calculator import calculate_risk_score, percent
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.base import Candle
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.strategies.universe import StrategyUniverseService
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class RangeGridEstimate:
    """Read-only grid estimate."""

    approved: bool
    reasons: list[str]
    symbol: str
    exchange: str
    regime: str
    lower_price: Decimal
    upper_price: Decimal
    current_price: Decimal
    grid_levels: list[Decimal]
    spacing_pct: Decimal
    level_notional_usdt: Decimal
    completed_grid_cycles: int
    gross_profit_usdt: Decimal
    estimated_fee_usdt: Decimal
    estimated_slippage_usdt: Decimal
    net_profit_usdt: Decimal
    net_profit_pct: Decimal
    range_width_pct: Decimal
    depth_usdt: Decimal

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


class RangeGridStrategyService:
    """Build range-grid opportunities for paper validation only."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def scan(self, symbol: str = "BTC/USDT", exchange: str | None = None) -> list[ArbitrageOpportunity]:
        """Return range-grid paper opportunities."""
        target_exchange = exchange or self.settings.range_grid.exchange
        estimate = self._estimate(symbol=symbol, exchange=target_exchange)
        if not estimate.approved:
            return []
        return [self._opportunity(estimate)]

    def diagnose(self, symbol: str = "BTC/USDT", exchange: str | None = None) -> dict[str, Any]:
        """Return diagnostics even when no opportunity passes filters."""
        target_exchange = exchange or self.settings.range_grid.exchange
        return self._estimate(symbol=symbol, exchange=target_exchange).to_dict()

    def _estimate(self, *, symbol: str, exchange: str) -> RangeGridEstimate:
        adapter = self.exchanges.get(exchange)
        universe = StrategyUniverseService(self.settings, self.exchanges).symbol_report(exchange=exchange, symbol=symbol)
        ticker = adapter.get_ticker(symbol)
        orderbook = adapter.get_orderbook(symbol)
        candles = [
            candle
            for candle in adapter.get_candles(
                symbol,
                bar=self.settings.universe.bar,
                limit=max(self.settings.range_grid.lookback_candles, self.settings.universe.candles_limit),
            )
            if candle.complete
        ][-self.settings.range_grid.lookback_candles :]
        lower, upper = _bounds(candles, ticker.last)
        levels = _grid_levels(lower, upper, self.settings.range_grid.grid_levels)
        spacing_pct = _spacing_pct(levels)
        range_width_pct = percent(upper - lower, ticker.last)
        level_notional = self.settings.range_grid.total_quote_usdt / Decimal(self.settings.range_grid.grid_levels)
        completed_cycles = _completed_cycles(levels, ticker.last)
        gross_profit = level_notional * Decimal(completed_cycles) * spacing_pct / Decimal("100")
        fees = level_notional * Decimal(completed_cycles) * self.settings.range_grid.fee_pct * Decimal("2")
        slippage = level_notional * Decimal(completed_cycles) * self.settings.range_grid.slippage_pct * Decimal("2")
        net_profit = gross_profit - fees - slippage
        net_profit_pct = percent(net_profit, self.settings.range_grid.total_quote_usdt)
        depth = max(min(orderbook.depth_notional("bid"), orderbook.depth_notional("ask")), Decimal("0"))
        reasons = _reasons(
            enabled=self.settings.range_grid.enabled,
            regime=universe.regime,
            spacing_pct=spacing_pct,
            min_spacing_pct=self.settings.range_grid.min_grid_spacing_pct,
            range_width_pct=range_width_pct,
            max_range_width_pct=self.settings.range_grid.max_range_width_pct,
            completed_cycles=completed_cycles,
            net_profit=net_profit,
        )
        return RangeGridEstimate(
            approved=not reasons,
            reasons=reasons,
            symbol=ticker.symbol,
            exchange=exchange,
            regime=universe.regime,
            lower_price=lower,
            upper_price=upper,
            current_price=ticker.last,
            grid_levels=levels,
            spacing_pct=spacing_pct,
            level_notional_usdt=level_notional,
            completed_grid_cycles=completed_cycles,
            gross_profit_usdt=gross_profit,
            estimated_fee_usdt=fees,
            estimated_slippage_usdt=slippage,
            net_profit_usdt=net_profit,
            net_profit_pct=net_profit_pct,
            range_width_pct=range_width_pct,
            depth_usdt=depth,
        )

    def _opportunity(self, estimate: RangeGridEstimate) -> ArbitrageOpportunity:
        quantity = estimate.level_notional_usdt / estimate.current_price if estimate.current_price > 0 else Decimal("0")
        return ArbitrageOpportunity(
            opportunity_id=f"range-grid-{estimate.exchange}-{estimate.symbol.lower().replace('/', '-')}",
            strategy_type="range-grid",
            symbol=estimate.symbol,
            buy_exchange=estimate.exchange,
            sell_exchange=estimate.exchange,
            expected_profit=estimate.gross_profit_usdt,
            expected_profit_pct=percent(estimate.gross_profit_usdt, self.settings.range_grid.total_quote_usdt),
            estimated_fee=estimate.estimated_fee_usdt,
            estimated_slippage=estimate.estimated_slippage_usdt,
            required_capital=self.settings.range_grid.total_quote_usdt,
            net_profit=estimate.net_profit_usdt,
            risk_score=calculate_risk_score(estimate.net_profit_pct, self.settings.range_grid.slippage_pct, estimate.depth_usdt),
            confidence=Decimal("0.58"),
            metadata={
                "read_only": True,
                "paper_only": True,
                "demo_supported": False,
                "live_supported": False,
                "regime": estimate.regime,
                "grid_levels": estimate.grid_levels,
                "spacing_pct": estimate.spacing_pct,
                "range_width_pct": estimate.range_width_pct,
                "completed_grid_cycles": estimate.completed_grid_cycles,
                "level_notional_usdt": estimate.level_notional_usdt,
                "diagnostics": estimate.to_dict(),
                "legs": [
                    {
                        "exchange": estimate.exchange,
                        "symbol": estimate.symbol,
                        "side": "buy",
                        "market": "spot",
                        "price": estimate.current_price,
                        "quantity": quantity,
                        "notional_usdt": estimate.level_notional_usdt,
                    },
                    {
                        "exchange": estimate.exchange,
                        "symbol": estimate.symbol,
                        "side": "sell",
                        "market": "spot",
                        "price": estimate.current_price * (Decimal("1") + estimate.spacing_pct / Decimal("100")),
                        "quantity": quantity,
                        "notional_usdt": estimate.level_notional_usdt,
                    },
                ],
                "quantity": quantity,
            },
        )


def _bounds(candles: list[Candle], fallback: Decimal) -> tuple[Decimal, Decimal]:
    """Return grid lower/upper bounds."""
    if not candles:
        return fallback * Decimal("0.99"), fallback * Decimal("1.01")
    lower = min(candle.low for candle in candles)
    upper = max(candle.high for candle in candles)
    if lower <= 0 or upper <= lower:
        return fallback * Decimal("0.99"), fallback * Decimal("1.01")
    return lower, upper


def _grid_levels(lower: Decimal, upper: Decimal, levels: int) -> list[Decimal]:
    """Return evenly spaced grid levels."""
    if levels <= 1:
        return [lower, upper]
    step = (upper - lower) / Decimal(levels - 1)
    return [lower + step * Decimal(index) for index in range(levels)]


def _spacing_pct(levels: list[Decimal]) -> Decimal:
    """Return average adjacent grid spacing as a percent."""
    if len(levels) < 2:
        return Decimal("0")
    spacings = [percent(levels[index] - levels[index - 1], levels[index - 1]) for index in range(1, len(levels)) if levels[index - 1] > 0]
    if not spacings:
        return Decimal("0")
    return sum(spacings, Decimal("0")) / Decimal(len(spacings))


def _completed_cycles(levels: list[Decimal], current_price: Decimal) -> int:
    """Estimate how many lower grid levels can complete a round trip."""
    if len(levels) < 2:
        return 0
    lower_levels = [level for level in levels[:-1] if level < current_price]
    upper_room = [level for level in levels[1:] if level > current_price]
    return max(0, min(len(lower_levels), len(upper_room)))


def _reasons(
    *,
    enabled: bool,
    regime: str,
    spacing_pct: Decimal,
    min_spacing_pct: Decimal,
    range_width_pct: Decimal,
    max_range_width_pct: Decimal,
    completed_cycles: int,
    net_profit: Decimal,
) -> list[str]:
    """Return range-grid filter reason codes."""
    reasons: list[str] = []
    if not enabled:
        reasons.append("range_grid_disabled")
    if regime != "range":
        reasons.append("regime_not_range")
    if spacing_pct < min_spacing_pct:
        reasons.append("grid_spacing_below_minimum")
    if range_width_pct > max_range_width_pct:
        reasons.append("range_width_above_maximum")
    if completed_cycles <= 0:
        reasons.append("no_completed_grid_cycles")
    if net_profit <= 0:
        reasons.append("net_profit_after_costs_not_positive")
    return reasons
