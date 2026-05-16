"""Paper-only Smart DCA basket strategy scanner."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from trading_assistant.arbitrage.calculator import calculate_risk_score, percent
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.base import Candle
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class SmartDcaEstimate:
    """Read-only Smart DCA basket estimate."""

    approved: bool
    reasons: list[str]
    read_only: bool
    paper_only: bool
    symbol: str
    exchange: str
    current_price: Decimal
    execution_price: Decimal
    recent_high: Decimal
    drawdown_pct: Decimal
    tier_multiplier: Decimal
    target_weight_pct: Decimal
    current_weight_pct: Decimal
    weight_gap_pct: Decimal
    rebalance_action: str
    portfolio_value_usdt: Decimal
    quote_balance_usdt: Decimal
    asset_value_usdt: Decimal
    depth_usdt: Decimal
    order_notional_usdt: Decimal
    quantity: Decimal
    expected_discount_usdt: Decimal
    estimated_fee_usdt: Decimal
    estimated_slippage_usdt: Decimal
    net_edge_usdt: Decimal
    net_edge_pct: Decimal

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(
            {
                **self.__dict__,
                "dca_order": self.dca_order(),
                "basket": self.basket(),
            }
        )

    def dca_order(self) -> dict[str, Decimal | str]:
        """Return DCA order evidence."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "side": "buy",
            "price": self.execution_price,
            "current_price": self.current_price,
            "recent_high": self.recent_high,
            "drawdown_pct": self.drawdown_pct,
            "tier_multiplier": self.tier_multiplier,
            "order_notional_usdt": self.order_notional_usdt,
            "expected_discount_usdt": self.expected_discount_usdt,
            "estimated_fee_usdt": self.estimated_fee_usdt,
            "estimated_slippage_usdt": self.estimated_slippage_usdt,
            "net_edge_usdt": self.net_edge_usdt,
        }

    def basket(self) -> dict[str, Decimal | str]:
        """Return basket rebalance evidence."""
        return {
            "portfolio_value_usdt": self.portfolio_value_usdt,
            "quote_balance_usdt": self.quote_balance_usdt,
            "asset_value_usdt": self.asset_value_usdt,
            "target_weight_pct": self.target_weight_pct,
            "current_weight_pct": self.current_weight_pct,
            "weight_gap_pct": self.weight_gap_pct,
            "rebalance_action": self.rebalance_action,
        }


