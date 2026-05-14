"""End-to-end trading route orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from trading_assistant.account.service import AccountService
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.arbitrage.scanner import ArbitrageScanner
from trading_assistant.backtesting.engine import BacktestEngine
from trading_assistant.config.schema import Settings
from trading_assistant.execution.engine import ExecutionEngine
from trading_assistant.execution.live_agent import AgentLiveTradingGate
from trading_assistant.execution.paper import PaperTradingLedger
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.market_data.service import MarketDataService
from trading_assistant.reporting.report import ReportGenerator
from trading_assistant.risk.manager import RiskManager
from trading_assistant.utils.serialization import to_jsonable


StageStatus = Literal["completed", "blocked"]


@dataclass(frozen=True)
class WorkflowStage:
    """One route stage status."""

    name: str
    status: StageStatus
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe stage payload."""
        return to_jsonable(self)


@dataclass(frozen=True)
class ReadinessResult:
    """Readiness gate result."""

    ready: bool
    reasons: list[str]
    checks: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe readiness payload."""
        return to_jsonable(self)


@dataclass(frozen=True)
class WorkflowResult:
    """Full safe trading route result."""

    completed: bool
    live_ready: bool
    selected_opportunity_id: str | None
    stages: list[WorkflowStage]
    opportunities: dict[str, list[dict[str, Any]]]
    paper_trading: dict[str, Any]
    sandbox_readiness: ReadinessResult
    live_readiness: ReadinessResult
    agent_live_readiness: ReadinessResult
    report: dict[str, Any]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe workflow payload."""
        return to_jsonable(self)


