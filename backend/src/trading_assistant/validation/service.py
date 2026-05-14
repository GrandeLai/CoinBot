"""Three-layer strategy validation and promotion decision service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.strategies.guard import StrategyRuntimeGuard
from trading_assistant.strategies.models import StrategyRunResult, StrategyStats
from trading_assistant.strategies.registry import StrategyRegistry
from trading_assistant.strategies.review import StrategyReviewService
from trading_assistant.strategies.runner import StrategyRunner
from trading_assistant.utils.serialization import to_jsonable


ValidationStatus = Literal["Pass", "Fail", "Needs More Samples"]
RunnerFactory = Callable[[Settings, ExchangeFactory], StrategyRunner]
OpenRiskChecker = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class StrategyValidationResult:
    """Validation result for one layer."""

    layer: Literal["local", "demo", "live"]
    status: ValidationStatus
    strategy_name: str
    reasons: list[str]
    metrics: dict[str, Any]
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe result."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyPromotionStatus:
    """Promotion status across all layers."""

    strategy_name: str
    local: StrategyValidationResult
    demo: StrategyValidationResult
    live: StrategyValidationResult
    promotable_to_live_canary: bool

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe status."""
        return to_jsonable(self)


class StrategyValidationService:
    """Run and summarize local/demo validation and live-canary promotion status."""

    def __init__(
        self,
        settings: Settings,
        exchanges: ExchangeFactory,
        runner_factory: RunnerFactory | None = None,
        open_risk_checker: OpenRiskChecker | None = None,
    ) -> None:
        self.settings = settings
        self.exchanges = exchanges
        self.runner_factory = runner_factory or (lambda settings, exchanges: StrategyRunner(settings, exchanges))
        self.open_risk_checker = open_risk_checker or self._okx_demo_open_risk_check
        self.registry = StrategyRegistry()

    def validate_local(self, strategy_name: str = "all", cycles: int = 1, symbol: str = "BTC/USDT") -> dict[str, Any]:
        """Run local paper validation and return a layer result."""
        runner = self.runner_factory(self.settings, self.exchanges)
        run = runner.run(
            strategy_name=strategy_name,
            max_cycles=cycles,
            interval_seconds=0,
            execution_mode="paper",
            symbol=symbol,
        )
        result = self._result_from_run("local", strategy_name, run)
        return {"local_validation": result.to_dict(), "strategy_run": run.to_dict()}

    def validate_demo_window(self, strategy_name: str = "all", cycles: int = 5, symbol: str = "BTC/USDT") -> dict[str, Any]:
        """Run an OKX Demo Trading validation window and return a layer result."""
        active_guard_entries = self._active_demo_guard_entries(strategy_name)
        if active_guard_entries and len(active_guard_entries) == len(self._target_strategy_names(strategy_name)):
            run = _guard_blocked_run(
                strategy_name=strategy_name,
                journal_path=self.settings.strategy_runtime.journal_path,
            )
            post_run_open_risk = {"checked": False, "reason": "runtime_guard_cooldown"}
            result = StrategyValidationResult(
                layer="demo",
                status="Fail",
                strategy_name=strategy_name,
                reasons=["runtime_guard_cooldown"],
                metrics=_metrics_from_run(run),
                details={
                    "summary": run.summary,
                    "guard_entries": active_guard_entries,
                    "post_run_open_risk": post_run_open_risk,
                },
            )
            return {
                "demo_window_validation": result.to_dict(),
                "strategy_run": run.to_dict(),
                "post_run_open_risk": post_run_open_risk,
            }
        runner = self.runner_factory(self.settings, self.exchanges)
        run = runner.run(
            strategy_name=strategy_name,
            max_cycles=cycles,
            interval_seconds=0,
            execution_mode="demo",
            symbol=symbol,
        )
        post_run_open_risk = self.open_risk_checker()
        result = self._result_from_run("demo", strategy_name, run, post_run_open_risk=post_run_open_risk)
        return {
            "demo_window_validation": result.to_dict(),
            "strategy_run": run.to_dict(),
            "post_run_open_risk": post_run_open_risk,
        }

    def promotion_status(self, strategy_name: str = "all") -> dict[str, Any]:
        """Return advisory promotion status without executing trades."""
        names = self.registry.names() if strategy_name == "all" else [definition.name for definition in self.registry.expand(strategy_name)]
        paper_stats = StrategyReviewService(self.settings.strategy_runtime).review(execution_mode="paper").strategy_stats
        demo_stats = StrategyReviewService(self.settings.strategy_runtime).review(execution_mode="demo").strategy_stats
        guard = StrategyRuntimeGuard(self.settings.strategy_runtime)
        statuses = []
        for name in names:
            local = self._result_from_stats("local", name, paper_stats.get(name))
            demo = self._result_from_stats("demo", name, demo_stats.get(name))
            guard_status = guard.status(strategy_names=[name])["entries"]
            live = self._live_result(name, demo, guard_status)
            statuses.append(
                StrategyPromotionStatus(
                    strategy_name=name,
                    local=local,
                    demo=demo,
                    live=live,
                    promotable_to_live_canary=local.status == "Pass" and demo.status == "Pass" and live.status == "Pass",
                )
            )
        return {"strategy_promotion_status": [status.to_dict() for status in statuses]}

    def _result_from_run(
        self,
        layer: Literal["local", "demo"],
        strategy_name: str,
        run: StrategyRunResult,
        post_run_open_risk: dict[str, Any] | None = None,
    ) -> StrategyValidationResult:
        metrics = _metrics_from_run(run)
        reasons: list[str] = []
        if not run.completed:
            reasons.append("run_not_completed")
        if run.stopped_reason:
            reasons.append(run.stopped_reason)
        if layer == "demo":
            reasons.extend(_demo_evidence_reasons(run, post_run_open_risk or {}))
        status = self._status_for_metrics(layer, metrics, reasons)
        return StrategyValidationResult(
            layer=layer,
            status=status,
            strategy_name=strategy_name,
            reasons=reasons,
            metrics=metrics,
            details={"summary": run.summary, "post_run_open_risk": post_run_open_risk or {}},
        )

    def _result_from_stats(
        self,
        layer: Literal["local", "demo"],
        strategy_name: str,
        stats: StrategyStats | None,
    ) -> StrategyValidationResult:
        metrics = _metrics_from_stats(stats)
        reasons: list[str] = []
        status = self._status_for_metrics(layer, metrics, reasons)
        return StrategyValidationResult(layer=layer, status=status, strategy_name=strategy_name, reasons=reasons, metrics=metrics)

    def _status_for_metrics(self, layer: Literal["local", "demo"], metrics: dict[str, Any], reasons: list[str]) -> ValidationStatus:
        if reasons:
            return "Fail"
        executed = int(metrics["executed"])
        min_samples = (
            self.settings.strategy_runtime.validation_min_local_executions
            if layer == "local"
            else self.settings.strategy_runtime.validation_min_demo_executions
        )
        if executed < min_samples:
            reasons.append(f"minimum_samples_not_met:{executed}<{min_samples}")
            return "Needs More Samples"
        net_profit = Decimal(str(metrics["net_profit"]))
        if net_profit < self.settings.strategy_runtime.validation_min_net_profit_usdt:
            reasons.append("net_profit_below_threshold")
            return "Fail"
        win_rate = Decimal(str(metrics["win_rate_pct"]))
        if win_rate < self.settings.strategy_runtime.validation_min_win_rate_pct:
            reasons.append("win_rate_below_threshold")
            return "Fail"
        max_drawdown = Decimal(str(metrics.get("max_drawdown_usdt", "0")))
        if max_drawdown > self.settings.strategy_runtime.validation_max_drawdown_usdt:
            reasons.append("drawdown_above_threshold")
            return "Fail"
        return "Pass"

    def _live_result(
        self,
        strategy_name: str,
        demo: StrategyValidationResult,
        guard_entries: list[dict[str, Any]],
    ) -> StrategyValidationResult:
        reasons: list[str] = []
        if demo.status != "Pass":
            reasons.append("demo_layer_not_passed")
        if not self.settings.strategy_runtime.validation_allow_live_canary:
            reasons.append("live_canary_promotion_disabled")
        if not self.settings.trading.live_trading or self.settings.trading.dry_run:
            reasons.append("live_trading_gate_not_enabled")
        if not self.settings.agent_trading.allow_live_orders:
            reasons.append("agent_live_orders_disabled")
        if any(entry.get("cooldown_active") for entry in guard_entries):
            reasons.append("runtime_guard_cooldown")
        status: ValidationStatus = "Pass" if not reasons else "Fail"
        return StrategyValidationResult(
            layer="live",
            status=status,
            strategy_name=strategy_name,
            reasons=reasons,
            metrics={
                "demo_status": demo.status,
                "live_trading": self.settings.trading.live_trading,
                "dry_run": self.settings.trading.dry_run,
                "agent_live_orders_allowed": self.settings.agent_trading.allow_live_orders,
                "validation_allow_live_canary": self.settings.strategy_runtime.validation_allow_live_canary,
            },
            details={"guard_entries": guard_entries},
        )

    def _okx_demo_open_risk_check(self) -> dict[str, Any]:
        okx = self.settings.exchanges.get("okx")
        if okx is None or not okx.enabled or okx.adapter != "okx" or not okx.sandbox:
            return {"checked": False, "reason": "okx_demo_exchange_not_enabled"}
        from coinbot_api.broker.okx import OKXTradingProvider

        provider = OKXTradingProvider()
        return {
            "checked": True,
            "configured": provider.configured,
            "demo": provider.demo,
            "open_spot_orders": len(provider.get_open_orders()),
            "open_swap_orders": len(provider.get_open_futures_orders(inst_type="SWAP")),
            "swap_positions": len(provider.get_positions(inst_type="SWAP")),
        }

    def _target_strategy_names(self, strategy_name: str) -> list[str]:
        if strategy_name == "all":
            return self.registry.names()
        return [definition.name for definition in self.registry.expand(strategy_name)]

    def _active_demo_guard_entries(self, strategy_name: str) -> list[dict[str, Any]]:
        entries = StrategyRuntimeGuard(self.settings.strategy_runtime).status(
            strategy_names=self._target_strategy_names(strategy_name),
            execution_mode="demo",
        )["entries"]
        return [dict(entry) for entry in entries if entry.get("cooldown_active")]


