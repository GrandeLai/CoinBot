"""Market data application service."""

from __future__ import annotations

from trading_assistant.exchanges.base import Candle, OrderBook, Ticker
from trading_assistant.exchanges.factory import ExchangeFactory


class MarketDataService:
    """Fetch market-data snapshots through exchange adapters."""

    def __init__(self, exchanges: ExchangeFactory) -> None:
        self.exchanges = exchanges

    def get_ticker(self, exchange: str, symbol: str) -> Ticker:
        """Return ticker from one exchange."""
        return self.exchanges.get(exchange).get_ticker(symbol)

    def get_orderbook(self, exchange: str, symbol: str) -> OrderBook:
        """Return orderbook from one exchange."""
        return self.exchanges.get(exchange).get_orderbook(symbol)

    def get_candles(self, exchange: str, symbol: str, bar: str = "15m", limit: int = 100, history: bool = False) -> list[Candle]:
        """Return candles from one exchange."""
        return self.exchanges.get(exchange).get_candles(symbol, bar=bar, limit=limit, history=history)
