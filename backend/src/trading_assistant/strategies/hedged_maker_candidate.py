"""Read-only hedged-maker OKX Demo candidate generation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from trading_assistant.arbitrage.calculator import calculate_risk_score, percent
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.base import Exchange
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.exchanges.mock import MockExchange
from trading_assistant.utils.serialization import to_jsonable


MakerSide = Literal["buy", "sell"]
HedgeSide = Literal["buy", "sell"]


@dataclass(frozen=True)
class HedgedMakerDemoCandidateEstimate:
    """One OKX demo-manager candidate estimate."""

    symbol: str
    target_exchange: str
    maker_side: MakerSide
    hedge_side: HedgeSide
    maker_mid_price: Decimal
    maker_quote_price: Decimal
    hedge_price: Decimal
    quantity: Decimal
    quote_notional_usdt: Decimal
    hedge_notional_usdt: Decimal
    gross_profit_usdt: Decimal
    estimated_fee_usdt: Decimal
    estimated_slippage_usdt: Decimal
    net_profit_usdt: Decimal
    net_profit_pct: Decimal
    maker_depth_usdt: Decimal
    hedge_depth_usdt: Decimal

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe estimate."""
        return to_jsonable(self)


@dataclass(frozen=True)
class HedgedMakerDemoCandidateReport:
    """Read-only OKX Demo hedged-maker candidate payload."""

    symbol: str
    target_exchange: str
    approved: bool
    demo_manager_compatible: bool
    reasons: list[str]
    opportunity_file_payload: dict[str, Any] | None
    diagnostics: dict[str, Any]
    next_actions: list[str]
    read_only: bool = True
    orders_sent: bool = False
    live_orders_sent: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report."""
        return to_jsonable(self)


class HedgedMakerDemoCandidateService:
    """Build explicit OKX Demo manager opportunity payloads without trading."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def candidate(self, symbol: str = "BTC/USDT", target_exchange: str = "okx") -> HedgedMakerDemoCandidateReport:
        """Return the best read-only hedged-maker demo candidate."""
        config_reasons = self._config_reasons(target_exchange)
        exchange = self._exchange(target_exchange)
        estimate = self._estimate(symbol=symbol, target_exchange=target_exchange)
        quality = _execution_quality(estimate)
        opportunity = self._opportunity(estimate, quality)
        economic_reasons = self._economic_reasons(estimate)
        reasons = sorted(set([*config_reasons, *economic_reasons]))
        demo_manager_compatible = not config_reasons
        approved = demo_manager_compatible and not economic_reasons and _quality_approved(quality)
        return HedgedMakerDemoCandidateReport(
            symbol=exchange.get_ticker(symbol).symbol,
            target_exchange=target_exchange,
            approved=approved,
            demo_manager_compatible=demo_manager_compatible,
            reasons=reasons,
            opportunity_file_payload=opportunity.to_dict(),
            diagnostics={
                "estimate": estimate.to_dict(),
                "execution_quality": quality,
                "guardrails": [
                    "read_only_no_orders",
                    "explicit_opportunity_file_required",
                    "strategy_hedged_maker_demo_gate_still_required",
                ],
            },
            next_actions=_next_actions(approved=approved, reasons=reasons),
        )

    def _exchange(self, target_exchange: str) -> Exchange:
        """Return market data, falling back to the default mock profile for mock OKX tests."""
        exchange_config = self.settings.exchanges.get(target_exchange)
        if exchange_config is not None and exchange_config.adapter == "mock" and target_exchange not in {"mock", "mock_alt"}:
            return MockExchange(name="mock")
        return self.exchanges.get(target_exchange)

    def _estimate(self, *, symbol: str, target_exchange: str) -> HedgedMakerDemoCandidateEstimate:
        """Return the best same-exchange maker/hedge candidate."""
        exchange = self._exchange(target_exchange)
        ticker = exchange.get_ticker(symbol)
        orderbook = exchange.get_orderbook(symbol)
        maker_mid = (ticker.bid + ticker.ask) / Decimal("2")
        candidates = [
            self._candidate(
                symbol=ticker.symbol,
                target_exchange=target_exchange,
                maker_side="buy",
                hedge_side="sell",
                maker_mid=maker_mid,
                maker_quote_price=maker_mid * (Decimal("1") - self.settings.hedged_maker.quote_spread_pct / Decimal("100")),
                hedge_price=ticker.bid,
                maker_depth=orderbook.depth_notional("bid"),
                hedge_depth=orderbook.depth_notional("bid"),
            ),
            self._candidate(
                symbol=ticker.symbol,
                target_exchange=target_exchange,
                maker_side="sell",
                hedge_side="buy",
                maker_mid=maker_mid,
                maker_quote_price=maker_mid * (Decimal("1") + self.settings.hedged_maker.quote_spread_pct / Decimal("100")),
                hedge_price=ticker.ask,
                maker_depth=orderbook.depth_notional("ask"),
                hedge_depth=orderbook.depth_notional("ask"),
            ),
        ]
        return max(candidates, key=lambda item: item.net_profit_usdt)

    def _candidate(
        self,
        *,
        symbol: str,
        target_exchange: str,
        maker_side: MakerSide,
        hedge_side: HedgeSide,
        maker_mid: Decimal,
        maker_quote_price: Decimal,
        hedge_price: Decimal,
        maker_depth: Decimal,
        hedge_depth: Decimal,
    ) -> HedgedMakerDemoCandidateEstimate:
        """Return one same-exchange maker/hedge estimate."""
        quantity = self.settings.hedged_maker.quote_notional_usdt / maker_quote_price if maker_quote_price > 0 else Decimal("0")
        quote_notional = maker_quote_price * quantity
        hedge_notional = hedge_price * quantity
        gross_profit = (hedge_notional - quote_notional) if maker_side == "buy" else (quote_notional - hedge_notional)
        fees = quote_notional * self.settings.hedged_maker.maker_fee_pct + hedge_notional * self.settings.hedged_maker.taker_fee_pct
        slippage = hedge_notional * self.settings.hedged_maker.hedge_slippage_pct
        net_profit = gross_profit - fees - slippage
        return HedgedMakerDemoCandidateEstimate(
            symbol=symbol,
            target_exchange=target_exchange,
            maker_side=maker_side,
            hedge_side=hedge_side,
            maker_mid_price=maker_mid,
            maker_quote_price=maker_quote_price,
            hedge_price=hedge_price,
            quantity=quantity,
            quote_notional_usdt=quote_notional,
            hedge_notional_usdt=hedge_notional,
            gross_profit_usdt=gross_profit,
            estimated_fee_usdt=fees,
            estimated_slippage_usdt=slippage,
            net_profit_usdt=net_profit,
            net_profit_pct=percent(net_profit, quote_notional),
            maker_depth_usdt=maker_depth,
            hedge_depth_usdt=hedge_depth,
        )

    def _opportunity(self, estimate: HedgedMakerDemoCandidateEstimate, quality: dict[str, Any]) -> ArbitrageOpportunity:
        """Return an explicit opportunity-file payload for the OKX Demo manager."""
        return ArbitrageOpportunity(
            opportunity_id=f"hedged-maker-demo-candidate-{estimate.symbol.lower().replace('/', '-')}",
            strategy_type="hedged-maker",
            symbol=estimate.symbol,
            buy_exchange=estimate.target_exchange,
            sell_exchange=estimate.target_exchange,
            expected_profit=estimate.gross_profit_usdt,
            expected_profit_pct=percent(estimate.gross_profit_usdt, estimate.quote_notional_usdt),
            estimated_fee=estimate.estimated_fee_usdt,
            estimated_slippage=estimate.estimated_slippage_usdt,
            required_capital=estimate.quote_notional_usdt,
            net_profit=estimate.net_profit_usdt,
            risk_score=calculate_risk_score(estimate.net_profit_pct, self.settings.hedged_maker.hedge_slippage_pct, estimate.hedge_depth_usdt),
            confidence=Decimal("0.58"),
            metadata={
                "read_only": True,
                "paper_only": False,
                "demo_manager_candidate": True,
                "demo_supported": True,
                "live_supported": False,
                "maker_order_type": "limit_post_only",
                "hedge_order_type": "limit_after_observed_maker_fill",
                "maker_quote": {
                    "exchange": estimate.target_exchange,
                    "symbol": estimate.symbol,
                    "side": estimate.maker_side,
                    "price": estimate.maker_quote_price,
                    "quantity": estimate.quantity,
                    "notional_usdt": estimate.quote_notional_usdt,
                },
                "hedge_preview": {
                    "exchange": estimate.target_exchange,
                    "symbol": estimate.symbol,
                    "side": estimate.hedge_side,
                    "price": estimate.hedge_price,
                    "quantity": estimate.quantity,
                    "notional_usdt": estimate.hedge_notional_usdt,
                },
                "execution_quality": quality,
                "diagnostics": estimate.to_dict(),
            },
        )

    def _config_reasons(self, target_exchange: str) -> list[str]:
        """Return target exchange compatibility blockers for demo manager use."""
        reasons: list[str] = []
        if target_exchange != "okx":
            reasons.append("target_exchange_not_okx")
        exchange_config = self.settings.exchanges.get(target_exchange)
        if exchange_config is None:
            return [*reasons, "target_exchange_config_missing"]
        if not exchange_config.enabled:
            reasons.append("target_exchange_disabled")
        if not exchange_config.sandbox:
            reasons.append("target_exchange_not_sandbox")
        if exchange_config.okx_demo is not True:
            reasons.append("target_exchange_not_okx_demo")
        if exchange_config.adapter == "mock":
            reasons.append("target_exchange_adapter_is_mock")
        return reasons

    def _economic_reasons(self, estimate: HedgedMakerDemoCandidateEstimate) -> list[str]:
        """Return candidate economics and liquidity blockers."""
        reasons: list[str] = []
        if not self.settings.hedged_maker.enabled:
            reasons.append("hedged_maker_disabled")
        if estimate.hedge_depth_usdt < self.settings.hedged_maker.min_hedge_depth_usdt:
            reasons.append("hedge_depth_below_minimum")
        if estimate.net_profit_pct < self.settings.hedged_maker.min_edge_pct:
            reasons.append("edge_below_minimum")
        if estimate.quantity <= 0:
            reasons.append("quantity_not_positive")
        return reasons


