"""Read-only market comparison for strategy optimization loops."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from trading_assistant.arbitrage.calculator import percent
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import ExchangeConfig, Settings
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.exceptions import ExchangeError
from trading_assistant.strategies.platform import StrategyController, StrategyScanReport
from trading_assistant.strategies.registry import StrategyRegistry
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class StrategyMarketSnapshot:
    """One strategy scan snapshot against one market source."""

    strategy_name: str
    scanner_type: str
    exchange: str
    status: str
    opportunity_count: int
    best_opportunity_id: str | None
    best_net_profit_usdt: Decimal
    best_net_profit_pct: Decimal
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyMarketComparison:
    """Baseline-vs-target comparison for one strategy."""

    strategy_name: str
    scanner_type: str
    baseline: StrategyMarketSnapshot
    target: StrategyMarketSnapshot
    delta_net_profit_usdt: Decimal
    verdict: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyMarketComparisonResult:
    """Read-only strategy market comparison result."""

    symbol: str
    baseline_exchange: str
    target_exchange: str
    read_only: bool
    orders_sent: bool
    safety: dict[str, Any]
    comparisons: list[StrategyMarketComparison]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


class StrategyMarketComparisonService:
    """Compare mock baseline scans with a configured target market source.

    The service deliberately builds scan-only settings: it never touches the
    strategy runner, journal, retrospective, broker, or order execution paths.
    """

    def __init__(self, settings: Settings, factory_cls: type[ExchangeFactory] = ExchangeFactory) -> None:
        self.settings = settings
        self.factory_cls = factory_cls
        self.registry = StrategyRegistry()

    def compare(
        self,
        strategy_name: str = "all",
        symbol: str = "BTC/USDT",
        target_exchange: str | None = None,
    ) -> StrategyMarketComparisonResult:
        """Return read-only mock-vs-target strategy comparison."""
        baseline_exchange = "mock"
        resolved_target = target_exchange or self._default_target_exchange()
        target_config = self.settings.exchanges.get(resolved_target)
        if target_config is None:
            raise ExchangeError(f"Unknown target exchange: {resolved_target}")
        if not target_config.enabled:
            raise ExchangeError(f"Target exchange is disabled: {resolved_target}")

        baseline_settings = self._scan_settings_for_exchange(baseline_exchange, force_mock_baseline=True)
        target_settings = self._scan_settings_for_exchange(resolved_target, force_mock_baseline=False)
        baseline_reports = self._scan(baseline_settings, strategy_name=strategy_name, symbol=symbol)
        target_reports = self._scan(target_settings, strategy_name=strategy_name, symbol=symbol)
        comparisons = [
            self._compare_reports(
                baseline=self._report_for(report.strategy_name, baseline_reports),
                target=report,
                baseline_exchange=baseline_exchange,
                target_exchange=resolved_target,
            )
            for report in target_reports
        ]
        return StrategyMarketComparisonResult(
            symbol=symbol,
            baseline_exchange=baseline_exchange,
            target_exchange=resolved_target,
            read_only=True,
            orders_sent=False,
            safety={
                "live_trading": False,
                "dry_run": True,
                "require_confirm_before_order": True,
                "journal_written": False,
                "retrospective_updated": False,
            },
            comparisons=comparisons,
        )

    def _default_target_exchange(self) -> str:
        enabled = [
            name
            for name, config in self.settings.exchanges.items()
            if config.enabled and config.adapter != "mock"
        ]
        if enabled:
            return enabled[0]
        fallback = [name for name, config in self.settings.exchanges.items() if config.enabled]
        return fallback[0] if fallback else "mock"

    def _scan_settings_for_exchange(self, exchange: str, *, force_mock_baseline: bool) -> Settings:
        scan_settings = self.settings.model_copy(deep=True)
        scan_settings.trading.live_trading = False
        scan_settings.trading.dry_run = True
        scan_settings.trading.require_confirm_before_order = True
        for name, config in scan_settings.exchanges.items():
            config.enabled = name == exchange
        if force_mock_baseline:
            scan_settings.exchanges["mock"] = ExchangeConfig(enabled=True, sandbox=True, adapter="mock")
            scan_settings.exchanges["mock_alt"] = ExchangeConfig(enabled=True, sandbox=True, adapter="mock")
        return scan_settings

    def _scan(self, settings: Settings, strategy_name: str, symbol: str) -> list[StrategyScanReport]:
        try:
            return StrategyController(settings, self.factory_cls(settings)).scan(
                strategy_name=strategy_name,
                symbol=symbol,
            )
        except Exception as exc:
            return [
                StrategyScanReport(
                    strategy_name=definition.name,
                    scanner_type=definition.scanner_type,
                    status="error",
                    opportunities=[],
                    notes=f"read-only scan failed: {exc}",
                    diagnostics={
                        "approved": False,
                        "reasons": [f"scan_error:{exc.__class__.__name__}"],
                        "message": str(exc),
                    },
                )
                for definition in self.registry.expand(strategy_name)
            ]

    def _compare_reports(
        self,
        baseline: StrategyScanReport,
        target: StrategyScanReport,
        baseline_exchange: str,
        target_exchange: str,
    ) -> StrategyMarketComparison:
        baseline_snapshot = _snapshot(baseline, baseline_exchange)
        target_snapshot = _snapshot(target, target_exchange)
        delta = target_snapshot.best_net_profit_usdt - baseline_snapshot.best_net_profit_usdt
        verdict, reasons = _verdict(target_snapshot, delta)
        return StrategyMarketComparison(
            strategy_name=target.strategy_name,
            scanner_type=target.scanner_type,
            baseline=baseline_snapshot,
            target=target_snapshot,
            delta_net_profit_usdt=delta,
            verdict=verdict,
            reasons=reasons,
        )

    @staticmethod
    def _report_for(strategy_name: str, reports: list[StrategyScanReport]) -> StrategyScanReport:
        for report in reports:
            if report.strategy_name == strategy_name:
                return report
        return StrategyScanReport(
            strategy_name=strategy_name,
            scanner_type=strategy_name,
            status="missing",
            opportunities=[],
            notes="baseline scan did not return this strategy",
            diagnostics={"approved": False, "reasons": ["baseline_missing"]},
        )


def _snapshot(report: StrategyScanReport, exchange: str) -> StrategyMarketSnapshot:
    best = _best_opportunity(report.opportunities)
    return StrategyMarketSnapshot(
        strategy_name=report.strategy_name,
        scanner_type=report.scanner_type,
        exchange=exchange,
        status=report.status,
        opportunity_count=len(report.opportunities),
        best_opportunity_id=best.opportunity_id if best else None,
        best_net_profit_usdt=best.net_profit if best else Decimal("0"),
        best_net_profit_pct=percent(best.net_profit, best.required_capital) if best else Decimal("0"),
        diagnostics=report.diagnostics,
    )


def _best_opportunity(opportunities: list[ArbitrageOpportunity]) -> ArbitrageOpportunity | None:
    return max(opportunities, key=lambda opportunity: opportunity.net_profit, default=None)


def _verdict(target: StrategyMarketSnapshot, delta_net_profit_usdt: Decimal) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if target.opportunity_count <= 0:
        reasons.append("target_no_opportunity")
        reasons.extend(_diagnostic_reasons(target.diagnostics))
        return "observe_only", sorted(set(reasons))
    if target.best_net_profit_usdt <= 0:
        reasons.append("target_non_positive_net_profit")
        return "observe_only", sorted(set(reasons))
    if delta_net_profit_usdt < 0:
        reasons.append("target_weaker_than_mock_baseline")
        return "paper_only", sorted(set(reasons))
    reasons.append("target_has_positive_edge")
    return "demo_preflight_candidate", sorted(set(reasons))


def _diagnostic_reasons(diagnostics: dict[str, Any]) -> list[str]:
    candidate = diagnostics.get("best_candidate")
    source: dict[str, Any] = candidate if isinstance(candidate, dict) else diagnostics
    raw = source.get("reasons")
    if not isinstance(raw, list):
        return []
    return [f"diagnostic:{reason}" for reason in raw]
