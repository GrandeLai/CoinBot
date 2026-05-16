"""OKX Demo Trading order manager for hedged-maker maker quotes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from pathlib import Path
from typing import Any, Literal

from coinbot_api.broker.okx import OKXTradingProvider

from trading_assistant.arbitrage.calculator import percent
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import Settings
from trading_assistant.exceptions import SafetyError
from trading_assistant.execution.live_agent import AgentLiveTradingGate
from trading_assistant.risk.manager import RiskDecision, RiskManager
from trading_assistant.strategies.models import StrategyBudgetDecision
from trading_assistant.strategies.policy import StrategyPolicy
from trading_assistant.utils.serialization import to_jsonable


DemoManagerStatus = Literal[
    "blocked_risk",
    "blocked_budget",
    "maker_submitted",
    "maker_open",
    "maker_replaced",
    "maker_filled_hedged",
    "maker_partial_hedged",
]


@dataclass(frozen=True)
class HedgedMakerDemoManagerResult:
    """Result of one OKX Demo hedged-maker manager step."""

    status: DemoManagerStatus
    state_path: str
    provider_demo: bool
    demo_orders_sent: bool
    live_orders_sent: bool
    readiness: dict[str, Any]
    risk_decision: dict[str, Any]
    budget: dict[str, Any] | None
    maker_order: dict[str, Any] | None
    hedge_order: dict[str, Any] | None
    canceled_order_ids: list[str]
    active_order_count: int
    message: str
    strategy_name: str = "hedged-maker"

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe result."""
        return to_jsonable(self)


