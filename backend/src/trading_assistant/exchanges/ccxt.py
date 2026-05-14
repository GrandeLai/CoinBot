"""Optional CCXT exchange adapter for sandbox-first market data reads."""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, Protocol

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


class CCXTClient(Protocol):
    """Minimal CCXT-like client surface used by the adapter."""

    markets: dict[str, dict[str, Any]]
    has: dict[str, bool]

    def load_markets(self) -> dict[str, dict[str, Any]]:
        """Load exchange markets."""

    def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        """Fetch one ticker."""

    def fetch_order_book(self, symbol: str, limit: int = 5) -> dict[str, Any]:
        """Fetch one orderbook."""

    def fetch_ohlcv(self, symbol: str, timeframe: str = "15m", limit: int = 100) -> list[list[Any]]:
        """Fetch OHLCV rows."""

    def fetch_balance(self) -> dict[str, Any]:
        """Fetch account balances."""


class CCXTExchange(Exchange):
    """CCXT-backed exchange adapter with no order-dispatch methods."""

    def __init__(
        self,
        name: str,
        *,
        exchange_id: str | None = None,
        sandbox: bool = True,
        client: CCXTClient | None = None,
    ) -> None:
        self.name = name
        self.exchange_id = exchange_id or name
        self.sandbox = sandbox
        self.client = client or create_ccxt_client(self.exchange_id, sandbox=sandbox)

    def ping(self) -> bool:
        """Return whether market metadata can be loaded."""
        try:
            self._markets()
        except Exception:
            return False
        return True

    def list_symbols(self) -> list[str]:
        """Return spot symbols supported by the exchange."""
        return sorted(_display_symbol(symbol) for symbol, market in self._markets().items() if _market_type(market) == "spot")

    def get_ticker(self, symbol: str) -> Ticker:
        """Return ticker for one spot symbol."""
        market_symbol = self._resolve_symbol(symbol, "spot")
        row = self.client.fetch_ticker(market_symbol)
        return Ticker(
            exchange=self.name,
            symbol=_display_symbol(str(row.get("symbol") or market_symbol)),
            bid=_decimal(row.get("bid")),
            ask=_decimal(row.get("ask")),
            last=_decimal(row.get("last")),
            volume=_decimal(row.get("quoteVolume", row.get("baseVolume", row.get("volume", "0")))),
            timestamp=_parse_timestamp(row.get("timestamp")),
        )

    def get_orderbook(self, symbol: str) -> OrderBook:
        """Return orderbook for one spot symbol."""
        market_symbol = self._resolve_symbol(symbol, "spot")
        row = self.client.fetch_order_book(market_symbol, limit=5)
        return OrderBook(
            exchange=self.name,
            symbol=_display_symbol(market_symbol),
            bids=_levels(row.get("bids", [])),
            asks=_levels(row.get("asks", [])),
            timestamp=_parse_timestamp(row.get("timestamp")),
        )

    def get_candles(self, symbol: str, bar: str = "15m", limit: int = 100, history: bool = False) -> list[Candle]:
        """Return OHLCV candles ordered oldest to newest."""
        market_symbol = self._resolve_symbol(symbol, "spot")
        if not _has(self.client, "fetchOHLCV"):
            raise ExchangeError(f"CCXT exchange {self.name} does not support OHLCV reads")
        rows = self.client.fetch_ohlcv(market_symbol, timeframe=bar, limit=limit)
        candles: list[Candle] = []
        for row in rows:
            if not isinstance(row, list | tuple) or len(row) < 6:
                continue
            candles.append(
                Candle(
                    exchange=self.name,
                    symbol=_display_symbol(market_symbol),
                    bar=bar,
                    open=_decimal(row[1]),
                    high=_decimal(row[2]),
                    low=_decimal(row[3]),
                    close=_decimal(row[4]),
                    volume=_decimal(row[5]),
                    timestamp=_parse_timestamp(row[0]),
                    complete=True,
                )
            )
        return candles

    def get_balances(self) -> AccountSnapshot:
        """Return account balances using CCXT's private balance read."""
        row = self.client.fetch_balance()
        total = _balance_map(row.get("total", {}))
        free = _balance_map(row.get("free", {}))
        used = _balance_map(row.get("used", row.get("locked", {})))
        assets = sorted(set(total) | set(free) | set(used))
        balances = {
            asset: Balance(
                asset=asset,
                total=total.get(asset, Decimal("0")),
                free=free.get(asset, Decimal("0")),
                locked=used.get(asset, Decimal("0")),
            )
            for asset in assets
        }
        return AccountSnapshot(exchange=self.name, balances=balances, timestamp=utcnow())

    def get_funding_rates(self) -> list[FundingRate]:
        """Return funding rates for swap markets when the CCXT client supports them."""
        rows: list[dict[str, Any]] = []
        fetch_many = getattr(self.client, "fetch_funding_rates", None)
        if callable(fetch_many) and _has(self.client, "fetchFundingRates"):
            payload = fetch_many([symbol for symbol, market in self._markets().items() if _market_type(market) == "swap"])
            if isinstance(payload, Mapping):
                rows.extend(dict(value) for value in payload.values() if isinstance(value, Mapping))
            elif isinstance(payload, list):
                rows.extend(dict(value) for value in payload if isinstance(value, Mapping))
        else:
            fetch_one = getattr(self.client, "fetch_funding_rate", None)
            if callable(fetch_one) and _has(self.client, "fetchFundingRate"):
                for symbol, market in self._markets().items():
                    if _market_type(market) != "swap":
                        continue
                    rows.append(dict(fetch_one(symbol)))
        return [
            FundingRate(
                exchange=self.name,
                symbol=_display_symbol(str(row.get("symbol", ""))),
                funding_rate=_decimal(row.get("fundingRate", row.get("rate", "0"))),
                next_funding_time=_parse_timestamp(row.get("nextFundingTimestamp", row.get("nextFundingTime"))),
            )
            for row in rows
        ]

    def get_spot_perp_quote(self, symbol: str) -> SpotPerpQuote:
        """Return spot and perpetual quotes for a symbol."""
        spot_symbol = self._resolve_symbol(symbol, "spot")
        swap_symbol = self._resolve_symbol(symbol, "swap")
        spot = self.client.fetch_ticker(spot_symbol)
        swap = self.client.fetch_ticker(swap_symbol)
        funding_rate = Decimal("0")
        fetch_one = getattr(self.client, "fetch_funding_rate", None)
        if callable(fetch_one) and _has(self.client, "fetchFundingRate"):
            funding = fetch_one(swap_symbol)
            funding_rate = _decimal(funding.get("fundingRate", funding.get("rate", "0")))
        return SpotPerpQuote(
            exchange=self.name,
            symbol=_display_symbol(spot_symbol),
            spot_bid=_decimal(spot.get("bid")),
            spot_ask=_decimal(spot.get("ask")),
            perp_bid=_decimal(swap.get("bid")),
            perp_ask=_decimal(swap.get("ask")),
            funding_rate=funding_rate,
        )

    def list_instruments(self, market_type: Literal["spot", "swap", "futures"] | None = None) -> list[InstrumentMetadata]:
        """Return instrument metadata from CCXT market rows."""
        instruments: list[InstrumentMetadata] = []
        for symbol, market in self._markets().items():
            row_market_type = _market_type(market)
            if market_type is not None and row_market_type != market_type:
                continue
            limits = market.get("limits", {}) if isinstance(market.get("limits"), Mapping) else {}
            amount_limit = limits.get("amount", {}) if isinstance(limits.get("amount"), Mapping) else {}
            precision = market.get("precision", {}) if isinstance(market.get("precision"), Mapping) else {}
            instruments.append(
                InstrumentMetadata(
                    exchange=self.name,
                    symbol=_display_symbol(symbol),
                    market_type=row_market_type,
                    base_asset=str(market.get("base", "")).upper(),
                    quote_asset=str(market.get("quote", "")).upper(),
                    min_size=_decimal(amount_limit.get("min", "0")),
                    tick_size=_decimal(precision.get("price", "0")),
                    contract_value=_decimal(market.get("contractSize", "1")),
                    expiry=_parse_timestamp(market.get("expiry")) if market.get("expiry") else None,
                )
            )
        return instruments

    def get_futures_basis_quote(self, symbol: str) -> FuturesBasisQuote:
        """Return spot, perpetual, and dated futures quotes when futures are available."""
        spot_symbol = self._resolve_symbol(symbol, "spot")
        swap_symbol = self._resolve_symbol(symbol, "swap")
        futures_symbol = self._resolve_symbol(symbol, "futures")
        spot = self.client.fetch_ticker(spot_symbol)
        swap = self.client.fetch_ticker(swap_symbol)
        futures = self.client.fetch_ticker(futures_symbol)
        futures_market = self._markets()[futures_symbol]
        return FuturesBasisQuote(
            exchange=self.name,
            symbol=_display_symbol(spot_symbol),
            spot_bid=_decimal(spot.get("bid")),
            spot_ask=_decimal(spot.get("ask")),
            perp_bid=_decimal(swap.get("bid")),
            perp_ask=_decimal(swap.get("ask")),
            futures_bid=_decimal(futures.get("bid")),
            futures_ask=_decimal(futures.get("ask")),
            futures_expiry=_parse_timestamp(futures_market.get("expiry")) if futures_market.get("expiry") else None,
            funding_rate=self.get_spot_perp_quote(symbol).funding_rate,
        )

    def _markets(self) -> dict[str, dict[str, Any]]:
        markets = getattr(self.client, "markets", None) or self.client.load_markets()
        if not isinstance(markets, dict):
            raise ExchangeError(f"CCXT adapter returned invalid markets for {self.name}")
        return {str(symbol): dict(row) for symbol, row in markets.items() if isinstance(row, Mapping)}

    def _resolve_symbol(self, symbol: str, market_type: Literal["spot", "swap", "futures"]) -> str:
        normalized = _display_symbol(symbol)
        for market_symbol, market in self._markets().items():
            if _market_type(market) == market_type and _display_symbol(market_symbol) == normalized:
                return market_symbol
        raise ExchangeError(f"{self.name} has no {market_type} market for {normalized}")


