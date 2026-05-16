"""Long-running strategy runtime orchestration."""

from __future__ import annotations

import inspect
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any, cast

from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.arbitrage.scanner import ArbitrageScanner
from trading_assistant.config.schema import ExchangeConfig, Settings
from trading_assistant.execution.engine import ExecutionEngine
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.exceptions import ExchangeError, SafetyError
from trading_assistant.risk.manager import RiskManager
from trading_assistant.strategies.demo_execution import StrategyDemoExecutionService
from trading_assistant.strategies.guard import RuntimeGuardDecision, StrategyRuntimeGuard
from trading_assistant.strategies.hedged_maker_lifecycle import HedgedMakerPaperLifecycleService
from trading_assistant.strategies.journal import StrategyJournal
from trading_assistant.strategies.models import ExecutionMode, StrategyCycleResult, StrategyDecision, StrategyDefinition, StrategyRunResult
from trading_assistant.strategies.policy import StrategyPolicy
from trading_assistant.strategies.preflight_buffer import AdaptivePreflightBufferService
from trading_assistant.strategies.registry import StrategyRegistry


class StrategyRunner:
    """Run registered strategies through scan, risk, budget, execution, and journaling."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory, demo_executor: object | None = None) -> None:
        self.settings = settings
        self.exchanges = exchanges
        self.registry = StrategyRegistry()
        self.scanner = ArbitrageScanner(settings, exchanges)
        self.policy = StrategyPolicy(settings.strategy_runtime)
        self.journal = StrategyJournal(settings.strategy_runtime.journal_path)
        self.guard = StrategyRuntimeGuard(settings.strategy_runtime)
        self.preflight_buffer = AdaptivePreflightBufferService(settings.strategy_runtime)
        self.demo_executor = demo_executor or StrategyDemoExecutionService(settings)

    def scan_once(self, strategy_name: str, symbol: str = "BTC/USDT") -> list[ArbitrageOpportunity]:
        """Scan one strategy once."""
        definition = self.registry.get(strategy_name)
        return self._scan_definition(definition, symbol)

    def run(
        self,
        strategy_name: str = "all",
        max_cycles: int = 1,
        interval_seconds: int = 0,
        execution_mode: ExecutionMode | None = None,
        symbol: str = "BTC/USDT",
    ) -> StrategyRunResult:
        """Run one or all strategies for a bounded or unbounded number of cycles."""
        mode = execution_mode or self.settings.strategy_runtime.default_execution_mode
        definitions = self._enabled_definitions(strategy_name)
        results: list[StrategyCycleResult] = []
        cycles_completed = 0
        cycle = 0
        stopped_reason: str | None = None
        demo_cumulative_net_pnl = Decimal("0")
        demo_peak_net_pnl = Decimal("0")
        demo_max_drawdown = Decimal("0")
        while max_cycles <= 0 or cycle < max_cycles:
            cycle += 1
            for definition in definitions:
                guard_decision = self.guard.evaluate(definition.name, mode)
                if guard_decision.approved:
                    result = self._run_one(cycle, definition, mode, symbol)
                    self.guard.record(
                        strategy_name=definition.name,
                        execution_mode=mode,
                        decision=result.decision,
                        net_profit=result.net_profit,
                        reasons=result.risk_reasons,
                    )
                else:
                    result = self._guard_skipped_result(cycle, definition, mode, guard_decision)
                results.append(result)
                self.journal.append({"event": "strategy_cycle", **result.to_dict()})
                if mode == "demo" and result.decision == "executed":
                    demo_cumulative_net_pnl += result.net_profit
                    demo_peak_net_pnl = max(demo_peak_net_pnl, demo_cumulative_net_pnl)
                    demo_max_drawdown = max(demo_max_drawdown, demo_peak_net_pnl - demo_cumulative_net_pnl)
                    stopped_reason = self._demo_circuit_breaker_reason(demo_cumulative_net_pnl, demo_max_drawdown)
                    if stopped_reason is not None:
                        break
            cycles_completed = cycle
            if stopped_reason is not None:
                break
            if max_cycles <= 0 or cycle < max_cycles:
                time.sleep(max(interval_seconds, 0))
        summary = f"Completed {cycles_completed} cycle(s) for {strategy_name} in {mode} mode."
        if stopped_reason is not None:
            summary += f" Stopped by {stopped_reason}."
        return StrategyRunResult(
            completed=True,
            strategy_name=strategy_name,
            execution_mode=mode,
            cycles_completed=cycles_completed,
            results=results,
            journal_path=self.settings.strategy_runtime.journal_path,
            summary=summary,
            stopped_reason=stopped_reason,
            demo_cumulative_net_pnl=demo_cumulative_net_pnl if mode == "demo" else None,
            demo_max_drawdown_usdt=demo_max_drawdown if mode == "demo" else None,
        )

    def _run_one(self, cycle: int, definition: StrategyDefinition, mode: ExecutionMode, symbol: str) -> StrategyCycleResult:
        """Run one strategy in one cycle."""
        if mode == "demo":
            return self._run_demo_one(cycle, definition, symbol)
        opportunities, scan_error = self._try_scan_definition(definition, symbol)
        if scan_error is not None:
            return StrategyCycleResult(
                cycle=cycle,
                strategy_name=definition.name,
                decision="skipped",
                execution_mode=mode,
                opportunities_found=0,
                selected_opportunity_id=None,
                risk_approved=False,
                risk_reasons=[scan_error],
                budget=None,
                lifecycle=self.policy.lifecycle_plan(),
                execution={"scan_error": scan_error},
                net_profit=Decimal("0"),
                message="Strategy skipped because market data scan failed.",
            )
        if not opportunities:
            return StrategyCycleResult(
                cycle=cycle,
                strategy_name=definition.name,
                decision="skipped",
                execution_mode=mode,
                opportunities_found=0,
                selected_opportunity_id=None,
                risk_approved=False,
                risk_reasons=["no_opportunity"],
                budget=None,
                lifecycle=None,
                execution=None,
                net_profit=Decimal("0"),
                message="No opportunity found.",
            )
        selected = max(opportunities, key=lambda item: item.net_profit)
        risk_decision = RiskManager(self.settings.risk).evaluate(selected)
        lifecycle = self.policy.lifecycle_plan()
        hedged_maker_lifecycle: HedgedMakerPaperLifecycleService | None = None
        additional_orders = 1
        additional_capital = selected.required_capital
        active_orders = 0
        active_capital = Decimal("0")
        if definition.name == "hedged-maker":
            hedged_maker_lifecycle = HedgedMakerPaperLifecycleService(self.settings, self.exchanges)
            budget_state = hedged_maker_lifecycle.budget_state(selected, lifecycle)
            active_orders = budget_state.active_orders
            active_capital = budget_state.active_capital_usdt
            if budget_state.matching_active_order:
                additional_orders = 0
                additional_capital = Decimal("0")
        budget = self.policy.evaluate(
            definition.name,
            selected,
            active_orders=active_orders,
            active_capital_usdt=active_capital,
            additional_orders=additional_orders,
            additional_capital_usdt=additional_capital,
        )
        if not risk_decision.approved or not budget.approved:
            reasons = [*risk_decision.violations, *budget.reasons]
            return StrategyCycleResult(
                cycle=cycle,
                strategy_name=definition.name,
                decision="blocked",
                execution_mode=mode,
                opportunities_found=len(opportunities),
                selected_opportunity_id=selected.opportunity_id,
                risk_approved=risk_decision.approved,
                risk_reasons=reasons,
                budget=budget,
                lifecycle=lifecycle,
                execution=None,
                net_profit=selected.net_profit,
                message=f"Strategy blocked: {', '.join(reasons)}",
            )
        if definition.name == "hedged-maker":
            lifecycle_service = hedged_maker_lifecycle or HedgedMakerPaperLifecycleService(self.settings, self.exchanges)
            lifecycle_result = lifecycle_service.apply(selected, lifecycle)
            execution_payload = {
                "opportunity_id": selected.opportunity_id,
                "status": lifecycle_result.status,
                "dry_run": True,
                "paper_only": True,
                "simulation_only": True,
                "orders_sent": False,
                "live_orders_sent": False,
                "risk_decision": risk_decision.to_dict(),
                "expected_net_profit": selected.net_profit,
                "net_profit": lifecycle_result.realized_net_profit_usdt,
                "hedged_maker_lifecycle": lifecycle_result.to_dict(),
                "message": lifecycle_result.message,
            }
            decision: StrategyDecision = "blocked" if lifecycle_result.status == "blocked_open_order_limit" else "executed"
            risk_reasons = ["paper_open_order_limit_reached"] if decision == "blocked" else []
            return StrategyCycleResult(
                cycle=cycle,
                strategy_name=definition.name,
                decision=decision,
                execution_mode=mode,
                opportunities_found=len(opportunities),
                selected_opportunity_id=selected.opportunity_id,
                risk_approved=decision == "executed",
                risk_reasons=risk_reasons,
                budget=budget,
                lifecycle=lifecycle,
                execution=execution_payload,
                net_profit=lifecycle_result.realized_net_profit_usdt,
                message=lifecycle_result.message,
            )
        execution = ExecutionEngine(self.settings, self.exchanges).execute(selected.opportunity_id, dry_run=True)
        return StrategyCycleResult(
            cycle=cycle,
            strategy_name=definition.name,
            decision="executed",
            execution_mode=mode,
            opportunities_found=len(opportunities),
            selected_opportunity_id=selected.opportunity_id,
            risk_approved=True,
            risk_reasons=[],
            budget=budget,
            lifecycle=lifecycle,
            execution=execution.to_dict(),
            net_profit=execution.net_profit,
            message="Paper execution completed; lifecycle plan recorded for cancel/reprice control.",
        )

    def _run_demo_one(self, cycle: int, definition: StrategyDefinition, symbol: str) -> StrategyCycleResult:
        """Run one strategy through the controlled OKX Demo Trading executor."""
        lifecycle = self.policy.lifecycle_plan()
        execution_name = definition.execution_alias or definition.name
        if not definition.demo_supported:
            return StrategyCycleResult(
                cycle=cycle,
                strategy_name=definition.name,
                decision="skipped",
                execution_mode="demo",
                opportunities_found=0,
                selected_opportunity_id=None,
                risk_approved=False,
                risk_reasons=["demo_not_enabled_for_strategy"],
                budget=None,
                lifecycle=lifecycle,
                execution={"demo_supported": False, "reason": definition.notes},
                net_profit=Decimal("0"),
                message="OKX Demo Trading is not enabled for this strategy yet; use scan/paper validation first.",
            )
        local_gate = self._demo_local_validation_gate(definition, symbol)
        local_gate_approved = bool(local_gate["approved"])
        reasons = _local_gate_reasons(local_gate)
        directional_exit_override = (
            not local_gate_approved and _local_gate_has_directional_exit_signal(definition, local_gate)
        )
        if not local_gate_approved and not directional_exit_override:
            selected_opportunity_id = local_gate.get("selected_opportunity_id")
            return StrategyCycleResult(
                cycle=cycle,
                strategy_name=definition.name,
                decision="skipped",
                execution_mode="demo",
                opportunities_found=int(str(local_gate.get("opportunities_found", 0))),
                selected_opportunity_id=str(selected_opportunity_id) if selected_opportunity_id is not None else None,
                risk_approved=False,
                risk_reasons=["local_validation_not_passed", *reasons],
                budget=None,
                lifecycle=lifecycle,
                execution={"local_validation": local_gate},
                net_profit=Decimal("0"),
                message="OKX Demo Trading skipped because first-layer local validation did not pass.",
            )
        try:
            preview = self._demo_preflight(execution_name, local_gate)
            if preview is not None:
                preview = self.preflight_buffer.apply(definition.name, preview)
        except (ExchangeError, SafetyError) as exc:
            if not _is_runtime_market_error(exc):
                raise
            reason = _runtime_error_reason(exc)
            return StrategyCycleResult(
                cycle=cycle,
                strategy_name=definition.name,
                decision="skipped",
                execution_mode="demo",
                opportunities_found=0,
                selected_opportunity_id=f"okx-demo-{execution_name}",
                risk_approved=False,
                risk_reasons=[reason],
                budget=None,
                lifecycle=lifecycle,
                execution={"local_validation": local_gate, "preflight_error": reason},
                net_profit=Decimal("0"),
                message="OKX Demo Trading skipped because preflight market data failed.",
            )
        if directional_exit_override and not _is_directional_exit_preview(preview):
            reason = str((preview or {}).get("reason") or "directional_exit_preflight_missing")
            return StrategyCycleResult(
                cycle=cycle,
                strategy_name=definition.name,
                decision="skipped",
                execution_mode="demo",
                opportunities_found=int(str(local_gate.get("opportunities_found", 0))),
                selected_opportunity_id=None,
                risk_approved=False,
                risk_reasons=["local_validation_not_passed", *reasons, reason],
                budget=None,
                lifecycle=lifecycle,
                execution={"local_validation": local_gate, "preflight": preview},
                net_profit=Decimal(str((preview or {}).get("net_pnl_usdt", "0"))),
                message="OKX Demo Trading skipped because reverse-signal context did not preview a managed exit.",
            )
        if preview is not None and not self._demo_preflight_approved(preview):
            reason = str(preview.get("reason") or "demo_preflight_not_profitable")
            message = "OKX Demo Trading execution skipped by preflight profitability gate."
            if reason == "directional_position_hold":
                message = "OKX Demo Trading held the existing managed directional position; no new order was sent."
            return StrategyCycleResult(
                cycle=cycle,
                strategy_name=definition.name,
                decision="skipped",
                execution_mode="demo",
                opportunities_found=1,
                selected_opportunity_id=f"okx-demo-{execution_name}",
                risk_approved=False,
                risk_reasons=[reason],
                budget=None,
                lifecycle=lifecycle,
                execution={"local_validation": local_gate, "preflight": preview},
                net_profit=Decimal(str(preview.get("net_pnl_usdt", "0"))),
                message=message,
            )
        execution = self._demo_execute(execution_name, local_gate)
        execution["local_validation"] = local_gate
        if preview is not None:
            execution["preflight"] = preview
        net_profit = Decimal(str(execution.get("net_pnl_usdt", "0")))
        return StrategyCycleResult(
            cycle=cycle,
            strategy_name=definition.name,
            decision="executed",
            execution_mode="demo",
            opportunities_found=1,
            selected_opportunity_id=f"okx-demo-{execution_name}",
            risk_approved=True,
            risk_reasons=[],
            budget=None,
            lifecycle=lifecycle,
            execution=execution,
            net_profit=net_profit,
            message="OKX Demo Trading execution completed; orders were filled or canceled under lifecycle controls.",
        )

    def _demo_preflight(self, strategy_name: str, context: dict[str, object] | None = None) -> dict[str, object] | None:
        """Return optional demo preflight estimate from the executor."""
        preview = getattr(self.demo_executor, "preview", None)
        if preview is None:
            return None
        if _accepts_context(preview):
            return dict(preview(strategy_name, context=context or {}))
        return dict(preview(strategy_name))

    def _demo_execute(self, strategy_name: str, context: dict[str, object]) -> dict[str, object]:
        """Execute demo strategy while passing local-validation context when supported."""
        execute = getattr(self.demo_executor, "execute")
        if _accepts_context(execute):
            return dict(execute(strategy_name, context=context))
        return dict(execute(strategy_name))

    def _demo_preflight_approved(self, preview: dict[str, object]) -> bool:
        """Return whether demo execution should send orders after preflight."""
        if _is_directional_exit_preview(preview):
            return True
        if not self.settings.strategy_runtime.demo_require_profitable_preflight:
            return True
        if not bool(preview.get("approved", False)):
            return False
        net_pnl = Decimal(str(preview.get("net_pnl_usdt", "0")))
        return net_pnl >= self.settings.strategy_runtime.demo_min_preflight_net_pnl_usdt

    def _demo_circuit_breaker_reason(self, cumulative_pnl: Decimal, max_drawdown: Decimal) -> str | None:
        """Return a stop reason when demo PnL circuit breakers trip."""
        if cumulative_pnl <= -self.settings.strategy_runtime.demo_stop_loss_usdt:
            return "demo_stop_loss"
        if max_drawdown >= self.settings.strategy_runtime.demo_max_drawdown_usdt:
            return "demo_max_drawdown"
        return None

    def _demo_local_validation_gate(self, definition: StrategyDefinition, symbol: str) -> dict[str, object]:
        """Run local mock scan, risk, and budget checks before any OKX Demo Trading order."""
        local_settings = self.settings.model_copy(deep=True)
        local_settings.exchanges["mock"] = ExchangeConfig(enabled=True, sandbox=True, adapter="mock")
        local_settings.exchanges["mock_alt"] = ExchangeConfig(enabled=True, sandbox=True, adapter="mock")
        if "okx" in local_settings.exchanges:
            local_settings.exchanges["okx"].enabled = False
        scanner = ArbitrageScanner(local_settings, ExchangeFactory(local_settings))
        try:
            if definition.category == "directional":
                opportunities = scanner.scan(definition.scanner_type, symbol=symbol, exchange="mock")
            elif definition.scanner_type in {"triangular", "triangular-multi-route", "funding-carry-hedged"}:
                opportunities = scanner.scan(definition.scanner_type, exchange="mock")
            elif definition.scanner_type in {"spot-perp-carry", "futures-perp-basis", "range-grid", "hedged-maker"}:
                opportunities = scanner.scan(definition.scanner_type, symbol=symbol, exchange="mock")
            else:
                opportunities = scanner.scan(definition.scanner_type, symbol=symbol)
        except ExchangeError as exc:
            return {
                "approved": False,
                "layer": "local",
                "reasons": [f"local_scan_error:{exc}"],
                "opportunities_found": 0,
                "selected_opportunity_id": None,
            }
        if not opportunities:
            diagnostics = self._local_diagnostics(scanner, definition, symbol)
            no_opportunity_reasons = _diagnostic_reasons(diagnostics) or ["no_local_opportunity"]
            payload: dict[str, object] = {
                "approved": False,
                "layer": "local",
                "reasons": no_opportunity_reasons,
                "opportunities_found": 0,
                "selected_opportunity_id": None,
            }
            if diagnostics:
                payload["diagnostics"] = diagnostics
            directional_signal = _directional_signal_from_diagnostics(diagnostics)
            if directional_signal is not None:
                payload["directional_signal"] = directional_signal
            return payload
        selected = max(opportunities, key=lambda item: item.net_profit)
        risk_decision = RiskManager(local_settings.risk).evaluate(selected)
        budget = StrategyPolicy(local_settings.strategy_runtime).evaluate(definition.name, selected)
        reasons = [*risk_decision.violations, *budget.reasons]
        payload = {
            "approved": risk_decision.approved and budget.approved,
            "layer": "local",
            "reasons": reasons,
            "opportunities_found": len(opportunities),
            "selected_opportunity_id": selected.opportunity_id,
            "net_profit": selected.net_profit,
            "risk": risk_decision.to_dict(),
            "budget": budget.to_dict(),
        }
        if definition.category == "directional":
            directional_signal = selected.metadata.get("directional_signal")
            if isinstance(directional_signal, dict):
                payload["directional_signal"] = directional_signal
        return payload

    def _local_diagnostics(
        self,
        scanner: ArbitrageScanner,
        definition: StrategyDefinition,
        symbol: str,
    ) -> dict[str, Any]:
        """Return local scan diagnostics when a strategy can explain filtered signals."""
        if definition.category != "directional":
            return {}
        try:
            return scanner.diagnose(definition.scanner_type, symbol=symbol, exchange="mock")
        except ExchangeError:
            return {}

    def _guard_skipped_result(
        self,
        cycle: int,
        definition: StrategyDefinition,
        mode: ExecutionMode,
        guard_decision: RuntimeGuardDecision,
    ) -> StrategyCycleResult:
        """Return a strategy result blocked by the stateful runtime guard."""
        return StrategyCycleResult(
            cycle=cycle,
            strategy_name=definition.name,
            decision="skipped",
            execution_mode=mode,
            opportunities_found=0,
            selected_opportunity_id=None,
            risk_approved=False,
            risk_reasons=guard_decision.reasons,
            budget=None,
            lifecycle=self.policy.lifecycle_plan(),
            execution={"runtime_guard": guard_decision.to_dict()},
            net_profit=Decimal("0"),
            message="Strategy skipped by stateful runtime guard cooldown.",
        )

    def _scan_definition(self, definition: StrategyDefinition, symbol: str) -> list[ArbitrageOpportunity]:
        """Scan one registered strategy definition."""
        opportunities, _ = self._try_scan_definition(definition, symbol)
        return opportunities

    def _try_scan_definition(self, definition: StrategyDefinition, symbol: str) -> tuple[list[ArbitrageOpportunity], str | None]:
        """Scan one registered strategy definition and surface exchange-data failures."""
        try:
            if definition.category == "directional":
                return self.scanner.scan(definition.scanner_type, symbol=symbol, exchange=self._preferred_single_exchange()), None
            if definition.scanner_type in {"triangular", "triangular-multi-route", "funding-carry-hedged"}:
                return self.scanner.scan(definition.scanner_type, exchange=self._preferred_single_exchange()), None
            if definition.scanner_type in {"spot-perp-carry", "futures-perp-basis", "range-grid", "hedged-maker"}:
                return self.scanner.scan(definition.scanner_type, symbol=symbol, exchange=self._preferred_single_exchange()), None
            return self.scanner.scan(definition.scanner_type, symbol=symbol), None
        except ExchangeError as exc:
            return [], _runtime_error_reason(exc)

    def _enabled_definitions(self, strategy_name: str) -> list[StrategyDefinition]:
        """Return configured enabled strategy definitions."""
        definitions = self.registry.expand(strategy_name)
        if strategy_name != "all":
            return definitions
        enabled = set(self.settings.strategy_runtime.enabled_strategies)
        return [
            definition
            for definition in definitions
            if definition.name in enabled or any(alias in enabled for alias in definition.aliases)
        ]

    def _preferred_single_exchange(self) -> str:
        """Return configured single-exchange target for paper scans."""
        enabled = self.exchanges.list_enabled()
        if "mock" in enabled:
            return "mock"
        if "okx" in enabled:
            return "okx"
        return enabled[0] if enabled else "mock"


def _runtime_error_reason(exc: Exception) -> str:
    """Return a compact guard-classifiable reason for exchange runtime errors."""
    message = _compact_exception(exc)
    if _looks_like_rate_limit(message):
        return f"exchange_rate_limit:{message}"
    return f"market_data_error:{message}"


def _is_runtime_market_error(exc: Exception) -> bool:
    """Return whether an exception is safe to treat as transient market-data trouble."""
    message = _compact_exception(exc).lower()
    return isinstance(exc, ExchangeError) or any(
        marker in message
        for marker in (
            "rate limit",
            "too many requests",
            "429",
            "51011",
            "50011",
            "unable to fetch",
            "ticker",
            "orderbook",
            "funding",
            "instrument",
            "okx api",
            "market data",
        )
    )


def _looks_like_rate_limit(message: str) -> bool:
    """Return whether an error string looks like exchange throttling."""
    normalized = message.lower()
    return any(marker in normalized for marker in ("rate limit", "too many requests", "429", "51011", "50011"))


def _compact_exception(exc: Exception) -> str:
    """Return a bounded one-line exception description for reports and guard state."""
    text = f"{exc.__class__.__name__}: {exc}".replace("\n", " ").strip()
    return text[:240]


def _local_gate_reasons(local_gate: dict[str, object]) -> list[str]:
    """Return normalized local validation reason codes."""
    raw_reasons = local_gate.get("reasons", [])
    reason_values = raw_reasons if isinstance(raw_reasons, list) else [raw_reasons]
    return [str(reason) for reason in reason_values if reason is not None]


def _local_gate_has_directional_exit_signal(definition: StrategyDefinition, local_gate: dict[str, object]) -> bool:
    """Return whether a failed local directional gate is an explicit exit signal."""
    if definition.category != "directional":
        return False
    signal_value = _local_gate_signal_value(local_gate)
    if signal_value in {"sell", "exit", "close", "reduce"}:
        return True
    return "signal_sell" in _local_gate_reasons(local_gate)


def _local_gate_signal_value(local_gate: dict[str, object]) -> str | None:
    """Extract a normalized directional signal value from local validation context."""
    signal = local_gate.get("directional_signal")
    if isinstance(signal, dict):
        value = signal.get("signal") or signal.get("action")
        if value is not None:
            return str(value).lower()
    diagnostics = local_gate.get("diagnostics")
    if isinstance(diagnostics, dict):
        signal = _directional_signal_from_diagnostics(diagnostics)
        if signal is not None:
            value = signal.get("signal") or signal.get("action")
            if value is not None:
                return str(value).lower()
    return None


def _diagnostic_reasons(diagnostics: dict[str, Any]) -> list[str]:
    """Return scanner diagnostic reason codes."""
    raw_reasons = diagnostics.get("reasons", [])
    reason_values = raw_reasons if isinstance(raw_reasons, list) else [raw_reasons]
    return [str(reason) for reason in reason_values if reason is not None]


def _directional_signal_from_diagnostics(diagnostics: dict[str, Any]) -> dict[str, Any] | None:
    """Extract the first directional signal row from scanner diagnostics."""
    best = diagnostics.get("best_candidate")
    if isinstance(best, dict) and isinstance(best.get("signal"), dict):
        return best["signal"]
    candidates = diagnostics.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if isinstance(candidate, dict) and isinstance(candidate.get("signal"), dict):
                return candidate["signal"]
    return None


def _is_directional_exit_preview(preview: dict[str, object] | None) -> bool:
    """Return whether a preflight preview is a managed directional exit."""
    if preview is None or not bool(preview.get("approved", False)):
        return False
    return str(preview.get("reason") or "").startswith("directional_exit_")


def _accepts_context(callable_obj: object) -> bool:
    """Return whether a demo executor callable accepts a context keyword."""
    try:
        signature = inspect.signature(cast(Callable[..., Any], callable_obj))
    except (TypeError, ValueError):
        return False
    return "context" in signature.parameters
