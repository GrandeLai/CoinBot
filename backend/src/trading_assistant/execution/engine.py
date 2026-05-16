"""Execution engine with explicit real-trading safety gates."""

from __future__ import annotations

from trading_assistant.arbitrage.scanner import ArbitrageScanner
from trading_assistant.config.schema import Settings
from trading_assistant.exceptions import NotFoundError, RiskError, SafetyError
from trading_assistant.execution.order import ExecutionResult
from trading_assistant.execution.simulator import OrderSimulator
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.risk.manager import RiskManager


class ExecutionEngine:
    """Execute opportunities through dry-run simulation by default."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def execute(self, opportunity_id: str, dry_run: bool | None = None) -> ExecutionResult:
        """Execute or simulate an opportunity after safety and risk checks."""
        effective_dry_run = self.settings.trading.dry_run if dry_run is None else dry_run
        opportunity = self.find_opportunity(opportunity_id)
        risk_decision = RiskManager(self.settings.risk).evaluate(opportunity)
        if not risk_decision.approved:
            raise RiskError(f"Risk check failed: {', '.join(risk_decision.violations)}")
        if not effective_dry_run:
            self._assert_real_trading_allowed(opportunity.buy_exchange, opportunity.sell_exchange)
        orders = OrderSimulator().simulate(opportunity)
        return ExecutionResult(
            opportunity_id=opportunity.opportunity_id,
            status="simulated",
            dry_run=True,
            risk_decision=risk_decision,
            orders=orders,
            net_profit=opportunity.net_profit,
            message="Dry-run simulation completed; no live orders were sent.",
        )

    def find_opportunity(self, opportunity_id: str):
        """Find a deterministic opportunity by ID."""
        scanner = ArbitrageScanner(self.settings, self.exchanges)
        for strategy_type in (
            "cross-exchange",
            "triangular",
            "triangular-multi-route",
            "funding-rate",
            "funding-carry-hedged",
            "spot-perp",
            "spot-perp-carry",
            "futures-perp-basis",
            "trend-breakout",
            "mean-reversion-spot",
            "volatility-squeeze-breakout",
            "momentum-rotation",
            "orderbook-imbalance-scalp",
            "range-grid",
            "smart-dca-basket",
            "hedged-maker",
        ):
            symbols = self.settings.directional.symbols if strategy_type in {"momentum-rotation"} else ["BTC/USDT", *self.settings.directional.symbols]
            for symbol in dict.fromkeys(symbols):
                for opportunity in scanner.scan(strategy_type, symbol=symbol, exchange="mock"):
                    if opportunity.opportunity_id == opportunity_id:
                        return opportunity
        raise NotFoundError(f"Opportunity not found: {opportunity_id}")

    def _find_opportunity(self, opportunity_id: str):
        """Backward-compatible private alias."""
        return self.find_opportunity(opportunity_id)

    def _assert_real_trading_allowed(self, buy_exchange: str | None, sell_exchange: str | None) -> None:
        """Guard real execution behind all required safety gates."""
        if not self.settings.trading.live_trading:
            raise SafetyError("real trading requires trading.live_trading=true")
        if self.settings.trading.dry_run:
            raise SafetyError("real trading requires trading.dry_run=false")
        involved = {name for name in (buy_exchange, sell_exchange) if name}
        if any(name.startswith("mock") for name in involved):
            raise SafetyError("real trading requires a non-mock exchange")
        for name in involved:
            config = self.settings.exchanges.get(name)
            if config is None or not config.enabled:
                raise SafetyError(f"real trading requires enabled exchange config: {name}")
            if not config.redacted_credentials().get("api_key") or not config.redacted_credentials().get("api_secret"):
                raise SafetyError(f"real trading requires credentials from environment variables: {name}")
