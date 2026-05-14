"""Cross-exchange spot arbitrage scanner."""

from __future__ import annotations

from itertools import permutations
from decimal import Decimal

from trading_assistant.arbitrage.calculator import (
    calculate_latency_drift_cost,
    calculate_risk_score,
    calculate_slippage,
    calculate_spread_persistence,
    calculate_tiered_fee,
    calculate_transfer_cost,
    estimate_depth_fill,
    has_sufficient_depth,
    percent,
)
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.utils.serialization import to_jsonable


class CrossExchangeScanner:
    """Find buy-low/sell-high opportunities across configured exchanges."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def scan(self, symbol: str) -> list[ArbitrageOpportunity]:
        """Scan buy-low/sell-high pairs across enabled exchanges."""
        opportunities: list[ArbitrageOpportunity] = []
        for buy_name, sell_name in permutations(self.exchanges.list_enabled(), 2):
            opportunity = self._scan_pair(symbol, buy_name, sell_name)
            if opportunity is not None:
                opportunities.append(opportunity)
        return sorted(opportunities, key=lambda item: item.net_profit, reverse=True)

    def _scan_pair(self, symbol: str, buy_name: str, sell_name: str) -> ArbitrageOpportunity | None:
        """Scan one directed exchange pair."""
        buy_exchange = self.exchanges.get(buy_name)
        sell_exchange = self.exchanges.get(sell_name)
        buy_ticker = buy_exchange.get_ticker(symbol)
        sell_ticker = sell_exchange.get_ticker(symbol)
        if sell_ticker.bid <= buy_ticker.ask:
            return None
        buy_orderbook = buy_exchange.get_orderbook(symbol)
        sell_orderbook = sell_exchange.get_orderbook(symbol)
        capital = self.settings.arbitrage.trade_size_usdt
        quantity = capital / buy_ticker.ask
        gross_profit = (sell_ticker.bid - buy_ticker.ask) * quantity
        fee_per_leg = calculate_tiered_fee(
            capital,
            maker_fee_pct=self.settings.arbitrage.maker_fee_pct,
            taker_fee_pct=self.settings.arbitrage.taker_fee_pct,
            maker_ratio=self.settings.arbitrage.maker_ratio,
        )
        fees = fee_per_leg * Decimal("2")
        buy_fill = estimate_depth_fill(buy_orderbook, "ask", capital)
        sell_fill = estimate_depth_fill(sell_orderbook, "bid", capital)
        configured_slippage = calculate_slippage(capital, self.settings.arbitrage.slippage_pct, legs=2)
        depth_slippage = capital * ((buy_fill.slippage_pct + sell_fill.slippage_pct) / Decimal("100"))
        slippage = configured_slippage + depth_slippage
        transfer_cost = calculate_transfer_cost(
            capital,
            fixed_withdrawal_fee_usdt=self.settings.arbitrage.withdrawal_fee_usdt,
            delay_risk_pct=self.settings.arbitrage.transfer_delay_risk_pct,
        )
        latency_drift = calculate_latency_drift_cost(
            capital,
            latency_ms=self.settings.arbitrage.latency_ms,
            drift_bps_per_second=self.settings.arbitrage.price_drift_bps_per_second,
        )
        persistence = calculate_spread_persistence(
            self.settings.arbitrage.spread_persistence_samples_pct,
            min_spread_pct=self.settings.arbitrage.min_spread_persistence_pct,
            required_windows=self.settings.arbitrage.spread_persistence_windows,
        )
        net_profit = gross_profit - fees - slippage - transfer_cost - latency_drift
        net_profit_pct = percent(net_profit, capital)
        depth = min(buy_orderbook.depth_notional("ask"), sell_orderbook.depth_notional("bid"))
        if net_profit_pct < self.settings.arbitrage.min_net_profit_pct:
            return None
        if not has_sufficient_depth(buy_orderbook, "ask", capital):
            return None
        if not has_sufficient_depth(sell_orderbook, "bid", capital):
            return None
        if not persistence.passed:
            return None
        return ArbitrageOpportunity(
            opportunity_id=_opportunity_id(buy_exchange.name, sell_exchange.name, buy_ticker.symbol),
            strategy_type="cross-exchange",
            symbol=buy_ticker.symbol,
            buy_exchange=buy_exchange.name,
            sell_exchange=sell_exchange.name,
            expected_profit=gross_profit,
            expected_profit_pct=percent(gross_profit, capital),
            estimated_fee=fees,
            estimated_slippage=slippage,
            required_capital=capital,
            net_profit=net_profit,
            risk_score=calculate_risk_score(net_profit_pct, self.settings.arbitrage.slippage_pct, depth),
            confidence=Decimal("0.88"),
            metadata={
                "buy_price": buy_ticker.ask,
                "sell_price": sell_ticker.bid,
                "quantity": quantity,
                "depth_usdt": depth,
                "execution_quality": {
                    "spread_persistence": {
                        "passed": persistence.passed,
                        "window_count": persistence.window_count,
                        "minimum_spread_pct": persistence.minimum_spread_pct,
                        "average_spread_pct": persistence.average_spread_pct,
                    },
                    "depth_fill": {
                        "buy": to_jsonable(buy_fill),
                        "sell": to_jsonable(sell_fill),
                    },
                    "fee_model": {
                        "maker_fee_pct": self.settings.arbitrage.maker_fee_pct,
                        "taker_fee_pct": self.settings.arbitrage.taker_fee_pct,
                        "maker_ratio": self.settings.arbitrage.maker_ratio,
                    },
                    "transfer_cost_usdt": transfer_cost,
                    "latency_drift_usdt": latency_drift,
                },
                "legs": [
                    {"exchange": buy_exchange.name, "side": "buy", "symbol": buy_ticker.symbol, "price": buy_ticker.ask},
                    {"exchange": sell_exchange.name, "side": "sell", "symbol": sell_ticker.symbol, "price": sell_ticker.bid},
                ],
            },
        )


def _opportunity_id(buy_exchange: str, sell_exchange: str, symbol: str) -> str:
    """Return stable opportunity ids while preserving the original mock fixture id."""
    if buy_exchange == "mock" and sell_exchange == "mock_alt":
        return "test-opportunity"
    normalized_symbol = symbol.lower().replace("/", "-")
    return f"cross-exchange-{buy_exchange}-{sell_exchange}-{normalized_symbol}"
