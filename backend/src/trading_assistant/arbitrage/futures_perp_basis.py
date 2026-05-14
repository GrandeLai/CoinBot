"""Dated-futures versus perpetual basis scanner."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

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
from trading_assistant.exceptions import ExchangeError


class FuturesPerpBasisScanner:
    """Scan spot/perp/dated-futures basis opportunities."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def scan(self, symbol: str, exchange_name: str = "mock") -> list[ArbitrageOpportunity]:
        """Return basis opportunities or an empty list when futures data is unavailable."""
        estimate = self.diagnose(symbol, exchange_name)
        if not bool(estimate.get("approved", False)):
            return []
        exchange = self.exchanges.get(exchange_name)
        quote = exchange.get_futures_basis_quote(symbol)
        capital = Decimal(str(estimate["capital_usdt"]))
        quantity = Decimal(str(estimate["quantity"]))
        gross_profit = Decimal(str(estimate["gross_profit_usdt"]))
        fees = Decimal(str(estimate["estimated_fee_usdt"]))
        slippage = Decimal(str(estimate["estimated_slippage_usdt"]))
        net_profit = Decimal(str(estimate["net_profit_usdt"]))
        net_profit_pct = Decimal(str(estimate["net_profit_pct"]))
        return [
            ArbitrageOpportunity(
                opportunity_id=f"futures-perp-basis-{exchange.name}-{quote.symbol.lower().replace('/', '-')}",
                strategy_type="futures-perp-basis",
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
                confidence=Decimal("0.66"),
                metadata={
                    "futures_perp_basis": Decimal(str(estimate["futures_perp_basis"])),
                    "basis_profit_usdt": Decimal(str(estimate["basis_profit_usdt"])),
                    "futures_expiry": quote.futures_expiry,
                    "days_to_expiry": estimate.get("days_to_expiry"),
                    "funding_rate": quote.funding_rate,
                    "funding_carry": estimate["funding_carry"],
                    "diagnostics": estimate,
                    "legs": [
                        {
                            "exchange": exchange.name,
                            "side": "buy",
                            "market": "swap",
                            "symbol": quote.symbol,
                            "price": quote.perp_ask,
                            "quantity": quantity,
                        },
                        {
                            "exchange": exchange.name,
                            "side": "sell",
                            "market": "futures",
                            "symbol": quote.symbol,
                            "price": quote.futures_bid,
                            "quantity": quantity,
                        },
                    ],
                },
            )
        ]

    def diagnose(self, symbol: str, exchange_name: str = "mock") -> dict[str, Any]:
        """Return basis diagnostics even when no opportunity passes filters."""
        exchange = self.exchanges.get(exchange_name)
        try:
            quote = exchange.get_futures_basis_quote(symbol)
        except ExchangeError:
            return {
                "strategy_type": "futures-perp-basis",
                "symbol": symbol,
                "exchange": exchange.name,
                "approved": False,
                "reasons": ["futures_basis_data_unavailable"],
            }
        if quote.futures_expiry is not None:
            days_to_expiry = (quote.futures_expiry - datetime.now(tz=UTC)).days
            if days_to_expiry < self.settings.arbitrage.futures_basis_min_days_to_expiry:
                return {
                    "strategy_type": "futures-perp-basis",
                    "symbol": symbol,
                    "exchange": exchange.name,
                    "approved": False,
                    "reasons": ["futures_expiry_too_near"],
                    "days_to_expiry": days_to_expiry,
                    "min_days_to_expiry": self.settings.arbitrage.futures_basis_min_days_to_expiry,
                }
        else:
            days_to_expiry = None
        capital = self.settings.arbitrage.trade_size_usdt
        quantity = capital / quote.perp_ask
        futures_perp_basis = quote.futures_bid - quote.perp_ask
        futures_perp_basis_pct = percent(futures_perp_basis, quote.perp_ask)
        basis_profit = futures_perp_basis * quantity
        carry = calculate_funding_carry(
            capital=capital,
            funding_rate=quote.funding_rate,
            holding_hours=self.settings.arbitrage.basis_holding_hours,
            settlement_interval_hours=self.settings.arbitrage.funding_settlement_interval_hours,
            hedge_cost_pct=self.settings.arbitrage.funding_hedge_cost_pct,
        )
        fees = (
            calculate_tiered_fee(
                capital,
                maker_fee_pct=self.settings.arbitrage.maker_fee_pct,
                taker_fee_pct=self.settings.arbitrage.taker_fee_pct,
                maker_ratio=self.settings.arbitrage.maker_ratio,
            )
            * Decimal("2")
        )
        slippage = calculate_slippage(capital, self.settings.arbitrage.slippage_pct, legs=2)
        gross_profit = basis_profit + carry.projected_funding_usdt
        net_profit = gross_profit - fees - slippage - carry.holding_cost_usdt
        net_profit_pct = percent(net_profit, capital)
        min_required = capital * self.settings.arbitrage.min_net_profit_pct / Decimal("100")
        reasons: list[str] = []
        if futures_perp_basis_pct < self.settings.arbitrage.futures_basis_min_basis_pct:
            reasons.append("futures_basis_below_minimum")
        if carry.annualized_pct < self.settings.arbitrage.funding_min_annualized_pct:
            reasons.append("funding_annualized_below_minimum")
        if net_profit_pct < self.settings.arbitrage.min_net_profit_pct:
            reasons.append("net_profit_below_minimum")
        return {
            "strategy_type": "futures-perp-basis",
            "symbol": quote.symbol,
            "exchange": exchange.name,
            "approved": not reasons,
            "reasons": reasons,
            "capital_usdt": capital,
            "quantity": quantity,
            "gross_profit_usdt": gross_profit,
            "futures_perp_basis": futures_perp_basis,
            "futures_perp_basis_pct": futures_perp_basis_pct,
            "min_futures_basis_pct": self.settings.arbitrage.futures_basis_min_basis_pct,
            "basis_profit_usdt": basis_profit,
            "futures_expiry": quote.futures_expiry,
            "days_to_expiry": days_to_expiry,
            "funding_rate": quote.funding_rate,
            "min_funding_annualized_pct": self.settings.arbitrage.funding_min_annualized_pct,
            "funding_carry": {
                "projected_funding_usdt": carry.projected_funding_usdt,
                "holding_cost_usdt": carry.holding_cost_usdt,
                "net_carry_usdt": carry.net_carry_usdt,
                "annualized_pct": carry.annualized_pct,
            },
            "estimated_fee_usdt": fees,
            "estimated_slippage_usdt": slippage,
            "net_profit_usdt": net_profit,
            "net_profit_pct": net_profit_pct,
            "min_required_net_profit_usdt": min_required,
            "break_even_gap_usdt": max(min_required - net_profit, Decimal("0")),
        }
