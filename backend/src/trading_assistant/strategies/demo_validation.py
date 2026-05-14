"""OKX Demo Trading validation for production strategies."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN
from typing import Any, Literal

from coinbot_api.broker.okx import OKXTradingProvider
from coinbot_api.broker.types import CryptoOrderRequest, SwapOrderRequest, TradingOrderSide, TradingOrderType

from trading_assistant.config.schema import Settings
from trading_assistant.exceptions import SafetyError
from trading_assistant.strategies.registry import StrategyRegistry
from trading_assistant.utils.serialization import to_jsonable


InstrumentType = Literal["spot", "swap", "futures"]


@dataclass(frozen=True)
class DemoOrderSpec:
    """One tiny OKX demo validation order."""

    instrument_type: InstrumentType
    symbol: str
    side: Literal["buy", "sell"]
    quantity: Decimal
    price: Decimal


@dataclass(frozen=True)
class SubmittedOrderRef:
    """Minimal provider order reference used by raw demo submit paths."""

    order_id: str


@dataclass(frozen=True)
class StrategyDemoValidationItem:
    """Validation result for one strategy."""

    strategy_name: str
    ok: bool
    live_orders_sent: bool
    orders: list[dict[str, Any]]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe item."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyDemoValidationResult:
    """Validation result for a batch of strategies."""

    completed: bool
    config_path: str | None
    provider_demo: bool
    live_trading: bool
    dry_run: bool
    results: list[StrategyDemoValidationItem]
    account_mode: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe result."""
        return to_jsonable(self)


