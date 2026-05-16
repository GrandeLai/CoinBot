"""Unified arbitrage scanner facade."""

from __future__ import annotations

from typing import Any

from trading_assistant.arbitrage.cross_exchange import CrossExchangeScanner
from trading_assistant.arbitrage.funding_carry_hedged import FundingCarryHedgedScanner
from trading_assistant.arbitrage.funding_rate import FundingRateScanner
from trading_assistant.arbitrage.futures_perp_basis import FuturesPerpBasisScanner
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.arbitrage.spot_perp import SpotPerpScanner
from trading_assistant.arbitrage.spot_perp_carry import SpotPerpCarryScanner
from trading_assistant.arbitrage.triangular import TriangularScanner
from trading_assistant.arbitrage.triangular_multi_route import TriangularMultiRouteScanner
from trading_assistant.config.schema import Settings
from trading_assistant.directional.scanner import DIRECTIONAL_STRATEGY_TYPES, DirectionalOpportunityScanner
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.exceptions import ConfigError
from trading_assistant.strategies.hedged_maker import HedgedMakerStrategyService
from trading_assistant.strategies.range_grid import RangeGridStrategyService


class ArbitrageScanner:
    """Dispatch to a concrete arbitrage scanner."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def scan(
        self,
        strategy_type: str,
        symbol: str | None = None,
        exchange: str | None = None,
        route_mode: str = "configured",
    ) -> list[ArbitrageOpportunity]:
        """Scan one arbitrage type."""
        if strategy_type in DIRECTIONAL_STRATEGY_TYPES:
            opportunities, _diagnostics = DirectionalOpportunityScanner(self.settings, self.exchanges).scan(
                strategy_type,
                symbol=symbol or self.settings.directional.symbols[0],
                exchange=exchange,
            )
            return opportunities
        match strategy_type:
            case "cross-exchange":
                return CrossExchangeScanner(self.settings, self.exchanges).scan(symbol or self.settings.arbitrage.symbols[0])
            case "triangular":
                return TriangularScanner(self.settings, self.exchanges).scan(exchange or "mock")
            case "triangular-multi-route":
                return TriangularMultiRouteScanner(self.settings, self.exchanges).scan(exchange or "mock", route_mode=route_mode)
            case "funding-rate":
                return FundingRateScanner(self.settings, self.exchanges).scan()
            case "funding-carry-hedged":
                return FundingCarryHedgedScanner(self.settings, self.exchanges).scan(exchange or "mock")
            case "spot-perp":
                return SpotPerpScanner(self.settings, self.exchanges).scan(symbol or self.settings.arbitrage.symbols[0])
            case "spot-perp-carry":
                return SpotPerpCarryScanner(self.settings, self.exchanges).scan(symbol or self.settings.arbitrage.symbols[0], exchange or "mock")
            case "futures-perp-basis":
                return FuturesPerpBasisScanner(self.settings, self.exchanges).scan(symbol or self.settings.arbitrage.symbols[0], exchange or "mock")
            case "range-grid":
                return RangeGridStrategyService(self.settings, self.exchanges).scan(symbol or self.settings.range_grid.symbols[0], exchange=exchange)
            case "hedged-maker":
                return HedgedMakerStrategyService(self.settings, self.exchanges).scan(
                    symbol or self.settings.hedged_maker.symbols[0],
                    maker_exchange=exchange,
                )
            case _:
                raise ConfigError(f"Unsupported arbitrage type: {strategy_type}")

    def diagnose(self, strategy_type: str, symbol: str | None = None, exchange: str | None = None) -> dict[str, Any]:
        """Return scanner diagnostics for strategies that support explainable filtering."""
        if strategy_type in DIRECTIONAL_STRATEGY_TYPES:
            _opportunities, diagnostics = DirectionalOpportunityScanner(self.settings, self.exchanges).scan(
                strategy_type,
                symbol=symbol or self.settings.directional.symbols[0],
                exchange=exchange,
            )
            return diagnostics
        match strategy_type:
            case "funding-carry-hedged":
                return FundingCarryHedgedScanner(self.settings, self.exchanges).diagnose(exchange or "mock")
            case "spot-perp-carry":
                return SpotPerpCarryScanner(self.settings, self.exchanges).diagnose(symbol or self.settings.arbitrage.symbols[0], exchange or "mock")
            case "futures-perp-basis":
                return FuturesPerpBasisScanner(self.settings, self.exchanges).diagnose(symbol or self.settings.arbitrage.symbols[0], exchange or "mock")
            case "range-grid":
                return RangeGridStrategyService(self.settings, self.exchanges).diagnose(symbol or self.settings.range_grid.symbols[0], exchange=exchange)
            case "hedged-maker":
                return HedgedMakerStrategyService(self.settings, self.exchanges).diagnose(
                    symbol or self.settings.hedged_maker.symbols[0],
                    maker_exchange=exchange,
                )
            case _:
                return {}
