"""Hedged funding-carry scanner."""

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
from trading_assistant.exceptions import ExchangeError


class FundingCarryHedgedScanner:
    """Rank positive swap funding opportunities with a spot hedge check."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def scan(self, exchange_name: str = "mock") -> list[ArbitrageOpportunity]:
        """Return hedged funding opportunities that pass net-profit and depth checks."""
        exchange = self.exchanges.get(exchange_name)
        opportunities: list[ArbitrageOpportunity] = []
        for estimate in self.diagnose(exchange_name).get("candidates", []):
            if not bool(estimate.get("approved", False)):
                continue
            funding_symbol = str(estimate["symbol"])
            quote = exchange.get_spot_perp_quote(funding_symbol)
            capital = Decimal(str(estimate["capital_usdt"]))
            quantity = Decimal(str(estimate["quantity"]))
            gross_profit = Decimal(str(estimate["gross_profit_usdt"]))
            fees = Decimal(str(estimate["estimated_fee_usdt"]))
            slippage = Decimal(str(estimate["estimated_slippage_usdt"]))
            net_profit = Decimal(str(estimate["net_profit_usdt"]))
            net_profit_pct = Decimal(str(estimate["net_profit_pct"]))
            depth = Decimal(str(estimate["depth_usdt"]))
            opportunities.append(
                ArbitrageOpportunity(
                    opportunity_id=f"funding-carry-hedged-{exchange.name}-{funding_symbol.lower().replace('/', '-')}",
                    strategy_type="funding-carry-hedged",
                    symbol=funding_symbol,
                    buy_exchange=exchange.name,
                    sell_exchange=exchange.name,
                    expected_profit=gross_profit,
                    expected_profit_pct=percent(gross_profit, capital),
                    estimated_fee=fees,
                    estimated_slippage=slippage,
                    required_capital=capital,
                    net_profit=net_profit,
                    risk_score=calculate_risk_score(net_profit_pct, self.settings.arbitrage.slippage_pct, depth),
                    confidence=Decimal("0.70"),
                    metadata={
                        "funding_rate": Decimal(str(estimate["funding_rate"])),
                        "next_funding_time": estimate.get("next_funding_time"),
                        "basis_hedge_cost_usdt": Decimal(str(estimate["basis_hedge_cost_usdt"])),
                        "funding_carry": estimate["funding_carry"],
                        "diagnostics": estimate,
                        "legs": [
                            {
                                "exchange": exchange.name,
                                "side": "buy",
                                "market": "spot",
                                "symbol": funding_symbol,
                                "price": quote.spot_ask,
                                "quantity": quantity,
                            },
                            {
                                "exchange": exchange.name,
                                "side": "sell",
                                "market": "swap",
                                "symbol": funding_symbol,
                                "price": quote.perp_bid,
                                "quantity": quantity,
                            },
                        ],
                    },
                )
            )
        return sorted(opportunities, key=lambda item: item.net_profit, reverse=True)

    def diagnose(self, exchange_name: str = "mock") -> dict[str, Any]:
        """Return candidate diagnostics for all funding rates, including filtered ones."""
        exchange = self.exchanges.get(exchange_name)
        capital = self.settings.arbitrage.trade_size_usdt
        candidates: list[dict[str, Any]] = []
        for funding in exchange.get_funding_rates():
            try:
                quote = exchange.get_spot_perp_quote(funding.symbol)
                orderbook = exchange.get_orderbook(funding.symbol)
            except ExchangeError:
                continue
            carry = calculate_funding_carry(
                capital=capital,
                funding_rate=funding.funding_rate,
                holding_hours=self.settings.arbitrage.funding_holding_hours,
                settlement_interval_hours=self.settings.arbitrage.funding_settlement_interval_hours,
                hedge_cost_pct=self.settings.arbitrage.funding_hedge_cost_pct,
            )
            quantity = capital / quote.spot_ask
            basis_cost = max(quote.perp_ask - quote.spot_bid, Decimal("0")) * (capital / quote.spot_bid) * Decimal("0.05")
            basis_hedge_cost_pct = percent(basis_cost, capital)
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
            gross_profit = carry.projected_funding_usdt
            net_profit = gross_profit - fees - slippage - carry.holding_cost_usdt - basis_cost
            net_profit_pct = percent(net_profit, capital)
            depth = orderbook.depth_notional("ask")
            min_required = capital * self.settings.arbitrage.min_net_profit_pct / Decimal("100")
            reasons: list[str] = []
            if carry.annualized_pct < self.settings.arbitrage.funding_min_annualized_pct:
                reasons.append("funding_annualized_below_minimum")
            if basis_hedge_cost_pct > self.settings.arbitrage.funding_max_basis_hedge_cost_pct:
                reasons.append("basis_hedge_cost_above_maximum")
            if net_profit_pct < self.settings.arbitrage.min_net_profit_pct:
                reasons.append("net_profit_below_minimum")
            if not has_sufficient_depth(orderbook, "ask", capital):
                reasons.append("insufficient_depth")
            candidates.append(
                {
                    "strategy_type": "funding-carry-hedged",
                    "symbol": funding.symbol,
                    "exchange": exchange.name,
                    "approved": not reasons,
                    "reasons": reasons,
                    "capital_usdt": capital,
                    "quantity": quantity,
                    "gross_profit_usdt": gross_profit,
                    "funding_rate": funding.funding_rate,
                    "min_funding_annualized_pct": self.settings.arbitrage.funding_min_annualized_pct,
                    "next_funding_time": funding.next_funding_time,
                    "basis_hedge_cost_usdt": basis_cost,
                    "basis_hedge_cost_pct": basis_hedge_cost_pct,
                    "max_basis_hedge_cost_pct": self.settings.arbitrage.funding_max_basis_hedge_cost_pct,
                    "funding_carry": {
                        "projected_funding_usdt": carry.projected_funding_usdt,
                        "holding_cost_usdt": carry.holding_cost_usdt,
                        "net_carry_usdt": carry.net_carry_usdt,
                        "annualized_pct": carry.annualized_pct,
                        "holding_hours": self.settings.arbitrage.funding_holding_hours,
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
            )
        return {
            "strategy_type": "funding-carry-hedged",
            "exchange": exchange.name,
            "candidate_count": len(candidates),
            "approved_count": sum(1 for item in candidates if item["approved"]),
            "best_candidate": max(candidates, key=lambda item: Decimal(str(item["net_profit_usdt"])), default=None),
            "candidates": sorted(candidates, key=lambda item: Decimal(str(item["net_profit_usdt"])), reverse=True),
        }