class StrategyDemoValidationService:
    """Submit/cancel tiny OKX Demo Trading orders for each strategy."""

    def __init__(
        self,
        settings: Settings,
        provider: Any | None = None,
        config_path: str | None = None,
        allow_account_mode_switch: bool = False,
    ) -> None:
        self.settings = settings
        self.provider = provider or OKXTradingProvider()
        self.config_path = config_path
        self.allow_account_mode_switch = allow_account_mode_switch
        self.registry = StrategyRegistry()
        self._swap_validation_blocker: str | None = None
        self._account_level_for_orders: str | None = None

    def validate(self, strategies: list[str] | None = None) -> StrategyDemoValidationResult:
        """Validate strategies sequentially through OKX Demo Trading."""
        self._assert_demo_allowed()
        names = strategies or self.registry.names()
        account_mode = self._prepare_account_mode(names)
        results = [self._validate_one(name) for name in names]
        return StrategyDemoValidationResult(
            completed=bool(account_mode.get("ok", True)) and all(item.ok for item in results),
            config_path=self.config_path,
            provider_demo=bool(getattr(self.provider, "demo", False)),
            live_trading=self.settings.trading.live_trading,
            dry_run=self.settings.trading.dry_run,
            account_mode=account_mode,
            results=results,
        )

    def _assert_demo_allowed(self) -> None:
        """Require explicit OKX demo mode and reject live trading."""
        okx = self.settings.exchanges.get("okx")
        if self.settings.trading.live_trading:
            raise SafetyError("strategy demo validation requires trading.live_trading=false")
        if okx is None or not okx.enabled or not okx.sandbox or okx.okx_demo is not True:
            raise SafetyError("strategy demo validation requires enabled OKX sandbox with okx_demo=true")
        if not self.settings.agent_trading.allow_demo_orders:
            raise SafetyError("strategy demo validation requires agent_trading.allow_demo_orders=true")
        if not bool(getattr(self.provider, "configured", False)):
            raise SafetyError("OKX provider is not configured")
        if not bool(getattr(self.provider, "demo", False)):
            raise SafetyError("OKX provider is not in demo mode")

    def _validate_one(self, strategy_name: str) -> StrategyDemoValidationItem:
        """Validate one strategy and continue on recoverable per-strategy errors."""
        self.registry.get(strategy_name)
        if _requires_swap(strategy_name) and self._swap_validation_blocker:
            return StrategyDemoValidationItem(
                strategy_name=strategy_name,
                ok=False,
                live_orders_sent=False,
                orders=[],
                error=self._swap_validation_blocker,
            )
        try:
            order_results = [self._submit_cancel_confirm(spec) for spec in self._order_specs(strategy_name)]
            return StrategyDemoValidationItem(
                strategy_name=strategy_name,
                ok=all(item["submitted"] and item["canceled"] and not item["open_after_cancel"] for item in order_results),
                live_orders_sent=False,
                orders=order_results,
            )
        except Exception as exc:
            return StrategyDemoValidationItem(
                strategy_name=strategy_name,
                ok=False,
                live_orders_sent=False,
                orders=[],
                error=f"{exc.__class__.__name__}: {exc}",
            )

    def _prepare_account_mode(self, strategy_names: list[str]) -> dict[str, Any]:
        """Ensure OKX demo account mode can validate derivative-based strategies."""
        requires_swap = any(_requires_swap(name) for name in strategy_names)
        status: dict[str, Any] = {
            "required_for_swap": requires_swap,
            "target_account_level": "2",
            "checked": False,
            "switch_allowed": self.allow_account_mode_switch,
            "switch_attempted": False,
            "switched": False,
            "ok": True,
        }
        if not hasattr(self.provider, "_get"):
            if requires_swap:
                status["message"] = "Provider does not expose account-mode API; derivative validation will rely on order response"
            return status
        try:
            current = self._account_level()
            self._account_level_for_orders = current
            status["checked"] = True
            status["before"] = current
            if not requires_swap:
                status["after"] = current
                return status
            if current in {"2", "3", "4"}:
                status["after"] = current
                return status
            if not self.allow_account_mode_switch:
                self._swap_validation_blocker = (
                    "OKX demo account level is spot-only (acctLv=1); rerun with "
                    "--allow-account-mode-switch after confirming demo account permissions"
                )
                status["ok"] = False
                status["after"] = current
                status["message"] = self._swap_validation_blocker
                return status
            self._assert_no_open_swap_blockers()
            self._precheck_account_level_switch("2")
            status["switch_attempted"] = True
            self.provider._post("/api/v5/account/set-account-level", {"acctLv": "2"})
            after = self._account_level()
            self._account_level_for_orders = after
            status["after"] = after
            status["switched"] = after == "2"
            status["ok"] = after in {"2", "3", "4"}
            if not status["ok"]:
                self._swap_validation_blocker = f"OKX demo account level switch did not enable derivative validation: acctLv={after}"
                status["message"] = self._swap_validation_blocker
        except Exception as exc:
            self._swap_validation_blocker = f"{exc.__class__.__name__}: {exc}"
            status["ok"] = False
            status["error"] = self._swap_validation_blocker
        return status

    def _account_level(self) -> str:
        """Return current OKX account level."""
        payload = self.provider._get("/api/v5/account/config", signed=True)
        rows = payload.get("data") or []
        if not rows:
            raise SafetyError("OKX account config returned no data")
        return str(rows[0].get("acctLv", ""))

    def _precheck_account_level_switch(self, target_account_level: str) -> None:
        """Run OKX account-level switch precheck when available."""
        payload = self.provider._get(
            "/api/v5/account/set-account-switch-precheck",
            {"acctLv": target_account_level},
            signed=True,
        )
        rows = payload.get("data") or []
        if rows:
            check_code = str(rows[0].get("sCode", "0") or "0")
            if check_code != "0":
                message = rows[0].get("sMsg") or rows[0].get("msg") or "account mode switch precheck did not pass"
                raise SafetyError(f"OKX demo account mode switch precheck failed: sCode={check_code}, {message}")

    def _assert_no_open_swap_blockers(self) -> None:
        """Reject account-mode switching when open orders or positions are present."""
        open_spot = self.provider.get_open_orders() if hasattr(self.provider, "get_open_orders") else []
        open_swap = (
            self.provider.get_open_futures_orders(inst_type="SWAP")
            if hasattr(self.provider, "get_open_futures_orders")
            else []
        )
        positions = self.provider.get_positions(inst_type="SWAP") if hasattr(self.provider, "get_positions") else []
        if open_spot or open_swap or positions:
            raise SafetyError("Refusing OKX demo account mode switch while open orders or swap positions exist")

    def _submit_cancel_confirm(self, spec: DemoOrderSpec) -> dict[str, Any]:
        """Submit one order, cancel it, and confirm it is not open."""
        order_id = ""
        canceled = False
        try:
            if spec.instrument_type == "spot":
                provider_order = self._submit_spot_order(spec)
            elif spec.instrument_type == "futures":
                provider_order = self._submit_derivative_order(spec)
            else:
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
            self.provider.cancel_order(_cancel_symbol(spec), order_id)
            canceled = True
            return {
                "instrument_type": spec.instrument_type,
                "symbol": spec.symbol,
                "side": spec.side,
                "quantity": spec.quantity,
                "price": spec.price,
                "submitted": bool(order_id),
                "canceled": canceled,
                "open_after_cancel": self._is_open_after_cancel(spec, order_id),
                "order_id_suffix": order_id[-8:] if order_id else "",
            }
        finally:
            if order_id and not canceled:
                self.provider.cancel_order(_cancel_symbol(spec), order_id)

    def _submit_spot_order(self, spec: DemoOrderSpec) -> Any:
        """Submit a spot validation order with account-mode aware tdMode."""
        td_mode = self._spot_td_mode()
        if td_mode == "cash" or not hasattr(self.provider, "_post"):
            return self.provider.submit_order(
                CryptoOrderRequest(
                    symbol=spec.symbol,
                    side=TradingOrderSide(spec.side),
                    order_type=TradingOrderType.LIMIT,
                    quantity=float(spec.quantity),
                    price=float(spec.price),
                )
            )
        body = {
            "instId": _spot_inst_id(spec.symbol),
            "tdMode": td_mode,
            "side": spec.side,
            "ordType": "limit",
            "sz": str(spec.quantity),
            "px": str(spec.price),
        }
        response = self.provider._post("/api/v5/trade/order", body)
        rows = response.get("data") or []
        if not rows or not rows[0].get("ordId"):
            raise SafetyError("OKX demo spot order response did not include ordId")
        return SubmittedOrderRef(order_id=str(rows[0]["ordId"]))

    def _submit_derivative_order(self, spec: DemoOrderSpec) -> SubmittedOrderRef:
        """Submit a raw futures validation order."""
        if not hasattr(self.provider, "_post"):
            raise SafetyError("Provider does not expose raw OKX order API for futures validation")
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
        return SubmittedOrderRef(order_id=str(rows[0]["ordId"]))

    def _spot_td_mode(self) -> str:
        """Return OKX tdMode for spot validation orders."""
        if self._account_level_for_orders in {"3", "4"}:
            return "cross"
        return "cash"

    def _is_open_after_cancel(self, spec: DemoOrderSpec, order_id: str) -> bool:
        """Return whether the submitted order is still open."""
        if spec.instrument_type == "spot":
            return order_id in {str(getattr(order, "order_id", "")) for order in self.provider.get_open_orders(spec.symbol)}
        if spec.instrument_type == "futures":
            return order_id in {
                str(getattr(order, "order_id", ""))
                for order in self.provider.get_open_futures_orders(inst_type="FUTURES", inst_id=spec.symbol)
            }
        return order_id in {
            str(getattr(order, "order_id", ""))
            for order in self.provider.get_open_futures_orders(inst_type="SWAP", inst_id=_swap_inst_id(spec.symbol))
        }

    def _order_specs(self, strategy_name: str) -> list[DemoOrderSpec]:
        """Return tiny demo orders for one strategy validation."""
        btc_usdt = _spot_price(self.provider, "BTC/USDT")
        eth_usdt = _spot_price(self.provider, "ETH/USDT")
        eth_btc = _spot_price(self.provider, "ETH/BTC")
        if strategy_name == "cross-exchange":
            return [DemoOrderSpec("spot", "BTC/USDT", "buy", Decimal("0.0001"), _buy_price(btc_usdt))]
        if strategy_name == "triangular":
            return [
                DemoOrderSpec("spot", "BTC/USDT", "buy", Decimal("0.0001"), _buy_price(btc_usdt)),
                DemoOrderSpec("spot", "ETH/BTC", "buy", Decimal("0.001"), _buy_price(eth_btc, tick=Decimal("0.000001"))),
                DemoOrderSpec("spot", "ETH/USDT", "sell", Decimal("0.001"), _sell_price(eth_usdt)),
            ]
        if strategy_name == "funding-rate":
            return [DemoOrderSpec("swap", "BTC/USDT", "sell", Decimal("0.01"), _sell_price(btc_usdt))]
        if strategy_name in {"spot-perp", "spot-perp-carry", "funding-carry-hedged"}:
            return [
                DemoOrderSpec("spot", "BTC/USDT", "buy", Decimal("0.0001"), _buy_price(btc_usdt)),
                DemoOrderSpec("swap", "BTC/USDT", "sell", Decimal("0.01"), _sell_price(btc_usdt)),
            ]
        if strategy_name == "futures-perp-basis":
            futures_inst_id = _futures_inst_id(self.provider, "BTC/USDT")
            futures_price = _instrument_price(self.provider, futures_inst_id, fallback_symbol="BTC/USDT")
            return [
                DemoOrderSpec("swap", "BTC/USDT", "buy", Decimal("0.01"), _buy_price(btc_usdt)),
                DemoOrderSpec("futures", futures_inst_id, "sell", Decimal("0.01"), _sell_price(futures_price)),
            ]
        raise SafetyError(f"Unsupported demo validation strategy: {strategy_name}")


