"""Dry-run order simulator."""

from __future__ import annotations

from decimal import Decimal

from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.execution.order import SimulatedOrder


class OrderSimulator:
    """Convert opportunity legs into simulated orders."""

    def simulate(self, opportunity: ArbitrageOpportunity) -> list[SimulatedOrder]:
        """Create simulated order legs from opportunity metadata."""
        legs = opportunity.metadata.get("legs", [])
        quantity = Decimal(str(opportunity.metadata.get("quantity", "0")))
        if quantity == 0:
            quantity = opportunity.required_capital / Decimal(str(legs[0].get("price", "1"))) if legs else Decimal("0")
        orders: list[SimulatedOrder] = []
        for leg in legs:
            price = Decimal(str(leg["price"]))
            leg_quantity = Decimal(str(leg.get("quantity", quantity)))
            orders.append(
                SimulatedOrder(
                    exchange=str(leg["exchange"]),
                    symbol=str(leg["symbol"]),
                    side=leg["side"],
                    price=price,
                    quantity=leg_quantity,
                    notional=price * leg_quantity,
                    status="simulated",
                )
            )
        return orders
