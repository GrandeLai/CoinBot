"""OKX live broker adapter for guarded agent execution."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from coinbot_api.broker.okx import OKXTradingProvider
from coinbot_api.broker.types import CryptoOrderRequest, TradingOrderSide, TradingOrderType

from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.exceptions import SafetyError
from trading_assistant.execution.live_broker import LiveExecutionResult, LiveOrderReceipt


class OKXLiveBroker:
    """Submit OKX spot limit orders for already-approved opportunities."""

    def __init__(self, provider: Any | None = None, expected_demo: bool | None = None) -> None:
        self.provider = provider or OKXTradingProvider()
        self.expected_demo = expected_demo

    def execute(self, opportunity: ArbitrageOpportunity) -> LiveExecutionResult:
        """Submit all supported OKX spot legs."""
        if not bool(getattr(self.provider, "configured", False)):
            raise SafetyError("OKX provider is not configured")
        if self.expected_demo is not None and bool(getattr(self.provider, "demo", self.expected_demo)) != self.expected_demo:
            raise SafetyError("OKX provider demo mode does not match config")
        receipts: list[LiveOrderReceipt] = []
        for request in self._order_requests(opportunity):
            provider_order = self.provider.submit_order(
                CryptoOrderRequest(
                    symbol=request["symbol"],
                    side=TradingOrderSide(request["side"]),
                    order_type=TradingOrderType.LIMIT,
                    quantity=float(request["quantity"]),
                    price=float(request["price"]),
                )
            )
            receipts.append(
                LiveOrderReceipt(
                    exchange="okx",
                    order_id=str(getattr(provider_order, "order_id", "")),
                    symbol=str(getattr(provider_order, "symbol", request["symbol"])),
                    side=request["side"],
                    market=request["market"],
                    order_type=str(getattr(getattr(provider_order, "order_type", "limit"), "value", "limit")),
                    status=str(getattr(getattr(provider_order, "status", "submitted"), "value", "submitted")),
                    submitted_quantity=Decimal(str(getattr(provider_order, "quantity", request["quantity"]))),
                    submitted_price=_optional_decimal(getattr(provider_order, "submitted_price", request["price"])),
                    raw={"provider": "okx"},
                )
            )
        return LiveExecutionResult(
            opportunity_id=opportunity.opportunity_id,
            status="submitted",
            live_orders_sent=bool(receipts),
            orders=receipts,
            message="OKX spot limit orders submitted after agent live-trading gates passed.",
        )

    def _order_requests(self, opportunity: ArbitrageOpportunity) -> list[dict[str, Any]]:
        """Convert opportunity legs to OKX spot limit order requests."""
        legs = opportunity.metadata.get("legs", [])
        if not isinstance(legs, list) or not legs:
            raise SafetyError("OKX live execution requires opportunity metadata legs")

        quantity = Decimal(str(opportunity.metadata.get("quantity", "0")))
        requests: list[dict[str, Any]] = []
        for leg in legs:
            if not isinstance(leg, dict):
                raise SafetyError("OKX live execution requires structured legs")
            exchange = str(leg.get("exchange", ""))
            market = str(leg.get("market", "spot"))
            side = str(leg.get("side", ""))
            symbol = str(leg.get("symbol", opportunity.symbol))
            price = Decimal(str(leg.get("price", "0")))
            if exchange != "okx" or market != "spot" or side not in {"buy", "sell"} or price <= 0:
                raise SafetyError("OKX live broker currently only supports OKX spot limit orders")
            leg_quantity = quantity if quantity > 0 else opportunity.required_capital / price
            requests.append(
                {
                    "symbol": symbol,
                    "side": _side(side),
                    "market": market,
                    "quantity": leg_quantity,
                    "price": price,
                }
            )
        return requests


def _side(value: str) -> Literal["buy", "sell"]:
    """Type-narrow an order side after validation."""
    if value == "buy":
        return "buy"
    return "sell"


def _optional_decimal(value: Any) -> Decimal | None:
    """Convert optional provider values to Decimal."""
    if value is None:
        return None
    return Decimal(str(value))