def _metrics_from_stats(stats: StrategyStats | None) -> dict[str, Any]:
    if stats is None:
        return {
            "total": 0,
            "executed": 0,
            "blocked": 0,
            "skipped": 0,
            "wins": 0,
            "losses": 0,
            "net_profit": "0",
            "win_rate_pct": "0",
            "max_drawdown_usdt": "0",
        }
    return {
        "total": stats.total,
        "executed": stats.executed,
        "blocked": stats.blocked,
        "skipped": stats.skipped,
        "wins": stats.wins,
        "losses": stats.losses,
        "net_profit": str(stats.net_profit),
        "win_rate_pct": str(stats.win_rate_pct),
        "max_drawdown_usdt": "0",
    }


def _metrics_from_run(run: StrategyRunResult) -> dict[str, Any]:
    executed_results = [item for item in run.results if item.decision == "executed"]
    wins = sum(1 for item in executed_results if item.net_profit > 0)
    losses = sum(1 for item in executed_results if item.net_profit <= 0)
    net_profit = sum((item.net_profit for item in executed_results), Decimal("0"))
    win_rate = (Decimal(wins) / Decimal(len(executed_results)) * Decimal("100")).quantize(Decimal("0.01")) if executed_results else Decimal("0")
    return {
        "cycles_completed": run.cycles_completed,
        "total": len(run.results),
        "executed": len(executed_results),
        "blocked": sum(1 for item in run.results if item.decision == "blocked"),
        "skipped": sum(1 for item in run.results if item.decision == "skipped"),
        "wins": wins,
        "losses": losses,
        "net_profit": str(net_profit),
        "win_rate_pct": str(win_rate),
        "max_drawdown_usdt": str(run.demo_max_drawdown_usdt or Decimal("0")),
    }


