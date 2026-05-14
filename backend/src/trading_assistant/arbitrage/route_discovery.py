"""Instrument-driven triangular route discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.base import InstrumentMetadata
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.exceptions import ExchangeError
from trading_assistant.utils.serialization import to_jsonable


DEFAULT_TRIANGULAR_ASSETS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "OKB", "USDC"]


@dataclass(frozen=True)
class RouteDiscoveryCandidate:
    """One accepted or filtered triangular route candidate."""

    route: list[str]
    symbols: list[str]
    status: str
    reasons: list[str] = field(default_factory=list)
    route_depth_usdt: Decimal = Decimal("0")
    quote_volume_usdt: Decimal = Decimal("0")
    min_size_adjustments: dict[str, str] = field(default_factory=dict)
    tick_sizes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe route candidate."""
        return to_jsonable(self)


@dataclass(frozen=True)
class TriangularRouteDiscoveryReport:
    """Read-only route discovery report."""

    exchange: str
    quote: str
    route_limit: int
    universe_assets: list[str]
    accepted_routes: list[RouteDiscoveryCandidate]
    filtered_routes: list[RouteDiscoveryCandidate]
    read_only: bool = True
    orders_sent: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe discovery report."""
        return to_jsonable(self)


class TriangularRouteDiscoveryService:
    """Discover executable triangular spot routes from exchange instrument metadata."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def discover(self, exchange_name: str = "mock", quote: str = "USDT", route_limit: int = 100) -> TriangularRouteDiscoveryReport:
        """Return accepted and filtered triangular route candidates."""
        normalized_quote = quote.upper()
        limit = max(route_limit, 1)
        exchange = self.exchanges.get(exchange_name)
        instruments = [item for item in exchange.list_instruments("spot") if item.base_asset and item.quote_asset]
        by_pair = {(item.base_asset.upper(), item.quote_asset.upper()): item for item in instruments}
        universe = self._universe(exchange_name, normalized_quote, instruments)
        accepted: list[RouteDiscoveryCandidate] = []
        filtered: list[RouteDiscoveryCandidate] = []
        seen_routes: set[tuple[str, ...]] = set()
        for route in [*self.settings.arbitrage.triangular_routes, *self._candidate_routes(normalized_quote, universe)]:
            normalized = [item.upper() for item in route]
            key = tuple(normalized)
            if key in seen_routes:
                continue
            seen_routes.add(key)
            candidate = self._evaluate_route(exchange_name, normalized, by_pair)
            if candidate.status == "accepted" and len(accepted) < limit:
                accepted.append(candidate)
            else:
                filtered.append(candidate)
        return TriangularRouteDiscoveryReport(
            exchange=exchange_name,
            quote=normalized_quote,
            route_limit=limit,
            universe_assets=universe,
            accepted_routes=accepted,
            filtered_routes=filtered,
        )

    def _universe(self, exchange_name: str, quote: str, instruments: list[InstrumentMetadata]) -> list[str]:
        priority = [asset for asset in DEFAULT_TRIANGULAR_ASSETS if asset != quote]
        exchange = self.exchanges.get(exchange_name)
        volume_rows: list[tuple[Decimal, str]] = []
        ticker_volume_by_symbol = _bulk_ticker_volume_by_symbol(exchange)
        for item in instruments:
            base = item.base_asset.upper()
            if item.quote_asset.upper() != quote or base == quote:
                continue
            if item.symbol in ticker_volume_by_symbol:
                volume_rows.append((ticker_volume_by_symbol[item.symbol], base))
                continue
            if base not in priority:
                continue
            try:
                ticker = exchange.get_ticker(item.symbol)
            except ExchangeError:
                continue
            volume_rows.append((ticker.volume, base))
        top_volume_assets = [asset for _volume, asset in sorted(volume_rows, reverse=True)[:20]]
        merged: list[str] = []
        for asset in [*priority, *top_volume_assets]:
            if asset not in merged:
                merged.append(asset)
        return merged

    def _candidate_routes(self, quote: str, universe: list[str]) -> list[list[str]]:
        routes: list[list[str]] = []
        for asset_a in universe:
            if asset_a == quote:
                continue
            for asset_b in universe:
                if asset_b in {quote, asset_a}:
                    continue
                routes.append([quote, asset_a, asset_b, quote])
        return routes

    def _evaluate_route(
        self,
        exchange_name: str,
        route: list[str],
        by_pair: dict[tuple[str, str], InstrumentMetadata],
    ) -> RouteDiscoveryCandidate:
        quote, asset_a, asset_b, end_quote = route
        symbols = [f"{asset_a}/{quote}", f"{asset_b}/{asset_a}", f"{asset_b}/{quote}"]
        reasons: list[str] = []
        if quote != end_quote or len(route) != 4:
            reasons.append("invalid_route_shape")
        required_pairs = [(asset_a, quote), (asset_b, asset_a), (asset_b, quote)]
        metadata: list[InstrumentMetadata] = []
        for pair, symbol in zip(required_pairs, symbols, strict=True):
            instrument = by_pair.get(pair)
            if instrument is None:
                reasons.append(f"missing_symbol:{symbol}")
            else:
                metadata.append(instrument)
        depth = Decimal("0")
        volume = Decimal("0")
        if not reasons:
            depth, volume, reasons = self._liquidity_checks(exchange_name, symbols, metadata)
        status = "filtered" if reasons else "accepted"
        return RouteDiscoveryCandidate(
            route=route,
            symbols=symbols,
            status=status,
            reasons=reasons,
            route_depth_usdt=depth,
            quote_volume_usdt=volume,
            min_size_adjustments={item.symbol: str(item.min_size) for item in metadata},
            tick_sizes={item.symbol: str(item.tick_size) for item in metadata},
        )

    def _liquidity_checks(
        self,
        exchange_name: str,
        symbols: list[str],
        metadata: list[InstrumentMetadata],
    ) -> tuple[Decimal, Decimal, list[str]]:
        exchange = self.exchanges.get(exchange_name)
        reasons: list[str] = []
        tickers = []
        books = []
        for symbol in symbols:
            try:
                tickers.append(exchange.get_ticker(symbol))
                books.append(exchange.get_orderbook(symbol))
            except ExchangeError as exc:
                reasons.append(f"market_data_error:{exc}")
                return Decimal("0"), Decimal("0"), reasons
        first_bid = tickers[0].bid
        first_depth = books[0].depth_notional("ask")
        second_depth_usdt = books[1].depth_notional("ask") * first_bid
        third_depth = books[2].depth_notional("bid")
        route_depth = min(first_depth, second_depth_usdt, third_depth)
        volume = min(ticker.volume for ticker in tickers)
        if route_depth < self.settings.arbitrage.min_route_depth_usdt:
            reasons.append("route_depth_below_minimum")
        if any(item.min_size <= 0 for item in metadata):
            reasons.append("instrument_min_size_missing")
        if any(item.tick_size <= 0 for item in metadata):
            reasons.append("instrument_tick_size_missing")
        trade_size = self.settings.arbitrage.trade_size_usdt
        first_amount = trade_size / tickers[0].ask if tickers[0].ask else Decimal("0")
        second_amount = first_amount / tickers[1].ask if tickers[1].ask else Decimal("0")
        if first_amount < metadata[0].min_size:
            reasons.append(f"min_size_not_met:{symbols[0]}")
        if second_amount < metadata[1].min_size:
            reasons.append(f"min_size_not_met:{symbols[1]}")
        if second_amount < metadata[2].min_size:
            reasons.append(f"min_size_not_met:{symbols[2]}")
        return route_depth, volume, reasons


def _bulk_ticker_volume_by_symbol(exchange: Any) -> dict[str, Decimal]:
    """Return bulk spot ticker volumes when an adapter exposes an OKX-like client."""
    client = getattr(exchange, "client", None)
    list_tickers = getattr(client, "list_tickers", None)
    if list_tickers is None:
        return {}
    try:
        rows = list_tickers("SPOT")
    except Exception:
        return {}
    volumes: dict[str, Decimal] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        inst_id = str(row.get("instId", ""))
        if not inst_id:
            continue
        symbol = inst_id.replace("-", "/")
        volumes[symbol] = Decimal(str(row.get("volCcy24h", row.get("vol24h", "0")) or "0"))
    return volumes