class HedgedMakerDemoOrderManager:
    """Manage one stateful OKX Demo Trading hedged-maker quote."""

    def __init__(self, settings: Settings, provider: Any | None = None) -> None:
        self.settings = settings
        self.provider = provider or OKXTradingProvider()
        self.path = Path(settings.hedged_maker.demo_state_path)
        self._account_level: str | None = None

    def manage(
        self,
        opportunity: ArbitrageOpportunity,
        now: datetime | None = None,
    ) -> HedgedMakerDemoManagerResult:
        """Advance one OKX Demo maker quote lifecycle step."""
        current_time = _as_utc(now or datetime.now(tz=UTC))
        self._assert_hedged_maker_opportunity(opportunity)
        risk_decision = RiskManager(self.settings.risk).evaluate(opportunity)
        readiness = self._assert_demo_gate(opportunity, risk_decision)
        state = self._read_state()
        orders = _orders_from_state(state)
        active_order = self._matching_active_order(orders, opportunity)
        active_orders = _active_order_count(orders)
        active_capital = sum((_open_notional_usdt(order) for order in orders if _is_active_order(order)), Decimal("0"))
        budget = StrategyPolicy(self.settings.strategy_runtime).evaluate(
            "hedged-maker",
            opportunity,
            active_orders=active_orders,
            active_capital_usdt=active_capital,
            additional_orders=0 if active_order is not None else 1,
            additional_capital_usdt=Decimal("0") if active_order is not None else opportunity.required_capital,
        )
        if not risk_decision.approved:
            return self._blocked_result(
                status="blocked_risk",
                opportunity=opportunity,
                readiness=readiness,
                risk_decision=risk_decision,
                budget=budget,
                message=f"Hedged-maker OKX demo manager blocked by risk: {', '.join(risk_decision.violations)}",
            )
        if not budget.approved:
            return self._blocked_result(
                status="blocked_budget",
                opportunity=opportunity,
                readiness=readiness,
                risk_decision=risk_decision,
                budget=budget,
                message=f"Hedged-maker OKX demo manager blocked by budget: {', '.join(budget.reasons)}",
            )

        if active_order is not None:
            filled = self._reconcile_fill(active_order, current_time, readiness, risk_decision, budget)
            if filled is not None:
                self._write_state(orders, current_time)
                self._audit("hedge_submitted", opportunity, filled.status, maker_order=filled.maker_order, hedge_order=filled.hedge_order)
                return filled
            if self._needs_replace(active_order, opportunity, current_time):
                canceled_id = self._cancel_active_order(active_order, current_time)
                maker_order = self._submit_maker_order(opportunity, current_time, sequence=len(orders) + 1)
                orders.append(maker_order)
                self._write_state(orders, current_time)
                result = HedgedMakerDemoManagerResult(
                    status="maker_replaced",
                    state_path=str(self.path),
                    provider_demo=True,
                    demo_orders_sent=True,
                    live_orders_sent=False,
                    readiness=readiness.to_dict(),
                    risk_decision=risk_decision.to_dict(),
                    budget=budget.to_dict(),
                    maker_order=to_jsonable(maker_order),
                    hedge_order=None,
                    canceled_order_ids=[canceled_id],
                    active_order_count=_active_order_count(orders),
                    message="Existing OKX Demo maker quote was canceled and replaced.",
                )
                self._audit("maker_replaced", opportunity, result.status, maker_order=maker_order, canceled_order_ids=[canceled_id])
                return result
            self._write_state(orders, current_time)
            return HedgedMakerDemoManagerResult(
                status="maker_open",
                state_path=str(self.path),
                provider_demo=True,
                demo_orders_sent=False,
                live_orders_sent=False,
                readiness=readiness.to_dict(),
                risk_decision=risk_decision.to_dict(),
                budget=budget.to_dict(),
                maker_order=to_jsonable(active_order),
                hedge_order=None,
                canceled_order_ids=[],
                active_order_count=_active_order_count(orders),
                message="Existing OKX Demo maker quote remains open.",
            )

        maker_order = self._submit_maker_order(opportunity, current_time, sequence=len(orders) + 1)
        orders.append(maker_order)
        self._write_state(orders, current_time)
        result = HedgedMakerDemoManagerResult(
            status="maker_submitted",
            state_path=str(self.path),
            provider_demo=True,
            demo_orders_sent=True,
            live_orders_sent=False,
            readiness=readiness.to_dict(),
            risk_decision=risk_decision.to_dict(),
            budget=budget.to_dict(),
            maker_order=to_jsonable(maker_order),
            hedge_order=None,
            canceled_order_ids=[],
            active_order_count=_active_order_count(orders),
            message="Submitted a new OKX Demo post-only maker quote.",
        )
        self._audit("maker_submitted", opportunity, result.status, maker_order=maker_order)
        return result

    def _assert_hedged_maker_opportunity(self, opportunity: ArbitrageOpportunity) -> None:
        """Require an explicit OKX hedged-maker opportunity payload."""
        if opportunity.strategy_type != "hedged-maker":
            raise SafetyError("hedged-maker demo manager requires strategy_type=hedged-maker")
        maker_quote = _mapping(opportunity.metadata.get("maker_quote"))
        hedge_preview = _mapping(opportunity.metadata.get("hedge_preview"))
        if maker_quote.get("exchange") != "okx" or hedge_preview.get("exchange") != "okx":
            raise SafetyError("hedged-maker demo manager requires maker_quote.exchange=okx and hedge_preview.exchange=okx")
        if opportunity.buy_exchange != "okx" or opportunity.sell_exchange != "okx":
            raise SafetyError("hedged-maker demo manager requires opportunity buy/sell exchanges to be okx")
        if _decimal(maker_quote.get("price")) <= 0 or _decimal(maker_quote.get("quantity")) <= 0:
            raise SafetyError("hedged-maker demo manager requires positive maker quote price and quantity")

    def _assert_demo_gate(self, opportunity: ArbitrageOpportunity, risk_decision: RiskDecision) -> Any:
        """Require every autonomous demo-order gate before touching orders."""
        readiness = AgentLiveTradingGate(self.settings).evaluate(opportunity, risk_decision)
        if not readiness.ready:
            raise SafetyError(f"hedged-maker demo manager gate blocked: {', '.join(readiness.reasons)}")
        okx = self.settings.exchanges.get("okx")
        if okx is None or not okx.enabled or not okx.sandbox or okx.okx_demo is not True:
            raise SafetyError("hedged-maker demo manager requires enabled OKX sandbox with okx_demo=true")
        if not bool(getattr(self.provider, "configured", False)):
            raise SafetyError("OKX provider is not configured")
        if not bool(getattr(self.provider, "demo", False)):
            raise SafetyError("OKX provider is not in demo mode")
        return readiness

    def _blocked_result(
        self,
        *,
        status: Literal["blocked_risk", "blocked_budget"],
        opportunity: ArbitrageOpportunity,
        readiness: Any,
        risk_decision: RiskDecision,
        budget: StrategyBudgetDecision | None,
        message: str,
    ) -> HedgedMakerDemoManagerResult:
        """Return a no-order blocked result."""
        self._audit(status, opportunity, status, maker_order=None)
        return HedgedMakerDemoManagerResult(
            status=status,
            state_path=str(self.path),
            provider_demo=bool(getattr(self.provider, "demo", False)),
            demo_orders_sent=False,
            live_orders_sent=False,
            readiness=readiness.to_dict(),
            risk_decision=risk_decision.to_dict(),
            budget=budget.to_dict() if budget is not None else None,
            maker_order=None,
            hedge_order=None,
            canceled_order_ids=[],
            active_order_count=_active_order_count(_orders_from_state(self._read_state())),
            message=message,
        )

    def _read_state(self) -> dict[str, Any]:
        """Read persisted OKX Demo manager state."""
        if not self.path.exists():
            return {"orders": []}
        payload = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        if not isinstance(payload, dict):
            return {"orders": []}
        return {"orders": _orders_from_state(payload)}

    def _write_state(self, orders: list[dict[str, Any]], now: datetime) -> None:
        """Persist OKX Demo manager state."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"orders": orders, "updated_at": now.isoformat()}
        self.path.write_text(json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _matching_active_order(self, orders: list[dict[str, Any]], opportunity: ArbitrageOpportunity) -> dict[str, Any] | None:
        """Return the current active maker order for this opportunity."""
        for order in orders:
            if not _is_active_order(order):
                continue
            if (
                order.get("opportunity_id") == opportunity.opportunity_id
                and order.get("symbol") == opportunity.symbol
            ):
                return order
        return None

    def _reconcile_fill(
        self,
        order: dict[str, Any],
        now: datetime,
        readiness: Any,
        risk_decision: RiskDecision,
        budget: StrategyBudgetDecision,
    ) -> HedgedMakerDemoManagerResult | None:
        """Hedge newly observed maker fills and update order state."""
        detail = self._fetch_order_detail(str(order["symbol"]), str(order["order_id"]))
        exchange_state = str(detail.get("state", ""))
        accumulated_fill = _decimal(detail.get("accFillSz") or detail.get("fillSz"))
        previous_fill = _decimal(order.get("filled_quantity"))
        new_fill = accumulated_fill - previous_fill
        if exchange_state == "canceled":
            order["status"] = "canceled"
            order["updated_at"] = now.isoformat()
            order["canceled_at"] = now.isoformat()
            return None
        if new_fill <= 0:
            return None
        hedge_order = self._submit_hedge_order(order, new_fill, now)
        total_quantity = _decimal(order.get("quantity"))
        remaining = max(total_quantity - accumulated_fill, Decimal("0"))
        order["filled_quantity"] = str(accumulated_fill)
        order["remaining_quantity"] = str(remaining)
        order["updated_at"] = now.isoformat()
        order["last_fill_at"] = now.isoformat()
        order["hedge_order_id"] = hedge_order["order_id"]
        order["hedged_quantity"] = str(_decimal(order.get("hedged_quantity")) + new_fill)
        order["status"] = "hedged" if remaining == 0 or exchange_state == "filled" else "partial_open"
        status: DemoManagerStatus = "maker_filled_hedged" if order["status"] == "hedged" else "maker_partial_hedged"
        return HedgedMakerDemoManagerResult(
            status=status,
            state_path=str(self.path),
            provider_demo=True,
            demo_orders_sent=True,
            live_orders_sent=False,
            readiness=readiness.to_dict(),
            risk_decision=risk_decision.to_dict(),
            budget=budget.to_dict(),
            maker_order=to_jsonable(order),
            hedge_order=to_jsonable(hedge_order),
            canceled_order_ids=[],
            active_order_count=1 if order["status"] == "partial_open" else 0,
            message="Observed OKX Demo maker fill and submitted the corresponding hedge.",
        )

    def _needs_replace(self, order: dict[str, Any], opportunity: ArbitrageOpportunity, now: datetime) -> bool:
        """Return whether an active maker quote should be canceled and replaced."""
        created_at = _parse_time(order.get("created_at"))
        if created_at is not None and now - created_at > timedelta(seconds=self.settings.strategy_runtime.order_ttl_seconds):
            return True
        old_price = _decimal(order.get("price"))
        maker_quote = _mapping(opportunity.metadata.get("maker_quote"))
        if str(order.get("maker_side")) != str(maker_quote.get("side")):
            return True
        new_price = _decimal(maker_quote.get("price"))
        if old_price <= 0:
            return True
        return abs(percent(new_price - old_price, old_price)) >= self.settings.strategy_runtime.reprice_threshold_pct

    def _cancel_active_order(self, order: dict[str, Any], now: datetime) -> str:
        """Cancel one active OKX Demo maker quote and mark local state."""
        order_id = str(order["order_id"])
        self.provider.cancel_order(str(order["symbol"]), order_id)
        order["status"] = "canceled"
        order["updated_at"] = now.isoformat()
        order["canceled_at"] = now.isoformat()
        return order_id

    def _submit_maker_order(self, opportunity: ArbitrageOpportunity, now: datetime, sequence: int) -> dict[str, Any]:
        """Submit one OKX Demo post-only maker quote."""
        maker_quote = _mapping(opportunity.metadata.get("maker_quote"))
        symbol = str(maker_quote.get("symbol") or opportunity.symbol)
        side = _side(maker_quote.get("side"))
        price = _decimal(maker_quote.get("price"))
        quantity = _decimal(maker_quote.get("quantity"))
        order_id = self._submit_spot_order(symbol=symbol, side=side, order_type="post_only", quantity=quantity, price=price)
        return {
            "order_id": order_id,
            "order_id_suffix": order_id[-8:],
            "opportunity_id": opportunity.opportunity_id,
            "symbol": symbol,
            "maker_side": side,
            "hedge_side": _side(_mapping(opportunity.metadata.get("hedge_preview")).get("side")),
            "price": _format_decimal(price),
            "quantity": _format_decimal(quantity),
            "filled_quantity": "0",
            "remaining_quantity": _format_decimal(quantity),
            "status": "open",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "sequence": sequence,
        }

    def _submit_hedge_order(self, maker_order: dict[str, Any], quantity: Decimal, now: datetime) -> dict[str, Any]:
        """Submit one OKX Demo hedge order for newly filled maker quantity."""
        symbol = str(maker_order["symbol"])
        side = _side(maker_order.get("hedge_side"))
        price = self._marketable_hedge_price(symbol, side)
        order_id = self._submit_spot_order(symbol=symbol, side=side, order_type="limit", quantity=quantity, price=price)
        return {
            "order_id": order_id,
            "order_id_suffix": order_id[-8:],
            "symbol": symbol,
            "side": side,
            "price": _format_decimal(price),
            "quantity": _format_decimal(quantity),
            "status": "submitted",
            "created_at": now.isoformat(),
            "maker_order_id": str(maker_order["order_id"]),
        }

    def _submit_spot_order(
        self,
        *,
        symbol: str,
        side: Literal["buy", "sell"],
        order_type: Literal["limit", "post_only"],
        quantity: Decimal,
        price: Decimal,
    ) -> str:
        """Submit a raw OKX Demo spot order and return its id."""
        self._account_level = self._account_level or self._read_account_level()
        response = self.provider._post(
            "/api/v5/trade/order",
            {
                "instId": _spot_inst_id(symbol),
                "tdMode": "cross" if self._account_level in {"3", "4"} else "cash",
                "side": side,
                "ordType": order_type,
                "sz": _format_decimal(quantity),
                "px": _format_decimal(price),
            },
        )
        rows = response.get("data") or []
        if not rows or not rows[0].get("ordId"):
            raise SafetyError("OKX demo hedged-maker order response did not include ordId")
        return str(rows[0]["ordId"])

    def _fetch_order_detail(self, symbol: str, order_id: str) -> dict[str, Any]:
        """Fetch one OKX Demo order detail row."""
        payload = self.provider._get(
            "/api/v5/trade/order",
            {"instId": _spot_inst_id(symbol), "ordId": order_id},
            signed=True,
        )
        rows = payload.get("data") or []
        if not rows:
            raise SafetyError(f"OKX demo hedged-maker order detail returned no data: {order_id[-8:]}")
        return dict(rows[0])

    def _read_account_level(self) -> str:
        """Read current OKX account mode."""
        payload = self.provider._get("/api/v5/account/config", signed=True)
        rows = payload.get("data") or []
        if not rows:
            raise SafetyError("OKX account config returned no data")
        return str(rows[0].get("acctLv", "unknown"))

    def _marketable_hedge_price(self, symbol: str, side: Literal["buy", "sell"]) -> Decimal:
        """Return a marketable OKX Demo limit price for the hedge leg."""
        tick = _price_tick(symbol)
        reference = _orderbook_price(self.provider, symbol, "ask" if side == "buy" else "bid")
        if reference is None:
            reference = Decimal(str(self.provider.get_price(symbol)))
        if reference <= 0:
            raise SafetyError(f"Unable to price OKX demo hedge for {symbol}")
        buffer_pct = self.settings.strategy_runtime.demo_limit_price_buffer_pct
        if side == "buy":
            return _ceil_to_tick(reference * (Decimal("1") + buffer_pct), tick)
        return _floor_to_tick(reference * (Decimal("1") - buffer_pct), tick)

    def _audit(
        self,
        action: str,
        opportunity: ArbitrageOpportunity,
        status: str,
        *,
        maker_order: dict[str, Any] | None = None,
        hedge_order: dict[str, Any] | None = None,
        canceled_order_ids: list[str] | None = None,
    ) -> None:
        """Append a redacted audit event for a demo manager decision."""
        if not self.settings.agent_trading.audit_log_path.strip():
            return
        AgentLiveTradingGate(self.settings).append_audit_event(
            {
                "event": "hedged_maker_demo_manager",
                "action": action,
                "status": status,
                "strategy_name": "hedged-maker",
                "opportunity_id": opportunity.opportunity_id,
                "symbol": opportunity.symbol,
                "maker_order_id_suffix": str((maker_order or {}).get("order_id", ""))[-8:] or None,
                "hedge_order_id_suffix": str((hedge_order or {}).get("order_id", ""))[-8:] or None,
                "canceled_order_id_suffixes": [order_id[-8:] for order_id in (canceled_order_ids or [])],
                "demo_orders_sent": action in {"maker_submitted", "maker_replaced", "hedge_submitted"},
                "live_orders_sent": False,
            }
        )


def _orders_from_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    orders = state.get("orders", [])
    if not isinstance(orders, list):
        return []
    return [dict(order) for order in orders if isinstance(order, dict)]


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _decimal(value: object) -> Decimal:
    return Decimal(str(value or "0"))


def _side(value: object) -> Literal["buy", "sell"]:
    side = str(value or "").lower()
    if side not in {"buy", "sell"}:
        raise SafetyError(f"Unsupported hedged-maker demo side: {value}")
    return "buy" if side == "buy" else "sell"


def _is_active_order(order: dict[str, Any]) -> bool:
    return str(order.get("status")) in {"open", "partial_open"}


def _active_order_count(orders: list[dict[str, Any]]) -> int:
    return sum(1 for order in orders if _is_active_order(order))


def _open_quantity(order: dict[str, Any]) -> Decimal:
    remaining = order.get("remaining_quantity")
    if remaining is not None:
        return _decimal(remaining)
    return _decimal(order.get("quantity"))


def _open_notional_usdt(order: dict[str, Any]) -> Decimal:
    return _decimal(order.get("price")) * _open_quantity(order)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return _as_utc(datetime.fromisoformat(value))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _spot_inst_id(symbol: str) -> str:
    return symbol.replace("/", "-").upper()


def _price_tick(symbol: str) -> Decimal:
    if "/BTC" in symbol or "-BTC" in symbol:
        return Decimal("0.000001")
    if symbol.startswith(("XRP/", "DOGE/", "ADA/")):
        return Decimal("0.0001")
    if symbol.startswith("SOL/"):
        return Decimal("0.01")
    return Decimal("0.1")


def _orderbook_price(provider: Any, symbol: str, side: Literal["ask", "bid"]) -> Decimal | None:
    if not hasattr(provider, "_get"):
        return None
    try:
        payload = provider._get("/api/v5/market/books", {"instId": _spot_inst_id(symbol), "sz": "1"})
        rows = payload.get("data") or []
        levels = rows[0].get("asks" if side == "ask" else "bids") if rows else []
        price = Decimal(str((levels or [[0]])[0][0]))
    except Exception:
        return None
    return price if price > 0 else None


def _floor_to_tick(value: Decimal, tick: Decimal) -> Decimal:
    if tick <= 0:
        return value
    return (value // tick) * tick


def _ceil_to_tick(value: Decimal, tick: Decimal) -> Decimal:
    if tick <= 0:
        return value
    return (value / tick).to_integral_value(rounding=ROUND_UP) * tick


def _format_decimal(value: Decimal) -> str:
    rendered = format(value.quantize(_smallest_exponent(value), rounding=ROUND_DOWN), "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _smallest_exponent(value: Decimal) -> Decimal:
    raw_exponent = value.as_tuple().exponent
    exponent = min(raw_exponent, 0) if isinstance(raw_exponent, int) else 0
    return Decimal(1).scaleb(exponent)
