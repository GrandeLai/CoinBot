"""Read-only strategy-family diversification reporting."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any

from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.strategies.advisory_ranker import StrategyAdvisoryRankerService, StrategyAdvisoryRanking
from trading_assistant.strategies.models import ExecutionMode, StrategyDefinition
from trading_assistant.strategies.registry import StrategyRegistry
from trading_assistant.utils.serialization import to_jsonable


PCT_QUANT = Decimal("0.01")


@dataclass(frozen=True)
class StrategyFamilyDiversificationRow:
    """One strategy-family concentration and validation-budget row."""

    family: str
    strategies: list[str]
    strategy_count: int
    ranking_count: int
    candidate_count: int
    demo_candidate_count: int
    validation_executed: int
    validation_net_profit_usdt: Decimal
    validation_max_drawdown_usdt: Decimal
    opportunity_density_count: int
    candidate_share_pct: Decimal
    validation_budget_share_pct: Decimal
    over_concentration: bool
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe row."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyValidationQueueItem:
    """One read-only candidate for the next family-balanced validation window."""

    rank: int
    strategy_name: str
    family: str
    execution_mode: ExecutionMode | None
    recommended_stage: str
    advisory_score: Decimal
    validation_budget_share_pct: Decimal
    candidate_share_pct: Decimal
    opportunity_count: int
    density_opportunity_count: int
    demo_candidate_count: int
    validation_executed: int
    validation_net_profit_usdt: Decimal
    guard_cooldown_active: bool
    quality_score: Decimal
    quality_bucket: str
    quality_reasons: list[str]
    next_action: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe queue item."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyDiversificationReport:
    """Read-only strategy-family diversification report."""

    strategy_name: str
    symbol: str
    execution_mode: ExecutionMode | None
    window: str
    limit: int
    max_family_share_pct: Decimal
    families: list[StrategyFamilyDiversificationRow]
    validation_queue: list[StrategyValidationQueueItem]
    summary: dict[str, Any]
    recommendations: list[str]
    guardrails: list[str]
    model_policy: dict[str, Any]
    generated_at: str
    read_only: bool = True
    orders_sent: bool = False
    live_orders_sent: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report."""
        return to_jsonable(
            {
                "strategy_name": self.strategy_name,
                "symbol": self.symbol,
                "execution_mode": self.execution_mode,
                "window": self.window,
                "limit": self.limit,
                "max_family_share_pct": self.max_family_share_pct,
                "families": [row.to_dict() for row in self.families],
                "validation_queue": [item.to_dict() for item in self.validation_queue],
                "summary": self.summary,
                "recommendations": self.recommendations,
                "guardrails": self.guardrails,
                "model_policy": self.model_policy,
                "generated_at": self.generated_at,
                "read_only": self.read_only,
                "orders_sent": self.orders_sent,
                "live_orders_sent": self.live_orders_sent,
            }
        )


