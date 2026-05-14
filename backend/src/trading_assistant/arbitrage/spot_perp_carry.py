"""Spot-perpetual carry scanner."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from trading_assistant.arbitrage.calculator import (
    calculate_funding_carry,
    calculate_risk_score,
    calculate_slippage,
    calculate_tiered_fee,
    has_sufficient_depth,
    percent,
)
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.factory import ExchangeFactory


class SpotPerpCarryScanner:
    """Find market-neutral spot-long/perp-short carry opportunities."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def scan(self, symbol: str, exchange_name: str = "mock") -> list[ArbitrageOpportunity]:
        """Return carry opportunities with explicit open and close conditions."""
        estimate = self._estimate(symbol, exchange_name)
        if estimate is None or not bool(estimate["approved"]):
            return []
        exchange = self.exchanges.get(exchange_name)
        quote = exchange.get_spot_perp_quote(symbol)
        quantity = Decimal(str(estimate["quantity"]))
        capital = Decimal(str(estimate["capital_usdt"]))
        gross_profit = Decimal(str(estimate["gross_profit_usdt"]))
        fees = Decimal(str(estimate["estimated_fee_usdt"]))
        slippage = Decimal(str(estimate["estimated_slippage_usdt"]))
        net_profit = Decimal(str(estimate["net_profit_usdt"]))
        net_profit_pct = Decimal(str(estimate["net_profit_pct"]))
        depth = Decimal(str(estimate["depth_usdt"]))
        return [
            ArbitrageOpportunity(
                opportunity_id=f"spot-perp-carry-{exchange.name}-{quote.symbol.lower().replace('/', '-')}",
                strategy_type="spot-perp-carry",
                symbol=quote.symbol,
                buy_exchange=exchange.name,
                sell_exchange=exchange.name,
                expected_profit=gross_profit,
                expected_profit_pct=percent(gross_profit, capital),
                estimated_fee=fees,
                estimated_slippage=slippage,
                required_capital=capital,
                net_profit=net_profit,
                risk_score=calculate_risk_score(net_profit_pct, self.settings.arbitrage.slippage_pct, depth),
                confidence=Decimal("0.73"),
                metadata={
                    "basis": quote.perp_bid - quote.spot_ask,
                    "basis_profit_usdt": Decimal(str(estimate["basis_profit_usdt"])),
                    "funding_rate": quote.funding_rate,
                    "funding_carry": estimate["funding_carry"],
                    "close_conditions": {
                        "basis_reverts_to_usdt": "0",
                        "funding_rate_below": "0",
                        "risk_or_drawdown_triggered": True,
                    },
                    "diagnostics": estimate,
                    "legs": [
                        {
                            "exchange": exchange.name,
                            "side": "buy",
                            "market": "spot",
                            "symbol": quote.symbol,
                            "price": quote.spot_ask,
                            "quantity": quantity,
                        },
                        {
                            "exchange": exchange.name,
                            "side": "sell",
                            "market": "swap",
                            "symbol": quote.symbol,
                            "price": quote.perp_bid,
                            "quantity": quantity,
                        },
                    ],
                },
            )
        ]

    def diagnose(self, symbol: str, exchange_name: str = "mock") -> dict[str, Any]:
        """Return a scan diagnostic even when no opportunity passes filters."""
        estimate = self._estimate(symbol, exchange_name)
        if estimate is None:
            return {"strategy_type": "spot-perp-carry", "symbol": symbol, "exchange": exchange_name, "approved": False, "reasons": ["quote_unavailable"]}
        return estimate

    def _estimate(self, symbol: str, exchange_name: str) -> dict[str, Any] | None:
        """Estimate spot-perp carry economics before filtering."""
        exchange = self.exchanges.get(exchange_name)
        quote = exchange.get_spot_perp_quote(symbol)
        orderbook = exchange.get_orderbook(symbol)
        capital = self.settings.arbitrage.trade_size_usdt
        quantity = capital / quote.spot_ask
        basis = quote.perp_bid - quote.spot_ask
        basis_pct = percent(basis, quote.spot_ask)
        basis_profit = (quote.perp_bid - quote.spot_ask) * quantity
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
        depth = orderbook.depth_notional("ask")
        min_required = capital * self.settings.arbitrage.min_net_profit_pct / Decimal("100")
        reasons: list[str] = []
        if basis_pct < self.settings.arbitrage.spot_perp_min_basis_pct:
            reasons.append("basis_below_minimum")
        if carry.annualized_pct < self.settings.arbitrage.funding_min_annualized_pct:
            reasons.append("funding_annualized_below_minimum")
        if net_profit_pct < self.settings.arbitrage.min_net_profit_pct:
            reasons.append("net_profit_below_minimum")
        if not has_sufficient_depth(orderbook, "ask", capital):
            reasons.append("insufficient_depth")
        return {
            "strategy_type": "spot-perp-carry",
            "symbol": quote.symbol,
            "exchange": exchange.name,
            "approved": not reasons,
            "reasons": reasons,
            "capital_usdt": capital,
            "quantity": quantity,
            "gross_profit_usdt": gross_profit,
            "basis": basis,
            "basis_pct": basis_pct,
            "min_basis_pct": self.settings.arbitrage.spot_perp_min_basis_pct,
            "basis_profit_usdt": basis_profit,
            "funding_rate": quote.funding_rate,
            "min_funding_annualized_pct": self.settings.arbitrage.funding_min_annualized_pct,
            "funding_carry": {
                "projected_funding_usdt": carry.projected_funding_usdt,
                "holding_cost_usdt": carry.holding_cost_usdt,
                "net_carry_usdt": carry.net_carry_usdt,
                "annualized_pct": carry.annualized_pct,
                "holding_hours": self.settings.arbitrage.basis_holding_hours,
            },
            "estimated_fee_usdt": fees,
            "estimated_slippage_usdt": slippage,
            "net_profit_usdt": net_profit,
            "net_profit_pct": net_profit_pct,
            "min_required_net_profit_usdt": min_required,
            "break_even_gap_usdt": max(min_required - net_profit, Decimal("0")),
            "depth_usdt": depth,
            "depth_required_usdt": capital,
            "depth_sufficient": has_sufficient_depth(orderbook, "ask", capital),
        }
