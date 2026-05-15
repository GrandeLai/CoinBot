"""Detached paper/demo autopilot runtime."""

from __future__ import annotations

from typing import Any, cast

from trading_assistant.autopilot.models import (
    AutopilotCycleRecord,
    AutopilotMode,
    AutopilotReport,
    AutopilotRunResult,
    AutopilotState,
    AutopilotStatus,
    GuardStatusProducer,
    OperatorBriefProducer,
    PayloadProducer,
    PromotionStatusProducer,
    Sleeper,
    ValidationReporter,
)
from trading_assistant.autopilot.state import AutopilotStateStore
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.base import utcnow
from trading_assistant.strategies.models import ExecutionMode


class AutopilotRuntime:
    """Run bounded or unbounded paper/demo autopilot cycles."""

    def __init__(
        self,
        *,
        settings: Settings,
        state_store: AutopilotStateStore,
        paper_runner: PayloadProducer,
        validation_reporter: ValidationReporter,
        operator_brief: OperatorBriefProducer,
        guard_status: GuardStatusProducer,
        promotion_status: PromotionStatusProducer,
        sleeper: Sleeper,
        demo_runner: PayloadProducer | None = None,
    ) -> None:
        self.settings = settings
        self.state_store = state_store
        self.paper_runner = paper_runner
        self.demo_runner = demo_runner
        self.validation_reporter = validation_reporter
        self.operator_brief = operator_brief
        self.guard_status = guard_status
        self.promotion_status = promotion_status
        self.sleeper = sleeper

    def run(
        self,
        *,
        mode: AutopilotMode,
        strategy_name: str,
        symbol: str,
        cycles: int,
        interval_seconds: int | None,
        demo_cycles_per_window: int,
        report_limit: int,
    ) -> AutopilotRunResult:
        """Run autopilot cycles and persist state after every decision."""
        requested = max(cycles, 0)
        sleep_seconds = max(
            interval_seconds
            if interval_seconds is not None
            else self.settings.strategy_runtime.autopilot_default_interval_seconds,
            0,
        )
        if mode == "paper" and self.settings.trading.live_trading:
            return self._stopped_before_cycle(mode, strategy_name, symbol, requested, "paper_live_trading_enabled")
        if mode == "demo" and self.settings.trading.live_trading:
            return self._stopped_before_cycle(mode, strategy_name, symbol, requested, "demo_live_trading_enabled")

        records: list[AutopilotCycleRecord] = []
        cycles_completed = 0
        consecutive_blocked = 0
        live_orders_sent = False
        orders_attempted = False
        stopped_reason: str | None = None
        self._write_state("Running", mode, strategy_name, symbol, requested, 0, None, 0, False, False, {})

        cycle = 0
        while requested == 0 or cycle < requested:
            cycle += 1
            try:
                payload = self.paper_runner() if mode == "paper" else self._run_demo_payload()
                validation = self.validation_reporter(_execution_mode(mode), strategy_name, report_limit)
                brief = self.operator_brief(_execution_mode(mode), strategy_name, report_limit)
                merged_payload = {**payload, **validation, **brief}
                record = _cycle_record(cycle, mode, merged_payload)
            except Exception as exc:
                self.state_store.write(
                    AutopilotState(
                        status="Failed",
                        mode=mode,
                        strategy_name=strategy_name,
                        symbol=symbol,
                        cycles_requested=requested,
                        cycles_completed=cycles_completed,
                        stopped_reason="exception",
                        consecutive_blocked_cycles=consecutive_blocked,
                        live_orders_sent=live_orders_sent,
                        orders_attempted=orders_attempted,
                        error_type=exc.__class__.__name__,
                        error_message=str(exc),
                        last_cycle_at=utcnow().isoformat(),
                    )
                )
                raise

            records.append(record)
            cycles_completed = cycle
            live_orders_sent = live_orders_sent or record.live_orders_sent
            orders_attempted = orders_attempted or record.orders_attempted
            consecutive_blocked = consecutive_blocked + 1 if record.blocked else 0
            stopped_reason = _stop_reason(
                record,
                consecutive_blocked,
                self.settings.strategy_runtime.autopilot_max_consecutive_blocked_cycles,
                stop_on_live_signal=self.settings.strategy_runtime.autopilot_stop_on_live_signal,
            )
            self._write_state(
                "Stopped" if stopped_reason else "Running",
                mode,
                strategy_name,
                symbol,
                requested,
                cycles_completed,
                stopped_reason,
                consecutive_blocked,
                live_orders_sent,
                orders_attempted,
                record.payload_summary,
            )
            if stopped_reason is not None:
                break
            if requested == 0 or cycle < requested:
                self.sleeper(sleep_seconds)

        status: AutopilotStatus = "Stopped" if stopped_reason else "Completed"
        self._write_state(
            status,
            mode,
            strategy_name,
            symbol,
            requested,
            cycles_completed,
            stopped_reason,
            consecutive_blocked,
            live_orders_sent,
            orders_attempted,
            records[-1].payload_summary if records else {},
        )
        return AutopilotRunResult(
            status=status,
            mode=mode,
            strategy_name=strategy_name,
            symbol=symbol,
            cycles_requested=requested,
            cycles_completed=cycles_completed,
            stopped_reason=stopped_reason,
            live_orders_sent=live_orders_sent,
            orders_attempted=orders_attempted,
            state_path=str(self.state_store.path),
            cycles=records,
            summary=f"Autopilot {status.lower()} after {cycles_completed} cycle(s) in {mode} mode.",
        )

    def report(self, *, mode: AutopilotMode, strategy_name: str, report_limit: int) -> AutopilotReport:
        """Return a read-only report from state and existing evidence services."""
        execution_mode = _execution_mode(mode)
        state = self.state_store.read().to_dict()
        guard = self.guard_status(execution_mode, strategy_name)
        validation = self.validation_reporter(execution_mode, strategy_name, report_limit)
        brief = self.operator_brief(execution_mode, strategy_name, report_limit)
        promotion = self.promotion_status(strategy_name)
        return AutopilotReport(
            state=state,
            guard=guard,
            validation=validation,
            operator_brief=brief,
            promotion_status=promotion,
            orders_sent=bool(state.get("orders_attempted")),
            live_orders_sent=bool(state.get("live_orders_sent")),
        )

    def _run_demo_payload(self) -> dict[str, Any]:
        if self.demo_runner is None:
            raise RuntimeError("demo_runner is required for demo autopilot mode")
        return self.demo_runner()

    def _stopped_before_cycle(
        self,
        mode: AutopilotMode,
        strategy_name: str,
        symbol: str,
        cycles_requested: int,
        reason: str,
    ) -> AutopilotRunResult:
        self._write_state("Stopped", mode, strategy_name, symbol, cycles_requested, 0, reason, 0, False, False, {})
        return AutopilotRunResult(
            status="Stopped",
            mode=mode,
            strategy_name=strategy_name,
            symbol=symbol,
            cycles_requested=cycles_requested,
            cycles_completed=0,
            stopped_reason=reason,
            live_orders_sent=False,
            orders_attempted=False,
            state_path=str(self.state_store.path),
            cycles=[],
            summary=f"Autopilot stopped before execution: {reason}.",
        )

    def _write_state(
        self,
        status: AutopilotStatus,
        mode: AutopilotMode,
        strategy_name: str,
        symbol: str,
        cycles_requested: int,
        cycles_completed: int,
        stopped_reason: str | None,
        consecutive_blocked: int,
        live_orders_sent: bool,
        orders_attempted: bool,
        payload_summary: dict[str, Any],
    ) -> None:
        self.state_store.write(
            AutopilotState(
                status=status,
                mode=mode,
                strategy_name=strategy_name,
                symbol=symbol,
                cycles_requested=cycles_requested,
                cycles_completed=cycles_completed,
                stopped_reason=stopped_reason,
                consecutive_blocked_cycles=consecutive_blocked,
                live_orders_sent=live_orders_sent,
                orders_attempted=orders_attempted,
                last_payload_summary=payload_summary,
                last_cycle_at=utcnow().isoformat(),
            )
        )


