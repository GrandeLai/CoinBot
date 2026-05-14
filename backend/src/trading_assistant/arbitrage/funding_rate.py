"""Funding-rate arbitrage scanner."""

from __future__ import annotations

from decimal import Decimal

from trading_assistant.arbitrage.calculator import (
    calculate_funding_carry,
    calculate_risk_score,
    calculate_slippage,
    calculate_tiered_fee,
    percent,
)
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.factory import ExchangeFactory


class FundingRateScanner:
    """Find positive funding carry opportunities."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def scan(self) -> list[ArbitrageOpportunity]:
        """Scan configured mock exchanges for positive funding."""
        exchange = self.exchanges.get("mock")
        opportunities: list[ArbitrageOpportunity] = []
        capital = self.settings.arbitrage.trade_size_usdt
        for funding in exchange.get_funding_rates():
            carry = calculate_funding_carry(
                capital=capital,
                funding_rate=funding.funding_rate,
                holding_hours=self.settings.arbitrage.funding_holding_hours,
                settlement_interval_hours=self.settings.arbitrage.funding_settlement_interval_hours,
                hedge_cost_pct=self.settings.arbitrage.funding_hedge_cost_pct,
            )
            gross_profit = carry.projected_funding_usdt
            fees = calculate_tiered_fee(
                capital,
                maker_fee_pct=self.settings.arbitrage.maker_fee_pct,
                taker_fee_pct=self.settings.arbitrage.taker_fee_pct,
                maker_ratio=self.settings.arbitrage.maker_ratio,
            ) * Decimal("2")
            slippage = calculate_slippage(capital, self.settings.arbitrage.slippage_pct, legs=2)
            net_profit = gross_profit - fees - slippage - carry.holding_cost_usdt
            net_profit_pct = percent(net_profit, capital)
            expected_pct = funding.funding_rate * Decimal("100")
            opportunities.append(
                ArbitrageOpportunity(
                    opportunity_id=f"funding-{funding.symbol.lower().replace('/', '-')}",
                    strategy_type="funding-rate",
                    symbol=funding.symbol,
                    buy_exchange=exchange.name,
                    sell_exchange=exchange.name,
                    expected_profit=gross_profit,
                    expected_profit_pct=expected_pct,
                    estimated_fee=fees,
                    estimated_slippage=slippage,
                    required_capital=capital,
                    net_profit=net_profit,
                    risk_score=calculate_risk_score(max(net_profit_pct, Decimal("0")), self.settings.arbitrage.slippage_pct, Decimal("100000")),
                    confidence=Decimal("0.65"),
                    metadata={
                        "funding_rate": funding.funding_rate,
                        "next_funding_time": funding.next_funding_time,
                        "funding_carry": {
                            "projected_funding_usdt": carry.projected_funding_usdt,
                            "holding_cost_usdt": carry.holding_cost_usdt,
                            "net_carry_usdt": carry.net_carry_usdt,
                            "annualized_pct": carry.annualized_pct,
                            "holding_hours": self.settings.arbitrage.funding_holding_hours,
                            "settlement_interval_hours": self.settings.arbitrage.funding_settlement_interval_hours,
                        },
                    },
                )
            )
        return opportunities
