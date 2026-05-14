"""Safety-gated OKX demo-window orchestration."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from trading_assistant.utils.serialization import to_jsonable


Precheck = Callable[[], dict[str, Any]]
DemoWindowRunner = Callable[[], dict[str, Any]]


class StrategyDemoWindowOrchestrator:
    """Run no-order prechecks before an OKX Demo Trading validation window."""

    def __init__(
        self,
        health_checker: Precheck,
        guard_checker: Precheck,
        market_compare_checker: Precheck,
        validation_report_checker: Precheck,
        demo_window_runner: DemoWindowRunner,
    ) -> None:
        self.health_checker = health_checker
        self.guard_checker = guard_checker
        self.market_compare_checker = market_compare_checker
        self.validation_report_checker = validation_report_checker
        self.demo_window_runner = demo_window_runner

    def run(
        self,
        strategy_name: str,
        target_strategy_names: list[str],
        cycles: int,
        symbol: str,
    ) -> dict[str, Any]:
        """Run prechecks and execute the demo window only when all gates pass."""
        prechecks: dict[str, Any] = {}

        health = _capture_precheck(self.health_checker)
        prechecks["health"] = health
        if not _health_ok(health):
            return self._blocked(strategy_name, target_strategy_names, cycles, symbol, prechecks, ["health_check_failed"])

        guard = _capture_precheck(self.guard_checker)
        prechecks["guard"] = _guard_summary(guard)
        if prechecks["guard"]["cooldown_active"]:
            return self._blocked(strategy_name, target_strategy_names, cycles, symbol, prechecks, ["runtime_guard_cooldown"])

        market_compare = _capture_precheck(self.market_compare_checker)
        prechecks["market_compare"] = _market_compare_summary(market_compare, target_strategy_names)
        if not prechecks["market_compare"]["ok"]:
            return self._blocked(strategy_name, target_strategy_names, cycles, symbol, prechecks, ["market_compare_failed"])
        if prechecks["market_compare"]["missing_candidate_strategies"]:
            return self._blocked(strategy_name, target_strategy_names, cycles, symbol, prechecks, ["missing_demo_preflight_candidate"])

        validation_report = _capture_precheck(self.validation_report_checker)
        prechecks["validation_report"] = _validation_report_summary(validation_report)
        if not prechecks["validation_report"]["ok"]:
            return self._blocked(strategy_name, target_strategy_names, cycles, symbol, prechecks, ["validation_report_failed"])
        if prechecks["validation_report"]["quality_block_reasons"]:
            return self._blocked(
                strategy_name,
                target_strategy_names,
                cycles,
                symbol,
                prechecks,
                prechecks["validation_report"]["quality_block_reasons"],
            )

        demo_window = self.demo_window_runner()
        return to_jsonable(
            {
                "status": "Executed",
                "completed": True,
                "strategy_name": strategy_name,
                "target_strategy_names": target_strategy_names,
                "cycles": cycles,
                "symbol": symbol,
                "orders_attempted": _demo_orders_attempted(demo_window),
                "live_orders_sent": _live_orders_sent(demo_window),
                "block_reasons": [],
                "prechecks": prechecks,
                "demo_window": demo_window,
            }
        )

    @staticmethod
    def _blocked(
        strategy_name: str,
        target_strategy_names: list[str],
        cycles: int,
        symbol: str,
        prechecks: dict[str, Any],
        reasons: list[str],
    ) -> dict[str, Any]:
        """Return a blocked orchestration payload without running demo orders."""
        return to_jsonable(
            {
                "status": "Blocked",
                "completed": False,
                "strategy_name": strategy_name,
                "target_strategy_names": target_strategy_names,
                "cycles": cycles,
                "symbol": symbol,
                "orders_attempted": False,
                "live_orders_sent": False,
                "block_reasons": reasons,
                "prechecks": prechecks,
                "demo_window": None,
            }
        )


def _capture_precheck(callback: Precheck) -> dict[str, Any]:
    """Run a precheck and convert exceptions into a blocked payload."""
    try:
        return callback()
    except Exception as exc:
        return {
            "ok": False,
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        }


def _health_ok(payload: dict[str, Any]) -> bool:
    sandbox = payload.get("sandbox_check")
    if isinstance(sandbox, dict):
        return bool(sandbox.get("ok")) and not bool(sandbox.get("live_orders_sent"))
    return bool(payload.get("ok")) and not bool(payload.get("live_orders_sent"))


def _guard_summary(payload: dict[str, Any]) -> dict[str, Any]:
    status = payload.get("strategy_guard_status")
    entries = status.get("entries", []) if isinstance(status, dict) else []
    normalized_entries = [entry for entry in entries if isinstance(entry, dict)]
    active = [entry for entry in normalized_entries if entry.get("cooldown_active")]
    return {
        "ok": payload.get("ok", True) is not False,
        "cooldown_active": bool(active),
        "active_cooldowns": active,
        "entries": normalized_entries,
        "error_type": payload.get("error_type"),
        "error": payload.get("error"),
    }


def _market_compare_summary(payload: dict[str, Any], target_strategy_names: list[str]) -> dict[str, Any]:
    result = payload.get("strategy_market_compare")
    comparisons = result.get("comparisons", []) if isinstance(result, dict) else []
    normalized = [comparison for comparison in comparisons if isinstance(comparison, dict)]
    candidate_strategies = [
        str(comparison.get("strategy_name"))
        for comparison in normalized
        if comparison.get("verdict") == "demo_preflight_candidate"
    ]
    missing = sorted(set(target_strategy_names) - set(candidate_strategies))
    return {
        "ok": payload.get("ok", True) is not False and isinstance(result, dict) and not bool(result.get("orders_sent")),
        "orders_sent": bool(result.get("orders_sent")) if isinstance(result, dict) else False,
        "candidate_strategies": candidate_strategies,
        "missing_candidate_strategies": missing,
        "comparisons": normalized,
        "error_type": payload.get("error_type"),
        "error": payload.get("error"),
    }


def _validation_report_summary(payload: dict[str, Any]) -> dict[str, Any]:
    report = payload.get("strategy_validation_report")
    total = report.get("total", {}) if isinstance(report, dict) else {}
    quality_reasons: list[str] = []
    if total.get("execution_quality_passed") is False:
        quality_reasons.append("rolling_execution_quality_failed")
    if int(total.get("positive_cash_flow_negative_equity_delta") or 0) > 0:
        quality_reasons.append("rolling_positive_cash_flow_negative_equity_delta")
    if Decimal(str(total.get("max_drawdown_usdt", "0") or "0")) > Decimal("0"):
        quality_reasons.append("rolling_drawdown_present")
    return {
        "ok": payload.get("ok", True) is not False and isinstance(report, dict),
        "quality_block_reasons": quality_reasons,
        "total": total,
        "recommendations": report.get("recommendations", []) if isinstance(report, dict) else [],
        "error_type": payload.get("error_type"),
        "error": payload.get("error"),
    }


def _demo_orders_attempted(payload: dict[str, Any]) -> bool:
    return any(_execution_value(payload, "demo_orders_sent"))


def _live_orders_sent(payload: dict[str, Any]) -> bool:
    return any(_execution_value(payload, "live_orders_sent"))


def _execution_value(payload: dict[str, Any], key: str) -> list[bool]:
    strategy_run = payload.get("strategy_run")
    results = strategy_run.get("results", []) if isinstance(strategy_run, dict) else []
    values: list[bool] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        execution = result.get("execution")
        if isinstance(execution, dict):
            values.append(bool(execution.get(key)))
    return values