def _execution_quality(estimate: HedgedMakerDemoCandidateEstimate) -> dict[str, Any]:
    """Return execution-quality metadata required by demo gates."""
    buy_complete = estimate.maker_depth_usdt >= estimate.quote_notional_usdt and estimate.hedge_depth_usdt >= estimate.hedge_notional_usdt
    sell_complete = buy_complete
    spread_positive = estimate.gross_profit_usdt > 0
    return {
        "spread_persistence": {
            "passed": spread_positive,
            "gross_profit_usdt": estimate.gross_profit_usdt,
        },
        "depth_fill": {
            "buy": {
                "complete": buy_complete,
                "required_notional_usdt": estimate.quote_notional_usdt,
                "available_depth_usdt": estimate.maker_depth_usdt,
            },
            "sell": {
                "complete": sell_complete,
                "required_notional_usdt": estimate.hedge_notional_usdt,
                "available_depth_usdt": estimate.hedge_depth_usdt,
            },
        },
    }


def _quality_approved(quality: dict[str, Any]) -> bool:
    """Return whether execution quality clears the live-agent metadata contract."""
    spread = quality.get("spread_persistence", {})
    depth = quality.get("depth_fill", {})
    buy = depth.get("buy", {}) if isinstance(depth, dict) else {}
    sell = depth.get("sell", {}) if isinstance(depth, dict) else {}
    return bool(spread.get("passed") and buy.get("complete") and sell.get("complete"))


def _next_actions(*, approved: bool, reasons: list[str]) -> list[str]:
    """Return conservative next actions for the generated payload."""
    if approved:
        return [
            "review_opportunity_file_payload",
            "submit_with_strategy_hedged_maker_demo_after_demo_gate",
            "do_not_use_generic_strategy_run_demo_path",
        ]
    actions = ["keep_candidate_read_only"]
    if "target_exchange_adapter_is_mock" in reasons:
        actions.append("rerun_with_okx_demo_config_before_demo_manager")
    if "edge_below_minimum" in reasons:
        actions.append("wait_for_wider_maker_spread_before_demo")
    if "hedge_depth_below_minimum" in reasons:
        actions.append("wait_for_deeper_hedge_book_before_demo")
    return actions