def _guard_blocked_run(
    strategy_name: str,
    journal_path: str,
) -> StrategyRunResult:
    return StrategyRunResult(
        completed=False,
        strategy_name=strategy_name,
        execution_mode="demo",
        cycles_completed=0,
        results=[],
        journal_path=journal_path,
        summary="Demo validation skipped before execution because every requested strategy is in runtime guard cooldown.",
        stopped_reason="runtime_guard_cooldown",
        demo_cumulative_net_pnl=Decimal("0"),
        demo_max_drawdown_usdt=Decimal("0"),
    )


def _demo_evidence_reasons(run: StrategyRunResult, post_run_open_risk: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for item in run.results:
        if item.decision != "executed":
            continue
        execution = item.execution or {}
        if execution.get("live_orders_sent") is True:
            reasons.append("live_order_sent_in_demo_validation")
        if execution.get("provider_demo") is not True:
            reasons.append("provider_not_demo")
        validation = execution.get("pnl_validation") or {}
        if validation.get("within_tolerance") is not True:
            reasons.append("pnl_reconciliation_failed")
        if validation.get("residual_inventory_within_tolerance") is False:
            reasons.append("residual_inventory_above_tolerance")
        receipts = validation.get("exchange_receipts") or {}
        if receipts.get("complete") is not True:
            reasons.append("exchange_receipts_incomplete")
    if post_run_open_risk.get("checked"):
        if post_run_open_risk.get("demo") is not True:
            reasons.append("post_run_provider_not_demo")
        if int(post_run_open_risk.get("open_spot_orders", 0)) > 0:
            reasons.append("open_spot_orders_after_run")
        if int(post_run_open_risk.get("open_swap_orders", 0)) > 0:
            reasons.append("open_swap_orders_after_run")
        if int(post_run_open_risk.get("swap_positions", 0)) > 0:
            reasons.append("swap_positions_after_run")
    return sorted(set(reasons))
