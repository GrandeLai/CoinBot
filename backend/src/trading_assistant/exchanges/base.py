"""Exchange interface and shared market/account models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from trading_assistant.exceptions import ExchangeError
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class Ticker:
    """Best bid/ask ticker snapshot."""

    exchange: str
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume: Decimal
    timestamp: datetime

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class Candle:
    """Completed or in-progress OHLCV candle."""

    exchange: str
    symbol: str
    bar: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timestamp: datetime
    complete: bool = True

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class OrderBookLevel:
    """Single orderbook level."""

    price: Decimal
    amount: Decimal

    @property
    def notional(self) -> Decimal:
        """Quote notional at this level."""
        return self.price * self.amount


@dataclass(frozen=True)
class OrderBook:
    """Orderbook snapshot."""

    exchange: str
    symbol: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    timestamp: datetime

    @property
    def best_bid(self) -> OrderBookLevel:
        """Return top bid."""
        if not self.bids:
            raise ExchangeError(f"No bids for {self.exchange}:{self.symbol}")
        return self.bids[0]

    @property
    def best_ask(self) -> OrderBookLevel:
        """Return top ask."""
        if not self.asks:
            raise ExchangeError(f"No asks for {self.exchange}:{self.symbol}")
        return self.asks[0]

    def depth_notional(self, side: Literal["bid", "ask"], levels: int = 5) -> Decimal:
        """Return cumulative quote notional for one side."""
        rows = self.bids if side == "bid" else self.asks
        return sum((level.notional for level in rows[:levels]), Decimal("0"))

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class Balance:
    """Asset balance."""

    asset: str
    total: Decimal
    free: Decimal
    locked: Decimal


@dataclass(frozen=True)
class AccountSnapshot:
    """Exchange account balance snapshot."""

    exchange: str
    balances: dict[str, Balance]
    timestamp: datetime

    def balance_for(self, asset: str) -> Balance:
        """Return balance for one asset or a zero balance."""
        return self.balances.get(asset, Balance(asset=asset, total=Decimal("0"), free=Decimal("0"), locked=Decimal("0")))

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class FundingRate:
    """Perpetual funding-rate snapshot."""

    exchange: str
    symbol: str
    funding_rate: Decimal
    next_funding_time: datetime


@dataclass(frozen=True)
class SpotPerpQuote:
    """Spot and perpetual quote pair."""

    exchange: str
    symbol: str
    spot_bid: Decimal
    spot_ask: Decimal
    perp_bid: Decimal
    perp_ask: Decimal
    funding_rate: Decimal


@dataclass(frozen=True)
class InstrumentMetadata:
    """Tradable instrument metadata needed by strategy scanners."""

    exchange: str
    symbol: str
    market_type: Literal["spot", "swap", "futures"]
    base_asset: str
    quote_asset: str
    min_size: Decimal
    tick_size: Decimal
    contract_value: Decimal = Decimal("1")
    expiry: datetime | None = None


@dataclass(frozen=True)
class FuturesBasisQuote:
    """Spot, perpetual, and dated futures quote set."""

    exchange: str
    symbol: str
    spot_bid: Decimal
    spot_ask: Decimal
    perp_bid: Decimal
    perp_ask: Decimal
    futures_bid: Decimal
    futures_ask: Decimal
    futures_expiry: datetime | None
    funding_rate: Decimal


class Exchange(ABC):
    """Abstract exchange adapter."""

    name: str

    @abstractmethod
    def ping(self) -> bool:
        """Return whether the adapter is available."""

    @abstractmethod
    def list_symbols(self) -> list[str]:
        """Return supported symbols."""

    @abstractmethod
    def get_ticker(self, symbol: str) -> Ticker:
        """Return ticker for a symbol."""

    @abstractmethod
    def get_orderbook(self, symbol: str) -> OrderBook:
        """Return orderbook for a symbol."""

    @abstractmethod
    def get_candles(self, symbol: str, bar: str = "15m", limit: int = 100, history: bool = False) -> list[Candle]:
        """Return OHLCV candles ordered oldest to newest."""

    @abstractmethod
    def get_balances(self) -> AccountSnapshot:
        """Return account balances."""

    @abstractmethod
    def get_funding_rates(self) -> list[FundingRate]:
        """Return available funding rates."""

    @abstractmethod
    def get_spot_perp_quote(self, symbol: str) -> SpotPerpQuote:
        """Return spot/perp quote for basis calculations."""

    @abstractmethod
    def list_instruments(self, market_type: Literal["spot", "swap", "futures"] | None = None) -> list[InstrumentMetadata]:
        """Return instrument metadata by market type."""

    @abstractmethod
    def get_futures_basis_quote(self, symbol: str) -> FuturesBasisQuote:
        """Return spot/perp/futures quote for basis calculations."""


def utcnow() -> datetime:
    """Return timezone-aware current UTC time."""
    return datetime.now(tz=UTC)
