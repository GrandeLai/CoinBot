"""Triangular arbitrage scanner for one exchange."""

from __future__ import annotations

from decimal import Decimal

from trading_assistant.arbitrage.calculator import calculate_fee, calculate_risk_score, calculate_slippage, percent
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.factory import ExchangeFactory


class TriangularScanner:
    """Scan a deterministic USDT -> BTC -> ETH -> USDT route."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def scan(self, exchange_name: str = "mock") -> list[ArbitrageOpportunity]:
        """Return profitable triangular route when mock prices support it."""
        exchange = self.exchanges.get(exchange_name)
        capital = self.settings.arbitrage.trade_size_usdt
        btc_usdt = exchange.get_ticker("BTC/USDT")
        eth_btc = exchange.get_ticker("ETH/BTC")
        eth_usdt = exchange.get_ticker("ETH/USDT")
        btc_amount = capital / btc_usdt.ask
        eth_amount = btc_amount / eth_btc.ask
        final_usdt = eth_amount * eth_usdt.bid
        gross_profit = final_usdt - capital
        fees = calculate_fee(capital, self.settings.arbitrage.fee_pct, legs=3)
        slippage = calculate_slippage(capital, self.settings.arbitrage.slippage_pct, legs=3)
        net_profit = gross_profit - fees - slippage
        net_profit_pct = percent(net_profit, capital)
        if net_profit_pct < self.settings.arbitrage.min_net_profit_pct:
            return []
        return [
            ArbitrageOpportunity(
                opportunity_id="triangular-mock-btc-eth-usdt",
                strategy_type="triangular",
                symbol="BTC/ETH/USDT",
                buy_exchange=exchange.name,
                sell_exchange=exchange.name,
                expected_profit=gross_profit,
                expected_profit_pct=percent(gross_profit, capital),
                estimated_fee=fees,
                estimated_slippage=slippage,
                required_capital=capital,
                net_profit=net_profit,
                risk_score=calculate_risk_score(net_profit_pct, self.settings.arbitrage.slippage_pct, Decimal("100000")),
                confidence=Decimal("0.76"),
                metadata={
                    "quantity": btc_amount,
                    "route": ["USDT", "BTC", "ETH", "USDT"],
                    "final_usdt": final_usdt,
                    "legs": [
                        {"exchange": exchange.name, "side": "buy", "symbol": "BTC/USDT", "price": btc_usdt.ask, "quantity": btc_amount},
                        {"exchange": exchange.name, "side": "buy", "symbol": "ETH/BTC", "price": eth_btc.ask, "quantity": eth_amount},
                        {"exchange": exchange.name, "side": "sell", "symbol": "ETH/USDT", "price": eth_usdt.bid, "quantity": eth_amount},
                    ],
                },
            )
        ]
