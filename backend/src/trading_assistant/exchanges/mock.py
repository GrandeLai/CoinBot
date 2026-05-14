"""Deterministic offline exchange adapter used by tests and dry-run flows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, TypedDict

from trading_assistant.exchanges.base import (
    AccountSnapshot,
    Balance,
    Candle,
    Exchange,
    FundingRate,
    FuturesBasisQuote,
    InstrumentMetadata,
    OrderBook,
    OrderBookLevel,
    SpotPerpQuote,
    Ticker,
    utcnow,
)
from trading_assistant.exceptions import ExchangeError


class TickerData(TypedDict):
    """Typed mock ticker row."""

    bid: Decimal
    ask: Decimal
    last: Decimal
    volume: Decimal


class MockProfile(TypedDict):
    """Typed mock profile."""

    tickers: dict[str, TickerData]


class MockExchange(Exchange):
    """Mock exchange with stable prices, balances, funding, and depth."""

    def __init__(self, name: str = "mock") -> None:
        self.name = name

    def ping(self) -> bool:
        """Return mock availability."""
        return True

    def list_symbols(self) -> list[str]:
        """Return supported mock symbols."""
        return sorted(_profile(self.name)["tickers"])

    def get_ticker(self, symbol: str) -> Ticker:
        """Return deterministic ticker."""
        profile = _profile(self.name)
        normalized = _normalize_symbol(symbol)
        try:
            data = profile["tickers"][normalized]
        except KeyError as exc:
            raise ExchangeError(f"Symbol not supported on {self.name}: {symbol}") from exc
        return Ticker(exchange=self.name, symbol=normalized, timestamp=utcnow(), **data)

    def get_orderbook(self, symbol: str) -> OrderBook:
        """Return deterministic orderbook."""
        ticker = self.get_ticker(symbol)
        return OrderBook(
            exchange=self.name,
            symbol=ticker.symbol,
            bids=[
                OrderBookLevel(ticker.bid, Decimal("2")),
                OrderBookLevel(ticker.bid - Decimal("5"), Decimal("2.5")),
                OrderBookLevel(ticker.bid - Decimal("10"), Decimal("3")),
            ],
            asks=[
                OrderBookLevel(ticker.ask, Decimal("2")),
                OrderBookLevel(ticker.ask + Decimal("5"), Decimal("2.5")),
                OrderBookLevel(ticker.ask + Decimal("10"), Decimal("3")),
            ],
            timestamp=utcnow(),
        )

    def get_candles(self, symbol: str, bar: str = "15m", limit: int = 100, history: bool = False) -> list[Candle]:
        """Return deterministic completed candles ordered oldest to newest."""
        ticker = self.get_ticker(symbol)
        count = max(min(limit, 500), 1)
        return _mock_candles(self.name, ticker.symbol, bar, count)

    def get_balances(self) -> AccountSnapshot:
        """Return deterministic balances."""
        balances = {
            "USDT": Balance(asset="USDT", total=Decimal("10000"), free=Decimal("10000"), locked=Decimal("0")),
            "BTC": Balance(asset="BTC", total=Decimal("1.5"), free=Decimal("1.5"), locked=Decimal("0")),
            "ETH": Balance(asset="ETH", total=Decimal("20"), free=Decimal("20"), locked=Decimal("0")),
            "SOL": Balance(asset="SOL", total=Decimal("100"), free=Decimal("100"), locked=Decimal("0")),
            "XRP": Balance(asset="XRP", total=Decimal("5000"), free=Decimal("5000"), locked=Decimal("0")),
            "DOGE": Balance(asset="DOGE", total=Decimal("10000"), free=Decimal("10000"), locked=Decimal("0")),
            "ADA": Balance(asset="ADA", total=Decimal("6000"), free=Decimal("6000"), locked=Decimal("0")),
        }
        return AccountSnapshot(exchange=self.name, balances=balances, timestamp=utcnow())

    def get_funding_rates(self) -> list[FundingRate]:
        """Return deterministic funding rates."""
        next_time = datetime.now(tz=UTC) + timedelta(hours=8)
        return [
            FundingRate(exchange=self.name, symbol="BTC/USDT", funding_rate=Decimal("0.0060"), next_funding_time=next_time),
            FundingRate(exchange=self.name, symbol="ETH/USDT", funding_rate=Decimal("0.0058"), next_funding_time=next_time),
            FundingRate(exchange=self.name, symbol="SOL/USDT", funding_rate=Decimal("0.0042"), next_funding_time=next_time),
        ]

    def get_spot_perp_quote(self, symbol: str) -> SpotPerpQuote:
        """Return deterministic spot/perpetual quotes."""
        ticker = self.get_ticker(symbol)
        perp = _profile(self.name)["tickers"].get(f"{ticker.symbol}-SWAP")
        return SpotPerpQuote(
            exchange=self.name,
            symbol=ticker.symbol,
            spot_bid=ticker.bid,
            spot_ask=ticker.ask,
            perp_bid=perp["bid"] if perp else ticker.bid + Decimal("230"),
            perp_ask=perp["ask"] if perp else ticker.ask + Decimal("240"),
            funding_rate=Decimal("0.0006"),
        )

    def list_instruments(self, market_type: Literal["spot", "swap", "futures"] | None = None) -> list[InstrumentMetadata]:
        """Return deterministic instrument metadata."""
        instruments = [
            InstrumentMetadata(self.name, "BTC/USDT", "spot", "BTC", "USDT", Decimal("0.0001"), Decimal("0.1")),
            InstrumentMetadata(self.name, "ETH/USDT", "spot", "ETH", "USDT", Decimal("0.001"), Decimal("0.01")),
            InstrumentMetadata(self.name, "SOL/USDT", "spot", "SOL", "USDT", Decimal("0.01"), Decimal("0.001")),
            InstrumentMetadata(self.name, "XRP/USDT", "spot", "XRP", "USDT", Decimal("1"), Decimal("0.0001")),
            InstrumentMetadata(self.name, "DOGE/USDT", "spot", "DOGE", "USDT", Decimal("1"), Decimal("0.00001")),
            InstrumentMetadata(self.name, "ADA/USDT", "spot", "ADA", "USDT", Decimal("1"), Decimal("0.0001")),
            InstrumentMetadata(self.name, "ETH/BTC", "spot", "ETH", "BTC", Decimal("0.001"), Decimal("0.000001")),
            InstrumentMetadata(self.name, "SOL/BTC", "spot", "SOL", "BTC", Decimal("0.01"), Decimal("0.0000001")),
            InstrumentMetadata(self.name, "BTC/USDT", "swap", "BTC", "USDT", Decimal("0.01"), Decimal("0.1"), Decimal("0.01")),
            InstrumentMetadata(self.name, "ETH/USDT", "swap", "ETH", "USDT", Decimal("0.1"), Decimal("0.01"), Decimal("0.1")),
            InstrumentMetadata(
                self.name,
                "BTC/USDT",
                "futures",
                "BTC",
                "USDT",
                Decimal("0.01"),
                Decimal("0.1"),
                Decimal("0.01"),
                datetime.now(tz=UTC) + timedelta(days=30),
            ),
        ]
        if market_type is not None:
            return [item for item in instruments if item.market_type == market_type]
        return instruments

    def get_futures_basis_quote(self, symbol: str) -> FuturesBasisQuote:
        """Return deterministic spot/perp/futures quotes."""
        spot = self.get_ticker(symbol)
        perp = self.get_spot_perp_quote(symbol)
        futures = _profile(self.name)["tickers"].get(f"{spot.symbol}-FUTURES")
        futures_bid = futures["bid"] if futures else spot.bid + Decimal("420")
        futures_ask = futures["ask"] if futures else spot.ask + Decimal("430")
        futures_expiry = datetime.now(tz=UTC) + timedelta(days=30)
        return FuturesBasisQuote(
            exchange=self.name,
            symbol=spot.symbol,
            spot_bid=spot.bid,
            spot_ask=spot.ask,
            perp_bid=perp.perp_bid,
            perp_ask=perp.perp_ask,
            futures_bid=futures_bid,
            futures_ask=futures_ask,
            futures_expiry=futures_expiry,
            funding_rate=perp.funding_rate,
        )


def _profile(name: str) -> MockProfile:
    """Return a named mock price profile."""
    profiles: dict[str, MockProfile] = {
        "mock": {
            "tickers": {
                "BTC/USDT": {
                    "bid": Decimal("50000"),
                    "ask": Decimal("50010"),
                    "last": Decimal("50005"),
                    "volume": Decimal("1200"),
                },
                "ETH/USDT": {
                    "bid": Decimal("2600"),
                    "ask": Decimal("2602"),
                    "last": Decimal("2601"),
                    "volume": Decimal("8000"),
                },
                "ETH/BTC": {
                    "bid": Decimal("0.0498"),
                    "ask": Decimal("0.05"),
                    "last": Decimal("0.0499"),
                    "volume": Decimal("5000"),
                },
                "SOL/USDT": {
                    "bid": Decimal("170"),
                    "ask": Decimal("170.2"),
                    "last": Decimal("170.1"),
                    "volume": Decimal("9000"),
                },
                "XRP/USDT": {
                    "bid": Decimal("0.5200"),
                    "ask": Decimal("0.5205"),
                    "last": Decimal("0.5203"),
                    "volume": Decimal("250000"),
                },
                "DOGE/USDT": {
                    "bid": Decimal("0.1420"),
                    "ask": Decimal("0.1422"),
                    "last": Decimal("0.1421"),
                    "volume": Decimal("700000"),
                },
                "ADA/USDT": {
                    "bid": Decimal("0.4500"),
                    "ask": Decimal("0.4506"),
                    "last": Decimal("0.4504"),
                    "volume": Decimal("400000"),
                },
                "SOL/BTC": {
                    "bid": Decimal("0.00325"),
                    "ask": Decimal("0.00327"),
                    "last": Decimal("0.00326"),
                    "volume": Decimal("5000"),
                },
                "BTC/USDT-SWAP": {
                    "bid": Decimal("50230"),
                    "ask": Decimal("50250"),
                    "last": Decimal("50240"),
                    "volume": Decimal("5000"),
                },
                "BTC/USDT-FUTURES": {
                    "bid": Decimal("50440"),
                    "ask": Decimal("50460"),
                    "last": Decimal("50450"),
                    "volume": Decimal("2400"),
                },
            }
        },
        "mock_alt": {
            "tickers": {
                "BTC/USDT": {
                    "bid": Decimal("50280"),
                    "ask": Decimal("50290"),
                    "last": Decimal("50285"),
                    "volume": Decimal("1100"),
                },
                "ETH/USDT": {
                    "bid": Decimal("2620"),
                    "ask": Decimal("2623"),
                    "last": Decimal("2621"),
                    "volume": Decimal("7000"),
                },
                "ETH/BTC": {
                    "bid": Decimal("0.0500"),
                    "ask": Decimal("0.0502"),
                    "last": Decimal("0.0501"),
                    "volume": Decimal("4000"),
                },
                "SOL/USDT": {
                    "bid": Decimal("171"),
                    "ask": Decimal("171.3"),
                    "last": Decimal("171.1"),
                    "volume": Decimal("7000"),
                },
                "XRP/USDT": {
                    "bid": Decimal("0.5230"),
                    "ask": Decimal("0.5238"),
                    "last": Decimal("0.5234"),
                    "volume": Decimal("210000"),
                },
                "DOGE/USDT": {
                    "bid": Decimal("0.1430"),
                    "ask": Decimal("0.1433"),
                    "last": Decimal("0.1431"),
                    "volume": Decimal("620000"),
                },
                "ADA/USDT": {
                    "bid": Decimal("0.4520"),
                    "ask": Decimal("0.4527"),
                    "last": Decimal("0.4524"),
                    "volume": Decimal("360000"),
                },
                "SOL/BTC": {
                    "bid": Decimal("0.00328"),
                    "ask": Decimal("0.00330"),
                    "last": Decimal("0.00329"),
                    "volume": Decimal("3000"),
                },
                "BTC/USDT-SWAP": {
                    "bid": Decimal("50480"),
                    "ask": Decimal("50500"),
                    "last": Decimal("50490"),
                    "volume": Decimal("4300"),
                },
                "BTC/USDT-FUTURES": {
                    "bid": Decimal("50650"),
                    "ask": Decimal("50680"),
                    "last": Decimal("50660"),
                    "volume": Decimal("2100"),
                },
            }
        },
    }
    if name not in profiles:
        raise ExchangeError(f"Unknown mock profile: {name}")
    return profiles[name]


def _mock_candles(exchange: str, symbol: str, bar: str, count: int) -> list[Candle]:
    """Build deterministic spot candles with several exploitable regimes."""
    start = datetime(2026, 5, 10, tzinfo=UTC)
    base = _profile(exchange)["tickers"][symbol]["last"]
    step = _trend_step(symbol, base)
    candles: list[Candle] = []
    price = base - (step * Decimal(count))
    for index in range(count):
        is_last = index == count - 1
        if symbol == "ETH/USDT":
            # ETH fixture ends with a completed oversold rebound setup.
            drift = Decimal("-0.002") if index < count - 5 else Decimal("0.006")
            close = price * (Decimal("1") + drift)
            low = min(price, close) * Decimal("0.985") if index >= count - 5 else min(price, close) * Decimal("0.995")
            high = max(price, close) * Decimal("1.004")
            volume = Decimal("8000") + Decimal(index * 12)
        elif symbol == "SOL/USDT":
            # SOL fixture compresses before a breakout.
            compression = Decimal("0.0006") if index < count - 3 else Decimal("0.018")
            close = price * (Decimal("1") + compression)
            low = min(price, close) * Decimal("0.998")
            high = max(price, close) * (Decimal("1.002") if index < count - 3 else Decimal("1.018"))
            volume = Decimal("6000") if index < count - 3 else Decimal("13000")
        elif symbol in {"XRP/USDT", "DOGE/USDT", "ADA/USDT"}:
            close = price * (Decimal("1") + Decimal(index % 5) / Decimal("10000"))
            low = min(price, close) * Decimal("0.997")
            high = max(price, close) * Decimal("1.004")
            volume = Decimal("100000") + Decimal(index * 1000)
        else:
            close = price + step
            low = min(price, close) * Decimal("0.998")
            high = max(price, close) * Decimal("1.002")
            volume = Decimal("1000") + Decimal(index * 20)
            if is_last or index == max(count // 2, 35):
                close = close + step * Decimal("8")
                high = close * Decimal("1.002")
                volume = volume * Decimal("2")
        candles.append(
            Candle(
                exchange=exchange,
                symbol=symbol,
                bar=bar,
                open=price,
                high=high,
                low=low,
                close=close,
                volume=volume,
                timestamp=start + timedelta(minutes=15 * index),
                complete=True,
            )
        )
        price = close
    return candles


def _trend_step(symbol: str, base: Decimal) -> Decimal:
    """Return a symbol-scaled trend step for candle fixtures."""
    if symbol in {"BTC/USDT", "ETH/USDT"}:
        return (base * Decimal("0.0008")).quantize(Decimal("0.0001"))
    if symbol == "SOL/USDT":
        return Decimal("0.05")
    return (base * Decimal("0.001")).quantize(Decimal("0.0000001"))


def _normalize_symbol(symbol: str) -> str:
    """Normalize common crypto symbol spellings."""
    cleaned = symbol.upper()
    suffix = ""
    for candidate in ("-SWAP", "-FUTURES"):
        if cleaned.endswith(candidate):
            cleaned = cleaned.removesuffix(candidate)
            suffix = candidate
            break
    cleaned = cleaned.replace("-", "/")
    if "/" not in cleaned and cleaned.endswith("USDT"):
        cleaned = f"{cleaned[:-4]}/USDT"
    if suffix:
        return f"{cleaned}{suffix}"
    return cleaned