def create_ccxt_client(exchange_id: str, *, sandbox: bool) -> CCXTClient:
    """Create a CCXT client or fail with a clear optional-dependency error."""
    try:
        ccxt = importlib.import_module("ccxt")
    except ImportError as exc:
        raise ExchangeError("CCXT adapter requires installing the optional 'ccxt' package") from exc
    try:
        exchange_cls = getattr(ccxt, exchange_id)
    except AttributeError as exc:
        raise ExchangeError(f"CCXT exchange is not available: {exchange_id}") from exc
    client = exchange_cls({"enableRateLimit": True})
    set_sandbox = getattr(client, "set_sandbox_mode", None)
    if callable(set_sandbox):
        set_sandbox(sandbox)
    return client


def _display_symbol(symbol: str) -> str:
    cleaned = symbol.upper().replace("-", "/")
    if ":" in cleaned:
        cleaned = cleaned.split(":", maxsplit=1)[0]
    parts = cleaned.split("/")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    if cleaned.endswith("USDT"):
        return f"{cleaned[:-4]}/USDT"
    return cleaned


def _market_type(market: Mapping[str, Any]) -> Literal["spot", "swap", "futures"]:
    if bool(market.get("future")) or str(market.get("type", "")).lower() == "future":
        return "futures"
    if bool(market.get("swap")) or str(market.get("type", "")).lower() == "swap":
        return "swap"
    return "spot"


def _decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def _parse_timestamp(value: Any) -> datetime:
    try:
        if value is None:
            raise ValueError
        return datetime.fromtimestamp(float(Decimal(str(value)) / Decimal("1000")), tz=UTC)
    except Exception:
        return utcnow()


def _levels(rows: Any) -> list[OrderBookLevel]:
    if not isinstance(rows, list):
        return []
    levels: list[OrderBookLevel] = []
    for row in rows:
        if isinstance(row, list | tuple) and len(row) >= 2:
            levels.append(OrderBookLevel(price=_decimal(row[0]), amount=_decimal(row[1])))
    return levels


def _balance_map(row: Any) -> dict[str, Decimal]:
    if not isinstance(row, Mapping):
        return {}
    return {str(asset).upper(): _decimal(value) for asset, value in row.items()}


def _has(client: Any, feature: str) -> bool:
    has = getattr(client, "has", {})
    return bool(has.get(feature)) if isinstance(has, Mapping) else False
