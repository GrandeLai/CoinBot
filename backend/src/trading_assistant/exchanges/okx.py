"""OKX exchange adapter for market, account, and funding data."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, Protocol

import httpx

from coinbot_api.broker.okx import OKXTradingProvider

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


class OKXClient(Protocol):
    """Minimal OKX client interface used by the adapter."""

    def ping(self) -> bool:
        """Return whether OKX public API is reachable."""

    def list_symbols(self) -> list[str]:
        """Return OKX instrument IDs."""

    def get_ticker(self, inst_id: str) -> dict[str, Any]:
        """Return one OKX ticker payload."""

    def list_tickers(self, inst_type: str) -> list[dict[str, Any]]:
        """Return OKX ticker rows for one instrument type."""

    def get_orderbook(self, inst_id: str, depth: int = 5) -> dict[str, Any]:
        """Return one OKX orderbook payload."""

    def get_candles(self, inst_id: str, bar: str = "15m", limit: int = 100, history: bool = False) -> list[list[Any]]:
        """Return OKX candle rows."""

    def get_account_balances(self) -> list[dict[str, Any]]:
        """Return normalized account balance rows."""

    def get_funding_rates(self) -> list[dict[str, Any]]:
        """Return funding-rate rows."""

    def get_spot_perp_quote(self, inst_id: str) -> dict[str, Any]:
        """Return normalized spot/perp quote row."""

    def list_instruments(self, inst_type: str) -> list[dict[str, Any]]:
        """Return OKX instrument metadata rows."""

    def get_futures_basis_quote(self, inst_id: str) -> dict[str, Any]:
        """Return normalized futures basis quote row."""


class OKXExchange(Exchange):
    """OKX adapter implementing the trading assistant exchange interface."""

    def __init__(self, name: str = "okx", client: OKXClient | None = None) -> None:
        self.name = name
        self.client = client or OKXRestClient()

    def ping(self) -> bool:
        """Return OKX public API availability."""
        return self.client.ping()

    def list_symbols(self) -> list[str]:
        """Return supported spot symbols in display form."""
        return sorted(_display_symbol(inst_id) for inst_id in self.client.list_symbols())

    def get_ticker(self, symbol: str) -> Ticker:
        """Return ticker for one OKX spot symbol."""
        payload = self.client.get_ticker(_inst_id(symbol))
        return Ticker(
            exchange=self.name,
            symbol=_display_symbol(str(payload.get("instId", _inst_id(symbol)))),
            bid=Decimal(str(payload.get("bidPx", "0"))),
            ask=Decimal(str(payload.get("askPx", "0"))),
            last=Decimal(str(payload.get("last", "0"))),
            volume=Decimal(str(payload.get("volCcy24h", payload.get("vol24h", "0")))),
            timestamp=_parse_okx_ts(payload.get("ts")),
        )

    def get_orderbook(self, symbol: str) -> OrderBook:
        """Return orderbook for one OKX spot symbol."""
        inst_id = _inst_id(symbol)
        payload = self.client.get_orderbook(inst_id, depth=5)
        return OrderBook(
            exchange=self.name,
            symbol=_display_symbol(inst_id),
            bids=_levels(payload.get("bids", [])),
            asks=_levels(payload.get("asks", [])),
            timestamp=_parse_okx_ts(payload.get("ts")),
        )

    def get_candles(self, symbol: str, bar: str = "15m", limit: int = 100, history: bool = False) -> list[Candle]:
        """Return completed OKX spot candles ordered oldest to newest."""
        inst_id = _inst_id(symbol)
        rows = self.client.get_candles(inst_id, bar=bar, limit=limit, history=history)
        candles: list[Candle] = []
        for row in reversed(rows):
            if len(row) < 6:
                continue
            complete = str(row[8]) == "1" if len(row) > 8 else True
            if not complete:
                continue
            candles.append(
                Candle(
                    exchange=self.name,
                    symbol=_display_symbol(inst_id),
                    bar=bar,
                    open=Decimal(str(row[1])),
                    high=Decimal(str(row[2])),
                    low=Decimal(str(row[3])),
                    close=Decimal(str(row[4])),
                    volume=Decimal(str(row[5])),
                    timestamp=_parse_okx_ts(row[0]),
                    complete=True,
                )
            )
        return candles

    def get_balances(self) -> AccountSnapshot:
        """Return account balances from OKX private API when configured."""
        rows = self.client.get_account_balances()
        balances = {
            str(row["asset"]).upper(): Balance(
                asset=str(row["asset"]).upper(),
                total=Decimal(str(row.get("total", "0"))),
                free=Decimal(str(row.get("free", "0"))),
                locked=Decimal(str(row.get("locked", "0"))),
            )
            for row in rows
        }
        return AccountSnapshot(exchange=self.name, balances=balances, timestamp=utcnow())

    def get_funding_rates(self) -> list[FundingRate]:
        """Return normalized OKX funding rates."""
        return [
            FundingRate(
                exchange=self.name,
                symbol=_display_symbol(str(row.get("instId", ""))),
                funding_rate=Decimal(str(row.get("fundingRate", "0"))),
                next_funding_time=_parse_okx_ts(row.get("nextFundingTime")),
            )
            for row in self.client.get_funding_rates()
        ]

    def get_spot_perp_quote(self, symbol: str) -> SpotPerpQuote:
        """Return OKX spot/perp quote for basis calculations."""
        inst_id = _inst_id(symbol)
        row = self.client.get_spot_perp_quote(inst_id)
        return SpotPerpQuote(
            exchange=self.name,
            symbol=_display_symbol(str(row.get("instId", inst_id))),
            spot_bid=Decimal(str(row.get("spotBid", "0"))),
            spot_ask=Decimal(str(row.get("spotAsk", "0"))),
            perp_bid=Decimal(str(row.get("perpBid", "0"))),
            perp_ask=Decimal(str(row.get("perpAsk", "0"))),
            funding_rate=Decimal(str(row.get("fundingRate", "0"))),
        )

    def list_instruments(self, market_type: Literal["spot", "swap", "futures"] | None = None) -> list[InstrumentMetadata]:
        """Return OKX instrument metadata rows."""
        inst_types = [_okx_market_type(market_type)] if market_type is not None else ["SPOT", "SWAP", "FUTURES"]
        instruments: list[InstrumentMetadata] = []
        for inst_type in inst_types:
            for row in self.client.list_instruments(inst_type):
                inst_id = str(row.get("instId", ""))
                base = str(row.get("baseCcy") or row.get("uly", "").split("-")[0] or "")
                quote = str(row.get("quoteCcy") or row.get("uly", "").split("-")[-1] or "")
                instruments.append(
                    InstrumentMetadata(
                        exchange=self.name,
                        symbol=_display_symbol(inst_id),
                        market_type=_display_market_type(inst_type),
                        base_asset=base,
                        quote_asset=quote,
                        min_size=Decimal(str(row.get("minSz", "0") or "0")),
                        tick_size=Decimal(str(row.get("tickSz", "0") or "0")),
                        contract_value=Decimal(str(row.get("ctVal", "1") or "1")),
                        expiry=_parse_okx_ts(row.get("expTime")) if row.get("expTime") else None,
                    )
                )
        return instruments

    def get_futures_basis_quote(self, symbol: str) -> FuturesBasisQuote:
        """Return OKX spot/perp/futures quote for basis calculations."""
        inst_id = _inst_id(symbol)
        row = self.client.get_futures_basis_quote(inst_id)
        return FuturesBasisQuote(
            exchange=self.name,
            symbol=_display_symbol(str(row.get("instId", inst_id))),
            spot_bid=Decimal(str(row.get("spotBid", "0"))),
            spot_ask=Decimal(str(row.get("spotAsk", "0"))),
            perp_bid=Decimal(str(row.get("perpBid", "0"))),
            perp_ask=Decimal(str(row.get("perpAsk", "0"))),
            futures_bid=Decimal(str(row.get("futuresBid", "0"))),
            futures_ask=Decimal(str(row.get("futuresAsk", "0"))),
            futures_expiry=_parse_okx_ts(row.get("futuresExpiry")) if row.get("futuresExpiry") else None,
            funding_rate=Decimal(str(row.get("fundingRate", "0"))),
        )


class OKXRestClient:
    """Small OKX REST client used when the adapter is explicitly enabled."""

    base_url = "https://www.okx.com"

    def ping(self) -> bool:
        """Return whether OKX public time endpoint is reachable."""
        try:
            self._get("/api/v5/public/time")
        except Exception:
            return False
        return True

    def list_symbols(self) -> list[str]:
        """Return all OKX spot instrument IDs."""
        payload = self._get("/api/v5/public/instruments", {"instType": "SPOT"})
        return [str(row.get("instId", "")) for row in payload if row.get("instId")]

    def get_ticker(self, inst_id: str) -> dict[str, Any]:
        """Return one ticker row."""
        rows = self._get("/api/v5/market/ticker", {"instId": inst_id})
        if not rows:
            raise ExchangeError(f"OKX ticker not found: {inst_id}")
        return dict(rows[0])

    def list_tickers(self, inst_type: str) -> list[dict[str, Any]]:
        """Return ticker rows for one OKX instrument type."""
        return self._get("/api/v5/market/tickers", {"instType": inst_type})

    def get_orderbook(self, inst_id: str, depth: int = 5) -> dict[str, Any]:
        """Return one orderbook row."""
        rows = self._get("/api/v5/market/books", {"instId": inst_id, "sz": str(depth)})
        if not rows:
            raise ExchangeError(f"OKX orderbook not found: {inst_id}")
        return dict(rows[0])

    def get_candles(self, inst_id: str, bar: str = "15m", limit: int = 100, history: bool = False) -> list[list[Any]]:
        """Return one OKX candle window from public market endpoints."""
        path = "/api/v5/market/history-candles" if history else "/api/v5/market/candles"
        data = self._get_data(path, {"instId": inst_id, "bar": bar, "limit": str(limit)})
        return [list(row) for row in data if isinstance(row, list | tuple)]

    def get_account_balances(self) -> list[dict[str, Any]]:
        """Return normalized private balances through the existing OKX provider."""
        account = OKXTradingProvider().get_account()
        return [
            {
                "asset": balance.asset,
                "free": balance.free,
                "locked": balance.locked,
                "total": balance.total,
            }
            for balance in account.balances
        ]

    def get_funding_rates(self) -> list[dict[str, Any]]:
        """Return funding rates for common swaps."""
        rows: list[dict[str, Any]] = []
        for inst_id in ("BTC-USDT-SWAP", "ETH-USDT-SWAP"):
            data = self._get("/api/v5/public/funding-rate", {"instId": inst_id})
            if data:
                rows.append(dict(data[0]))
        return rows

    def get_spot_perp_quote(self, inst_id: str) -> dict[str, Any]:
        """Return normalized spot/perp quote using public endpoints."""
        spot = self.get_ticker(inst_id)
        swap_id = f"{inst_id}-SWAP"
        perp = self.get_ticker(swap_id)
        funding_rows = self._get("/api/v5/public/funding-rate", {"instId": swap_id})
        funding_rate = funding_rows[0].get("fundingRate", "0") if funding_rows else "0"
        return {
            "instId": inst_id,
            "spotBid": spot.get("bidPx", "0"),
            "spotAsk": spot.get("askPx", "0"),
            "perpBid": perp.get("bidPx", "0"),
            "perpAsk": perp.get("askPx", "0"),
            "fundingRate": funding_rate,
        }

    def list_instruments(self, inst_type: str) -> list[dict[str, Any]]:
        """Return OKX instrument metadata rows."""
        return self._get("/api/v5/public/instruments", {"instType": inst_type})

    def get_futures_basis_quote(self, inst_id: str) -> dict[str, Any]:
        """Return normalized spot/perp/futures quote using public endpoints."""
        spot_perp = self.get_spot_perp_quote(inst_id)
        futures_rows = self._get("/api/v5/public/instruments", {"instType": "FUTURES", "uly": inst_id})
        futures_ids = [str(row.get("instId", "")) for row in futures_rows if row.get("instId")]
        if not futures_ids:
            raise ExchangeError(f"OKX futures instrument not found for {inst_id}")
        futures_row = sorted(futures_rows, key=lambda row: str(row.get("expTime", "")))[0]
        futures_id = str(futures_row.get("instId", ""))
        futures = self.get_ticker(futures_id)
        return {
            **spot_perp,
            "futuresBid": futures.get("bidPx", "0"),
            "futuresAsk": futures.get("askPx", "0"),
            "futuresExpiry": futures_row.get("expTime", "0"),
        }

    def _get(self, path: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        """Call an OKX public endpoint and return data rows."""
        data = self._get_data(path, params)
        return [dict(row) for row in data if isinstance(row, dict)]

    def _get_data(self, path: str, params: dict[str, str] | None = None) -> list[Any]:
        """Call an OKX endpoint and return raw data rows."""
        response = httpx.get(f"{self.base_url}{path}", params=params, timeout=10.0)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != "0":
            raise ExchangeError(f"OKX request failed: {payload.get('msg', 'unknown error')}")
        data = payload.get("data", [])
        if not isinstance(data, list):
            raise ExchangeError("OKX response data must be a list")
        return list(data)


def _inst_id(symbol: str) -> str:
    """Convert display symbol to OKX instrument ID."""
    cleaned = symbol.upper().replace("/", "-")
    if cleaned.endswith("-SWAP"):
        return cleaned
    if "-" not in cleaned and cleaned.endswith("USDT"):
        return f"{cleaned[:-4]}-USDT"
    return cleaned


def _display_symbol(inst_id: str) -> str:
    """Convert OKX instrument ID to display symbol."""
    cleaned = inst_id.upper()
    if cleaned.endswith("-SWAP"):
        cleaned = cleaned.removesuffix("-SWAP")
    parts = cleaned.split("-")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return cleaned.replace("-", "/")


def _okx_market_type(market_type: Literal["spot", "swap", "futures"]) -> str:
    """Convert internal market type to OKX instType."""
    return {"spot": "SPOT", "swap": "SWAP", "futures": "FUTURES"}[market_type]


def _display_market_type(inst_type: str) -> Literal["spot", "swap", "futures"]:
    """Convert OKX instType to internal market type."""
    if inst_type == "SWAP":
        return "swap"
    if inst_type == "FUTURES":
        return "futures"
    return "spot"


def _levels(rows: Any) -> list[OrderBookLevel]:
    """Convert OKX orderbook rows to domain levels."""
    levels: list[OrderBookLevel] = []
    if not isinstance(rows, list):
        return levels
    for row in rows:
        if isinstance(row, list | tuple) and len(row) >= 2:
            levels.append(OrderBookLevel(price=Decimal(str(row[0])), amount=Decimal(str(row[1]))))
    return levels


def _parse_okx_ts(value: Any) -> datetime:
    """Parse an OKX millisecond timestamp."""
    try:
        return datetime.fromtimestamp(float(Decimal(str(value)) / Decimal("1000")), tz=UTC)
    except Exception:
        return utcnow()