def _execution_mode(mode: AutopilotMode) -> ExecutionMode:
    """Map autopilot mode to strategy execution mode."""
    return "demo" if mode == "demo" else "paper"


def _cycle_record(cycle: int, mode: AutopilotMode, payload: dict[str, Any]) -> AutopilotCycleRecord:
    """Build a compact cycle record from nested strategy/demo payloads."""
    summary = _payload_summary(payload)
    live_orders_sent = _nested_truthy(payload, "live_orders_sent")
    orders_attempted = _nested_truthy(payload, "orders_attempted") or _nested_truthy(payload, "demo_orders_sent")
    blocked = bool(summary["block_reasons"]) or cast(dict[str, int], summary["decision_counts"]).get("executed", 0) == 0
    return AutopilotCycleRecord(
        cycle=cycle,
        mode=mode,
        status="Blocked" if blocked else "Executed",
        completed=not blocked,
        live_orders_sent=live_orders_sent,
        orders_attempted=orders_attempted,
        blocked=blocked,
        block_reasons=summary["block_reasons"],
        payload_summary=summary,
    )


def _payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Return decision counts and unique block reasons from nested payloads."""
    results = _strategy_results(payload)
    decision_counts = {"executed": 0, "blocked": 0, "skipped": 0}
    block_reasons: list[str] = []
    for result in results:
        decision = str(result.get("decision", ""))
        if decision in decision_counts:
            decision_counts[decision] += 1
        block_reasons.extend(str(reason) for reason in result.get("risk_reasons", []) if reason)

    orchestration = payload.get("strategy_demo_window_orchestration")
    if isinstance(orchestration, dict):
        block_reasons.extend(str(reason) for reason in orchestration.get("block_reasons", []) if reason)
        if orchestration.get("status") == "Executed":
            decision_counts["executed"] += 1
        elif orchestration.get("status") == "Blocked":
            decision_counts["blocked"] += 1

    return {
        "decision_counts": decision_counts,
        "block_reasons": sorted(set(block_reasons)),
    }


def _strategy_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract strategy runner result rows from direct or demo-window payloads."""
    run = payload.get("strategy_run")
    if isinstance(run, dict):
        return [item for item in run.get("results", []) if isinstance(item, dict)]

    orchestration = payload.get("strategy_demo_window_orchestration")
    if isinstance(orchestration, dict):
        demo_window = orchestration.get("demo_window")
        if isinstance(demo_window, dict):
            nested_run = demo_window.get("strategy_run")
            if isinstance(nested_run, dict):
                return [item for item in nested_run.get("results", []) if isinstance(item, dict)]
    return []


def _nested_truthy(value: Any, key: str) -> bool:
    """Return whether a nested payload contains a truthy key."""
    if isinstance(value, dict):
        return bool(value.get(key)) or any(_nested_truthy(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_nested_truthy(item, key) for item in value)
    return False


def _stop_reason(
    record: AutopilotCycleRecord,
    consecutive_blocked: int,
    max_blocked: int,
    *,
    stop_on_live_signal: bool,
) -> str | None:
    """Return a stop reason for the current cycle, if any."""
    if stop_on_live_signal and record.live_orders_sent:
        return "live_order_detected"
    if consecutive_blocked >= max_blocked:
        return "max_consecutive_blocked_cycles"
    return None
