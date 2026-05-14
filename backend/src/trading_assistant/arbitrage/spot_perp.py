"""Spot-perpetual basis arbitrage scanner."""

from __future__ import annotations

from decimal import Decimal

from trading_assistant.arbitrage.calculator import calculate_fee, calculate_risk_score, calculate_slippage, percent
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.factory import ExchangeFactory


class SpotPerpScanner:
    """Find spot/perpetual basis opportunities."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def scan(self, symbol: str) -> list[ArbitrageOpportunity]:
        """Return spot-long/perp-short basis opportunity when positive."""
        exchange = self.exchanges.get("mock")
        quote = exchange.get_spot_perp_quote(symbol)
        capital = self.settings.arbitrage.trade_size_usdt
        quantity = capital / quote.spot_ask
        basis_profit = (quote.perp_bid - quote.spot_ask) * quantity
        funding_profit = capital * quote.funding_rate
        gross_profit = basis_profit + funding_profit
        fees = calculate_fee(capital, self.settings.arbitrage.fee_pct, legs=2)
        slippage = calculate_slippage(capital, self.settings.arbitrage.slippage_pct, legs=2)
        net_profit = gross_profit - fees - slippage
        net_profit_pct = percent(net_profit, capital)
        if net_profit_pct < self.settings.arbitrage.min_net_profit_pct:
            return []
        return [
            ArbitrageOpportunity(
                opportunity_id=f"spot-perp-{quote.symbol.lower().replace('/', '-')}",
                strategy_type="spot-perp",
                symbol=quote.symbol,
                buy_exchange=exchange.name,
                sell_exchange=exchange.name,
                expected_profit=gross_profit,
                expected_profit_pct=percent(gross_profit, capital),
                estimated_fee=fees,
                estimated_slippage=slippage,
                required_capital=capital,
                net_profit=net_profit,
                risk_score=calculate_risk_score(net_profit_pct, self.settings.arbitrage.slippage_pct, Decimal("100000")),
                confidence=Decimal("0.72"),
                metadata={
                    "spot_ask": quote.spot_ask,
                    "perp_bid": quote.perp_bid,
                    "funding_rate": quote.funding_rate,
                    "basis": quote.perp_bid - quote.spot_ask,
                    "legs": [
                        {"exchange": exchange.name, "side": "buy", "market": "spot", "symbol": quote.symbol, "price": quote.spot_ask},
                        {"exchange": exchange.name, "side": "sell", "market": "perp", "symbol": quote.symbol, "price": quote.perp_bid},
                    ],
                },
            )
        ]

