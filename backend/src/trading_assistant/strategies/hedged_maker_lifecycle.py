"""Stateful paper lifecycle for hedged-maker quote simulation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from trading_assistant.arbitrage.calculator import percent
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.strategies.models import OrderLifecyclePlan
from trading_assistant.utils.serialization import to_jsonable


LifecycleStatus = Literal["quoted", "active_quote_unchanged", "replaced_after_ttl", "requoted", "filled_and_hedged", "blocked_open_order_limit"]


@dataclass(frozen=True)
class HedgedMakerLifecycleResult:
    """Result of one hedged-maker paper lifecycle evaluation."""

    status: LifecycleStatus
    state_path: str
    paper_order: dict[str, object] | None
    hedge_order: dict[str, object] | None
    canceled_order_ids: list[str]
    active_order_count: int
    expected_net_profit_usdt: Decimal
    realized_net_profit_usdt: Decimal
    message: str
    paper_only: bool = True
    dry_run: bool = True
    simulation_only: bool = True
    orders_sent: bool = False
    live_orders_sent: bool = False

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


class HedgedMakerPaperLifecycleService:
    """Persist and advance paper maker quotes for the hedged-maker strategy."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges
        self.path = Path(settings.hedged_maker.paper_state_path)

    def apply(
        self,
        opportunity: ArbitrageOpportunity,
        lifecycle: OrderLifecyclePlan,
        now: datetime | None = None,
    ) -> HedgedMakerLifecycleResult:
        """Advance paper quote state for one approved hedged-maker opportunity."""
        current_time = _as_utc(now or datetime.now(tz=UTC))
        state = self.read_state()
        orders = _orders_from_state(state)
        canceled_order_ids = self._cancel_expired_orders(orders, lifecycle, current_time)
        fill_result = self._fill_first_crossed_order(orders, opportunity, current_time)
        if fill_result is not None:
            self._write_state(orders, current_time)
            return fill_result

        matching_open = self._matching_open_order(orders, opportunity)
        if matching_open is not None:
            if self._needs_reprice(matching_open, opportunity, lifecycle):
                matching_open["status"] = "replaced"
                matching_open["updated_at"] = current_time.isoformat()
                canceled_order_ids.append(str(matching_open["order_id"]))
                result = self._create_quote_result(
                    orders=orders,
                    opportunity=opportunity,
                    status="requoted",
                    canceled_order_ids=canceled_order_ids,
                    now=current_time,
                    message="Existing paper maker quote was replaced after reprice threshold was reached.",
                )
                self._write_state(orders, current_time)
                return result
            self._write_state(orders, current_time)
            return HedgedMakerLifecycleResult(
                status="active_quote_unchanged",
                state_path=str(self.path),
                paper_order=to_jsonable(matching_open),
                hedge_order=None,
                canceled_order_ids=canceled_order_ids,
                active_order_count=_active_order_count(orders),
                expected_net_profit_usdt=_decimal(matching_open.get("expected_net_profit_usdt")),
                realized_net_profit_usdt=Decimal("0"),
                message="Existing paper maker quote remains open within the reprice threshold.",
            )

        if _active_order_count(orders) >= self.settings.strategy_runtime.max_open_orders_per_strategy:
            self._write_state(orders, current_time)
            return HedgedMakerLifecycleResult(
                status="blocked_open_order_limit",
                state_path=str(self.path),
                paper_order=None,
                hedge_order=None,
                canceled_order_ids=canceled_order_ids,
                active_order_count=_active_order_count(orders),
                expected_net_profit_usdt=opportunity.net_profit,
                realized_net_profit_usdt=Decimal("0"),
                message="Paper maker quote blocked by max_open_orders_per_strategy.",
            )

        status: Literal["quoted", "replaced_after_ttl"] = "replaced_after_ttl" if canceled_order_ids else "quoted"
        message = "Expired paper maker quote was canceled and replaced." if canceled_order_ids else "New paper maker quote recorded."
        result = self._create_quote_result(
            orders=orders,
            opportunity=opportunity,
            status=status,
            canceled_order_ids=canceled_order_ids,
            now=current_time,
            message=message,
        )
        self._write_state(orders, current_time)
        return result

    def read_state(self) -> dict[str, Any]:
        """Read lifecycle state from disk."""
        if not self.path.exists():
            return {"orders": []}
        payload = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        if not isinstance(payload, dict):
            return {"orders": []}
        orders = payload.get("orders", [])
        if not isinstance(orders, list):
            return {"orders": []}
        return {"orders": [dict(order) for order in orders if isinstance(order, dict)]}

    def _create_quote_result(
        self,
        *,
        orders: list[dict[str, Any]],
        opportunity: ArbitrageOpportunity,
        status: Literal["quoted", "replaced_after_ttl", "requoted"],
        canceled_order_ids: list[str],
        now: datetime,
        message: str,
    ) -> HedgedMakerLifecycleResult:
        paper_order = self._new_order(opportunity, now, sequence=len(orders) + 1)
        orders.append(paper_order)
        return HedgedMakerLifecycleResult(
            status=status,
            state_path=str(self.path),
            paper_order=to_jsonable(paper_order),
            hedge_order=None,
            canceled_order_ids=canceled_order_ids,
            active_order_count=_active_order_count(orders),
            expected_net_profit_usdt=opportunity.net_profit,
            realized_net_profit_usdt=Decimal("0"),
            message=message,
        )

    def _new_order(self, opportunity: ArbitrageOpportunity, now: datetime, sequence: int) -> dict[str, Any]:
        maker_quote = _mapping(opportunity.metadata.get("maker_quote"))
        hedge_preview = _mapping(opportunity.metadata.get("hedge_preview"))
        maker_side = str(maker_quote.get("side", "buy"))
        order_id = _order_id(opportunity.symbol, maker_side, sequence, now)
        return {
            "order_id": order_id,
            "opportunity_id": opportunity.opportunity_id,
            "symbol": opportunity.symbol,
            "maker_exchange": str(maker_quote.get("exchange", opportunity.buy_exchange)),
            "hedge_exchange": str(hedge_preview.get("exchange", opportunity.sell_exchange)),
            "maker_side": maker_side,
            "hedge_side": str(hedge_preview.get("side", "sell")),
            "maker_order_type": "limit_post_only",
            "hedge_order_type": "taker_market_preview",
            "price": str(maker_quote.get("price", "0")),
            "quantity": str(maker_quote.get("quantity", opportunity.metadata.get("quantity", "0"))),
            "expected_net_profit_usdt": str(opportunity.net_profit),
            "status": "open",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

    def _cancel_expired_orders(
        self,
        orders: list[dict[str, Any]],
        lifecycle: OrderLifecyclePlan,
        now: datetime,
    ) -> list[str]:
        canceled: list[str] = []
        ttl = timedelta(seconds=lifecycle.order_ttl_seconds)
        for order in orders:
            if order.get("status") != "open":
                continue
            created_at = _parse_time(order.get("created_at"))
            if created_at is not None and now - created_at > ttl:
                order["status"] = "canceled"
                order["updated_at"] = now.isoformat()
                order["canceled_at"] = now.isoformat()
                order["cancel_reason"] = "ttl_expired"
                canceled.append(str(order["order_id"]))
        return canceled

    def _fill_first_crossed_order(
        self,
        orders: list[dict[str, Any]],
        opportunity: ArbitrageOpportunity,
        now: datetime,
    ) -> HedgedMakerLifecycleResult | None:
        for order in orders:
            if order.get("status") != "open":
                continue
            if not self._is_crossed(order):
                continue
            hedge_order, net_profit = self._hedge_fill(order, now)
            order["status"] = "filled"
            order["updated_at"] = now.isoformat()
            order["filled_at"] = now.isoformat()
            order["hedged_at"] = now.isoformat()
            order["hedge_order"] = hedge_order
            order["realized_net_profit_usdt"] = str(net_profit)
            return HedgedMakerLifecycleResult(
                status="filled_and_hedged",
                state_path=str(self.path),
                paper_order=to_jsonable(order),
                hedge_order=to_jsonable(hedge_order),
                canceled_order_ids=[],
                active_order_count=_active_order_count(orders),
                expected_net_profit_usdt=_decimal(order.get("expected_net_profit_usdt", opportunity.net_profit)),
                realized_net_profit_usdt=net_profit,
                message="Paper maker quote filled and taker hedge was simulated.",
            )
        return None

    def _is_crossed(self, order: dict[str, Any]) -> bool:
        maker = self.exchanges.get(str(order["maker_exchange"]))
        ticker = maker.get_ticker(str(order["symbol"]))
        price = _decimal(order.get("price"))
        maker_side = str(order.get("maker_side"))
        return price >= ticker.ask if maker_side == "buy" else price <= ticker.bid

    def _hedge_fill(self, order: dict[str, Any], now: datetime) -> tuple[dict[str, Any], Decimal]:
        hedge = self.exchanges.get(str(order["hedge_exchange"]))
        ticker = hedge.get_ticker(str(order["symbol"]))
        hedge_side = str(order.get("hedge_side"))
        maker_side = str(order.get("maker_side"))
        quantity = _decimal(order.get("quantity"))
        maker_price = _decimal(order.get("price"))
        hedge_price = ticker.bid if hedge_side == "sell" else ticker.ask
        maker_notional = maker_price * quantity
        hedge_notional = hedge_price * quantity
        sell_notional = hedge_notional if hedge_side == "sell" else maker_notional
        buy_notional = maker_notional if maker_side == "buy" else hedge_notional
        fees = maker_notional * self.settings.hedged_maker.maker_fee_pct + hedge_notional * self.settings.hedged_maker.taker_fee_pct
        slippage = hedge_notional * self.settings.hedged_maker.hedge_slippage_pct
        net_profit = sell_notional - buy_notional - fees - slippage
        hedge_order = {
            "exchange": str(order["hedge_exchange"]),
            "symbol": str(order["symbol"]),
            "side": hedge_side,
            "price": str(hedge_price),
            "quantity": str(quantity),
            "notional_usdt": str(hedge_notional),
            "status": "simulated",
            "created_at": now.isoformat(),
            "maker_fill_price": str(maker_price),
            "maker_fill_notional_usdt": str(maker_notional),
            "estimated_fee_usdt": str(fees),
            "estimated_slippage_usdt": str(slippage),
            "realized_net_profit_usdt": str(net_profit),
        }
        return hedge_order, net_profit

    def _matching_open_order(self, orders: list[dict[str, Any]], opportunity: ArbitrageOpportunity) -> dict[str, Any] | None:
        maker_quote = _mapping(opportunity.metadata.get("maker_quote"))
        hedge_preview = _mapping(opportunity.metadata.get("hedge_preview"))
        for order in orders:
            if order.get("status") != "open":
                continue
            if order.get("symbol") != opportunity.symbol:
                continue
            if order.get("maker_exchange") != maker_quote.get("exchange"):
                continue
            if order.get("hedge_exchange") != hedge_preview.get("exchange"):
                continue
            return order
        return None

    def _needs_reprice(
        self,
        order: dict[str, Any],
        opportunity: ArbitrageOpportunity,
        lifecycle: OrderLifecyclePlan,
    ) -> bool:
        maker_quote = _mapping(opportunity.metadata.get("maker_quote"))
        if str(order.get("maker_side")) != str(maker_quote.get("side")):
            return True
        old_price = _decimal(order.get("price"))
        new_price = _decimal(maker_quote.get("price"))
        if old_price <= 0:
            return True
        return abs(percent(new_price - old_price, old_price)) >= lifecycle.reprice_threshold_pct

    def _write_state(self, orders: list[dict[str, Any]], now: datetime) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"orders": orders, "updated_at": now.isoformat()}
        self.path.write_text(json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _orders_from_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    orders = state.get("orders", [])
    if not isinstance(orders, list):
        return []
    return [dict(order) for order in orders if isinstance(order, dict)]


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _decimal(value: object) -> Decimal:
    return Decimal(str(value or "0"))


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value)
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _active_order_count(orders: list[dict[str, Any]]) -> int:
    return sum(1 for order in orders if order.get("status") == "open")


def _order_id(symbol: str, maker_side: str, sequence: int, now: datetime) -> str:
    safe_symbol = symbol.lower().replace("/", "-")
    safe_time = now.strftime("%Y%m%dT%H%M%SZ")
    return f"hedged-maker-{safe_symbol}-{maker_side}-{safe_time}-{sequence}"
