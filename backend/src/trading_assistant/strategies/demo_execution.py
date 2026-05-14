"""Controlled OKX Demo Trading execution for strategy runtime."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from typing import Any, Literal

from coinbot_api.broker.okx import OKXTradingProvider
from coinbot_api.broker.types import SwapOrderRequest, TradingOrderSide, TradingOrderType

from trading_assistant.config.schema import Settings
from trading_assistant.directional.position_store import DirectionalPositionStore, DirectionalStoredPosition
from trading_assistant.exceptions import SafetyError
from trading_assistant.utils.serialization import to_jsonable


InstrumentType = Literal["spot", "swap", "futures"]
OrderStatus = Literal["filled", "canceled", "submitted", "partial_filled", "unknown"]
TRIANGULAR_QUOTE_BUFFER = Decimal("0.9985")
TRIANGULAR_BASE_SELL_BUFFER = Decimal("0.999")
DIRECTIONAL_DEMO_STRATEGIES = {
    "trend-breakout",
    "mean-reversion-spot",
    "volatility-squeeze-breakout",
    "momentum-rotation",
}


@dataclass(frozen=True)
class DemoExecutionSpec:
    """One tiny OKX demo execution order."""

    instrument_type: InstrumentType
    symbol: str
    side: Literal["buy", "sell"]
    quantity: Decimal
    price: Decimal


@dataclass(frozen=True)
class DemoOrderExecution:
    """Normalized OKX demo order execution row."""

    order_id: str
    instrument_type: InstrumentType
    symbol: str
    side: Literal["buy", "sell"]
    quantity: Decimal
    submitted_price: Decimal
    executed_quantity: Decimal
    executed_price: Decimal
    status: OrderStatus
    canceled: bool
    order_id_suffix: str
    notional_usdt: Decimal

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe row."""
        return to_jsonable(self)