class SmartDcaStrategyService:
    """Build Smart DCA basket opportunities for paper validation only."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def scan(self, symbol: str = "BTC/USDT", exchange: str | None = None) -> list[ArbitrageOpportunity]:
        """Return Smart DCA paper opportunities."""
        target_exchange = exchange or self.settings.smart_dca.exchange
        estimate = self._estimate(symbol=symbol, exchange=target_exchange)
        if not estimate.approved:
            return []
        return [self._opportunity(estimate)]

    def diagnose(self, symbol: str = "BTC/USDT", exchange: str | None = None) -> dict[str, Any]:
        """Return diagnostics even when no opportunity passes filters."""
        target_exchange = exchange or self.settings.smart_dca.exchange
        return self._estimate(symbol=symbol, exchange=target_exchange).to_dict()

    def _estimate(self, *, symbol: str, exchange: str) -> SmartDcaEstimate:
        adapter = self.exchanges.get(exchange)
        ticker = adapter.get_ticker(symbol)
        orderbook = adapter.get_orderbook(ticker.symbol)
        candles = [
            candle
            for candle in adapter.get_candles(
                ticker.symbol,
                bar=self.settings.universe.bar,
                limit=max(self.settings.smart_dca.drawdown_lookback_candles, self.settings.universe.candles_limit),
            )
            if candle.complete
        ][-self.settings.smart_dca.drawdown_lookback_candles :]
        recent_high = _recent_high(candles, ticker.last)
        drawdown_pct = _drawdown_pct(recent_high, ticker.last)
        tier_multiplier = _tier_multiplier(
            drawdown_pct,
            self.settings.smart_dca.drawdown_tiers_pct,
            self.settings.smart_dca.tier_multipliers,
        )
        basket = _basket_state(
            settings=self.settings,
            exchanges=self.exchanges,
            exchange=exchange,
            symbol=ticker.symbol,
        )
        rebalance_action = _rebalance_action(
            current_weight_pct=basket["current_weight_pct"],
            target_weight_pct=basket["target_weight_pct"],
            band_pct=self.settings.smart_dca.rebalance_band_pct,
        )
        notional = self._order_notional(tier_multiplier=tier_multiplier, rebalance_action=rebalance_action)
        execution_price = orderbook.best_ask.price
        quantity = notional / execution_price if execution_price > 0 else Decimal("0")
        expected_discount = notional * drawdown_pct / Decimal("100")
        fee = notional * self.settings.smart_dca.fee_pct
        slippage = notional * self.settings.smart_dca.slippage_pct
        net_edge = expected_discount - fee - slippage
        net_edge_pct = percent(net_edge, notional)
        depth = max(orderbook.depth_notional("ask"), Decimal("0"))
        reasons = _reasons(
            enabled=self.settings.smart_dca.enabled,
            symbol=ticker.symbol,
            enabled_symbols=self.settings.smart_dca.symbols,
            drawdown_pct=drawdown_pct,
            min_drawdown_pct=self.settings.smart_dca.min_drawdown_pct,
            target_weight_pct=basket["target_weight_pct"],
            rebalance_action=rebalance_action,
            quote_balance_usdt=basket["quote_balance_usdt"],
            order_notional_usdt=notional,
            depth_usdt=depth,
            min_depth_usdt=self.settings.smart_dca.min_depth_usdt,
            net_edge_usdt=net_edge,
        )
        return SmartDcaEstimate(
            approved=not reasons,
            reasons=reasons,
            read_only=True,
            paper_only=True,
            symbol=ticker.symbol,
            exchange=exchange,
            current_price=ticker.last,
            execution_price=execution_price,
            recent_high=recent_high,
            drawdown_pct=drawdown_pct,
            tier_multiplier=tier_multiplier,
            target_weight_pct=basket["target_weight_pct"],
            current_weight_pct=basket["current_weight_pct"],
            weight_gap_pct=basket["target_weight_pct"] - basket["current_weight_pct"],
            rebalance_action=rebalance_action,
            portfolio_value_usdt=basket["portfolio_value_usdt"],
            quote_balance_usdt=basket["quote_balance_usdt"],
            asset_value_usdt=basket["asset_value_usdt"],
            depth_usdt=depth,
            order_notional_usdt=notional,
            quantity=quantity,
            expected_discount_usdt=expected_discount,
            estimated_fee_usdt=fee,
            estimated_slippage_usdt=slippage,
            net_edge_usdt=net_edge,
            net_edge_pct=net_edge_pct,
        )

    def _order_notional(self, *, tier_multiplier: Decimal, rebalance_action: str) -> Decimal:
        multiplier = tier_multiplier
        if rebalance_action == "accumulate_underweight":
            multiplier *= self.settings.smart_dca.underweight_boost_multiplier
        notional = self.settings.smart_dca.base_order_usdt * multiplier
        return min(notional, self.settings.smart_dca.max_cycle_quote_usdt)

    def _opportunity(self, estimate: SmartDcaEstimate) -> ArbitrageOpportunity:
        return ArbitrageOpportunity(
            opportunity_id=f"smart-dca-basket-{estimate.exchange}-{estimate.symbol.lower().replace('/', '-')}",
            strategy_type="smart-dca-basket",
            symbol=estimate.symbol,
            buy_exchange=estimate.exchange,
            sell_exchange=None,
            expected_profit=estimate.expected_discount_usdt,
            expected_profit_pct=percent(estimate.expected_discount_usdt, estimate.order_notional_usdt),
            estimated_fee=estimate.estimated_fee_usdt,
            estimated_slippage=estimate.estimated_slippage_usdt,
            required_capital=estimate.order_notional_usdt,
            net_profit=estimate.net_edge_usdt,
            risk_score=calculate_risk_score(estimate.net_edge_pct, self.settings.smart_dca.slippage_pct, estimate.depth_usdt),
            confidence=Decimal("0.52"),
            metadata={
                "read_only": True,
                "paper_only": True,
                "demo_supported": False,
                "live_supported": False,
                "dca_order": estimate.dca_order(),
                "basket": estimate.basket(),
                "diagnostics": estimate.to_dict(),
                "quantity": estimate.quantity,
                "legs": [
                    {
                        "exchange": estimate.exchange,
                        "symbol": estimate.symbol,
                        "side": "buy",
                        "market": "spot",
                        "price": estimate.execution_price,
                        "quantity": estimate.quantity,
                        "notional_usdt": estimate.order_notional_usdt,
                    }
                ],
            },
        )


def _recent_high(candles: list[Candle], fallback: Decimal) -> Decimal:
    """Return recent completed-candle high."""
    if not candles:
        return fallback
    return max((candle.high for candle in candles), default=fallback)


def _drawdown_pct(recent_high: Decimal, current_price: Decimal) -> Decimal:
    """Return current drawdown from recent high in percent."""
    if recent_high <= 0 or current_price >= recent_high:
        return Decimal("0")
    return percent(recent_high - current_price, recent_high)


def _tier_multiplier(drawdown_pct: Decimal, tiers: list[Decimal], multipliers: list[Decimal]) -> Decimal:
    """Return the configured DCA size multiplier for the observed drawdown."""
    selected = Decimal("1")
    for tier, multiplier in sorted(zip(tiers, multipliers), key=lambda item: item[0]):
        if drawdown_pct >= tier:
            selected = multiplier
    return selected


def _basket_state(
    *,
    settings: Settings,
    exchanges: ExchangeFactory,
    exchange: str,
    symbol: str,
) -> dict[str, Decimal]:
    """Return portfolio weight evidence for a configured basket symbol."""
    adapter = exchanges.get(exchange)
    balances = adapter.get_balances()
    quote_asset = symbol.split("/")[1]
    quote_balance = balances.balance_for(quote_asset).free
    target_weights = _normalized_targets(settings.smart_dca.target_weights_pct)
    asset_values: dict[str, Decimal] = {}
    for target_symbol in target_weights:
        base_asset = target_symbol.split("/")[0]
        balance = balances.balance_for(base_asset)
        try:
            price = adapter.get_ticker(target_symbol).last
        except Exception:
            price = Decimal("0")
        asset_values[target_symbol] = max(balance.free * price, Decimal("0"))
    portfolio_value = quote_balance + sum(asset_values.values(), Decimal("0"))
    asset_value = asset_values.get(symbol, Decimal("0"))
    return {
        "portfolio_value_usdt": portfolio_value,
        "quote_balance_usdt": quote_balance,
        "asset_value_usdt": asset_value,
        "target_weight_pct": target_weights.get(symbol, Decimal("0")),
        "current_weight_pct": percent(asset_value, portfolio_value),
    }


def _normalized_targets(targets: dict[str, Decimal]) -> dict[str, Decimal]:
    """Normalize configured target weights to percentage points."""
    total = sum(targets.values(), Decimal("0"))
    if total <= 0:
        return {symbol: Decimal("0") for symbol in targets}
    return {symbol: percent(weight, total) for symbol, weight in targets.items()}


def _rebalance_action(*, current_weight_pct: Decimal, target_weight_pct: Decimal, band_pct: Decimal) -> str:
    """Return the basket rebalance action for an asset."""
    if target_weight_pct <= 0:
        return "missing_target"
    if current_weight_pct < target_weight_pct - band_pct:
        return "accumulate_underweight"
    if current_weight_pct > target_weight_pct + band_pct:
        return "hold_overweight"
    return "hold_inside_band"


def _reasons(
    *,
    enabled: bool,
    symbol: str,
    enabled_symbols: list[str],
    drawdown_pct: Decimal,
    min_drawdown_pct: Decimal,
    target_weight_pct: Decimal,
    rebalance_action: str,
    quote_balance_usdt: Decimal,
    order_notional_usdt: Decimal,
    depth_usdt: Decimal,
    min_depth_usdt: Decimal,
    net_edge_usdt: Decimal,
) -> list[str]:
    """Return Smart DCA filter reason codes."""
    reasons: list[str] = []
    if not enabled:
        reasons.append("smart_dca_disabled")
    if symbol not in enabled_symbols:
        reasons.append("symbol_not_enabled")
    if drawdown_pct < min_drawdown_pct:
        reasons.append("drawdown_below_minimum")
    if target_weight_pct <= 0 or rebalance_action == "missing_target":
        reasons.append("target_weight_missing")
    if rebalance_action == "hold_overweight":
        reasons.append("basket_overweight")
    if quote_balance_usdt < order_notional_usdt:
        reasons.append("quote_balance_below_order_notional")
    if depth_usdt < min_depth_usdt or depth_usdt < order_notional_usdt:
        reasons.append("depth_below_minimum")
    if net_edge_usdt <= 0:
        reasons.append("expected_discount_after_costs_not_positive")
    return reasons
