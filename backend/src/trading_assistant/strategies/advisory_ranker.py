"""Read-only deterministic advisory ranking for strategy candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.base import utcnow
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.strategies.guard import StrategyRuntimeGuard
from trading_assistant.strategies.models import ExecutionMode, StrategyDefinition
from trading_assistant.strategies.opportunity_density import OpportunityDensityBucket, OpportunityDensityService
from trading_assistant.strategies.platform import StrategyScoreCard, StrategyScoreService
from trading_assistant.strategies.registry import StrategyRegistry
from trading_assistant.strategies.validation_report import StrategyValidationAggregate, StrategyValidationReportService
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class StrategyAdvisoryRanking:
    """One deterministic advisory ranking row."""

    rank: int
    strategy_name: str
    scanner_type: str
    category: str
    recommendation: str
    advisory_score: Decimal
    platform_score: Decimal
    opportunity_count: int
    expected_net_profit_usdt: Decimal
    expected_net_profit_pct: Decimal
    validation_executed: int
    validation_win_rate_pct: Decimal
    validation_net_profit_usdt: Decimal
    validation_max_drawdown_usdt: Decimal
    density_scan_count: int
    density_opportunity_count: int
    density_break_even_gap_usdt: Decimal
    demo_supported: bool
    live_supported: bool
    guard_cooldown_active: bool
    reasons: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyAdvisoryRankReport:
    """Read-only strategy advisory ranking report."""

    strategy_name: str
    symbol: str
    execution_mode: ExecutionMode | None
    window: str
    limit: int
    rankings: list[StrategyAdvisoryRanking]
    recommendations: list[str]
    model_policy: dict[str, Any]
    generated_at: str
    read_only: bool = True
    orders_sent: bool = False
    live_orders_sent: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(
            {
                "strategy_name": self.strategy_name,
                "symbol": self.symbol,
                "execution_mode": self.execution_mode,
                "window": self.window,
                "limit": self.limit,
                "rankings": [row.to_dict() for row in self.rankings],
                "recommendations": self.recommendations,
                "model_policy": self.model_policy,
                "generated_at": self.generated_at,
                "read_only": self.read_only,
                "orders_sent": self.orders_sent,
                "live_orders_sent": self.live_orders_sent,
            }
        )


class StrategyAdvisoryRankerService:
    """Rank strategies using local evidence without model calls or order dispatch."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory, registry: StrategyRegistry | None = None) -> None:
        self.settings = settings
        self.exchanges = exchanges
        self.registry = registry or StrategyRegistry()

    def rank(
        self,
        strategy_name: str = "all",
        symbol: str = "BTC/USDT",
        execution_mode: ExecutionMode | None = None,
        limit: int = 50,
        window: str = "24h",
    ) -> StrategyAdvisoryRankReport:
        """Return read-only deterministic advisory rankings."""
        requested_limit = max(limit, 1)
        cards = StrategyScoreService(self.settings, self.exchanges, self.registry).score(
            strategy_name=strategy_name,
            symbol=symbol,
        )
        validation = StrategyValidationReportService(self.settings.strategy_runtime).report(
            execution_mode=execution_mode,
            strategy_name=strategy_name,
            limit=requested_limit,
        )
        density = OpportunityDensityService(self.settings.strategy_runtime).report(window=window)
        strategy_names = [card.strategy_name for card in cards]
        guard = StrategyRuntimeGuard(self.settings.strategy_runtime).status(
            strategy_names=strategy_names,
            execution_mode=execution_mode,
        )
        unranked = [
            self._build_row(
                rank=0,
                card=card,
                validation=_validation_for(card.strategy_name, validation.by_strategy, self.registry),
                density=_density_for(card.strategy_name, density.by_strategy, self.registry),
                guard_entry=_guard_entry_for(card.strategy_name, guard.get("entries", [])),
                execution_mode=execution_mode,
            )
            for card in cards
        ]
        sorted_rows = sorted(
            unranked,
            key=lambda row: (row.advisory_score, row.validation_net_profit_usdt, row.opportunity_count),
            reverse=True,
        )
        ranked_rows = [
            StrategyAdvisoryRanking(
                rank=index + 1,
                strategy_name=row.strategy_name,
                scanner_type=row.scanner_type,
                category=row.category,
                recommendation=row.recommendation,
                advisory_score=row.advisory_score,
                platform_score=row.platform_score,
                opportunity_count=row.opportunity_count,
                expected_net_profit_usdt=row.expected_net_profit_usdt,
                expected_net_profit_pct=row.expected_net_profit_pct,
                validation_executed=row.validation_executed,
                validation_win_rate_pct=row.validation_win_rate_pct,
                validation_net_profit_usdt=row.validation_net_profit_usdt,
                validation_max_drawdown_usdt=row.validation_max_drawdown_usdt,
                density_scan_count=row.density_scan_count,
                density_opportunity_count=row.density_opportunity_count,
                density_break_even_gap_usdt=row.density_break_even_gap_usdt,
                demo_supported=row.demo_supported,
                live_supported=row.live_supported,
                guard_cooldown_active=row.guard_cooldown_active,
                reasons=row.reasons,
                evidence=row.evidence,
            )
            for index, row in enumerate(sorted_rows[:requested_limit])
        ]
        return StrategyAdvisoryRankReport(
            strategy_name=strategy_name,
            symbol=symbol,
            execution_mode=execution_mode,
            window=window,
            limit=requested_limit,
            rankings=ranked_rows,
            recommendations=_report_recommendations(ranked_rows),
            model_policy=_model_policy(),
            generated_at=utcnow().isoformat(),
        )

    def _build_row(
        self,
        *,
        rank: int,
        card: StrategyScoreCard,
        validation: StrategyValidationAggregate | None,
        density: OpportunityDensityBucket | None,
        guard_entry: dict[str, Any] | None,
        execution_mode: ExecutionMode | None,
    ) -> StrategyAdvisoryRanking:
        definition = self.registry.get(card.strategy_name)
        validation = validation or StrategyValidationAggregate(strategy_name=card.strategy_name)
        density = density or OpportunityDensityBucket(strategy_name=card.strategy_name)
        reasons = _dedupe([*card.reasons])
        cooldown_active = bool(guard_entry and guard_entry.get("cooldown_active"))
        if cooldown_active:
            reasons.append("runtime_guard_cooldown")
        if card.opportunity_count <= 0:
            reasons.append("no_current_opportunity")
        if validation.executed <= 0:
            reasons.append("insufficient_validation_samples")
        if validation.realized_net_profit_usdt > self.settings.strategy_runtime.validation_min_net_profit_usdt:
            reasons.append("positive_validation_pnl")
        if validation.win_rate_pct >= self.settings.strategy_runtime.validation_min_win_rate_pct and validation.executed > 0:
            reasons.append("validation_win_rate_met")
        if not validation.execution_quality_passed:
            reasons.append("validation_quality_failures")
        if density.break_even_gap_usdt > 0:
            reasons.append("break_even_gap_observed")
        if execution_mode == "demo" and not definition.demo_supported:
            reasons.append("demo_not_supported")
        if execution_mode == "paper" and not definition.paper_supported:
            reasons.append("paper_not_supported")
        if execution_mode is None and not definition.paper_supported:
            reasons.append("paper_not_supported")
        reasons = _dedupe(reasons)
        advisory_score = _advisory_score(card, validation, density, reasons)
        recommendation = _recommendation(
            definition=definition,
            execution_mode=execution_mode,
            validation=validation,
            advisory_score=advisory_score,
            reasons=reasons,
            settings=self.settings,
        )
        return StrategyAdvisoryRanking(
            rank=rank,
            strategy_name=card.strategy_name,
            scanner_type=card.scanner_type,
            category=definition.category,
            recommendation=recommendation,
            advisory_score=advisory_score,
            platform_score=card.score,
            opportunity_count=card.opportunity_count,
            expected_net_profit_usdt=card.expected_net_profit,
            expected_net_profit_pct=card.expected_net_profit_pct,
            validation_executed=validation.executed,
            validation_win_rate_pct=validation.win_rate_pct,
            validation_net_profit_usdt=validation.realized_net_profit_usdt,
            validation_max_drawdown_usdt=validation.max_drawdown_usdt,
            density_scan_count=density.scan_count,
            density_opportunity_count=density.opportunity_count,
            density_break_even_gap_usdt=density.break_even_gap_usdt,
            demo_supported=definition.demo_supported,
            live_supported=definition.live_supported,
            guard_cooldown_active=cooldown_active,
            reasons=reasons,
            evidence={
                "score_card": card.to_dict(),
                "validation": validation.to_dict(),
                "density": density.to_dict(),
                "guard": guard_entry or {},
            },
        )


