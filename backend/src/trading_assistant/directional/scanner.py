"""Opportunity scanner for long-only OKX spot directional strategies."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from trading_assistant.arbitrage.calculator import percent
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import Settings
from trading_assistant.directional.backtest import DirectionalBacktestEngine
from trading_assistant.directional.models import DirectionalBacktestResult, DirectionalSignal
from trading_assistant.directional.strategies import strategy_for_name
from trading_assistant.exchanges.factory import ExchangeFactory


DIRECTIONAL_STRATEGY_TYPES = {
    "trend-breakout",
    "mean-reversion-spot",
    "volatility-squeeze-breakout",
    "momentum-rotation",
    "orderbook-imbalance-scalp",
}


class DirectionalOpportunityScanner:
    """Scan directional spot strategies and wrap buy signals as opportunities."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def scan(
        self,
        strategy_name: str,
        *,
        symbol: str = "BTC/USDT",
        exchange: str | None = None,
    ) -> tuple[list[ArbitrageOpportunity], dict[str, Any]]:
        """Return opportunities and transparent diagnostics for one directional strategy."""
        target_exchange = exchange or self.settings.directional.exchange
        symbols = self._symbols_for_strategy(strategy_name, symbol)
        candidates: list[dict[str, Any]] = []
        opportunities: list[ArbitrageOpportunity] = []
        for candidate_symbol in symbols:
            opportunity, diagnostics = self._scan_symbol(strategy_name, candidate_symbol, target_exchange)
            candidates.append(diagnostics)
            if opportunity is not None:
                opportunities.append(opportunity)
        opportunities.sort(key=lambda item: item.net_profit, reverse=True)
        diagnostics = {
            "approved": bool(opportunities),
            "strategy_name": strategy_name,
            "exchange": target_exchange,
            "symbol": symbol,
            "candidates": candidates,
            "best_candidate": candidates[0] if candidates else {},
            "reasons": [] if opportunities else _unique_reasons(candidates),
        }
        if strategy_name == "momentum-rotation":
            opportunities = opportunities[:2]
        return opportunities, diagnostics

    def _scan_symbol(self, strategy_name: str, symbol: str, exchange: str) -> tuple[ArbitrageOpportunity | None, dict[str, Any]]:
        adapter = self.exchanges.get(exchange)
        candles = adapter.get_candles(symbol, bar=self.settings.directional.bar, limit=self.settings.directional.candles_limit)
        orderbook = adapter.get_orderbook(symbol) if strategy_name == "orderbook-imbalance-scalp" else None
        signal = strategy_for_name(strategy_name).generate_signal(candles, symbol=symbol, exchange=exchange, orderbook=orderbook)
        backtest = DirectionalBacktestEngine(
            notional_usdt=self._position_notional(),
            fee_pct=self.settings.directional.fee_pct,
            slippage_pct=self.settings.directional.slippage_pct,
        ).run(strategy_name, symbol, exchange, candles)
        reasons = self._gate_reasons(signal, backtest)
        diagnostics: dict[str, Any] = {
            "approved": not reasons,
            "strategy_name": strategy_name,
            "symbol": symbol,
            "exchange": exchange,
            "signal": signal.to_dict(),
            "backtest": backtest.to_dict(),
            "reasons": reasons,
        }
        if reasons:
            return None, diagnostics
        notional = self._position_notional()
        latest_price = candles[-1].close if candles else Decimal("1")
        quantity = (notional / latest_price).quantize(Decimal("0.00000001")) if latest_price > 0 else Decimal("0")
        expected_profit = (notional * signal.expected_edge_pct / Decimal("100")).quantize(Decimal("0.000001"))
        estimated_fee = (notional * self.settings.directional.fee_pct * Decimal("2")).quantize(Decimal("0.000001"))
        estimated_slippage = (notional * self.settings.directional.slippage_pct * Decimal("2")).quantize(Decimal("0.000001"))
        net_profit = (expected_profit - estimated_fee - estimated_slippage).quantize(Decimal("0.000001"))
        if net_profit <= 0:
            diagnostics["approved"] = False
            diagnostics["reasons"] = [*reasons, "net_profit_after_costs_not_positive"]
            diagnostics["net_profit_usdt"] = net_profit
            return None, diagnostics
        opportunity = ArbitrageOpportunity(
            opportunity_id=f"directional-{strategy_name}-{symbol.lower().replace('/', '-')}",
            strategy_type=strategy_name,
            symbol=symbol,
            buy_exchange=exchange,
            sell_exchange=None,
            expected_profit=expected_profit,
            expected_profit_pct=signal.expected_edge_pct,
            estimated_fee=estimated_fee,
            estimated_slippage=estimated_slippage,
            required_capital=notional,
            net_profit=net_profit,
            risk_score=_risk_score(signal, backtest),
            confidence=signal.confidence,
            metadata={
                "market": "spot",
                "direction": "long",
                "directional_signal": signal.to_dict(),
                "position_lifecycle": "planned",
                "backtest": backtest.to_dict(),
                "fees_slippage_adjusted": True,
                "account_equity_attribution": backtest.account_equity_attribution,
                "legs": [
                    {
                        "exchange": exchange,
                        "symbol": symbol,
                        "side": "buy",
                        "market": "spot",
                        "price": latest_price,
                        "quantity": quantity,
                        "notional_usdt": notional,
                    }
                ],
                "quantity": quantity,
            },
        )
        diagnostics["net_profit_usdt"] = net_profit
        diagnostics["net_profit_pct"] = percent(net_profit, notional)
        return opportunity, diagnostics

    def _gate_reasons(self, signal: DirectionalSignal, backtest: DirectionalBacktestResult) -> list[str]:
        reasons: list[str] = []
        if signal.signal != "buy":
            reasons.append(f"signal_{signal.signal}")
        if backtest.total_trades <= 0:
            reasons.append("backtest_no_trades")
        if backtest.net_pnl_usdt <= self.settings.directional.min_backtest_net_profit_usdt:
            reasons.append("backtest_net_profit_not_positive")
        if backtest.profit_factor < self.settings.directional.min_profit_factor:
            reasons.append("backtest_profit_factor_below_minimum")
        if backtest.max_drawdown_pct > self.settings.directional.max_backtest_drawdown_pct:
            reasons.append("backtest_drawdown_above_maximum")
        return reasons

    def _position_notional(self) -> Decimal:
        return min(
            self.settings.directional.max_position_value_usdt,
            self.settings.strategy_runtime.max_position_value_usdt,
            self.settings.risk.max_order_value_usdt,
        )

    def _symbols_for_strategy(self, strategy_name: str, symbol: str) -> list[str]:
        if strategy_name == "momentum-rotation":
            return list(self.settings.directional.symbols)
        return [symbol]


def _risk_score(signal: DirectionalSignal, backtest: DirectionalBacktestResult) -> Decimal:
    drawdown_component = min(backtest.max_drawdown_pct / Decimal("10"), Decimal("0.6"))
    confidence_offset = (Decimal("1") - signal.confidence) * Decimal("0.4")
    return max(Decimal("0.05"), min(drawdown_component + confidence_offset, Decimal("0.95"))).quantize(Decimal("0.0001"))


def _unique_reasons(candidates: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    for candidate in candidates:
        for reason in candidate.get("reasons", []):
            if str(reason) not in reasons:
                reasons.append(str(reason))
    return reasons