class StrategyDiversificationService:
    """Aggregate advisory evidence by strategy family without trading."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory, registry: StrategyRegistry | None = None) -> None:
        self.settings = settings
        self.exchanges = exchanges
        self.registry = registry or StrategyRegistry()

    def report(
        self,
        strategy_name: str = "all",
        symbol: str = "BTC/USDT",
        execution_mode: ExecutionMode | None = None,
        limit: int = 50,
        window: str = "24h",
        max_family_share_pct: Decimal = Decimal("60"),
        min_queue_quality_score: Decimal = Decimal("0"),
    ) -> StrategyDiversificationReport:
        """Return family-level concentration and validation-budget guidance."""
        cap = _pct_clamp(max_family_share_pct)
        quality_floor = _pct_clamp(min_queue_quality_score)
        advisory = StrategyAdvisoryRankerService(self.settings, self.exchanges, self.registry).rank(
            strategy_name=strategy_name,
            symbol=symbol,
            execution_mode=execution_mode,
            limit=limit,
            window=window,
        )
        groups: dict[str, list[StrategyAdvisoryRanking]] = defaultdict(list)
        family_by_strategy: dict[str, str] = {}
        for row in advisory.rankings:
            family = _family_for(self.registry.get(row.strategy_name))
            family_by_strategy[row.strategy_name] = family
            groups[family].append(row)
        total_candidates = sum(row.opportunity_count for row in advisory.rankings)
        candidate_families = [
            family
            for family, rows in groups.items()
            if sum(row.opportunity_count for row in rows) > 0 or sum(_demo_candidate_count(row) for row in rows) > 0
        ]
        budget_share = _budget_share_by_family(candidate_families, cap)
        family_rows = [
            self._family_row(
                family=family,
                rows=rows,
                total_candidates=total_candidates,
                validation_budget_share_pct=budget_share.get(family, Decimal("0")),
                cap=cap,
                candidate_family_count=len(candidate_families),
            )
            for family, rows in sorted(groups.items())
        ]
        family_rows = sorted(family_rows, key=lambda row: (row.candidate_share_pct, row.validation_net_profit_usdt), reverse=True)
        family_rows_by_family = {row.family: row for row in family_rows}
        unfiltered_validation_queue = _validation_queue(
            advisory.rankings,
            family_by_strategy=family_by_strategy,
            family_rows_by_family=family_rows_by_family,
            execution_mode=execution_mode,
        )
        validation_queue = _filter_queue_by_quality(unfiltered_validation_queue, min_quality_score=quality_floor)
        summary = _summary(
            family_rows,
            total_candidates=total_candidates,
            cap=cap,
            candidate_family_count=len(candidate_families),
            validation_queue=validation_queue,
            unfiltered_validation_queue=unfiltered_validation_queue,
            min_queue_quality_score=quality_floor,
        )
        return StrategyDiversificationReport(
            strategy_name=strategy_name,
            symbol=symbol,
            execution_mode=execution_mode,
            window=window,
            limit=max(limit, 1),
            max_family_share_pct=cap,
            families=family_rows,
            validation_queue=validation_queue,
            summary=summary,
            recommendations=_recommendations(family_rows),
            guardrails=[
                "read_only_no_orders",
                "family_concentration_guard",
                "family_budget_capped_non_triangular_first",
                "do_not_lower_preflight_to_force_diversification",
                "demo_window_gates_remain_authoritative",
            ],
            model_policy=advisory.model_policy,
            generated_at=advisory.generated_at,
        )

    def _family_row(
        self,
        *,
        family: str,
        rows: list[StrategyAdvisoryRanking],
        total_candidates: int,
        validation_budget_share_pct: Decimal,
        cap: Decimal,
        candidate_family_count: int,
    ) -> StrategyFamilyDiversificationRow:
        """Return one family row from advisory rankings."""
        candidate_count = sum(row.opportunity_count for row in rows)
        demo_candidate_count = sum(_demo_candidate_count(row) for row in rows)
        validation_executed = sum(row.validation_executed for row in rows)
        validation_net_profit = sum((row.validation_net_profit_usdt for row in rows), Decimal("0"))
        max_drawdown = sum((row.validation_max_drawdown_usdt for row in rows), Decimal("0"))
        density_count = sum(row.density_opportunity_count for row in rows)
        candidate_share = _pct(Decimal(candidate_count), Decimal(total_candidates))
        over_concentration = candidate_family_count > 1 and candidate_share > cap
        return StrategyFamilyDiversificationRow(
            family=family,
            strategies=sorted(row.strategy_name for row in rows),
            strategy_count=len({row.strategy_name for row in rows}),
            ranking_count=len(rows),
            candidate_count=candidate_count,
            demo_candidate_count=demo_candidate_count,
            validation_executed=validation_executed,
            validation_net_profit_usdt=validation_net_profit,
            validation_max_drawdown_usdt=max_drawdown,
            opportunity_density_count=density_count,
            candidate_share_pct=candidate_share,
            validation_budget_share_pct=validation_budget_share_pct,
            over_concentration=over_concentration,
            recommendations=_family_recommendations(
                family=family,
                candidate_count=candidate_count,
                demo_candidate_count=demo_candidate_count,
                over_concentration=over_concentration,
                cap=cap,
            ),
        )


def _family_for(definition: StrategyDefinition) -> str:
    """Return the diversification family for one strategy definition."""
    if definition.scanner_type in {"triangular", "triangular-multi-route"}:
        return "triangular"
    if definition.scanner_type in {"funding-carry-hedged", "spot-perp-carry", "futures-perp-basis"}:
        return "carry_basis"
    if definition.scanner_type == "cross-exchange":
        return "cross_exchange"
    if definition.scanner_type == "hedged-maker":
        return "hedged_maker"
    if definition.scanner_type == "range-grid":
        return "grid"
    if definition.category == "directional":
        return "directional"
    if definition.category == "portfolio":
        return "portfolio"
    return definition.category


def _demo_candidate_count(row: StrategyAdvisoryRanking) -> int:
    """Return journal-observed demo preflight candidate count from advisory evidence."""
    density = row.evidence.get("density")
    if not isinstance(density, dict):
        return 0
    return int(density.get("demo_preflight_candidate_count") or 0)


def _budget_share_by_family(candidate_families: list[str], cap: Decimal) -> dict[str, Decimal]:
    """Return advisory validation-budget shares capped by family."""
    if not candidate_families:
        return {}
    if len(candidate_families) == 1:
        return {candidate_families[0]: Decimal("100")}
    share = min(_pct(Decimal("1"), Decimal(len(candidate_families))), cap)
    return {family: share for family in candidate_families}


def _validation_queue(
    rankings: list[StrategyAdvisoryRanking],
    *,
    family_by_strategy: dict[str, str],
    family_rows_by_family: dict[str, StrategyFamilyDiversificationRow],
    execution_mode: ExecutionMode | None,
) -> list[StrategyValidationQueueItem]:
    """Return deterministic next-validation candidates with non-triangular candidates first."""
    candidate_rows = [row for row in rankings if _queue_candidate_count(row) > 0]
    if not candidate_rows:
        candidate_rows = rankings[:5]
    has_non_triangular_candidate = any(
        family_by_strategy.get(row.strategy_name) != "triangular" and _queue_candidate_count(row) > 0 for row in candidate_rows
    )
    sorted_rows = sorted(
        candidate_rows,
        key=lambda row: _queue_sort_key(
            row,
            family=family_by_strategy.get(row.strategy_name, row.category),
            family_rows_by_family=family_rows_by_family,
            has_non_triangular_candidate=has_non_triangular_candidate,
        ),
    )
    return [
        _queue_item(
            rank=index + 1,
            row=row,
            family=family_by_strategy.get(row.strategy_name, row.category),
            family_row=family_rows_by_family.get(family_by_strategy.get(row.strategy_name, row.category)),
            execution_mode=execution_mode,
            has_non_triangular_candidate=has_non_triangular_candidate,
        )
        for index, row in enumerate(sorted_rows)
    ]


def _queue_sort_key(
    row: StrategyAdvisoryRanking,
    *,
    family: str,
    family_rows_by_family: dict[str, StrategyFamilyDiversificationRow],
    has_non_triangular_candidate: bool,
) -> tuple[int, int, Decimal, Decimal, Decimal, Decimal, int, str]:
    """Return stable sort key for validation queue priority."""
    family_row = family_rows_by_family.get(family)
    family_budget = family_row.validation_budget_share_pct if family_row is not None else Decimal("0")
    non_triangular_rank = 0 if has_non_triangular_candidate and family != "triangular" else 1
    missing_current_opportunity_rank = 0 if row.opportunity_count > 0 else 1
    quality_score = _queue_quality_score(row, family=family)
    return (
        non_triangular_rank,
        missing_current_opportunity_rank,
        -quality_score,
        -family_budget,
        -row.advisory_score,
        -row.validation_net_profit_usdt,
        row.rank,
        row.strategy_name,
    )


def _queue_item(
    *,
    rank: int,
    row: StrategyAdvisoryRanking,
    family: str,
    family_row: StrategyFamilyDiversificationRow | None,
    execution_mode: ExecutionMode | None,
    has_non_triangular_candidate: bool,
) -> StrategyValidationQueueItem:
    """Build one JSON-safe validation queue item."""
    validation_budget_share = family_row.validation_budget_share_pct if family_row is not None else Decimal("0")
    candidate_share = family_row.candidate_share_pct if family_row is not None else Decimal("0")
    quality_score = _queue_quality_score(row, family=family)
    return StrategyValidationQueueItem(
        rank=rank,
        strategy_name=row.strategy_name,
        family=family,
        execution_mode=execution_mode,
        recommended_stage=row.recommendation,
        advisory_score=row.advisory_score,
        validation_budget_share_pct=validation_budget_share,
        candidate_share_pct=candidate_share,
        opportunity_count=row.opportunity_count,
        density_opportunity_count=row.density_opportunity_count,
        demo_candidate_count=_demo_candidate_count(row),
        validation_executed=row.validation_executed,
        validation_net_profit_usdt=row.validation_net_profit_usdt,
        guard_cooldown_active=row.guard_cooldown_active,
        quality_score=quality_score,
        quality_bucket=_quality_bucket(quality_score),
        quality_reasons=_queue_quality_reasons(row, family=family),
        next_action=_queue_next_action(
            row=row,
            family=family,
            has_non_triangular_candidate=has_non_triangular_candidate,
        ),
        reasons=_queue_reasons(row=row, family=family, has_non_triangular_candidate=has_non_triangular_candidate),
    )


def _queue_next_action(
    *,
    row: StrategyAdvisoryRanking,
    family: str,
    has_non_triangular_candidate: bool,
) -> str:
    """Return the advisory action for one queue item."""
    if row.guard_cooldown_active or row.recommendation == "wait_for_runtime_guard_cooldown":
        return "wait_for_runtime_guard_cooldown"
    if _queue_candidate_count(row) <= 0:
        return "collect_more_evidence"
    if family == "triangular" and has_non_triangular_candidate:
        return "hold_triangular_within_family_cap"
    if family != "triangular":
        return "validate_non_triangular_candidate"
    return "validate_candidate"


def _queue_reasons(
    *,
    row: StrategyAdvisoryRanking,
    family: str,
    has_non_triangular_candidate: bool,
) -> list[str]:
    """Return concise reasons for one queue item."""
    reasons = [*row.reasons]
    if family != "triangular":
        reasons.append("non_triangular_family")
    if family == "triangular" and has_non_triangular_candidate:
        reasons.append("triangular_family_capped_until_non_triangular_candidates_are_observed")
    if row.opportunity_count <= 0:
        reasons.append("no_current_opportunity")
    return _dedupe(reasons)


def _queue_candidate_count(row: StrategyAdvisoryRanking) -> int:
    """Return current plus recently observed candidate evidence for queue inclusion."""
    return row.opportunity_count + row.density_opportunity_count + _demo_candidate_count(row)


def _queue_quality_score(row: StrategyAdvisoryRanking, *, family: str) -> Decimal:
    """Return deterministic validation-candidate quality score."""
    score = row.advisory_score * Decimal("0.75")
    if row.opportunity_count > 0:
        score += Decimal("20")
    elif row.density_opportunity_count > 0 or _demo_candidate_count(row) > 0:
        score += Decimal("10")
    if row.validation_executed > 0:
        score += min(Decimal(row.validation_executed) * Decimal("5"), Decimal("10"))
    if row.validation_net_profit_usdt > 0:
        score += Decimal("10")
    if row.validation_win_rate_pct >= Decimal("60") and row.validation_executed > 0:
        score += Decimal("5")
    if family != "triangular":
        score += Decimal("5")
    if row.guard_cooldown_active:
        score -= Decimal("50")
    if "repeated_demo_preflight_not_profitable" in row.reasons:
        score -= Decimal("15")
    if any(reason.startswith("demo_break_even_gap_usdt:") for reason in row.reasons):
        score -= Decimal("10")
    if "validation_quality_failures" in row.reasons:
        score -= Decimal("20")
    if row.recommendation in {"paper_only", "watchlist"}:
        score -= Decimal("10")
    return max(Decimal("0"), min(score, Decimal("100"))).quantize(PCT_QUANT)


def _quality_bucket(score: Decimal) -> str:
    """Return stable quality bucket for a queue score."""
    if score >= Decimal("80"):
        return "high"
    if score >= Decimal("55"):
        return "medium"
    return "low"


def _queue_quality_reasons(row: StrategyAdvisoryRanking, *, family: str) -> list[str]:
    """Return deterministic score reasons for queue quality."""
    reasons: list[str] = []
    if row.opportunity_count > 0:
        reasons.append("current_opportunity_present")
    elif row.density_opportunity_count > 0 or _demo_candidate_count(row) > 0:
        reasons.append("recent_candidate_evidence")
    else:
        reasons.append("no_candidate_evidence")
    if row.validation_executed > 0:
        reasons.append("validation_samples_present")
    if row.validation_net_profit_usdt > 0:
        reasons.append("positive_validation_pnl")
    if row.validation_win_rate_pct >= Decimal("60") and row.validation_executed > 0:
        reasons.append("validation_win_rate_met")
    if family != "triangular":
        reasons.append("non_triangular_diversification_bonus")
    if row.guard_cooldown_active:
        reasons.append("runtime_guard_cooldown_penalty")
    if "repeated_demo_preflight_not_profitable" in row.reasons or any(
        reason.startswith("demo_break_even_gap_usdt:") for reason in row.reasons
    ):
        reasons.append("demo_preflight_pressure_penalty")
    if "validation_quality_failures" in row.reasons:
        reasons.append("validation_quality_failure_penalty")
    if row.recommendation in {"paper_only", "watchlist"}:
        reasons.append(f"{row.recommendation}_penalty")
    return _dedupe(reasons)


def _filter_queue_by_quality(
    queue: list[StrategyValidationQueueItem],
    *,
    min_quality_score: Decimal,
) -> list[StrategyValidationQueueItem]:
    """Return queue items at or above the quality floor with contiguous ranks."""
    filtered = [item for item in queue if item.quality_score >= min_quality_score]
    return [replace(item, rank=index + 1) for index, item in enumerate(filtered)]


def _summary(
    rows: list[StrategyFamilyDiversificationRow],
    *,
    total_candidates: int,
    cap: Decimal,
    candidate_family_count: int,
    validation_queue: list[StrategyValidationQueueItem],
    unfiltered_validation_queue: list[StrategyValidationQueueItem],
    min_queue_quality_score: Decimal,
) -> dict[str, Any]:
    """Return aggregate family diversification summary."""
    dominant = rows[0] if rows else None
    over_concentrated = [row.family for row in rows if row.over_concentration]
    non_triangular_queue_count = sum(1 for item in validation_queue if item.family != "triangular")
    triangular_queue_count = sum(1 for item in validation_queue if item.family == "triangular")
    return {
        "family_count": len(rows),
        "candidate_family_count": candidate_family_count,
        "total_candidate_count": total_candidates,
        "max_family_share_pct": cap,
        "dominant_family": dominant.family if dominant is not None else None,
        "dominant_candidate_share_pct": dominant.candidate_share_pct if dominant is not None else Decimal("0"),
        "over_concentrated": bool(over_concentrated),
        "over_concentrated_families": over_concentrated,
        "validation_queue_count": len(validation_queue),
        "unfiltered_validation_queue_count": len(unfiltered_validation_queue),
        "filtered_validation_queue_count": len(unfiltered_validation_queue) - len(validation_queue),
        "non_triangular_queue_count": non_triangular_queue_count,
        "triangular_queue_count": triangular_queue_count,
        "high_quality_queue_count": sum(1 for item in validation_queue if item.quality_bucket == "high"),
        "min_queue_quality_score": min_queue_quality_score,
        "queue_policy": "family_budget_capped_non_triangular_first",
    }


def _recommendations(rows: list[StrategyFamilyDiversificationRow]) -> list[str]:
    """Return report-level diversification recommendations."""
    recommendations: list[str] = []
    if any(row.over_concentration for row in rows):
        recommendations.append("cap_over_concentrated_family_validation_budget")
    if any(row.family == "triangular" and row.over_concentration for row in rows):
        recommendations.append("prioritize_non_triangular_candidate_collection")
    if not any(row.family == "carry_basis" and row.candidate_count > 0 for row in rows):
        recommendations.append("continue_bounded_carry_basis_observer")
    if not recommendations:
        recommendations.append("continue_family_balanced_validation")
    return recommendations


def _family_recommendations(
    *,
    family: str,
    candidate_count: int,
    demo_candidate_count: int,
    over_concentration: bool,
    cap: Decimal,
) -> list[str]:
    """Return family-specific recommendations."""
    recommendations: list[str] = []
    if over_concentration:
        recommendations.append(f"cap_validation_budget_at_{cap}_pct")
    if candidate_count <= 0:
        recommendations.append("collect_more_candidates")
    if demo_candidate_count <= 0:
        recommendations.append("collect_demo_preflight_candidates")
    if family == "carry_basis" and candidate_count <= 0:
        recommendations.append("run_bounded_carry_basis_sweep")
    if not recommendations:
        recommendations.append("eligible_for_family_balanced_validation")
    return recommendations


def _dedupe(values: list[str]) -> list[str]:
    """Return values once while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Return percentage with stable quantization."""
    if denominator <= 0:
        return Decimal("0")
    return (numerator / denominator * Decimal("100")).quantize(PCT_QUANT)


def _pct_clamp(value: Decimal) -> Decimal:
    """Clamp percentage-like input to 0..100."""
    quantized = max(Decimal("0"), min(value, Decimal("100"))).quantize(PCT_QUANT)
    if quantized == quantized.to_integral_value():
        return quantized.quantize(Decimal("1"))
    return quantized.normalize()