def _advisory_score(
    card: StrategyScoreCard,
    validation: StrategyValidationAggregate,
    density: OpportunityDensityBucket,
    reasons: list[str],
) -> Decimal:
    score = card.score
    if validation.executed > 0:
        score += min(Decimal(validation.executed) * Decimal("3"), Decimal("15"))
        score += min((validation.win_rate_pct / Decimal("100")) * Decimal("15"), Decimal("15"))
    if validation.realized_net_profit_usdt > 0:
        score += Decimal("10")
    if density.opportunity_count > 0:
        score += min(Decimal(density.opportunity_count) * Decimal("2"), Decimal("10"))
    if density.break_even_gap_usdt > 0:
        score -= min(density.break_even_gap_usdt, Decimal("15"))
    if "validation_quality_failures" in reasons:
        score -= Decimal("25")
    if "runtime_guard_cooldown" in reasons:
        score -= Decimal("50")
    if "demo_not_supported" in reasons or "paper_not_supported" in reasons:
        score -= Decimal("30")
    if "strategy_archived_by_evolution" in reasons:
        score -= Decimal("50")
    return max(Decimal("0"), min(score.quantize(Decimal("0.01")), Decimal("100")))


def _recommendation(
    *,
    definition: StrategyDefinition,
    execution_mode: ExecutionMode | None,
    validation: StrategyValidationAggregate,
    advisory_score: Decimal,
    reasons: list[str],
    settings: Settings,
) -> str:
    if execution_mode == "demo" and not definition.demo_supported:
        return "paper_only"
    if execution_mode == "paper" and not definition.paper_supported:
        return "watchlist"
    if "runtime_guard_cooldown" in reasons:
        return "wait_for_runtime_guard_cooldown"
    if "strategy_archived_by_evolution" in reasons:
        return "watchlist"
    required_executions = _required_executions(settings, execution_mode)
    if validation.executed < required_executions:
        return "collect_more_samples"
    if validation.realized_net_profit_usdt <= settings.strategy_runtime.validation_min_net_profit_usdt:
        return "watchlist"
    if validation.win_rate_pct < settings.strategy_runtime.validation_min_win_rate_pct:
        return "watchlist"
    if advisory_score >= Decimal("40"):
        return "prioritize_paper_validation"
    return "watchlist"