class TradingRouteWorkflow:
    """Orchestrate the safe route from research to live-readiness checks."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges

    def run(self, symbol: str = "BTC/USDT") -> WorkflowResult:
        """Run the complete offline-safe trading route."""
        stages: list[WorkflowStage] = []
        stages.append(self._config_stage())
        stages.append(self._market_stage(symbol))

        opportunities = self._scan_all(symbol)
        selected = self._select_opportunity(opportunities)
        stages.append(
            WorkflowStage(
                name="arbitrage_scan",
                status="completed",
                details={
                    "strategy_types": list(opportunities),
                    "selected_opportunity_id": selected.opportunity_id if selected else None,
                },
            )
        )

        backtest = BacktestEngine(self.settings, self.exchanges).run()
        stages.append(
            WorkflowStage(
                name="backtest",
                status="completed",
                details={"trades": backtest.metrics.trades, "total_return_pct": backtest.metrics.total_return_pct},
            )
        )

        paper_trading = self._paper_trade(selected)
        stages.append(
            WorkflowStage(
                name="paper_trading",
                status="completed",
                details={"trade_count": paper_trading["ledger"]["trade_count"], "dry_run": True},
            )
        )

        sandbox_readiness = self._sandbox_readiness(selected)
        stages.append(
            WorkflowStage(
                name="sandbox_readiness",
                status="completed" if sandbox_readiness.ready else "blocked",
                details=sandbox_readiness.to_dict(),
            )
        )

        live_readiness = self._live_readiness(selected)
        stages.append(
            WorkflowStage(
                name="live_readiness",
                status="completed" if live_readiness.ready else "blocked",
                details=live_readiness.to_dict(),
            )
        )

        agent_live_readiness = self._agent_live_readiness(selected)
        stages.append(
            WorkflowStage(
                name="agent_live_readiness",
                status="completed" if agent_live_readiness.ready else "blocked",
                details=agent_live_readiness.to_dict(),
            )
        )

        report = ReportGenerator(self.settings, self.exchanges).generate("daily").to_dict()
        stages.append(WorkflowStage(name="report", status="completed", details={"type": report["type"]}))

        non_blocking_gates = {"live_readiness", "agent_live_readiness"}
        return WorkflowResult(
            completed=all(stage.status == "completed" for stage in stages if stage.name not in non_blocking_gates),
            live_ready=live_readiness.ready and agent_live_readiness.ready,
            selected_opportunity_id=selected.opportunity_id if selected else None,
            stages=stages,
            opportunities={key: [opportunity.to_dict() for opportunity in value] for key, value in opportunities.items()},
            paper_trading=paper_trading,
            sandbox_readiness=sandbox_readiness,
            live_readiness=live_readiness,
            agent_live_readiness=agent_live_readiness,
            report=report,
            summary="Route completed through paper trading, sandbox readiness, and agent live-readiness gates; real orders were not sent.",
        )

    def _config_stage(self) -> WorkflowStage:
        """Return config validation stage."""
        return WorkflowStage(
            name="config",
            status="completed",
            details={
                "mode": self.settings.app.mode,
                "live_trading": self.settings.trading.live_trading,
                "dry_run": self.settings.trading.dry_run,
                "enabled_exchanges": self.exchanges.list_enabled(),
            },
        )

    def _market_stage(self, symbol: str) -> WorkflowStage:
        """Fetch mock market/account data."""
        market = MarketDataService(self.exchanges)
        account = AccountService(self.exchanges)
        ticker = market.get_ticker("mock", symbol)
        orderbook = market.get_orderbook("mock", symbol)
        balances = account.get_balance("mock")
        return WorkflowStage(
            name="mock_market_data",
            status="completed",
            details={
                "ticker": ticker.to_dict(),
                "best_bid": orderbook.best_bid.price,
                "best_ask": orderbook.best_ask.price,
                "usdt_free": balances.balance_for("USDT").free,
            },
        )

    def _scan_all(self, symbol: str) -> dict[str, list[ArbitrageOpportunity]]:
        """Scan all supported mock arbitrage strategy types."""
        scanner = ArbitrageScanner(self.settings, self.exchanges)
        return {
            "cross-exchange": scanner.scan("cross-exchange", symbol=symbol),
            "triangular": scanner.scan("triangular", exchange="mock"),
            "funding-rate": scanner.scan("funding-rate"),
            "spot-perp": scanner.scan("spot-perp", symbol=symbol),
        }

    def _select_opportunity(self, opportunities: dict[str, list[ArbitrageOpportunity]]) -> ArbitrageOpportunity | None:
        """Select the safest deterministic opportunity for paper execution."""
        cross_exchange = opportunities.get("cross-exchange", [])
        if cross_exchange:
            return cross_exchange[0]
        for candidates in opportunities.values():
            for opportunity in candidates:
                if opportunity.net_profit > Decimal("0"):
                    return opportunity
        return None

    def _paper_trade(self, selected: ArbitrageOpportunity | None) -> dict[str, Any]:
        """Dry-run execute the selected opportunity and record paper result."""
        if selected is None:
            return {"execution": None, "ledger": {"trade_count": 0, "cash_usdt": str(self.settings.backtest.initial_capital_usdt)}}
        execution = ExecutionEngine(self.settings, self.exchanges).execute(selected.opportunity_id, dry_run=True)
        ledger = PaperTradingLedger(starting_cash=self.settings.backtest.initial_capital_usdt)
        ledger.record(execution)
        return {
            "execution": execution.to_dict(),
            "ledger": {
                "trade_count": ledger.trade_count,
                "cash_usdt": ledger.cash_usdt,
                "realized_pnl_usdt": ledger.realized_pnl_usdt,
            },
        }

    def _sandbox_readiness(self, selected: ArbitrageOpportunity | None) -> ReadinessResult:
        """Check readiness for a mock/sandbox dry-run trial."""
        reasons: list[str] = []
        mock_config = self.settings.exchanges.get("mock")
        risk_decision = RiskManager(self.settings.risk).evaluate(selected) if selected is not None else None
        execution_quality_approved = self._execution_quality_approved(selected)
        if mock_config is None or not mock_config.enabled or not mock_config.sandbox:
            reasons.append("mock_sandbox_disabled")
        if not self.settings.trading.dry_run:
            reasons.append("dry_run_disabled")
        if risk_decision is None or not risk_decision.approved:
            reasons.append("risk_not_approved")
        if not execution_quality_approved:
            reasons.append("execution_quality_not_approved")
        return ReadinessResult(
            ready=not reasons,
            reasons=reasons,
            checks={
                "mock_exchange_enabled": bool(mock_config and mock_config.enabled),
                "mock_exchange_sandbox": bool(mock_config and mock_config.sandbox),
                "dry_run": self.settings.trading.dry_run,
                "risk_approved": bool(risk_decision and risk_decision.approved),
                "execution_quality_approved": execution_quality_approved,
            },
        )

    def _live_readiness(self, selected: ArbitrageOpportunity | None) -> ReadinessResult:
        """Check whether strict live-trading gates are satisfied."""
        reasons: list[str] = []
        if not self.settings.trading.live_trading:
            reasons.append("live_trading_disabled")
        if self.settings.trading.dry_run:
            reasons.append("dry_run_enabled")
        real_exchanges = {
            name: config
            for name, config in self.settings.exchanges.items()
            if config.enabled and config.adapter != "mock"
        }
        if not real_exchanges:
            reasons.append("non_mock_exchange_missing")
        if not any(
            config.redacted_credentials().get("api_key") and config.redacted_credentials().get("api_secret")
            for config in real_exchanges.values()
        ):
            reasons.append("credentials_missing")
        risk_decision = RiskManager(self.settings.risk).evaluate(selected) if selected is not None else None
        if risk_decision is None or not risk_decision.approved:
            reasons.append("risk_not_approved")
        return ReadinessResult(
            ready=not reasons,
            reasons=reasons,
            checks={
                "live_trading": self.settings.trading.live_trading,
                "dry_run": self.settings.trading.dry_run,
                "enabled_real_exchanges": list(real_exchanges),
                "credentials_from_environment": "credentials_missing" not in reasons,
                "risk_approved": bool(risk_decision and risk_decision.approved),
            },
        )

    def _agent_live_readiness(self, selected: ArbitrageOpportunity | None) -> ReadinessResult:
        """Check whether autonomous agent live-trading controls are satisfied."""
        risk_decision = RiskManager(self.settings.risk).evaluate(selected) if selected is not None else None
        readiness = AgentLiveTradingGate(self.settings).evaluate(selected, risk_decision)
        return ReadinessResult(
            ready=readiness.ready,
            reasons=readiness.reasons,
            checks=readiness.checks,
        )

    def _execution_quality_approved(self, selected: ArbitrageOpportunity | None) -> bool:
        """Return whether scanner execution-quality metadata clears sandbox gating."""
        if selected is None:
            return False
        quality = selected.metadata.get("execution_quality")
        if not isinstance(quality, dict):
            return True
        spread = quality.get("spread_persistence", {})
        depth_fill = quality.get("depth_fill", {})
        buy_fill = depth_fill.get("buy", {}) if isinstance(depth_fill, dict) else {}
        sell_fill = depth_fill.get("sell", {}) if isinstance(depth_fill, dict) else {}
        return bool(spread.get("passed") and buy_fill.get("complete") and sell_fill.get("complete"))