def _spot_price(provider: Any, symbol: str) -> Decimal:
    """Fetch a positive spot price from provider."""
    price = Decimal(str(provider.get_price(symbol)))
    if price <= 0:
        raise SafetyError(f"Unable to fetch OKX demo price for {symbol}")
    return price


def _instrument_price(provider: Any, inst_id: str, fallback_symbol: str) -> Decimal:
    """Fetch a derivative instrument price from raw OKX public API when available."""
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
    return _spot_price(provider, fallback_symbol)


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


def _buy_price(last: Decimal, tick: Decimal = Decimal("0.1")) -> Decimal:
    """Return a below-market validation buy price."""
    return (last * Decimal("0.99")).quantize(tick, rounding=ROUND_DOWN)


def _sell_price(last: Decimal, tick: Decimal = Decimal("0.1")) -> Decimal:
    """Return an above-market validation sell price."""
    return (last * Decimal("1.01")).quantize(tick, rounding=ROUND_DOWN)


def _swap_inst_id(symbol: str) -> str:
    """Return OKX swap instrument id."""
    return symbol.upper().replace("/", "-") + "-SWAP"


def _spot_inst_id(symbol: str) -> str:
    """Return OKX spot instrument id."""
    return symbol.upper().replace("/", "-")


def _cancel_symbol(spec: DemoOrderSpec) -> str:
    """Return provider cancel symbol for a validation order."""
    if spec.instrument_type == "swap":
        return _swap_inst_id(spec.symbol)
    if spec.instrument_type == "futures":
        return spec.symbol
    return spec.symbol


def _requires_swap(strategy_name: str) -> bool:
    """Return whether a strategy validation requires OKX derivative trading."""
    return strategy_name in {"funding-rate", "spot-perp", "spot-perp-carry", "funding-carry-hedged", "futures-perp-basis"}