def _required_executions(settings: Settings, execution_mode: ExecutionMode | None) -> int:
    if execution_mode == "demo":
        return settings.strategy_runtime.validation_min_demo_executions
    return settings.strategy_runtime.validation_min_local_executions


def _model_policy() -> dict[str, Any]:
    return {
        "name": "deterministic_evidence_ranker",
        "external_model_called": False,
        "llm_direct_ordering_allowed": False,
        "orders_sent": False,
        "live_orders_sent": False,
        "config_mutation_allowed": False,
        "purpose": "rank_and_explain_only",
    }


def _report_recommendations(rankings: list[StrategyAdvisoryRanking]) -> list[str]:
    recommendations: list[str] = []
    for row in rankings[:5]:
        recommendations.append(f"{row.strategy_name}:{row.recommendation}")
    if not recommendations:
        recommendations.append("no_rankable_strategy")
    return recommendations


def _validation_for(
    strategy_name: str,
    by_strategy: dict[str, StrategyValidationAggregate],
    registry: StrategyRegistry,
) -> StrategyValidationAggregate | None:
    return _first_match(strategy_name, by_strategy, registry)


def _density_for(
    strategy_name: str,
    by_strategy: dict[str, OpportunityDensityBucket],
    registry: StrategyRegistry,
) -> OpportunityDensityBucket | None:
    return _first_match(strategy_name, by_strategy, registry)


def _first_match[T](
    strategy_name: str,
    values: dict[str, T],
    registry: StrategyRegistry,
) -> T | None:
    if strategy_name in values:
        return values[strategy_name]
    definition = registry.get(strategy_name)
    for name in [*definition.aliases, definition.execution_alias]:
        if name and name in values:
            return values[name]
    return None


def _guard_entry_for(strategy_name: str, entries: Any) -> dict[str, Any] | None:
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("strategy_name") == strategy_name:
            return entry
    return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
