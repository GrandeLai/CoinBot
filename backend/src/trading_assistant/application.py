"""Application service facade used by CLI commands."""

from __future__ import annotations

from pathlib import Path
from time import sleep
from typing import Any

from trading_assistant.account.service import AccountService
from trading_assistant.arbitrage.io import load_opportunity_file
from trading_assistant.arbitrage.route_discovery import TriangularRouteDiscoveryService
from trading_assistant.arbitrage.scanner import ArbitrageScanner
from trading_assistant.autopilot import AutopilotRuntime, AutopilotStateStore
from trading_assistant.autopilot.models import AutopilotMode
from trading_assistant.backtesting.engine import BacktestEngine
from trading_assistant.config.loader import load_settings
from trading_assistant.config.schema import ExchangeConfig, Settings
from trading_assistant.execution.engine import ExecutionEngine
from trading_assistant.execution.live_broker import AgentLiveExecutionService
from trading_assistant.execution.live_agent import AgentLiveTradingGate
from trading_assistant.execution.okx_broker import OKXLiveBroker
from trading_assistant.execution.operation_hub import OperationValidationHub, default_operation_contracts
from trading_assistant.exceptions import SafetyError
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.exchanges.sandbox import OKXSandboxValidator
from trading_assistant.market_data.service import MarketDataService
from trading_assistant.reporting.report import ReportGenerator
from trading_assistant.risk.manager import RiskManager
from trading_assistant.strategies.demo_validation import StrategyDemoValidationService
from trading_assistant.strategies.evolution import StrategyEvolutionService
from trading_assistant.strategies.carry_basis_optimizer import CarryBasisOptimizationService
from trading_assistant.strategies.guard import StrategyRuntimeGuard
from trading_assistant.strategies.hedged_maker_report import HedgedMakerPaperEvaluationReportService
from trading_assistant.strategies.market_compare import StrategyMarketComparisonService
from trading_assistant.strategies.market_regime import StrategyMarketRegimeService
from trading_assistant.strategies.models import ExecutionMode
from trading_assistant.strategies.operator_brief import StrategyOperatorBriefService
from trading_assistant.strategies.opportunity_density import OpportunityDensityService
from trading_assistant.strategies.platform import StrategyCatalog, StrategyController, StrategyPortfolioService, StrategyScoreService
from trading_assistant.strategies.pnl_attribution import StrategyPnlAttributionService
from trading_assistant.strategies.position_executor import ExitOptimizerService
from trading_assistant.strategies.registry import StrategyRegistry
from trading_assistant.strategies.retrospective import StrategyRetrospectiveService
from trading_assistant.strategies.revival import StrategyRevivalWindowService
from trading_assistant.strategies.candidate_backtest import StrategyCandidateBacktestService
from trading_assistant.strategies.review import StrategyReviewService
from trading_assistant.strategies.runner import StrategyRunner
from trading_assistant.strategies.universe import StrategyUniverseService
from trading_assistant.strategies.validation_report import StrategyValidationReportService
from trading_assistant.validation.demo_window_orchestrator import StrategyDemoWindowOrchestrator
from trading_assistant.validation.demo_sampling_scheduler import StrategyDemoSamplingScheduler
from trading_assistant.validation.service import StrategyValidationService
from trading_assistant.workflow.route import TradingRouteWorkflow


