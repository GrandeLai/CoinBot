"""Configurable multi-route triangular arbitrage scanner."""

from __future__ import annotations

from decimal import Decimal

from trading_assistant.arbitrage.calculator import (
    DepthFillEstimate,
    calculate_risk_score,
    calculate_slippage,
    estimate_depth_fill,
    has_sufficient_depth,
    percent,
)
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.arbitrage.route_discovery import TriangularRouteDiscoveryService
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.base import InstrumentMetadata, OrderBook
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.exceptions import ExchangeError


class TriangularMultiRouteScanner:
    """Scan configured USDT -> asset A -> asset B -> USDT triangular paths."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def scan(self, exchange_name: str = "mock", route_mode: str = "configured") -> list[ArbitrageOpportunity]:
        """Return profitable configured or discovered triangular routes."""
        exchange = self.exchanges.get(exchange_name)
        opportunities: list[ArbitrageOpportunity] = []
        routes = self._routes(exchange_name, route_mode)
        metadata = {item.symbol: item for item in exchange.list_instruments("spot")}
        for route in routes:
            if len(route) != 4 or route[0] != route[-1]:
                continue
            try:
                opportunity = self._scan_route(exchange_name=exchange.name, route=route, metadata=metadata)
            except ExchangeError:
                continue
            if opportunity is not None:
                opportunities.append(opportunity)
        return sorted(opportunities, key=lambda item: item.net_profit, reverse=True)

    def _routes(self, exchange_name: str, route_mode: str) -> list[list[str]]:
        if route_mode != "discovered":
            return self.settings.arbitrage.triangular_routes
        report = TriangularRouteDiscoveryService(self.settings, self.exchanges).discover(exchange_name=exchange_name)
        return [candidate.route for candidate in report.accepted_routes]

    def _scan_route(
        self,
        exchange_name: str,
        route: list[str],
        metadata: dict[str, InstrumentMetadata] | None = None,
    ) -> ArbitrageOpportunity | None:
        quote_asset, asset_a, asset_b, _ = [item.upper() for item in route]
        exchange = self.exchanges.get(exchange_name)
        capital = self.settings.arbitrage.trade_size_usdt
        first_symbol = f"{asset_a}/{quote_asset}"
        second_symbol = f"{asset_b}/{asset_a}"
        third_symbol = f"{asset_b}/{quote_asset}"
        first = exchange.get_ticker(first_symbol)
        second = exchange.get_ticker(second_symbol)
        third = exchange.get_ticker(third_symbol)
        first_book = exchange.get_orderbook(first_symbol)
        second_book = exchange.get_orderbook(second_symbol)
        third_book = exchange.get_orderbook(third_symbol)
        metadata = metadata or {item.symbol: item for item in exchange.list_instruments("spot")}
        first_fill = estimate_depth_fill(first_book, "ask", capital)
        if not first_fill.complete:
            return None
        asset_a_amount = first_fill.filled_base
        second_fill = estimate_depth_fill(second_book, "ask", asset_a_amount)
        if not second_fill.complete:
            return None
        asset_b_amount = second_fill.filled_base
        third_fill = _estimate_base_sell_fill(third_book, asset_b_amount)
        if not third_fill["complete"]:
            return None
        size_adjustments = _min_size_adjustments(
            {
                first_symbol: metadata.get(first_symbol),
                second_symbol: metadata.get(second_symbol),
                third_symbol: metadata.get(third_symbol),
            },
            {first_symbol: asset_a_amount, second_symbol: asset_b_amount, third_symbol: asset_b_amount},
        )
        if any(value != Decimal("0") for value in size_adjustments.values()):
            return None
        final_quote = Decimal(str(third_fill["filled_quote"]))
        gross_profit = final_quote - capital
        leg_notional_usdt = capital + (second_fill.filled_notional * first_fill.average_price) + final_quote
        fees = leg_notional_usdt * self.settings.arbitrage.fee_pct
        orderbook_slippage = _orderbook_slippage_usdt(first_fill, second_fill, third_fill, first_fill.average_price)
        configured_slippage = calculate_slippage(capital, self.settings.arbitrage.slippage_pct, legs=3)
        slippage = max(orderbook_slippage, configured_slippage)
        net_profit = gross_profit - fees - slippage
        net_profit_pct = percent(net_profit, capital)
        first_depth = first_book.depth_notional("ask")
        second_depth_asset_a = second_book.depth_notional("ask")
        third_depth = third_book.depth_notional("bid")
        second_depth_quote = second_depth_asset_a * first.bid
        route_depth = min(first_depth, second_depth_quote, third_depth)
        if net_profit_pct < self.settings.arbitrage.min_net_profit_pct:
            return None
        if route_depth < self.settings.arbitrage.min_route_depth_usdt:
            return None
        if not has_sufficient_depth(first_book, "ask", capital):
            return None
        if second_depth_asset_a < asset_a_amount:
            return None
        if not has_sufficient_depth(third_book, "bid", capital):
            return None
        route_id = "-".join(item.lower() for item in route)
        return ArbitrageOpportunity(
            opportunity_id=f"triangular-multi-route-{exchange.name}-{route_id}",
            strategy_type="triangular-multi-route",
            symbol="/".join(route),
            buy_exchange=exchange.name,
            sell_exchange=exchange.name,
            expected_profit=gross_profit,
            expected_profit_pct=percent(gross_profit, capital),
            estimated_fee=fees,
            estimated_slippage=slippage,
            required_capital=capital,
            net_profit=net_profit,
            risk_score=calculate_risk_score(net_profit_pct, self.settings.arbitrage.slippage_pct, route_depth),
            confidence=Decimal("0.79"),
            metadata={
                "route": route,
                "final_quote": final_quote,
                "route_depth_usdt": route_depth,
                "legacy_strategy_alias": "triangular",
                "preflight_quality": {
                    "route_mode": "multi_level_orderbook",
                    "fee_estimate_usdt": fees,
                    "slippage_estimate_usdt": slippage,
                    "min_size_adjustments": {symbol: str(value) for symbol, value in size_adjustments.items()},
                    "net_positive_after_precision": net_profit > 0,
                },
                "legs": [
                    {
                        "exchange": exchange.name,
                        "side": "buy",
                        "market": "spot",
                        "symbol": first.symbol,
                        "price": first_fill.average_price,
                        "expected_fill_price": first_fill.average_price,
                        "submitted_limit_price": _submitted_limit_price(
                            first_fill.average_price,
                            metadata.get(first_symbol),
                            side="buy",
                            buffer_pct=self.settings.strategy_runtime.demo_limit_price_buffer_pct,
                        ),
                        "depth_consumed_pct": percent(first_fill.filled_notional, first_depth),
                        "slippage_estimate": (first_fill.average_price - first_fill.reference_price) * asset_a_amount,
                        "fee_estimate": capital * self.settings.arbitrage.fee_pct,
                        "min_size_adjustment": size_adjustments[first_symbol],
                        "quantity": asset_a_amount,
                    },
                    {
                        "exchange": exchange.name,
                        "side": "buy",
                        "market": "spot",
                        "symbol": second.symbol,
                        "price": second_fill.average_price,
                        "expected_fill_price": second_fill.average_price,
                        "submitted_limit_price": _submitted_limit_price(
                            second_fill.average_price,
                            metadata.get(second_symbol),
                            side="buy",
                            buffer_pct=self.settings.strategy_runtime.demo_limit_price_buffer_pct,
                        ),
                        "depth_consumed_pct": percent(second_fill.filled_notional, second_depth_asset_a),
                        "slippage_estimate": (second_fill.average_price - second_fill.reference_price) * asset_b_amount * first_fill.average_price,
                        "fee_estimate": second_fill.filled_notional * first_fill.average_price * self.settings.arbitrage.fee_pct,
                        "min_size_adjustment": size_adjustments[second_symbol],
                        "quantity": asset_b_amount,
                    },
                    {
                        "exchange": exchange.name,
                        "side": "sell",
                        "market": "spot",
                        "symbol": third.symbol,
                        "price": third_fill["average_price"],
                        "expected_fill_price": third_fill["average_price"],
                        "submitted_limit_price": _submitted_limit_price(
                            Decimal(str(third_fill["average_price"])),
                            metadata.get(third_symbol),
                            side="sell",
                            buffer_pct=self.settings.strategy_runtime.demo_limit_price_buffer_pct,
                        ),
                        "depth_consumed_pct": percent(final_quote, third_depth),
                        "slippage_estimate": (third_fill["reference_price"] - third_fill["average_price"]) * asset_b_amount,
                        "fee_estimate": final_quote * self.settings.arbitrage.fee_pct,
                        "min_size_adjustment": size_adjustments[third_symbol],
                        "quantity": asset_b_amount,
                    },
                ],
            },
        )


def _estimate_base_sell_fill(orderbook: OrderBook, base_amount: Decimal) -> dict[str, Decimal | bool]:
    remaining = base_amount
    filled_base = Decimal("0")
    filled_quote = Decimal("0")
    for level in orderbook.bids:
        if remaining <= 0:
            break
        take_base = min(remaining, level.amount)
        filled_base += take_base
        filled_quote += take_base * level.price
        remaining -= take_base
    average_price = filled_quote / filled_base if filled_base else Decimal("0")
    reference_price = orderbook.best_bid.price
    return {
        "requested_base": base_amount,
        "filled_base": filled_base,
        "filled_quote": filled_quote,
        "average_price": average_price,
        "reference_price": reference_price,
        "complete": filled_base >= base_amount,
    }


def _min_size_adjustments(
    metadata: dict[str, InstrumentMetadata | None],
    quantities: dict[str, Decimal],
) -> dict[str, Decimal]:
    adjustments: dict[str, Decimal] = {}
    for symbol, quantity in quantities.items():
        instrument = metadata[symbol]
        min_size = instrument.min_size if instrument is not None else Decimal("0")
        adjustments[symbol] = Decimal("0") if min_size <= 0 or quantity >= min_size else min_size - quantity
    return adjustments


def _submitted_limit_price(
    expected_fill_price: Decimal,
    metadata: InstrumentMetadata | None,
    side: str,
    buffer_pct: Decimal,
) -> Decimal:
    buffered = expected_fill_price * (Decimal("1") + buffer_pct if side == "buy" else Decimal("1") - buffer_pct)
    tick_size = metadata.tick_size if metadata is not None else Decimal("0")
    if tick_size <= 0:
        return buffered
    steps = buffered // tick_size
    if side == "buy" and buffered % tick_size:
        steps += 1
    return steps * tick_size


def _orderbook_slippage_usdt(
    first_fill: DepthFillEstimate,
    second_fill: DepthFillEstimate,
    third_fill: dict[str, Decimal | bool],
    first_asset_price_usdt: Decimal,
) -> Decimal:
    first_slippage = (first_fill.average_price - first_fill.reference_price) * first_fill.filled_base
    second_slippage = (second_fill.average_price - second_fill.reference_price) * second_fill.filled_base * first_asset_price_usdt
    third_slippage = (Decimal(str(third_fill["reference_price"])) - Decimal(str(third_fill["average_price"]))) * Decimal(str(third_fill["filled_base"]))
    return max(first_slippage, Decimal("0")) + max(second_slippage, Decimal("0")) + max(third_slippage, Decimal("0"))