class StrategyDemoExecutionService:
    """Execute tiny round-trip strategy canaries on OKX Demo Trading."""

    def __init__(self, settings: Settings, provider: Any | None = None) -> None:
        self.settings = settings
        self.provider = provider or OKXTradingProvider()
        self._account_level: str | None = None

    def execute(self, strategy_name: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run one controlled demo strategy and return PnL evidence."""
        self._assert_demo_allowed(strategy_name)
        self._account_level = self._read_account_level()
        if strategy_name in DIRECTIONAL_DEMO_STRATEGIES:
            return self._execute_directional_lifecycle(strategy_name, context or {})
        account_before = self._account_snapshot()
        if strategy_name == "triangular":
            orders, sequence_status, abort_reason = self._execute_triangular_sequence()
        else:
            specs = self._order_specs(strategy_name)
            self._assert_order_caps(specs)
            orders, sequence_status, abort_reason = self._execute_order_sequence(specs)
        account_after = self._account_snapshot()
        reference_prices = self._reference_prices()
        gross_pnl = _strategy_order_gross_pnl(strategy_name, orders, reference_prices)
        fee = sum((order.notional_usdt for order in orders), Decimal("0")) * self.settings.arbitrage.taker_fee_pct
        net_pnl = gross_pnl - fee
        pnl_validation = self._pnl_validation(account_before, account_after, net_pnl, orders)
        return to_jsonable(
            {
                "strategy_name": strategy_name,
                "status": sequence_status,
                "abort_reason": abort_reason,
                "provider_demo": bool(getattr(self.provider, "demo", False)),
                "demo_orders_sent": bool(orders),
                "live_orders_sent": False,
                "account_mode": self._account_level,
                "orders": [order.to_dict() for order in orders],
                "gross_pnl_usdt": _money(gross_pnl),
                "estimated_fee_usdt": _money(fee),
                "net_pnl_usdt": _money(net_pnl),
                "pnl_validation": pnl_validation,
                "account_before": account_before,
                "account_after": account_after,
            }
        )

    def _execute_directional_lifecycle(self, strategy_name: str, context: dict[str, Any]) -> dict[str, Any]:
        """Open, hold, or close one managed long-only OKX demo spot position."""
        account_before = self._account_snapshot()
        store = self._directional_store()
        symbol = self._directional_symbol(strategy_name, context)
        position = store.get(strategy_name, symbol)
        if position is None or position.state != "open":
            return self._execute_directional_entry(strategy_name, symbol, context, account_before, store)
        exit_reason = self._directional_exit_reason(position)
        if exit_reason is None:
            account_after = self._account_snapshot()
            current_price = _price(self.provider, position.symbol)
            unrealized = (current_price - position.entry_price) * position.quantity
            return to_jsonable(
                {
                    "strategy_name": strategy_name,
                    "strategy_family": "directional",
                    "status": "open",
                    "abort_reason": None,
                    "provider_demo": bool(getattr(self.provider, "demo", False)),
                    "demo_orders_sent": False,
                    "live_orders_sent": False,
                    "account_mode": self._account_level,
                    "orders": [],
                    "gross_pnl_usdt": _money(unrealized),
                    "estimated_fee_usdt": _money(Decimal("0")),
                    "net_pnl_usdt": _money(Decimal("0")),
                    "pnl_validation": self._directional_managed_position_validation(position, current_price),
                    "position_lifecycle": position.to_dict(),
                    "account_before": account_before,
                    "account_after": account_after,
                }
            )
        spec = self._directional_exit_spec(position)
        self._assert_order_caps([spec])
        order = self._submit_wait_close(spec)
        account_after = self._account_snapshot()
        if not _order_completed(order, spec):
            return to_jsonable(
                {
                    "strategy_name": strategy_name,
                    "strategy_family": "directional",
                    "status": "exit_submitted",
                    "abort_reason": _abort_reason(spec, order),
                    "provider_demo": bool(getattr(self.provider, "demo", False)),
                    "demo_orders_sent": True,
                    "live_orders_sent": False,
                    "account_mode": self._account_level,
                    "orders": [order.to_dict()],
                    "gross_pnl_usdt": _money(Decimal("0")),
                    "estimated_fee_usdt": _money(order.notional_usdt * self.settings.arbitrage.taker_fee_pct),
                    "net_pnl_usdt": _money(Decimal("0")),
                    "pnl_validation": self._directional_managed_position_validation(position, order.executed_price),
                    "position_lifecycle": position.to_dict(),
                    "account_before": account_before,
                    "account_after": account_after,
                }
            )
        fee = (position.entry_notional_usdt + order.notional_usdt) * self.settings.arbitrage.taker_fee_pct
        gross_pnl = order.notional_usdt - position.entry_notional_usdt
        net_pnl = gross_pnl - fee
        closed = store.mark_closed(
            position,
            exit_price=order.executed_price,
            realized_pnl_usdt=net_pnl,
            exit_reason=exit_reason,
        )
        return to_jsonable(
            {
                "strategy_name": strategy_name,
                "strategy_family": "directional",
                "status": "closed",
                "abort_reason": None,
                "provider_demo": bool(getattr(self.provider, "demo", False)),
                "demo_orders_sent": True,
                "live_orders_sent": False,
                "account_mode": self._account_level,
                "orders": [order.to_dict()],
                "gross_pnl_usdt": _money(gross_pnl),
                "estimated_fee_usdt": _money(fee),
                "net_pnl_usdt": _money(net_pnl),
                "pnl_validation": self._directional_closed_position_validation(position, order, net_pnl),
                "position_lifecycle": closed.to_dict(),
                "account_before": account_before,
                "account_after": account_after,
            }
        )

    def _execute_directional_entry(
        self,
        strategy_name: str,
        symbol: str,
        context: dict[str, Any],
        account_before: dict[str, Any],
        store: DirectionalPositionStore,
    ) -> dict[str, Any]:
        """Submit one managed directional spot entry and persist it when filled."""
        spec = self._directional_entry_spec(strategy_name, symbol)
        self._assert_order_caps([spec])
        order = self._submit_wait_close(spec)
        account_after = self._account_snapshot()
        fee = order.notional_usdt * self.settings.arbitrage.taker_fee_pct
        if not _order_completed(order, spec):
            return to_jsonable(
                {
                    "strategy_name": strategy_name,
                    "strategy_family": "directional",
                    "status": "aborted",
                    "abort_reason": _abort_reason(spec, order),
                    "provider_demo": bool(getattr(self.provider, "demo", False)),
                    "demo_orders_sent": True,
                    "live_orders_sent": False,
                    "account_mode": self._account_level,
                    "orders": [order.to_dict()],
                    "gross_pnl_usdt": _money(Decimal("0")),
                    "estimated_fee_usdt": _money(fee),
                    "net_pnl_usdt": _money(Decimal("0")),
                    "pnl_validation": {"method": "directional_entry_not_filled", "within_tolerance": True},
                    "position_lifecycle": {
                        "strategy_name": strategy_name,
                        "symbol": symbol,
                        "state": "aborted",
                    },
                    "account_before": account_before,
                    "account_after": account_after,
                }
            )
        profile = _directional_profile(strategy_name)
        now = _utcnow()
        position = DirectionalStoredPosition(
            strategy_name=strategy_name,
            symbol=symbol,
            exchange="okx",
            state="open",
            quantity=order.executed_quantity,
            entry_price=order.executed_price,
            entry_notional_usdt=order.notional_usdt,
            stop_loss_pct=Decimal(str(profile["stop_loss_pct"])),
            take_profit_pct=Decimal(str(profile["take_profit_pct"])),
            time_limit_minutes=int(profile["time_limit_minutes"]),
            opened_at=now,
            updated_at=now,
        )
        store.save(position)
        return to_jsonable(
            {
                "strategy_name": strategy_name,
                "strategy_family": "directional",
                "status": "open",
                "abort_reason": None,
                "provider_demo": bool(getattr(self.provider, "demo", False)),
                "demo_orders_sent": True,
                "live_orders_sent": False,
                "account_mode": self._account_level,
                "orders": [order.to_dict()],
                "gross_pnl_usdt": _money(Decimal("0")),
                "estimated_fee_usdt": _money(fee),
                "net_pnl_usdt": _money(Decimal("0")),
                "pnl_validation": self._directional_managed_position_validation(position, order.executed_price),
                "position_lifecycle": position.to_dict(),
                "local_signal": {
                    "selected_opportunity_id": context.get("selected_opportunity_id"),
                    "source": "local_validation_gate",
                },
                "account_before": account_before,
                "account_after": account_after,
            }
        )

    def _execute_order_sequence(self, specs: list[DemoExecutionSpec]) -> tuple[list[DemoOrderExecution], str, str | None]:
        """Execute legs sequentially and unwind filled legs when a leg cannot complete."""
        orders: list[DemoOrderExecution] = []
        for spec in specs:
            order = self._submit_wait_close(spec)
            orders.append(order)
            if not _order_completed(order, spec):
                abort_reason = (
                    f"leg_not_filled:{spec.instrument_type}:{spec.symbol}:{spec.side}:"
                    f"{order.status}:filled={order.executed_quantity}"
                )
                orders.extend(self._unwind_filled_orders(orders[:-1]))
                return orders, "aborted_unwound", abort_reason
        return orders, "closed", None

    def _execute_triangular_sequence(self) -> tuple[list[DemoOrderExecution], str, str | None]:
        """Execute a triangular canary with dynamic sizes based on actual filled inventory."""
        multiplier = self.settings.strategy_runtime.demo_order_size_multiplier
        btc_qty = (Decimal("0.0001") * multiplier).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
        first = DemoExecutionSpec("spot", "BTC/USDT", "buy", btc_qty, self._spot_market_buy_price("BTC/USDT"))
        self._assert_order_caps([first])
        orders = [self._submit_wait_close(first)]
        if not _order_completed(orders[-1], first):
            return orders, "aborted_unwound", _abort_reason(first, orders[-1])

        eth_btc_price = self._spot_market_buy_price("ETH/BTC", Decimal("0.000001"))
        btc_available_for_eth = (orders[-1].executed_quantity * TRIANGULAR_QUOTE_BUFFER).quantize(
            Decimal("0.00000001"),
            rounding=ROUND_DOWN,
        )
        eth_qty = (btc_available_for_eth / eth_btc_price).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
        second = DemoExecutionSpec("spot", "ETH/BTC", "buy", eth_qty, eth_btc_price)
        self._assert_order_caps([second])
        orders.append(self._submit_wait_close(second))
        if not _order_completed(orders[-1], second):
            abort_reason = _abort_reason(second, orders[-1])
            orders.extend(self._unwind_filled_orders([orders[0]]))
            return orders, "aborted_unwound", abort_reason

        eth_sell_qty = (orders[-1].executed_quantity * TRIANGULAR_BASE_SELL_BUFFER).quantize(
            Decimal("0.000001"),
            rounding=ROUND_DOWN,
        )
        third = DemoExecutionSpec("spot", "ETH/USDT", "sell", eth_sell_qty, self._spot_market_sell_price("ETH/USDT"))
        self._assert_order_caps([third])
        orders.append(self._submit_wait_close(third))
        if not _order_completed(orders[-1], third):
            abort_reason = _abort_reason(third, orders[-1])
            orders.extend(self._unwind_filled_orders([orders[1]]))
            return orders, "aborted_unwound", abort_reason
        return orders, "closed", None

    def _unwind_filled_orders(self, orders: list[DemoOrderExecution]) -> list[DemoOrderExecution]:
        """Submit opposite tiny orders to flatten already-filled demo legs."""
        unwinds: list[DemoOrderExecution] = []
        for order in reversed(orders):
            if order.executed_quantity <= 0:
                continue
            opposite_side: Literal["buy", "sell"] = "sell" if order.side == "buy" else "buy"
            tick = _price_tick(order.symbol)
            if order.instrument_type == "spot" and opposite_side == "sell":
                price = self._spot_market_sell_price(order.symbol, tick)
            elif order.instrument_type == "spot":
                price = self._spot_market_buy_price(order.symbol, tick)
            else:
                reference_price = _price_for_instrument(self.provider, order.instrument_type, order.symbol)
                price = (
                    _market_sell_price(reference_price, tick, self._limit_price_buffer_pct())
                    if opposite_side == "sell"
                    else _market_buy_price(reference_price, tick, self._limit_price_buffer_pct())
                )
            unwind_spec = DemoExecutionSpec(
                instrument_type=order.instrument_type,
                symbol=order.symbol,
                side=opposite_side,
                quantity=order.executed_quantity,
                price=price,
            )
            unwinds.append(self._submit_wait_close(unwind_spec))
        return unwinds

    def preview(self, strategy_name: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Estimate demo strategy PnL without submitting orders."""
        self._assert_demo_allowed(strategy_name)
        if strategy_name in DIRECTIONAL_DEMO_STRATEGIES:
            return self._preview_directional_lifecycle(strategy_name, context or {})
        specs = self._order_specs(strategy_name)
        self._assert_order_caps(specs)
        expected_specs = [replace(spec, price=self._expected_fill_price(spec)) for spec in specs]
        reference_prices = self._reference_prices()
        gross_pnl = _strategy_spec_gross_pnl(strategy_name, expected_specs, reference_prices)
        fee = sum((_estimated_notional(spec, reference_prices) for spec in expected_specs), Decimal("0")) * self.settings.arbitrage.taker_fee_pct
        net_pnl = gross_pnl - fee
        threshold = self.settings.strategy_runtime.demo_min_preflight_net_pnl_usdt
        approved = net_pnl >= threshold
        return to_jsonable(
            {
                "strategy_name": strategy_name,
                "approved": approved,
                "reason": "demo_preflight_profitable" if approved else "demo_preflight_not_profitable",
                "gross_pnl_usdt": _money(gross_pnl),
                "estimated_fee_usdt": _money(fee),
                "net_pnl_usdt": _money(net_pnl),
                "min_required_net_pnl_usdt": _money(threshold),
                "orders": [
                    {
                        "instrument_type": spec.instrument_type,
                        "symbol": spec.symbol,
                        "side": spec.side,
                        "quantity": spec.quantity,
                        "price": spec.price,
                        "submitted_limit_price": spec.price,
                        "expected_fill_price": expected_spec.price,
                        "limit_buffer_pct": self._limit_price_buffer_pct(),
                        "estimated_notional_usdt": _money(_estimated_notional(expected_spec, reference_prices)),
                        "submitted_limit_notional_usdt": _money(_estimated_notional(spec, reference_prices)),
                    }
                    for spec, expected_spec in zip(specs, expected_specs, strict=True)
                ],
            }
        )

    def _preview_directional_lifecycle(self, strategy_name: str, context: dict[str, Any]) -> dict[str, Any]:
        """Preview the next managed directional demo lifecycle action."""
        store = self._directional_store()
        symbol = self._directional_symbol(strategy_name, context)
        position = store.get(strategy_name, symbol)
        if position is not None and position.state == "open":
            exit_reason = self._directional_exit_reason(position)
            current_price = _price(self.provider, position.symbol)
            unrealized = (current_price - position.entry_price) * position.quantity
            if exit_reason is None:
                return to_jsonable(
                    {
                        "strategy_name": strategy_name,
                        "strategy_family": "directional",
                        "approved": False,
                        "reason": "directional_position_hold",
                        "gross_pnl_usdt": _money(unrealized),
                        "estimated_fee_usdt": _money(Decimal("0")),
                        "net_pnl_usdt": _money(Decimal("0")),
                        "min_required_net_pnl_usdt": _money(self.settings.strategy_runtime.demo_min_preflight_net_pnl_usdt),
                        "orders": [],
                        "open_position": position.to_dict(),
                    }
                )
            spec = self._directional_exit_spec(position)
            self._assert_order_caps([spec])
            fee = _estimated_notional(spec, self._reference_prices()) * self.settings.arbitrage.taker_fee_pct
            net_pnl = unrealized - fee
            return to_jsonable(
                {
                    "strategy_name": strategy_name,
                    "strategy_family": "directional",
                    "approved": True,
                    "reason": f"directional_exit_{exit_reason}",
                    "gross_pnl_usdt": _money(unrealized),
                    "estimated_fee_usdt": _money(fee),
                    "net_pnl_usdt": _money(net_pnl),
                    "min_required_net_pnl_usdt": _money(self.settings.strategy_runtime.demo_min_preflight_net_pnl_usdt),
                    "orders": [self._preview_order(spec)],
                    "open_position": position.to_dict(),
                }
            )
        spec = self._directional_entry_spec(strategy_name, symbol)
        self._assert_order_caps([spec])
        threshold = self.settings.strategy_runtime.demo_min_preflight_net_pnl_usdt
        return to_jsonable(
            {
                "strategy_name": strategy_name,
                "strategy_family": "directional",
                "approved": True,
                "reason": "directional_entry_gate_passed",
                "gross_pnl_usdt": _money(Decimal("0")),
                "estimated_fee_usdt": _money(_estimated_notional(spec, self._reference_prices()) * self.settings.arbitrage.taker_fee_pct),
                "net_pnl_usdt": _money(threshold),
                "min_required_net_pnl_usdt": _money(threshold),
                "orders": [self._preview_order(spec)],
                "open_position": None,
            }
        )

    def _assert_demo_allowed(self, strategy_name: str) -> None:
        """Require explicit OKX demo settings and reject live trading."""
        okx = self.settings.exchanges.get("okx")
        if self.settings.trading.live_trading:
            raise SafetyError("strategy demo execution requires trading.live_trading=false")
        if okx is None or not okx.enabled or not okx.sandbox or okx.okx_demo is not True:
            raise SafetyError("strategy demo execution requires enabled OKX sandbox with okx_demo=true")
        if not self.settings.agent_trading.allow_demo_orders:
            raise SafetyError("strategy demo execution requires agent_trading.allow_demo_orders=true")
        if self.settings.agent_trading.strategy_allowlist and strategy_name not in self.settings.agent_trading.strategy_allowlist:
            raise SafetyError(f"strategy demo execution requires strategy allowlist entry: {strategy_name}")
        if not bool(getattr(self.provider, "configured", False)):
            raise SafetyError("OKX provider is not configured")
        if not bool(getattr(self.provider, "demo", False)):
            raise SafetyError("OKX provider is not in demo mode")

    def _read_account_level(self) -> str:
        """Read current OKX account mode."""
        if not hasattr(self.provider, "_get"):
            return "unknown"
        payload = self.provider._get("/api/v5/account/config", signed=True)
        rows = payload.get("data") or []
        if not rows:
            raise SafetyError("OKX account config returned no data")
        return str(rows[0].get("acctLv", "unknown"))

    def _account_snapshot(self) -> dict[str, Any]:
        """Return a redacted account balance snapshot."""
        if not hasattr(self.provider, "get_account"):
            return {}
        account = self.provider.get_account()
        rows: dict[str, Any] = {}
        for balance in getattr(account, "balances", []):
            rows[str(getattr(balance, "asset", ""))] = {
                "free": str(getattr(balance, "free", "0")),
                "locked": str(getattr(balance, "locked", "0")),
                "total": str(getattr(balance, "total", "0")),
            }
        return rows

    def _assert_order_caps(self, specs: list[DemoExecutionSpec]) -> None:
        """Keep demo canary orders inside runtime and agent caps."""
        max_notional = min(
            self.settings.strategy_runtime.max_position_value_usdt,
            self.settings.strategy_runtime.demo_max_order_value_usdt,
            self.settings.agent_trading.max_autonomous_order_value_usdt,
        )
        for spec in specs:
            notional = _estimated_notional(spec, self._reference_prices())
            if notional > max_notional:
                raise SafetyError(f"strategy demo execution order exceeds cap: {notional} > {max_notional}")

    def _submit_wait_close(self, spec: DemoExecutionSpec) -> DemoOrderExecution:
        """Submit an order, wait briefly, and cancel if it remains open."""
        try:
            order_id = self._submit(spec)
        except ValueError as exc:
            adjusted = self._adjust_spot_price_after_limit_rejection(spec, exc)
            if adjusted is None:
                raise
            self._assert_order_caps([adjusted])
            spec = adjusted
            order_id = self._submit(spec)
        detail = self._poll_order(spec, order_id)
        status = _status(detail)
        canceled = False
        if status not in {"filled", "canceled"}:
            self.provider.cancel_order(_cancel_symbol(spec), order_id)
            canceled = True
            detail = self._fetch_order_detail(spec, order_id)
            status = _status(detail)
        executed_quantity = Decimal(str(detail.get("accFillSz") or detail.get("fillSz", "0") or "0"))
        executed_price = Decimal(str(detail.get("avgPx", "0") or "0"))
        if executed_price <= 0:
            executed_price = spec.price
        return DemoOrderExecution(
            order_id=order_id,
            instrument_type=spec.instrument_type,
            symbol=spec.symbol,
            side=spec.side,
            quantity=spec.quantity,
            submitted_price=spec.price,
            executed_quantity=executed_quantity,
            executed_price=executed_price,
            status=status,
            canceled=canceled or status == "canceled",
            order_id_suffix=order_id[-8:],
            notional_usdt=_estimated_notional(
                DemoExecutionSpec(
                    instrument_type=spec.instrument_type,
                    symbol=spec.symbol,
                    side=spec.side,
                    quantity=executed_quantity,
                    price=executed_price,
                ),
                self._reference_prices(),
            ),
        )

    def _adjust_spot_price_after_limit_rejection(self, spec: DemoExecutionSpec, exc: ValueError) -> DemoExecutionSpec | None:
        """Refresh OKX spot price limits once after a dynamic price-limit rejection."""
        if spec.instrument_type != "spot" or "price limit" not in str(exc).lower():
            return None
        limit = _spot_price_limit(self.provider, spec.symbol, spec.side)
        if limit is None:
            return None
        tick = _price_tick(spec.symbol)
        adjusted_price = _floor_to_tick(limit, tick) if spec.side == "buy" else _ceil_to_tick(limit, tick)
        if adjusted_price == spec.price:
            return None
        return replace(spec, price=adjusted_price)

    def _submit(self, spec: DemoExecutionSpec) -> str:
        """Submit a spot, swap, or futures order and return the OKX order id."""
        if spec.instrument_type == "spot":
            response = self.provider._post(
                "/api/v5/trade/order",
                {
                    "instId": _spot_inst_id(spec.symbol),
                    "tdMode": self._spot_td_mode(),
                    "side": spec.side,
                    "ordType": "limit",
                    "sz": str(spec.quantity),
                    "px": str(spec.price),
                },
            )
            rows = response.get("data") or []
            if not rows or not rows[0].get("ordId"):
                raise SafetyError("OKX demo spot order response did not include ordId")
            return str(rows[0]["ordId"])
        if spec.instrument_type == "futures":
            response = self.provider._post(
                "/api/v5/trade/order",
                {
                    "instId": spec.symbol,
                    "tdMode": "cross",
                    "side": spec.side,
                    "posSide": "net",
                    "ordType": "limit",
                    "sz": str(spec.quantity),
                    "px": str(spec.price),
                    "lever": "1",
                },
            )
            rows = response.get("data") or []
            if not rows or not rows[0].get("ordId"):
                raise SafetyError("OKX demo futures order response did not include ordId")
            return str(rows[0]["ordId"])
        provider_order = self.provider.submit_swap_order(
            SwapOrderRequest(
                inst_id=_swap_inst_id(spec.symbol),
                side=TradingOrderSide(spec.side),
                order_type=TradingOrderType.LIMIT,
                sz=float(spec.quantity),
                price=float(spec.price),
                pos_side="net",
                margin_mode="cross",
                lever="1",
            )
        )
        order_id = str(getattr(provider_order, "order_id", ""))
        if not order_id:
            raise SafetyError("OKX demo swap order response did not include order id")
        return order_id

    def _poll_order(self, spec: DemoExecutionSpec, order_id: str) -> dict[str, Any]:
        """Poll an order until it fills or the demo TTL expires."""
        deadline = time.monotonic() + self.settings.strategy_runtime.demo_order_wait_seconds
        detail = self._fetch_order_detail(spec, order_id)
        while _status(detail) not in {"filled", "canceled"} and time.monotonic() < deadline:
            time.sleep(float(self.settings.strategy_runtime.demo_order_poll_interval_seconds))
            detail = self._fetch_order_detail(spec, order_id)
        return detail

    def _fetch_order_detail(self, spec: DemoExecutionSpec, order_id: str) -> dict[str, Any]:
        """Fetch one OKX order detail row."""
        payload = self.provider._get(
            "/api/v5/trade/order",
            {"instId": _inst_id(spec), "ordId": order_id},
            signed=True,
        )
        rows = payload.get("data") or []
        if not rows:
            raise SafetyError(f"OKX demo order detail returned no data: {order_id[-8:]}")
        return dict(rows[0])

    def _directional_store(self) -> DirectionalPositionStore:
        """Return the configured persistent directional position store."""
        return DirectionalPositionStore(self.settings.directional.position_state_path)

    def _directional_symbol(self, strategy_name: str, context: dict[str, Any]) -> str:
        """Return the symbol selected by local validation, falling back to BTC/USDT."""
        opportunity_id = str(context.get("selected_opportunity_id") or "")
        prefix = f"directional-{strategy_name}-"
        if opportunity_id.startswith(prefix):
            suffix = opportunity_id[len(prefix) :]
            parts = suffix.split("-")
            if len(parts) >= 2:
                return f"{parts[0].upper()}/{parts[1].upper()}"
        raw_symbol = context.get("symbol")
        if isinstance(raw_symbol, str) and "/" in raw_symbol:
            return raw_symbol.upper()
        return "BTC/USDT"

    def _directional_entry_spec(self, strategy_name: str, symbol: str) -> DemoExecutionSpec:
        """Return one marketable long-only spot entry spec for a directional signal."""
        del strategy_name
        price = self._spot_market_buy_price(symbol, _price_tick(symbol))
        max_notional = min(
            self.settings.directional.demo_max_order_value_usdt,
            self.settings.strategy_runtime.demo_max_order_value_usdt,
            self.settings.agent_trading.max_autonomous_order_value_usdt,
        )
        quantity = (max_notional / price).quantize(_quantity_step(symbol), rounding=ROUND_DOWN)
        if quantity <= 0:
            raise SafetyError(f"directional demo quantity rounds to zero for {symbol}")
        return DemoExecutionSpec("spot", symbol, "buy", quantity, price)

    def _directional_exit_spec(self, position: DirectionalStoredPosition) -> DemoExecutionSpec:
        """Return one marketable spot exit spec for a managed directional position."""
        return DemoExecutionSpec(
            "spot",
            position.symbol,
            "sell",
            position.quantity.quantize(_quantity_step(position.symbol), rounding=ROUND_DOWN),
            self._spot_market_sell_price(position.symbol, _price_tick(position.symbol)),
        )

    def _directional_exit_reason(self, position: DirectionalStoredPosition) -> str | None:
        """Return the first exit trigger for an open directional position."""
        current_price = _price(self.provider, position.symbol)
        take_profit_price = position.entry_price * (Decimal("1") + position.take_profit_pct / Decimal("100"))
        stop_loss_price = position.entry_price * (Decimal("1") - position.stop_loss_pct / Decimal("100"))
        if current_price >= take_profit_price:
            return "take_profit"
        if current_price <= stop_loss_price:
            return "stop_loss"
        if position.opened_at + timedelta(minutes=position.time_limit_minutes) <= _utcnow():
            return "time_limit"
        return None

    def _preview_order(self, spec: DemoExecutionSpec) -> dict[str, Any]:
        """Return a JSON-safe preview row for one planned order."""
        reference_prices = self._reference_prices()
        return {
            "instrument_type": spec.instrument_type,
            "symbol": spec.symbol,
            "side": spec.side,
            "quantity": spec.quantity,
            "price": spec.price,
            "submitted_limit_price": spec.price,
            "expected_fill_price": self._expected_fill_price(spec),
            "limit_buffer_pct": self._limit_price_buffer_pct(),
            "estimated_notional_usdt": _money(_estimated_notional(spec, reference_prices)),
            "submitted_limit_notional_usdt": _money(_estimated_notional(spec, reference_prices)),
        }

    def _directional_managed_position_validation(
        self,
        position: DirectionalStoredPosition,
        current_price: Decimal,
    ) -> dict[str, Any]:
        """Return validation evidence for a deliberately managed open spot inventory."""
        current_value = current_price * position.quantity
        unrealized = current_value - position.entry_notional_usdt
        return to_jsonable(
            {
                "method": "managed_directional_open_position",
                "cash_flow_net_pnl_usdt": "0.000000",
                "equity_delta_usdt": None,
                "difference_usdt": "0.000000",
                "tolerance_usdt": _money(self.settings.strategy_runtime.demo_pnl_reconciliation_tolerance_usdt),
                "within_tolerance": True,
                "residual_inventory_usdt": _money(current_value),
                "residual_inventory_tolerance_usdt": _money(self.settings.directional.max_position_value_usdt),
                "residual_inventory_within_tolerance": current_value <= self.settings.directional.max_position_value_usdt,
                "managed_position": position.to_dict(),
                "unrealized_pnl_usdt": _money(unrealized),
                "exchange_receipts": {"source": "managed_position_state", "complete": True},
            }
        )

    def _directional_closed_position_validation(
        self,
        position: DirectionalStoredPosition,
        order: DemoOrderExecution,
        net_pnl: Decimal,
    ) -> dict[str, Any]:
        """Return validation evidence for a closed managed directional position."""
        return to_jsonable(
            {
                "method": "managed_directional_closed_position",
                "cash_flow_net_pnl_usdt": _money(net_pnl),
                "equity_delta_usdt": None,
                "difference_usdt": "0.000000",
                "tolerance_usdt": _money(self.settings.strategy_runtime.demo_pnl_reconciliation_tolerance_usdt),
                "within_tolerance": True,
                "residual_inventory_usdt": "0.000000",
                "residual_inventory_tolerance_usdt": _money(self.settings.strategy_runtime.demo_residual_inventory_tolerance_usdt),
                "residual_inventory_within_tolerance": True,
                "managed_position": position.to_dict(),
                "exit_order": order.to_dict(),
                "exchange_receipts": self._exchange_receipts([order], self._reference_prices()),
            }
        )

    def _order_specs(self, strategy_name: str) -> list[DemoExecutionSpec]:
        """Return tiny round-trip orders for one strategy."""
        btc_usdt = _price(self.provider, "BTC/USDT")
        multiplier = self.settings.strategy_runtime.demo_order_size_multiplier
        btc_qty = (Decimal("0.0001") * multiplier).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
        eth_qty = (btc_qty / self._spot_market_buy_price("ETH/BTC", Decimal("0.000001"))).quantize(
            Decimal("0.000001"),
            rounding=ROUND_DOWN,
        )
        if strategy_name == "cross-exchange":
            return [
                DemoExecutionSpec("spot", "BTC/USDT", "buy", btc_qty, self._spot_market_buy_price("BTC/USDT")),
                DemoExecutionSpec("spot", "BTC/USDT", "sell", btc_qty, self._spot_market_sell_price("BTC/USDT")),
            ]
        if strategy_name == "triangular":
            return [
                DemoExecutionSpec("spot", "BTC/USDT", "buy", btc_qty, self._spot_market_buy_price("BTC/USDT")),
                DemoExecutionSpec(
                    "spot",
                    "ETH/BTC",
                    "buy",
                    eth_qty,
                    self._spot_market_buy_price("ETH/BTC", Decimal("0.000001")),
                ),
                DemoExecutionSpec("spot", "ETH/USDT", "sell", eth_qty, self._spot_market_sell_price("ETH/USDT")),
            ]
        if strategy_name == "funding-rate":
            swap_qty = (Decimal("0.01") * multiplier).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            return [
                DemoExecutionSpec(
                    "swap",
                    "BTC/USDT",
                    "sell",
                    swap_qty,
                    _market_sell_price(btc_usdt, buffer_pct=self._limit_price_buffer_pct()),
                ),
                DemoExecutionSpec(
                    "swap",
                    "BTC/USDT",
                    "buy",
                    swap_qty,
                    _market_buy_price(btc_usdt, buffer_pct=self._limit_price_buffer_pct()),
                ),
            ]
        if strategy_name in {"spot-perp", "spot-perp-carry"}:
            swap_qty = (Decimal("0.01") * multiplier).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            return [
                DemoExecutionSpec("spot", "BTC/USDT", "buy", btc_qty, self._spot_market_buy_price("BTC/USDT")),
                DemoExecutionSpec(
                    "swap",
                    "BTC/USDT",
                    "sell",
                    swap_qty,
                    _market_sell_price(btc_usdt, buffer_pct=self._limit_price_buffer_pct()),
                ),
                DemoExecutionSpec("spot", "BTC/USDT", "sell", btc_qty, self._spot_market_sell_price("BTC/USDT")),
                DemoExecutionSpec(
                    "swap",
                    "BTC/USDT",
                    "buy",
                    swap_qty,
                    _market_buy_price(btc_usdt, buffer_pct=self._limit_price_buffer_pct()),
                ),
            ]
        if strategy_name == "funding-carry-hedged":
            swap_qty = (Decimal("0.01") * multiplier).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            return [
                DemoExecutionSpec("spot", "BTC/USDT", "buy", btc_qty, self._spot_market_buy_price("BTC/USDT")),
                DemoExecutionSpec(
                    "swap",
                    "BTC/USDT",
                    "sell",
                    swap_qty,
                    _market_sell_price(btc_usdt, buffer_pct=self._limit_price_buffer_pct()),
                ),
                DemoExecutionSpec(
                    "swap",
                    "BTC/USDT",
                    "buy",
                    swap_qty,
                    _market_buy_price(btc_usdt, buffer_pct=self._limit_price_buffer_pct()),
                ),
                DemoExecutionSpec("spot", "BTC/USDT", "sell", btc_qty, self._spot_market_sell_price("BTC/USDT")),
            ]
        if strategy_name == "futures-perp-basis":
            swap_qty = (Decimal("0.01") * multiplier).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            futures_inst_id = _futures_inst_id(self.provider, "BTC/USDT")
            futures_price = _instrument_price(self.provider, futures_inst_id, fallback_symbol="BTC/USDT")
            return [
                DemoExecutionSpec(
                    "swap",
                    "BTC/USDT",
                    "buy",
                    swap_qty,
                    _market_buy_price(btc_usdt, buffer_pct=self._limit_price_buffer_pct()),
                ),
                DemoExecutionSpec(
                    "futures",
                    futures_inst_id,
                    "sell",
                    swap_qty,
                    _market_sell_price(futures_price, buffer_pct=self._limit_price_buffer_pct()),
                ),
                DemoExecutionSpec(
                    "futures",
                    futures_inst_id,
                    "buy",
                    swap_qty,
                    _market_buy_price(futures_price, buffer_pct=self._limit_price_buffer_pct()),
                ),
                DemoExecutionSpec(
                    "swap",
                    "BTC/USDT",
                    "sell",
                    swap_qty,
                    _market_sell_price(btc_usdt, buffer_pct=self._limit_price_buffer_pct()),
                ),
            ]
        if strategy_name in DIRECTIONAL_DEMO_STRATEGIES:
            return [
                DemoExecutionSpec("spot", "BTC/USDT", "buy", btc_qty, self._spot_market_buy_price("BTC/USDT")),
                DemoExecutionSpec("spot", "BTC/USDT", "sell", btc_qty, self._spot_market_sell_price("BTC/USDT")),
            ]
        raise SafetyError(f"Unsupported demo execution strategy: {strategy_name}")

    def _spot_td_mode(self) -> str:
        """Return OKX tdMode for spot orders under the current account mode."""
        if self._account_level in {"3", "4"}:
            return "cross"
        return "cash"

    def _pnl_validation(
        self,
        account_before: dict[str, Any],
        account_after: dict[str, Any],
        net_pnl: Decimal,
        orders: list[DemoOrderExecution],
    ) -> dict[str, Any]:
        """Reconcile order cash-flow PnL with mark-to-market account equity delta."""
        reference_prices = self._reference_prices()
        before_equity, ignored_before = _account_equity_usdt(account_before, reference_prices)
        after_equity, ignored_after = _account_equity_usdt(account_after, reference_prices)
        equity_delta = after_equity - before_equity
        difference = equity_delta - net_pnl
        tolerance = self.settings.strategy_runtime.demo_pnl_reconciliation_tolerance_usdt
        residual_inventory, residual_assets, ignored_residual_assets = _account_residual_inventory_usdt(
            account_before,
            account_after,
            reference_prices,
        )
        residual_tolerance = self.settings.strategy_runtime.demo_residual_inventory_tolerance_usdt
        exchange_receipts = self._exchange_receipts(orders, reference_prices)
        return to_jsonable(
            {
                "method": "order_cash_flow_plus_fee_vs_account_equity_delta",
                "cash_flow_net_pnl_usdt": _money(net_pnl),
                "equity_before_usdt": _money(before_equity),
                "equity_after_usdt": _money(after_equity),
                "equity_delta_usdt": _money(equity_delta),
                "difference_usdt": _money(difference),
                "tolerance_usdt": _money(tolerance),
                "within_tolerance": abs(difference) <= tolerance,
                "residual_inventory_usdt": _money(residual_inventory),
                "residual_inventory_tolerance_usdt": _money(residual_tolerance),
                "residual_inventory_within_tolerance": residual_inventory <= residual_tolerance,
                "residual_assets": residual_assets,
                "reference_prices": reference_prices,
                "ignored_assets": sorted(set(ignored_before + ignored_after + ignored_residual_assets)),
                "exchange_receipts": exchange_receipts,
            }
        )

    def _exchange_receipts(self, orders: list[DemoOrderExecution], reference_prices: dict[str, Decimal]) -> dict[str, Any]:
        """Fetch OKX fills-history rows and summarize exchange-reported fills/fees."""
        expected_orders = [order for order in orders if order.executed_quantity > 0]
        rows_by_order: dict[str, list[dict[str, Any]]] = {}
        errors: list[dict[str, str]] = []
        for order in expected_orders:
            try:
                rows_by_order[order.order_id] = self._fetch_fills(order)
            except Exception as exc:  # noqa: BLE001 - keep reconciliation non-fatal and explicit
                rows_by_order[order.order_id] = []
                errors.append({"order_id_suffix": order.order_id_suffix, "message": str(exc)})
        flat_rows = [row for rows in rows_by_order.values() for row in rows]
        missing_suffixes = [order.order_id_suffix for order in expected_orders if not rows_by_order.get(order.order_id)]
        fee_expense = sum((_fill_fee_expense_usdt(row, reference_prices) for row in flat_rows), Decimal("0"))
        fill_pnl = sum((_fill_pnl_usdt(row, reference_prices) for row in flat_rows), Decimal("0"))
        receipt_cash_flow = sum((_fill_cash_flow_usdt(row, reference_prices) for row in flat_rows), Decimal("0"))
        return to_jsonable(
            {
                "source": "okx_fills_history",
                "complete": not missing_suffixes and not errors,
                "orders_expected": len(expected_orders),
                "orders_with_receipts": len([order_id for order_id, rows in rows_by_order.items() if rows]),
                "missing_order_suffixes": missing_suffixes,
                "fill_count": len(flat_rows),
                "fee_expense_usdt": _money(fee_expense),
                "fill_pnl_usdt": _money(fill_pnl),
                "receipt_cash_flow_usdt": _money(receipt_cash_flow),
                "receipt_net_pnl_usdt": _money(fill_pnl - fee_expense),
                "errors": errors,
            }
        )

    def _fetch_fills(self, order: DemoOrderExecution) -> list[dict[str, Any]]:
        """Fetch OKX fills-history rows for one order."""
        inst_type = "SPOT"
        if order.instrument_type == "swap":
            inst_type = "SWAP"
        elif order.instrument_type == "futures":
            inst_type = "FUTURES"
        payload = self.provider._get(
            "/api/v5/trade/fills-history",
            {
                "instType": inst_type,
                "instId": _inst_id_from_values(order.instrument_type, order.symbol),
                "ordId": order.order_id,
                "limit": "100",
            },
            signed=True,
        )
        return [dict(row) for row in payload.get("data", [])]

    def _reference_prices(self) -> dict[str, Decimal]:
        """Return reference prices used for account equity reconciliation."""
        prices = {
            "BTC": _price(self.provider, "BTC/USDT"),
            "ETH": _price(self.provider, "ETH/USDT"),
            "USDT": Decimal("1"),
        }
        for symbol in self.settings.directional.symbols:
            base = _base_asset(symbol)
            if base in prices:
                continue
            try:
                prices[base] = _price(self.provider, symbol)
            except Exception:
                continue
        return prices

    def _limit_price_buffer_pct(self) -> Decimal:
        """Return the configured marketability buffer for OKX demo limit orders."""
        return self.settings.strategy_runtime.demo_limit_price_buffer_pct

    def _spot_market_buy_price(self, symbol: str, tick: Decimal = Decimal("0.1")) -> Decimal:
        """Return a marketable spot buy limit using best ask when available."""
        reference = _spot_orderbook_price(self.provider, symbol, "ask") or _price(self.provider, symbol)
        price = _market_buy_price(reference, tick=tick, buffer_pct=self._limit_price_buffer_pct())
        limit = _spot_price_limit(self.provider, symbol, "buy")
        if limit is not None and price > limit:
            return _floor_to_tick(limit, tick)
        return price

    def _spot_market_sell_price(self, symbol: str, tick: Decimal = Decimal("0.1")) -> Decimal:
        """Return a marketable spot sell limit using best bid when available."""
        reference = _spot_orderbook_price(self.provider, symbol, "bid") or _price(self.provider, symbol)
        price = _market_sell_price(reference, tick=tick, buffer_pct=self._limit_price_buffer_pct())
        limit = _spot_price_limit(self.provider, symbol, "sell")
        if limit is not None and price < limit:
            return _ceil_to_tick(limit, tick)
        return price

    def _expected_fill_price(self, spec: DemoExecutionSpec) -> Decimal:
        """Return the current top-of-book fill estimate for a marketable demo limit."""
        side: Literal["ask", "bid"] = "ask" if spec.side == "buy" else "bid"
        return _orderbook_price(self.provider, spec.instrument_type, spec.symbol, side) or spec.price


def _price(provider: Any, symbol: str) -> Decimal:
    """Fetch a positive OKX demo price."""
    value = Decimal(str(provider.get_price(symbol)))
    if value <= 0:
        raise SafetyError(f"Unable to fetch OKX demo price for {symbol}")
    return value


def _instrument_price(provider: Any, inst_id: str, fallback_symbol: str) -> Decimal:
    """Fetch a derivative instrument price when the provider exposes raw OKX public API."""
    if hasattr(provider, "_get"):
        try:
            payload = provider._get("/api/v5/market/ticker", {"instId": inst_id})
            rows = payload.get("data") or []
            if rows:
                value = Decimal(str(rows[0].get("last", "0") or "0"))
                if value > 0:
                    return value
        except Exception:
            pass
    return _price(provider, fallback_symbol)


def _price_for_instrument(provider: Any, instrument_type: InstrumentType, symbol: str) -> Decimal:
    """Return a current reference price for a spot/swap/futures symbol."""
    if instrument_type == "futures":
        return _instrument_price(provider, symbol, fallback_symbol=symbol.replace("-", "/").rsplit("/", 1)[0])
    return _price(provider, symbol)


def _futures_inst_id(provider: Any, symbol: str) -> str:
    """Return the nearest OKX dated futures instrument id for a symbol."""
    uly = _spot_inst_id(symbol)
    if hasattr(provider, "_get"):
        try:
            payload = provider._get("/api/v5/public/instruments", {"instType": "FUTURES", "uly": uly})
            rows = sorted(payload.get("data") or [], key=lambda row: str(row.get("expTime", "")))
            for row in rows:
                inst_id = str(row.get("instId", "") or "")
                if inst_id:
                    return inst_id
        except Exception:
            pass
    return f"{uly}-260626"


def _spot_orderbook_price(provider: Any, symbol: str, side: Literal["ask", "bid"]) -> Decimal | None:
    """Return the top spot-book price when the provider exposes OKX raw GET."""
    return _orderbook_price(provider, "spot", symbol, side)


def _spot_price_limit(provider: Any, symbol: str, side: Literal["buy", "sell"]) -> Decimal | None:
    """Return OKX dynamic spot price limit when available."""
    if not hasattr(provider, "_get"):
        return None
    try:
        payload = provider._get("/api/v5/public/price-limit", {"instId": _spot_inst_id(symbol)})
        rows = payload.get("data") or []
        if not rows:
            return None
        key = "buyLmt" if side == "buy" else "sellLmt"
        value = Decimal(str(rows[0].get(key, "0") or "0"))
    except Exception:
        return None
    return value if value > 0 else None


def _orderbook_price(provider: Any, instrument_type: InstrumentType, symbol: str, side: Literal["ask", "bid"]) -> Decimal | None:
    """Return top-of-book price for an OKX instrument when raw market books are available."""
    if not hasattr(provider, "_get"):
        return None
    try:
        payload = provider._get("/api/v5/market/books", {"instId": _inst_id_from_values(instrument_type, symbol), "sz": "1"})
        rows = payload.get("data") or []
        if not rows:
            return None
        levels = rows[0].get("asks" if side == "ask" else "bids") or []
        if not levels:
            return None
        price = Decimal(str(levels[0][0]))
    except Exception:
        return None
    return price if price > 0 else None


def _market_buy_price(
    last: Decimal,
    tick: Decimal = Decimal("0.1"),
    buffer_pct: Decimal = Decimal("0.001"),
) -> Decimal:
    """Return a marketable demo buy limit price."""
    return (last * (Decimal("1") + buffer_pct)).quantize(tick, rounding=ROUND_DOWN)


def _market_sell_price(
    last: Decimal,
    tick: Decimal = Decimal("0.1"),
    buffer_pct: Decimal = Decimal("0.001"),
) -> Decimal:
    """Return a marketable demo sell limit price."""
    return (last * (Decimal("1") - buffer_pct)).quantize(tick, rounding=ROUND_DOWN)


def _floor_to_tick(value: Decimal, tick: Decimal) -> Decimal:
    """Round a price down to a valid tick."""
    if tick <= 0:
        return value
    return (value // tick) * tick


def _ceil_to_tick(value: Decimal, tick: Decimal) -> Decimal:
    """Round a price up to a valid tick."""
    if tick <= 0:
        return value
    steps = value // tick
    if value % tick:
        steps += 1
    return steps * tick


def _price_tick(symbol: str) -> Decimal:
    """Return a conservative price tick for demo canary limit prices."""
    if "/BTC" in symbol or "-BTC" in symbol:
        return Decimal("0.000001")
    if symbol.startswith(("XRP/", "DOGE/", "ADA/")):
        return Decimal("0.0001")
    if symbol.startswith("SOL/"):
        return Decimal("0.01")
    return Decimal("0.1")


def _quantity_step(symbol: str) -> Decimal:
    """Return a conservative spot quantity step for OKX demo orders."""
    base = _base_asset(symbol)
    if base == "BTC":
        return Decimal("0.0001")
    if base == "ETH":
        return Decimal("0.001")
    if base == "SOL":
        return Decimal("0.01")
    return Decimal("1")


def _directional_profile(strategy_name: str) -> dict[str, Decimal | int]:
    """Return first-pass lifecycle parameters for one directional strategy."""
    profiles: dict[str, dict[str, Decimal | int]] = {
        "trend-breakout": {
            "stop_loss_pct": Decimal("0.85"),
            "take_profit_pct": Decimal("1.90"),
            "time_limit_minutes": 180,
        },
        "mean-reversion-spot": {
            "stop_loss_pct": Decimal("0.70"),
            "take_profit_pct": Decimal("1.20"),
            "time_limit_minutes": 120,
        },
        "volatility-squeeze-breakout": {
            "stop_loss_pct": Decimal("0.90"),
            "take_profit_pct": Decimal("1.80"),
            "time_limit_minutes": 180,
        },
        "momentum-rotation": {
            "stop_loss_pct": Decimal("1.00"),
            "take_profit_pct": Decimal("2.00"),
            "time_limit_minutes": 240,
        },
    }
    return profiles.get(
        strategy_name,
        {
            "stop_loss_pct": Decimal("0.80"),
            "take_profit_pct": Decimal("1.50"),
            "time_limit_minutes": 120,
        },
    )


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(tz=UTC)


def _status(row: dict[str, Any]) -> OrderStatus:
    """Normalize OKX order state."""
    value = str(row.get("state", "unknown")).lower()
    if value in {"filled", "canceled", "submitted", "partial_filled"}:
        return value  # type: ignore[return-value]
    if value == "live":
        return "submitted"
    return "unknown"


def _order_completed(order: DemoOrderExecution, spec: DemoExecutionSpec) -> bool:
    """Return whether an order filled enough for the strategy to continue."""
    return order.status == "filled" and order.executed_quantity >= spec.quantity


def _abort_reason(spec: DemoExecutionSpec, order: DemoOrderExecution) -> str:
    """Return a compact reason for an aborted demo sequence."""
    return f"leg_not_filled:{spec.instrument_type}:{spec.symbol}:{spec.side}:{order.status}:filled={order.executed_quantity}"


def _order_cash_flow_usdt(order: DemoOrderExecution, reference_prices: dict[str, Decimal]) -> Decimal:
    """Return signed quote cash flow for an order."""
    notional = _estimated_notional(
        DemoExecutionSpec(order.instrument_type, order.symbol, order.side, order.executed_quantity, order.executed_price),
        reference_prices,
    )
    if order.side == "buy":
        return -notional
    return notional


def _spec_cash_flow_usdt(spec: DemoExecutionSpec, reference_prices: dict[str, Decimal]) -> Decimal:
    """Return signed estimated cash flow for a planned order."""
    notional = _estimated_notional(spec, reference_prices)
    if spec.side == "buy":
        return -notional
    return notional


def _strategy_order_gross_pnl(strategy_name: str, orders: list[DemoOrderExecution], reference_prices: dict[str, Decimal]) -> Decimal:
    """Return strategy-aware gross PnL for executed orders."""
    if strategy_name == "triangular" and _has_executed_order(orders, "ETH/BTC", "buy") and _has_executed_order(orders, "ETH/USDT", "sell"):
        btc_buy = _order_notional_by_symbol(orders, "BTC/USDT", "buy", reference_prices)
        eth_sell = _order_notional_by_symbol(orders, "ETH/USDT", "sell", reference_prices)
        return eth_sell - btc_buy
    return sum((_order_cash_flow_usdt(order, reference_prices) for order in orders), Decimal("0"))


def _strategy_spec_gross_pnl(strategy_name: str, specs: list[DemoExecutionSpec], reference_prices: dict[str, Decimal]) -> Decimal:
    """Return strategy-aware gross PnL for planned orders."""
    if strategy_name == "triangular" and len(specs) >= 3:
        btc_buy = _spec_notional_by_symbol(specs, "BTC/USDT", "buy", reference_prices)
        eth_sell = _spec_notional_by_symbol(specs, "ETH/USDT", "sell", reference_prices)
        return eth_sell - btc_buy
    return sum((_spec_cash_flow_usdt(spec, reference_prices) for spec in specs), Decimal("0"))


def _order_notional_by_symbol(
    orders: list[DemoOrderExecution],
    symbol: str,
    side: str,
    reference_prices: dict[str, Decimal],
) -> Decimal:
    """Return notional for the first matching executed order."""
    for order in orders:
        if order.symbol == symbol and order.side == side:
            return _estimated_notional(
                DemoExecutionSpec(order.instrument_type, order.symbol, order.side, order.executed_quantity, order.executed_price),
                reference_prices,
            )
    return Decimal("0")


def _has_executed_order(orders: list[DemoOrderExecution], symbol: str, side: str) -> bool:
    """Return whether a matching order executed any quantity."""
    return any(order.symbol == symbol and order.side == side and order.executed_quantity > 0 for order in orders)


def _spec_notional_by_symbol(
    specs: list[DemoExecutionSpec],
    symbol: str,
    side: str,
    reference_prices: dict[str, Decimal],
) -> Decimal:
    """Return notional for the first matching planned order."""
    for spec in specs:
        if spec.symbol == symbol and spec.side == side:
            return _estimated_notional(spec, reference_prices)
    return Decimal("0")


def _estimated_notional(spec: DemoExecutionSpec, reference_prices: dict[str, Decimal] | None = None) -> Decimal:
    """Estimate USDT notional for spot and OKX swap contract quantities."""
    return spec.quantity * spec.price * _contract_multiplier(spec) * _quote_usdt_price(spec.symbol, reference_prices)


def _contract_multiplier(spec: DemoExecutionSpec) -> Decimal:
    """Return OKX demo contract multiplier for notional estimates."""
    if spec.instrument_type in {"swap", "futures"} and _base_asset(spec.symbol) == "BTC":
        return Decimal("0.01")
    return Decimal("1")


def _quote_usdt_price(symbol: str, reference_prices: dict[str, Decimal] | None = None) -> Decimal:
    """Return the USDT price of a symbol's quote currency."""
    parts = symbol.split("/") if "/" in symbol else symbol.split("-")
    quote = parts[1].upper() if len(parts) > 1 else "USDT"
    if quote == "USDT":
        return Decimal("1")
    if reference_prices is None:
        return Decimal("1")
    return reference_prices.get(quote, Decimal("1"))


def _money(value: Decimal) -> Decimal:
    """Quantize USDT money for stable JSON output."""
    return value.quantize(Decimal("0.000001"), rounding=ROUND_DOWN)


def _account_equity_usdt(snapshot: dict[str, Any], reference_prices: dict[str, Decimal]) -> tuple[Decimal, list[str]]:
    """Return mark-to-market USDT equity for known assets."""
    equity = Decimal("0")
    ignored: list[str] = []
    for asset, row in snapshot.items():
        amount = Decimal(str(row.get("total", "0") or "0"))
        price = reference_prices.get(str(asset).upper())
        if price is None:
            ignored.append(str(asset))
            continue
        equity += amount * price
    return equity, ignored


def _account_residual_inventory_usdt(
    before: dict[str, Any],
    after: dict[str, Any],
    reference_prices: dict[str, Decimal],
) -> tuple[Decimal, dict[str, Decimal], list[str]]:
    """Return non-USDT mark-to-market asset deltas left after a demo execution."""
    total = Decimal("0")
    residuals: dict[str, Decimal] = {}
    ignored: list[str] = []
    for asset in sorted(set(before) | set(after)):
        normalized = str(asset).upper()
        if normalized == "USDT":
            continue
        price = reference_prices.get(normalized)
        if price is None:
            ignored.append(str(asset))
            continue
        delta = _snapshot_total(after.get(asset, {})) - _snapshot_total(before.get(asset, {}))
        if delta == 0:
            continue
        residuals[normalized] = delta
        total += abs(delta) * price
    return total, residuals, ignored


def _snapshot_total(row: Any) -> Decimal:
    """Return a Decimal total from a balance snapshot row."""
    if not isinstance(row, dict):
        return Decimal("0")
    return Decimal(str(row.get("total", "0") or "0"))


def _fill_fee_expense_usdt(row: dict[str, Any], reference_prices: dict[str, Decimal]) -> Decimal:
    """Return positive USDT fee expense from an OKX fill row."""
    fee = Decimal(str(row.get("fee", "0") or "0"))
    return -fee * _fill_currency_usdt_price(row, str(row.get("feeCcy", "USDT") or "USDT"), reference_prices)


def _fill_pnl_usdt(row: dict[str, Any], reference_prices: dict[str, Decimal]) -> Decimal:
    """Return exchange-reported fill PnL converted to USDT."""
    pnl = Decimal(str(row.get("fillPnl", "0") or "0"))
    pnl_currency = str(row.get("pnlCcy") or row.get("feeCcy") or "USDT")
    return pnl * _fill_currency_usdt_price(row, pnl_currency, reference_prices)


def _fill_cash_flow_usdt(row: dict[str, Any], reference_prices: dict[str, Decimal]) -> Decimal:
    """Return signed trade cash flow converted to USDT."""
    inst_id = str(row.get("instId", ""))
    parts = inst_id.split("-")
    quote = parts[1] if len(parts) > 1 else "USDT"
    fill_px = Decimal(str(row.get("fillPx", "0") or "0"))
    fill_sz = Decimal(str(row.get("fillSz", "0") or "0"))
    multiplier = _contract_multiplier(DemoExecutionSpec(_instrument_type_from_inst_id(inst_id), inst_id.replace("-", "/").replace("/SWAP", ""), "buy", fill_sz, fill_px))
    notional = fill_px * fill_sz * multiplier * reference_prices.get(quote.upper(), Decimal("1"))
    if str(row.get("side", "")).lower() == "buy":
        return -notional
    return notional


def _fill_currency_usdt_price(row: dict[str, Any], currency: str, reference_prices: dict[str, Decimal]) -> Decimal:
    """Return a fill-aware USDT conversion price for a fee/PnL currency."""
    ccy = currency.upper()
    if ccy == "USDT":
        return Decimal("1")
    inst_id = str(row.get("instId", ""))
    parts = inst_id.split("-")
    if len(parts) >= 2:
        base, quote = parts[0].upper(), parts[1].upper()
        fill_px = Decimal(str(row.get("fillPx", "0") or "0"))
        if ccy == base and fill_px > 0:
            return fill_px * reference_prices.get(quote, Decimal("1"))
        if ccy == quote:
            return reference_prices.get(quote, Decimal("1"))
    return reference_prices.get(ccy, Decimal("1"))


def _instrument_type_from_inst_id(inst_id: str) -> InstrumentType:
    """Infer instrument type from OKX instrument id."""
    if inst_id.endswith("-SWAP"):
        return "swap"
    if len(inst_id.split("-")) >= 3:
        return "futures"
    return "spot"


def _base_asset(symbol: str) -> str:
    """Return the base asset from a display symbol or OKX instrument id."""
    parts = symbol.split("/") if "/" in symbol else symbol.split("-")
    return parts[0].upper() if parts else symbol.upper()


def _spot_inst_id(symbol: str) -> str:
    """Return OKX spot instrument id."""
    return symbol.upper().replace("/", "-")


def _swap_inst_id(symbol: str) -> str:
    """Return OKX swap instrument id."""
    return _spot_inst_id(symbol) + "-SWAP"


def _inst_id(spec: DemoExecutionSpec) -> str:
    """Return OKX instrument id for a spec."""
    if spec.instrument_type == "swap":
        return _swap_inst_id(spec.symbol)
    if spec.instrument_type == "futures":
        return spec.symbol
    return _spot_inst_id(spec.symbol)


def _inst_id_from_values(instrument_type: InstrumentType, symbol: str) -> str:
    """Return OKX instrument id without constructing a full spec."""
    if instrument_type == "swap":
        return _swap_inst_id(symbol)
    if instrument_type == "futures":
        return symbol
    return _spot_inst_id(symbol)


def _cancel_symbol(spec: DemoExecutionSpec) -> str:
    """Return provider cancel symbol."""
    return _inst_id(spec)