class TradingAssistantApp:
    """Thin application facade for agent-friendly CLI workflows."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config_path = config_path
        self.settings: Settings = load_settings(config_path)
        self.exchanges = ExchangeFactory(self.settings)
        self.market = MarketDataService(self.exchanges)
        self.account = AccountService(self.exchanges)
        self.scanner = ArbitrageScanner(self.settings, self.exchanges)

    def status(self) -> dict[str, Any]:
        """Return service and safety status."""
        return {
            "status": "ok",
            "app": self.settings.app.model_dump(mode="json"),
            "safety": {
                "live_trading": self.settings.trading.live_trading,
                "dry_run": self.settings.trading.dry_run,
                "require_confirm_before_order": self.settings.trading.require_confirm_before_order,
                "agent_trading_enabled": self.settings.agent_trading.enabled,
                "agent_live_orders_allowed": self.settings.agent_trading.allow_live_orders,
            },
            "enabled_exchanges": self.exchanges.list_enabled(),
        }

    def validate_config(self) -> dict[str, Any]:
        """Return config validation payload."""
        return {"valid": True, "config": self.settings.redacted_dict()}

    def exchange_list(self) -> dict[str, Any]:
        """Return configured exchanges."""
        return {
            "exchanges": [
                {
                    "name": name,
                    "enabled": config.enabled,
                    "sandbox": config.sandbox,
                    "adapter": config.adapter,
                }
                for name, config in self.settings.exchanges.items()
            ]
        }

    def exchange_ping(self, exchange: str) -> dict[str, Any]:
        """Ping one exchange adapter."""
        return {"exchange": exchange, "ok": self.exchanges.get(exchange).ping()}

    def exchange_sandbox_check(self, exchange: str, symbol: str, include_private: bool = False) -> dict[str, Any]:
        """Run sandbox validation checks for an exchange."""
        adapter = self.exchanges.get(exchange)
        if exchange != "okx":
            from trading_assistant.exceptions import ExchangeError

            raise ExchangeError("Sandbox check currently supports only OKX")
        result = OKXSandboxValidator(adapter).run(symbol=symbol, include_private=include_private)
        return {"sandbox_check": result.to_dict()}

    def market_ticker(self, exchange: str, symbol: str) -> dict[str, Any]:
        """Return ticker payload."""
        return {"ticker": self.market.get_ticker(exchange, symbol).to_dict()}

    def market_orderbook(self, exchange: str, symbol: str) -> dict[str, Any]:
        """Return orderbook payload."""
        return {"orderbook": self.market.get_orderbook(exchange, symbol).to_dict()}

    def market_candles(self, exchange: str, symbol: str, bar: str, limit: int, history: bool = False) -> dict[str, Any]:
        """Return candle payload."""
        candles = self.market.get_candles(exchange, symbol, bar=bar, limit=limit, history=history)
        return {"candles": [candle.to_dict() for candle in candles]}

    def account_balance(self, exchange: str) -> dict[str, Any]:
        """Return account balance payload."""
        return {"account": self.account.get_balance(exchange).to_dict()}

    def arbitrage_scan(
        self,
        strategy_type: str,
        symbol: str | None = None,
        exchange: str | None = None,
        route_mode: str = "configured",
    ) -> dict[str, Any]:
        """Return arbitrage scan payload."""
        opportunities = self.scanner.scan(strategy_type, symbol=symbol, exchange=exchange, route_mode=route_mode)
        return {"opportunities": [opportunity.to_dict() for opportunity in opportunities]}

    def arbitrage_execute(self, opportunity_id: str, dry_run: bool | None = None) -> dict[str, Any]:
        """Return dry-run execution payload."""
        execution = ExecutionEngine(self.settings, self.exchanges).execute(opportunity_id, dry_run=dry_run)
        return {"execution": execution.to_dict()}

    def agent_live_readiness(self, opportunity_id: str | None = None, opportunity_file: str | Path | None = None) -> dict[str, Any]:
        """Return autonomous live-agent readiness for one opportunity."""
        opportunity = self._resolve_opportunity(opportunity_id, opportunity_file)
        risk_decision = RiskManager(self.settings.risk).evaluate(opportunity)
        readiness = AgentLiveTradingGate(self.settings).evaluate(opportunity, risk_decision)
        return {"agent_live_readiness": readiness.to_dict()}

    def agent_execute_live(self, opportunity_id: str | None = None, opportunity_file: str | Path | None = None) -> dict[str, Any]:
        """Attempt autonomous live execution after strict gate checks.

        The current broker implementation supports OKX spot limit-order legs.
        Other markets and exchanges remain blocked by the broker adapter.
        """
        opportunity = self._resolve_opportunity(opportunity_id, opportunity_file)
        risk_decision = RiskManager(self.settings.risk).evaluate(opportunity)
        execution = AgentLiveExecutionService(self.settings, broker=OKXLiveBroker(expected_demo=self._okx_expected_demo())).execute(opportunity, risk_decision)
        return {"agent_live_execution": execution.to_dict()}

    def agent_operation_catalog(self) -> dict[str, Any]:
        """Return demo/live operation parity contracts for agent trading."""
        hub = OperationValidationHub(default_operation_contracts())
        return {
            "operation_catalog": {
                **hub.to_dict(),
                "missing_demo_validation": hub.assert_all_live_operations_have_demo_validation(),
            }
        }

    def backtest_run(
        self,
        strategy_name: str | None = None,
        symbol: str | None = None,
        exchange: str | None = None,
        bar: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Return backtest payload."""
        result = BacktestEngine(self.settings, self.exchanges).run(
            strategy_name=strategy_name,
            symbol=symbol,
            exchange=exchange,
            bar=bar,
            limit=limit,
        )
        return {"backtest": result.to_dict()}

    def backtest_walk_forward(
        self,
        strategy_name: str | None = None,
        symbol: str | None = None,
        exchange: str | None = None,
        bar: str | None = None,
        limit: int | None = None,
        windows: int | None = None,
    ) -> dict[str, Any]:
        """Return walk-forward backtest payload."""
        report = BacktestEngine(self.settings, self.exchanges).walk_forward(
            strategy_name=strategy_name,
            symbol=symbol,
            exchange=exchange,
            bar=bar,
            limit=limit,
            windows=windows,
        )
        return {"backtest_walk_forward": report.to_dict()}

    def backtest_bias_check(
        self,
        strategy_name: str | None = None,
        symbol: str | None = None,
        exchange: str | None = None,
        bar: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Return backtest bias diagnostics payload."""
        report = BacktestEngine(self.settings, self.exchanges).bias_check(
            strategy_name=strategy_name,
            symbol=symbol,
            exchange=exchange,
            bar=bar,
            limit=limit,
        )
        return {"backtest_bias_check": report.to_dict()}

    def report_generate(self, report_type: str) -> dict[str, Any]:
        """Return report payload."""
        report = ReportGenerator(self.settings, self.exchanges).generate(report_type)
        return {"report": report.to_dict()}

    def workflow_run(self, symbol: str = "BTC/USDT") -> dict[str, Any]:
        """Run the complete safe trading route."""
        workflow = TradingRouteWorkflow(self.settings, self.exchanges).run(symbol=symbol)
        return {"workflow": workflow.to_dict()}

    def autopilot_run(
        self,
        *,
        mode: AutopilotMode,
        strategy_name: str,
        symbol: str,
        cycles: int,
        interval_seconds: int | None,
        demo_cycles_per_window: int,
        target_exchange: str,
        report_limit: int,
        include_private_health: bool,
    ) -> dict[str, Any]:
        """Run detached paper/demo autopilot cycles."""
        runtime = self._autopilot_runtime(
            strategy_name=strategy_name,
            symbol=symbol,
            demo_cycles_per_window=demo_cycles_per_window,
            target_exchange=target_exchange,
            report_limit=report_limit,
            include_private_health=include_private_health,
        )
        result = runtime.run(
            mode=mode,
            strategy_name=strategy_name,
            symbol=symbol,
            cycles=cycles,
            interval_seconds=interval_seconds,
            demo_cycles_per_window=demo_cycles_per_window,
            report_limit=report_limit,
        )
        return {"autopilot_run": result.to_dict()}

    def autopilot_status(self) -> dict[str, Any]:
        """Return persisted autopilot status."""
        store = AutopilotStateStore(self.settings.strategy_runtime.autopilot_state_path)
        return {"autopilot_status": store.read().to_dict()}

    def autopilot_report(
        self,
        *,
        mode: AutopilotMode,
        strategy_name: str,
        report_limit: int,
    ) -> dict[str, Any]:
        """Return read-only autopilot state and validation evidence."""
        runtime = self._autopilot_runtime(
            strategy_name=strategy_name,
            symbol="BTC/USDT",
            demo_cycles_per_window=1,
            target_exchange="okx",
            report_limit=report_limit,
            include_private_health=False,
        )
        return {"autopilot_report": runtime.report(mode=mode, strategy_name=strategy_name, report_limit=report_limit).to_dict()}

    def _autopilot_runtime(
        self,
        *,
        strategy_name: str,
        symbol: str,
        demo_cycles_per_window: int,
        target_exchange: str,
        report_limit: int,
        include_private_health: bool,
    ) -> AutopilotRuntime:
        """Build the detached autopilot runtime from existing safe services."""
        return AutopilotRuntime(
            settings=self.settings,
            state_store=AutopilotStateStore(self.settings.strategy_runtime.autopilot_state_path),
            paper_runner=lambda: self.strategy_run(
                strategy_name=strategy_name,
                max_cycles=1,
                interval_seconds=0,
                execution_mode="paper",
                symbol=symbol,
            ),
            demo_runner=lambda: self.strategy_demo_window(
                strategy_name=strategy_name,
                cycles=demo_cycles_per_window,
                symbol=symbol,
                target_exchange=target_exchange,
                report_limit=report_limit,
                include_private_health=include_private_health,
            ),
            validation_reporter=lambda execution_mode, strategy, limit: self.strategy_validation_report(
                execution_mode=execution_mode,
                strategy_name=strategy,
                limit=limit,
            ),
            operator_brief=lambda execution_mode, strategy, limit: self.strategy_operator_brief(
                execution_mode=execution_mode,
                strategy_name=strategy,
                limit=limit,
            ),
            guard_status=lambda execution_mode, strategy: self.strategy_guard_status(
                strategy_name=strategy,
                execution_mode=execution_mode,
            ),
            promotion_status=lambda strategy: self.strategy_promotion_status(strategy_name=strategy),
            sleeper=sleep,
        )

    def strategy_list(self) -> dict[str, Any]:
        """Return registered production strategy definitions."""
        return {"strategies": [strategy.to_dict() for strategy in StrategyRegistry().list()]}

    def strategy_catalog(self) -> dict[str, Any]:
        """Return strategy platform catalog metadata."""
        return {"strategy_catalog": StrategyCatalog().to_dict()}

    def strategy_scan(
        self,
        strategy_name: str,
        symbol: str,
        exchange: str | None = None,
        route_mode: str = "configured",
    ) -> dict[str, Any]:
        """Scan strategies through the strategy controller."""
        reports = StrategyController(self.settings, self.exchanges).scan(
            strategy_name=strategy_name,
            symbol=symbol,
            exchange=exchange,
            route_mode=route_mode,
        )
        return {"strategy_scan": [report.to_dict() for report in reports]}

    def strategy_discover_routes(self, exchange: str, quote: str, route_limit: int = 100) -> dict[str, Any]:
        """Discover triangular routes from exchange instruments without trading."""
        report = TriangularRouteDiscoveryService(self.settings, self.exchanges).discover(
            exchange_name=exchange,
            quote=quote,
            route_limit=route_limit,
        )
        return {"strategy_discover_routes": report.to_dict()}

    def strategy_opportunity_report(self, window: str = "24h") -> dict[str, Any]:
        """Return read-only opportunity-density evidence from the strategy journal."""
        return {"strategy_opportunity_report": OpportunityDensityService(self.settings.strategy_runtime).report(window=window).to_dict()}

    def strategy_universe(self, exchange: str) -> dict[str, Any]:
        """Return read-only dynamic universe and regime evidence."""
        report = StrategyUniverseService(self.settings, self.exchanges).report(exchange=exchange)
        return {"strategy_universe": report.to_dict()}

    def strategy_regime_report(self, exchange: str, symbol: str) -> dict[str, Any]:
        """Return read-only regime evidence for one symbol."""
        report = StrategyUniverseService(self.settings, self.exchanges).symbol_report(exchange=exchange, symbol=symbol)
        return {"strategy_regime_report": report.to_dict()}

    def strategy_exit_optimize(self, strategy_name: str, symbol: str, exchange: str) -> dict[str, Any]:
        """Return read-only triple-barrier exit parameter proposals."""
        report = ExitOptimizerService(self.settings, self.exchanges).optimize(
            strategy_name=strategy_name,
            symbol=symbol,
            exchange=exchange,
        )
        return {"strategy_exit_optimization": report.to_dict()}

    def strategy_position_report(self, strategy_name: str, symbol: str, exchange: str) -> dict[str, Any]:
        """Return read-only triple-barrier position simulation evidence."""
        report = ExitOptimizerService(self.settings, self.exchanges).position_report(
            strategy_name=strategy_name,
            symbol=symbol,
            exchange=exchange,
        )
        return {"strategy_position_report": report.to_dict()}

    def strategy_score(self, strategy_name: str, symbol: str) -> dict[str, Any]:
        """Score strategies through the strategy platform."""
        cards = StrategyScoreService(self.settings, self.exchanges).score(strategy_name=strategy_name, symbol=symbol)
        return {"strategy_score": [card.to_dict() for card in cards]}

    def strategy_market_compare(self, strategy_name: str, symbol: str, target_exchange: str | None = None) -> dict[str, Any]:
        """Compare mock baseline strategy scans against a configured target exchange."""
        result = StrategyMarketComparisonService(self.settings).compare(
            strategy_name=strategy_name,
            symbol=symbol,
            target_exchange=target_exchange,
        )
        return {"strategy_market_compare": result.to_dict()}

    def strategy_portfolio_status(self, symbol: str) -> dict[str, Any]:
        """Return strategy portfolio selection status."""
        return {"strategy_portfolio_status": StrategyPortfolioService(self.settings, self.exchanges).status(symbol=symbol).to_dict()}

    def strategy_run(
        self,
        strategy_name: str,
        max_cycles: int,
        interval_seconds: int,
        execution_mode: ExecutionMode | None,
        symbol: str,
    ) -> dict[str, Any]:
        """Run production strategy runtime."""
        retrospective = StrategyRetrospectiveService(self.settings.strategy_runtime)
        retrospective_before = retrospective.before_summary()
        result = StrategyRunner(self.settings, self.exchanges).run(
            strategy_name=strategy_name,
            max_cycles=max_cycles,
            interval_seconds=interval_seconds,
            execution_mode=execution_mode,
            symbol=symbol,
        )
        payload = {"strategy_run": result.to_dict()}
        retrospective_after = retrospective.update_after_payload("strategy_run", payload)
        evolution_after = StrategyEvolutionService(self.settings.strategy_runtime).update_after_payload(
            "strategy_run",
            payload,
            strategy_name=strategy_name,
            execution_mode=execution_mode,
        )
        return {
            **payload,
            "retrospective_before": retrospective_before,
            "retrospective_after": retrospective_after,
            "retrospective_path": retrospective_after["retrospective_path"],
            "evolution_after": evolution_after,
            "evolution_path": evolution_after["report_path"],
        }

    def strategy_review(self, execution_mode: ExecutionMode | None = None) -> dict[str, Any]:
        """Return strategy review and advisory learning suggestions."""
        retrospective = StrategyRetrospectiveService(self.settings.strategy_runtime)
        review = StrategyReviewService(self.settings.strategy_runtime).review(execution_mode=execution_mode).to_dict()
        return {"strategy_review": review, "retrospective_summary": retrospective.before_summary()}

    def strategy_retrospective(self, execution_mode: ExecutionMode | None = None) -> dict[str, Any]:
        """Return and refresh the living strategy retrospective document."""
        summary = StrategyRetrospectiveService(self.settings.strategy_runtime).refresh_from_journal(execution_mode=execution_mode)
        return {"strategy_retrospective": summary}

    def strategy_evolve(
        self,
        strategy_name: str = "all",
        execution_mode: ExecutionMode | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Refresh simulation-only strategy evolution and archive decisions."""
        market_regime = StrategyMarketRegimeService(self.settings, self.exchanges).snapshot(limit=self.settings.directional.candles_limit)
        summary = StrategyEvolutionService(self.settings.strategy_runtime).refresh(
            strategy_name=strategy_name,
            execution_mode=execution_mode,
            limit=limit,
            market_regime=market_regime,
        )
        return {"strategy_evolution": summary}

    def strategy_revival_window(
        self,
        strategy_name: str = "all",
        cycles: int = 1,
        symbol: str = "BTC/USDT",
    ) -> dict[str, Any]:
        """Run local-first OKX demo revival windows for revive candidates."""
        result = StrategyRevivalWindowService(self.settings, self.exchanges).run(
            strategy_name=strategy_name,
            cycles=cycles,
            symbol=symbol,
        )
        return {"strategy_revival_window": result}

    def strategy_candidate_backtest(
        self,
        strategy_name: str = "all",
        symbol: str = "BTC/USDT",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Evaluate evolution parameter candidates in isolated paper/backtest configs."""
        result = StrategyCandidateBacktestService(self.settings, self.exchanges).run(
            strategy_name=strategy_name,
            symbol=symbol,
            limit=limit,
        )
        return {"strategy_candidate_backtest": result}

    def strategy_validation_report(
        self,
        execution_mode: ExecutionMode | None = None,
        strategy_name: str = "all",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return a rolling validation evidence report from the strategy journal."""
        report = StrategyValidationReportService(self.settings.strategy_runtime).report(
            execution_mode=execution_mode,
            strategy_name=strategy_name,
            limit=limit,
        )
        return {"strategy_validation_report": report.to_dict()}

    def strategy_pnl_attribution(
        self,
        execution_mode: ExecutionMode | None = None,
        strategy_name: str = "all",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return read-only strategy-level PnL attribution from the journal."""
        report = StrategyPnlAttributionService(self.settings.strategy_runtime).report(
            execution_mode=execution_mode,
            strategy_name=strategy_name,
            limit=limit,
        )
        return {"strategy_pnl_attribution": report.to_dict()}

    def strategy_hedged_maker_report(self, limit: int = 50) -> dict[str, Any]:
        """Return read-only hedged-maker paper lifecycle evaluation evidence."""
        report = HedgedMakerPaperEvaluationReportService(self.settings).report(limit=limit)
        return {"strategy_hedged_maker_report": report.to_dict()}

    def strategy_operator_brief(
        self,
        execution_mode: ExecutionMode | None = None,
        strategy_name: str = "all",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return a read-only operator brief for strategy safety and validation state."""
        brief = StrategyOperatorBriefService(self.settings).brief(
            execution_mode=execution_mode,
            strategy_name=strategy_name,
            limit=limit,
        )
        return {"strategy_operator_brief": brief.to_dict()}

    def strategy_carry_basis_optimize(self, symbol: str = "BTC/USDT") -> dict[str, Any]:
        """Return read-only carry/basis optimization diagnostics."""
        report = CarryBasisOptimizationService(self.settings, self.exchanges).report(symbol=symbol)
        return {"strategy_carry_basis_optimization": report.to_dict()}

    def strategy_guard_status(self, strategy_name: str = "all", execution_mode: ExecutionMode | None = None) -> dict[str, Any]:
        """Return stateful strategy guard status."""
        registry = StrategyRegistry()
        strategies = registry.names() if strategy_name == "all" else [definition.name for definition in registry.expand(strategy_name)]
        return {
            "strategy_guard_status": StrategyRuntimeGuard(self.settings.strategy_runtime).status(
                strategy_names=strategies,
                execution_mode=execution_mode,
            )
        }

    def strategy_validate_demo(self, strategy_name: str, allow_account_mode_switch: bool = False, symbol: str = "BTC/USDT") -> dict[str, Any]:
        """Validate strategies by submitting/canceling tiny OKX demo orders after local validation."""
        self._assert_okx_demo_config_ready()
        registry = StrategyRegistry()
        strategies = registry.demo_validation_names() if strategy_name == "all" else [registry.get(strategy_name).execution_alias or strategy_name]
        local_validation = self._assert_local_validation_passed(strategy_name=strategy_name, symbol=symbol)
        result = StrategyDemoValidationService(
            self.settings,
            config_path=str(self.config_path) if self.config_path else None,
            allow_account_mode_switch=allow_account_mode_switch,
        ).validate(strategies)
        return {"local_validation": local_validation, "strategy_demo_validation": result.to_dict()}

    def strategy_validate_local(self, strategy_name: str, cycles: int, symbol: str) -> dict[str, Any]:
        """Run local paper validation for the strategy promotion pipeline."""
        retrospective = StrategyRetrospectiveService(self.settings.strategy_runtime)
        retrospective_before = retrospective.before_summary()
        payload = StrategyValidationService(self.settings, self.exchanges).validate_local(
            strategy_name=strategy_name,
            cycles=cycles,
            symbol=symbol,
        )
        retrospective_after = retrospective.update_after_payload("strategy_validate_local", payload)
        evolution_after = StrategyEvolutionService(self.settings.strategy_runtime).update_after_payload(
            "strategy_validate_local",
            payload,
            strategy_name=strategy_name,
            execution_mode="paper",
        )
        return {
            **payload,
            "retrospective_before": retrospective_before,
            "retrospective_after": retrospective_after,
            "retrospective_path": retrospective_after["retrospective_path"],
            "evolution_after": evolution_after,
            "evolution_path": evolution_after["report_path"],
        }

    def strategy_validate_demo_window(self, strategy_name: str, cycles: int, symbol: str) -> dict[str, Any]:
        """Run an OKX Demo Trading validation window for the strategy promotion pipeline."""
        self._assert_okx_demo_config_ready()
        retrospective = StrategyRetrospectiveService(self.settings.strategy_runtime)
        retrospective_before = retrospective.before_summary()
        local_validation = self._assert_local_validation_passed(strategy_name=strategy_name, symbol=symbol)
        demo_window = StrategyValidationService(self.settings, self.exchanges).validate_demo_window(
            strategy_name=strategy_name,
            cycles=cycles,
            symbol=symbol,
        )
        payload = {"local_validation": local_validation, **demo_window}
        retrospective_after = retrospective.update_after_payload("strategy_validate_demo_window", payload)
        evolution_after = StrategyEvolutionService(self.settings.strategy_runtime).update_after_payload(
            "strategy_validate_demo_window",
            payload,
            strategy_name=strategy_name,
            execution_mode="demo",
        )
        return {
            **payload,
            "retrospective_before": retrospective_before,
            "retrospective_after": retrospective_after,
            "retrospective_path": retrospective_after["retrospective_path"],
            "evolution_after": evolution_after,
            "evolution_path": evolution_after["report_path"],
        }

    def strategy_demo_window(
        self,
        strategy_name: str,
        cycles: int,
        symbol: str,
        target_exchange: str = "okx",
        report_limit: int = 30,
        include_private_health: bool = True,
    ) -> dict[str, Any]:
        """Run a safety-gated OKX Demo Trading window orchestration."""
        self._assert_okx_demo_config_ready()
        target_strategy_names = [definition.name for definition in StrategyRegistry().expand(strategy_name)]
        orchestrator = StrategyDemoWindowOrchestrator(
            health_checker=lambda: self.exchange_sandbox_check(
                target_exchange,
                symbol,
                include_private=include_private_health,
            ),
            guard_checker=lambda: self.strategy_guard_status(strategy_name=strategy_name, execution_mode="demo"),
            market_compare_checker=lambda: self.strategy_market_compare(
                strategy_name=strategy_name,
                symbol=symbol,
                target_exchange=target_exchange,
            ),
            validation_report_checker=lambda: self.strategy_validation_report(
                execution_mode="demo",
                strategy_name=strategy_name,
                limit=report_limit,
            ),
            demo_window_runner=lambda: self.strategy_validate_demo_window(
                strategy_name=strategy_name,
                cycles=cycles,
                symbol=symbol,
            ),
        )
        return {
            "strategy_demo_window_orchestration": orchestrator.run(
                strategy_name=strategy_name,
                target_strategy_names=target_strategy_names,
                cycles=cycles,
                symbol=symbol,
            )
        }

    def strategy_demo_sampling(
        self,
        strategy_name: str,
        windows: int,
        cycles_per_window: int,
        interval_seconds: int,
        symbol: str,
        target_exchange: str = "okx",
        report_limit: int = 30,
        include_private_health: bool = True,
    ) -> dict[str, Any]:
        """Run bounded same-size OKX demo-window samples."""
        self._assert_okx_demo_config_ready()
        target_strategy_names = [definition.name for definition in StrategyRegistry().expand(strategy_name)]
        size_stage = {
            "demo_order_size_multiplier": self.settings.strategy_runtime.demo_order_size_multiplier,
            "demo_max_order_value_usdt": self.settings.strategy_runtime.demo_max_order_value_usdt,
            "demo_strategy_size_overrides": {
                strategy_name: override.model_dump(mode="json")
                for strategy_name, override in self.settings.strategy_runtime.demo_strategy_size_overrides.items()
            },
        }
        scheduler = StrategyDemoSamplingScheduler(
            window_runner=lambda: self.strategy_demo_window(
                strategy_name=strategy_name,
                cycles=cycles_per_window,
                symbol=symbol,
                target_exchange=target_exchange,
                report_limit=report_limit,
                include_private_health=include_private_health,
            ),
            sleeper=sleep,
        )
        return {
            "strategy_demo_sampling": scheduler.run(
                strategy_name=strategy_name,
                target_strategy_names=target_strategy_names,
                windows=windows,
                cycles_per_window=cycles_per_window,
                symbol=symbol,
                interval_seconds=interval_seconds,
                size_stage=size_stage,
            )
        }

    def strategy_promotion_status(self, strategy_name: str) -> dict[str, Any]:
        """Return advisory promotion status for local, demo, and live-canary layers."""
        return StrategyValidationService(self.settings, self.exchanges).promotion_status(strategy_name=strategy_name)

    def _resolve_opportunity(self, opportunity_id: str | None, opportunity_file: str | Path | None) -> Any:
        """Resolve an opportunity by ID or JSON file."""
        if opportunity_file is not None:
            return load_opportunity_file(opportunity_file)
        if opportunity_id is None:
            from trading_assistant.exceptions import ConfigError

            raise ConfigError("Either opportunity_id or opportunity_file is required")
        return ExecutionEngine(self.settings, self.exchanges).find_opportunity(opportunity_id)

    def _okx_expected_demo(self) -> bool | None:
        """Return the OKX provider demo mode required by config."""
        okx = self.settings.exchanges.get("okx")
        if okx is None:
            return None
        if okx.okx_demo is not None:
            return okx.okx_demo
        return okx.sandbox

    def _assert_okx_demo_config_ready(self) -> None:
        """Fail fast when a command requires OKX Demo Trading configuration."""
        okx = self.settings.exchanges.get("okx")
        if self.settings.trading.live_trading:
            raise SafetyError("strategy demo execution requires trading.live_trading=false")
        if okx is None or not okx.enabled or not okx.sandbox or okx.okx_demo is not True:
            raise SafetyError("strategy demo execution requires enabled OKX sandbox with okx_demo=true")
        if not self.settings.agent_trading.allow_demo_orders:
            raise SafetyError("strategy demo execution requires agent_trading.allow_demo_orders=true")

    def _assert_local_validation_passed(self, strategy_name: str, symbol: str) -> dict[str, Any]:
        """Run first-layer mock/paper validation before any OKX Demo Trading action."""
        local_settings = self.settings.model_copy(deep=True)
        local_settings.trading.live_trading = False
        local_settings.trading.dry_run = True
        local_settings.trading.require_confirm_before_order = True
        local_settings.exchanges["mock"] = ExchangeConfig(enabled=True, sandbox=True, adapter="mock")
        local_settings.exchanges["mock_alt"] = ExchangeConfig(enabled=True, sandbox=True, adapter="mock")
        if "okx" in local_settings.exchanges:
            local_settings.exchanges["okx"].enabled = False
        local_payload = StrategyValidationService(
            local_settings,
            ExchangeFactory(local_settings),
        ).validate_local(strategy_name=strategy_name, cycles=1, symbol=symbol)
        validation = dict(local_payload["local_validation"])
        run = dict(local_payload["strategy_run"])
        non_executed = [
            f"{item.get('strategy_name')}:{item.get('decision')}"
            for item in run.get("results", [])
            if item.get("decision") != "executed"
        ]
        if validation.get("status") != "Pass":
            reasons = ", ".join(str(reason) for reason in validation.get("reasons", [])) or "local validation did not pass"
            raise SafetyError(f"First-layer local validation must pass before OKX demo orders: {reasons}")
        if non_executed:
            raise SafetyError(
                "First-layer local validation must execute every requested strategy before OKX demo orders: "
                + ", ".join(non_executed)
            )
        return validation
