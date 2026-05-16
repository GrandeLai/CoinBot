"""Paper-only hedged maker / XEMM quote planner."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from trading_assistant.arbitrage.calculator import calculate_risk_score, percent
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.utils.serialization import to_jsonable


MakerSide = Literal["buy", "sell"]
HedgeSide = Literal["buy", "sell"]


@dataclass(frozen=True)
class HedgedMakerEstimate:
    """Paper quote and hedge estimate."""

    approved: bool
    reasons: list[str]
    symbol: str
    maker_exchange: str
    hedge_exchange: str
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
    paper_only: bool = True
    read_only: bool = True

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


class HedgedMakerStrategyService:
    """Plan passive maker quotes and immediate taker hedge previews."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def scan(
        self,
        symbol: str = "BTC/USDT",
        maker_exchange: str | None = None,
        hedge_exchange: str | None = None,
    ) -> list[ArbitrageOpportunity]:
        """Return the best approved hedged-maker paper opportunity."""
        estimate = self._estimate(
            symbol=symbol,
            maker_exchange=maker_exchange or self.settings.hedged_maker.maker_exchange,
            hedge_exchange=hedge_exchange or self.settings.hedged_maker.hedge_exchange,
        )
        if not estimate.approved:
            return []
        return [self._opportunity(estimate)]

    def diagnose(
        self,
        symbol: str = "BTC/USDT",
        maker_exchange: str | None = None,
        hedge_exchange: str | None = None,
    ) -> dict[str, object]:
        """Return diagnostics even when no paper opportunity passes filters."""
        return self._estimate(
            symbol=symbol,
            maker_exchange=maker_exchange or self.settings.hedged_maker.maker_exchange,
            hedge_exchange=hedge_exchange or self.settings.hedged_maker.hedge_exchange,
        ).to_dict()

    def _estimate(self, *, symbol: str, maker_exchange: str, hedge_exchange: str) -> HedgedMakerEstimate:
        maker = self.exchanges.get(maker_exchange)
        hedge = self.exchanges.get(hedge_exchange)
        maker_ticker = maker.get_ticker(symbol)
        hedge_ticker = hedge.get_ticker(symbol)
        maker_orderbook = maker.get_orderbook(symbol)
        hedge_orderbook = hedge.get_orderbook(symbol)
        maker_mid = (maker_ticker.bid + maker_ticker.ask) / Decimal("2")
        candidates = [
            self._candidate(
                symbol=maker_ticker.symbol,
                maker_exchange=maker_exchange,
                hedge_exchange=hedge_exchange,
                maker_side="buy",
                hedge_side="sell",
                maker_mid=maker_mid,
                maker_quote_price=maker_mid * (Decimal("1") - self.settings.hedged_maker.quote_spread_pct / Decimal("100")),
                hedge_price=hedge_ticker.bid,
                maker_depth=maker_orderbook.depth_notional("bid"),
                hedge_depth=hedge_orderbook.depth_notional("bid"),
            ),
            self._candidate(
                symbol=maker_ticker.symbol,
                maker_exchange=maker_exchange,
                hedge_exchange=hedge_exchange,
                maker_side="sell",
                hedge_side="buy",
                maker_mid=maker_mid,
                maker_quote_price=maker_mid * (Decimal("1") + self.settings.hedged_maker.quote_spread_pct / Decimal("100")),
                hedge_price=hedge_ticker.ask,
                maker_depth=maker_orderbook.depth_notional("ask"),
                hedge_depth=hedge_orderbook.depth_notional("ask"),
            ),
        ]
        return max(candidates, key=lambda item: item.net_profit_usdt)

    def _candidate(
        self,
        *,
        symbol: str,
        maker_exchange: str,
        hedge_exchange: str,
        maker_side: MakerSide,
        hedge_side: HedgeSide,
        maker_mid: Decimal,
        maker_quote_price: Decimal,
        hedge_price: Decimal,
        maker_depth: Decimal,
        hedge_depth: Decimal,
    ) -> HedgedMakerEstimate:
        quantity = self.settings.hedged_maker.quote_notional_usdt / maker_quote_price if maker_quote_price > 0 else Decimal("0")
        quote_notional = maker_quote_price * quantity
        hedge_notional = hedge_price * quantity
        gross_profit = (hedge_notional - quote_notional) if maker_side == "buy" else (quote_notional - hedge_notional)
        fees = quote_notional * self.settings.hedged_maker.maker_fee_pct + hedge_notional * self.settings.hedged_maker.taker_fee_pct
        slippage = hedge_notional * self.settings.hedged_maker.hedge_slippage_pct
        net_profit = gross_profit - fees - slippage
        net_profit_pct = percent(net_profit, quote_notional)
        reasons = self._reasons(
            symbol=symbol,
            maker_exchange=maker_exchange,
            hedge_exchange=hedge_exchange,
            maker_side=maker_side,
            quantity=quantity,
            hedge_depth=hedge_depth,
            net_profit_pct=net_profit_pct,
        )
        return HedgedMakerEstimate(
            approved=not reasons,
            reasons=reasons,
            symbol=symbol,
            maker_exchange=maker_exchange,
            hedge_exchange=hedge_exchange,
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
            net_profit_pct=net_profit_pct,
            maker_depth_usdt=maker_depth,
            hedge_depth_usdt=hedge_depth,
        )

    def _reasons(
        self,
        *,
        symbol: str,
        maker_exchange: str,
        hedge_exchange: str,
        maker_side: MakerSide,
        quantity: Decimal,
        hedge_depth: Decimal,
        net_profit_pct: Decimal,
    ) -> list[str]:
        """Return hedged-maker filter reasons."""
        reasons: list[str] = []
        if not self.settings.hedged_maker.enabled:
            reasons.append("hedged_maker_disabled")
        if maker_exchange == hedge_exchange:
            reasons.append("maker_and_hedge_exchange_must_differ")
        if hedge_depth < self.settings.hedged_maker.min_hedge_depth_usdt:
            reasons.append("hedge_depth_below_minimum")
        if net_profit_pct < self.settings.hedged_maker.min_edge_pct:
            reasons.append("edge_below_minimum")
        reasons.extend(self._inventory_reasons(symbol, maker_exchange, maker_side, quantity))
        return reasons

    def _inventory_reasons(self, symbol: str, maker_exchange: str, maker_side: MakerSide, quantity: Decimal) -> list[str]:
        """Return maker inventory gating reasons for a paper quote."""
        account = self.exchanges.get(maker_exchange).get_balances()
        base_asset, quote_asset = _split_symbol(symbol)
        if maker_side == "buy":
            quote_balance = account.balance_for(quote_asset)
            if quote_balance.free < self.settings.hedged_maker.quote_notional_usdt:
                return ["maker_quote_balance_insufficient"]
            return []
        base_balance = account.balance_for(base_asset)
        if base_balance.free < quantity:
            return ["maker_inventory_insufficient"]
        return []

    def _opportunity(self, estimate: HedgedMakerEstimate) -> ArbitrageOpportunity:
        return ArbitrageOpportunity(
            opportunity_id=f"hedged-maker-{estimate.maker_exchange}-{estimate.hedge_exchange}-{estimate.symbol.lower().replace('/', '-')}",
            strategy_type="hedged-maker",
            symbol=estimate.symbol,
            buy_exchange=estimate.maker_exchange if estimate.maker_side == "buy" else estimate.hedge_exchange,
            sell_exchange=estimate.hedge_exchange if estimate.hedge_side == "sell" else estimate.maker_exchange,
            expected_profit=estimate.gross_profit_usdt,
            expected_profit_pct=percent(estimate.gross_profit_usdt, estimate.quote_notional_usdt),
            estimated_fee=estimate.estimated_fee_usdt,
            estimated_slippage=estimate.estimated_slippage_usdt,
            required_capital=estimate.quote_notional_usdt,
            net_profit=estimate.net_profit_usdt,
            risk_score=calculate_risk_score(estimate.net_profit_pct, self.settings.hedged_maker.hedge_slippage_pct, estimate.hedge_depth_usdt),
            confidence=Decimal("0.56"),
            metadata={
                "read_only": True,
                "paper_only": True,
                "demo_supported": False,
                "live_supported": False,
                "maker_order_type": "limit_post_only",
                "hedge_order_type": "taker_market_preview",
                "maker_quote": {
                    "exchange": estimate.maker_exchange,
                    "symbol": estimate.symbol,
                    "side": estimate.maker_side,
                    "price": estimate.maker_quote_price,
                    "quantity": estimate.quantity,
                    "notional_usdt": estimate.quote_notional_usdt,
                },
                "hedge_preview": {
                    "exchange": estimate.hedge_exchange,
                    "symbol": estimate.symbol,
                    "side": estimate.hedge_side,
                    "price": estimate.hedge_price,
                    "quantity": estimate.quantity,
                    "notional_usdt": estimate.hedge_notional_usdt,
                },
                "legs": [
                    {
                        "role": "maker_quote",
                        "exchange": estimate.maker_exchange,
                        "symbol": estimate.symbol,
                        "side": estimate.maker_side,
                        "market": "spot",
                        "price": estimate.maker_quote_price,
                        "quantity": estimate.quantity,
                        "notional_usdt": estimate.quote_notional_usdt,
                    },
                    {
                        "role": "taker_hedge",
                        "exchange": estimate.hedge_exchange,
                        "symbol": estimate.symbol,
                        "side": estimate.hedge_side,
                        "market": "spot",
                        "price": estimate.hedge_price,
                        "quantity": estimate.quantity,
                        "notional_usdt": estimate.hedge_notional_usdt,
                    },
                ],
                "quantity": estimate.quantity,
                "diagnostics": estimate.to_dict(),
            },
        )


def _split_symbol(symbol: str) -> tuple[str, str]:
    """Split BASE/QUOTE symbol text."""
    parts = symbol.split("/", 1)
    if len(parts) != 2:
        return symbol, "USDT"
    return parts[0], parts[1]
