"""Read-only carry and basis scanner optimization diagnostics."""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, TypeVar

from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.strategies.market_compare import StrategyMarketComparison, StrategyMarketComparisonService
from trading_assistant.strategies.platform import StrategyController
from trading_assistant.utils.serialization import to_jsonable


CARRY_BASIS_STRATEGIES = ["funding-carry-hedged", "spot-perp-carry", "futures-perp-basis"]
MONEY_QUANT = Decimal("0.000001")
DURATION_QUANT = Decimal("0.001")
T = TypeVar("T")


@dataclass(frozen=True)
class CarryBasisOptimizationCard:
    """Offline optimization diagnostics for one carry or basis strategy."""

    strategy_name: str
    scanner_type: str
    exchange: str | None
    symbol: str | None
    demo_ready: bool
    approved: bool
    opportunity_count: int
    reasons: list[str]
    net_profit_usdt: Decimal
    min_required_net_profit_usdt: Decimal
    break_even_gap_usdt: Decimal
    net_profit_pct: Decimal | None
    observed_basis_pct: Decimal | None
    observed_funding_annualized_pct: Decimal | None
    estimated_fee_usdt: Decimal
    estimated_slippage_usdt: Decimal
    holding_cost_usdt: Decimal
    basis_hedge_cost_usdt: Decimal
    suggested_config_fields: list[str]
    recommended_actions: list[str]
    target_exchange: str | None = None
    target_verdict: str | None = None
    target_reasons: list[str] = field(default_factory=list)
    target_best_net_profit_usdt: Decimal = Decimal("0")
    target_delta_net_profit_usdt: Decimal = Decimal("0")
    unlock_priority: str = "local_only"
    quality_score: Decimal = Decimal("0")
    quality_bucket: str = "low_quality"
    quality_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe card."""
        return to_jsonable(self)


@dataclass(frozen=True)
class CarryBasisOptimizationReport:
    """Read-only optimization report for carry and basis strategies."""

    read_only: bool
    orders_sent: bool
    live_orders_sent: bool
    symbol: str
    cards: list[CarryBasisOptimizationCard]
    summary: dict[str, Any]
    target_exchange: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report."""
        return {
            "read_only": self.read_only,
            "orders_sent": self.orders_sent,
            "live_orders_sent": self.live_orders_sent,
            "symbol": self.symbol,
            "target_exchange": self.target_exchange,
            "cards": [card.to_dict() for card in self.cards],
            "summary": to_jsonable(self.summary),
        }


@dataclass(frozen=True)
class CarryBasisSweepObservation:
    """Per-symbol sweep observation and failure classification."""

    symbol: str
    status: str
    elapsed_seconds: Decimal
    reasons: list[str] = field(default_factory=list)
    cache_hit: bool = False
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe observation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class CarryBasisOptimizationSweep:
    """Read-only multi-symbol carry/basis optimization sweep."""

    read_only: bool
    orders_sent: bool
    live_orders_sent: bool
    symbols: list[str]
    reports: list[CarryBasisOptimizationReport]
    ranked_cards: list[CarryBasisOptimizationCard]
    observations: list[CarryBasisSweepObservation]
    summary: dict[str, Any]
    target_exchange: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe sweep."""
        return {
            "mode": "sweep",
            "read_only": self.read_only,
            "orders_sent": self.orders_sent,
            "live_orders_sent": self.live_orders_sent,
            "symbols": list(self.symbols),
            "target_exchange": self.target_exchange,
            "reports": [report.to_dict() for report in self.reports],
            "ranked_cards": [card.to_dict() for card in self.ranked_cards],
            "observations": [observation.to_dict() for observation in self.observations],
            "summary": to_jsonable(self.summary),
        }


class SweepSymbolTimeout(TimeoutError):
    """Raised when a read-only sweep symbol exceeds its observation timeout."""


class CarryBasisOptimizationService:
    """Summarize carry/basis scanner diagnostics without sending orders."""

    def __init__(
        self,
        settings: Settings,
        exchanges: ExchangeFactory,
        market_compare_factory_cls: type[ExchangeFactory] = ExchangeFactory,
    ) -> None:
        self.settings = settings
        self.exchanges = exchanges
        self.controller = StrategyController(settings, exchanges)
        self.market_compare_factory_cls = market_compare_factory_cls
        self._report_cache: dict[tuple[str, str | None], CarryBasisOptimizationReport] = {}

    def report(self, symbol: str = "BTC/USDT", target_exchange: str | None = None) -> CarryBasisOptimizationReport:
        """Return offline optimization cards for carry and basis strategies."""
        cards: list[CarryBasisOptimizationCard] = []
        target_comparisons = self._target_comparisons(symbol=symbol, target_exchange=target_exchange)
        for strategy_name in CARRY_BASIS_STRATEGIES:
            scan = self.controller.scan(strategy_name=strategy_name, symbol=symbol)[0]
            diagnostic = _best_diagnostic(scan.diagnostics)
            target = target_comparisons.get(scan.strategy_name)
            unlock_priority = _unlock_priority(target)
            quality_score, quality_bucket, quality_reasons = _quality(
                unlock_priority=unlock_priority,
                demo_ready=bool(scan.opportunities) and bool(diagnostic.get("approved", bool(scan.opportunities))),
                reasons=_string_list(diagnostic.get("reasons")),
                net_profit_usdt=_money(_decimal_or_default(diagnostic, "net_profit_usdt", Decimal("0"))),
                min_required_net_profit_usdt=_money(_decimal_or_default(diagnostic, "min_required_net_profit_usdt", Decimal("0"))),
                break_even_gap_usdt=_money(_decimal_or_default(diagnostic, "break_even_gap_usdt", Decimal("0"))),
            )
            cards.append(
                CarryBasisOptimizationCard(
                    strategy_name=scan.strategy_name,
                    scanner_type=scan.scanner_type,
                    exchange=_optional_str(diagnostic.get("exchange") or scan.diagnostics.get("exchange")),
                    symbol=_optional_str(diagnostic.get("symbol") or scan.diagnostics.get("symbol")),
                    demo_ready=bool(scan.opportunities) and bool(diagnostic.get("approved", bool(scan.opportunities))),
                    approved=bool(diagnostic.get("approved", bool(scan.opportunities))),
                    opportunity_count=len(scan.opportunities),
                    reasons=_string_list(diagnostic.get("reasons")),
                    net_profit_usdt=_money(_decimal_or_default(diagnostic, "net_profit_usdt", Decimal("0"))),
                    min_required_net_profit_usdt=_money(_decimal_or_default(diagnostic, "min_required_net_profit_usdt", Decimal("0"))),
                    break_even_gap_usdt=_money(_decimal_or_default(diagnostic, "break_even_gap_usdt", Decimal("0"))),
                    net_profit_pct=_optional_decimal(diagnostic, "net_profit_pct"),
                    observed_basis_pct=_basis_pct(diagnostic),
                    observed_funding_annualized_pct=_funding_annualized(diagnostic),
                    estimated_fee_usdt=_money(_decimal_or_default(diagnostic, "estimated_fee_usdt", Decimal("0"))),
                    estimated_slippage_usdt=_money(_decimal_or_default(diagnostic, "estimated_slippage_usdt", Decimal("0"))),
                    holding_cost_usdt=_money(_holding_cost(diagnostic)),
                    basis_hedge_cost_usdt=_money(_decimal_or_default(diagnostic, "basis_hedge_cost_usdt", Decimal("0"))),
                    suggested_config_fields=_suggested_fields(scan.strategy_name),
                    recommended_actions=_actions(scan.strategy_name, diagnostic, bool(scan.opportunities)),
                    target_exchange=target.target.exchange if target is not None else target_exchange,
                    target_verdict=target.verdict if target is not None else None,
                    target_reasons=list(target.reasons) if target is not None else [],
                    target_best_net_profit_usdt=_money(target.target.best_net_profit_usdt) if target is not None else Decimal("0"),
                    target_delta_net_profit_usdt=_money(target.delta_net_profit_usdt) if target is not None else Decimal("0"),
                    unlock_priority=unlock_priority,
                    quality_score=quality_score,
                    quality_bucket=quality_bucket,
                    quality_reasons=quality_reasons,
                )
            )
        return CarryBasisOptimizationReport(
            read_only=True,
            orders_sent=False,
            live_orders_sent=False,
            symbol=symbol,
            cards=cards,
            summary=_summary(cards),
            target_exchange=target_exchange,
        )

    def sweep(
        self,
        symbols: list[str],
        target_exchange: str | None = None,
        min_quality_score: Decimal | None = None,
        max_symbols: int | None = None,
        request_budget_seconds: Decimal | None = None,
        per_symbol_timeout_seconds: Decimal | None = None,
    ) -> CarryBasisOptimizationSweep:
        """Return ranked carry/basis diagnostics across multiple symbols."""
        start = time.monotonic()
        normalized_symbols = _limited_symbols(_normalized_symbols(symbols), max_symbols)
        reports: list[CarryBasisOptimizationReport] = []
        observations: list[CarryBasisSweepObservation] = []
        for symbol in normalized_symbols:
            remaining_budget = _remaining_budget(start, request_budget_seconds)
            if remaining_budget is not None and remaining_budget <= Decimal("0"):
                observations.append(
                    CarryBasisSweepObservation(
                        symbol=symbol,
                        status="skipped_request_budget",
                        elapsed_seconds=_elapsed_since(start),
                        reasons=["request_budget_exhausted"],
                    )
                )
                continue
            symbol_start = time.monotonic()
            timeout_seconds = _effective_symbol_timeout(
                per_symbol_timeout_seconds=per_symbol_timeout_seconds,
                remaining_budget_seconds=remaining_budget,
            )
            try:
                report, cache_hit = _call_with_timeout(
                    lambda: self._cached_report(symbol=symbol, target_exchange=target_exchange),
                    timeout_seconds=timeout_seconds,
                )
            except SweepSymbolTimeout as exc:
                observations.append(
                    CarryBasisSweepObservation(
                        symbol=symbol,
                        status="timed_out",
                        elapsed_seconds=_elapsed_since(symbol_start),
                        reasons=["per_symbol_timeout_exceeded"],
                        message=str(exc),
                    )
                )
                continue
            except Exception as exc:
                observations.append(
                    CarryBasisSweepObservation(
                        symbol=symbol,
                        status="failed",
                        elapsed_seconds=_elapsed_since(symbol_start),
                        reasons=[f"sweep_symbol_error:{exc.__class__.__name__}"],
                        message=str(exc),
                    )
                )
                continue
            reports.append(report)
            observations.append(
                CarryBasisSweepObservation(
                    symbol=symbol,
                    status="cached" if cache_hit else "completed",
                    elapsed_seconds=_elapsed_since(symbol_start),
                    reasons=["cache_hit"] if cache_hit else [],
                    cache_hit=cache_hit,
                )
            )
        all_ranked_cards = _ranked_cards(reports)
        ranked_cards = _quality_filtered_cards(all_ranked_cards, min_quality_score)
        return CarryBasisOptimizationSweep(
            read_only=True,
            orders_sent=False,
            live_orders_sent=False,
            symbols=normalized_symbols,
            reports=reports,
            ranked_cards=ranked_cards,
            observations=observations,
            summary=_sweep_summary(
                reports,
                ranked_cards,
                observations=observations,
                total_card_count=len(all_ranked_cards),
                min_quality_score=min_quality_score,
                request_budget_seconds=request_budget_seconds,
                per_symbol_timeout_seconds=per_symbol_timeout_seconds,
                max_symbols=max_symbols,
                elapsed_seconds=_elapsed_since(start),
                requested_symbol_count=len(normalized_symbols),
            ),
            target_exchange=target_exchange,
        )

    def _cached_report(self, symbol: str, target_exchange: str | None) -> tuple[CarryBasisOptimizationReport, bool]:
        """Return a cached report for repeated sweep symbols in one service lifetime."""
        key = (symbol, target_exchange)
        cached = self._report_cache.get(key)
        if cached is not None:
            return cached, True
        report = self.report(symbol=symbol, target_exchange=target_exchange)
        self._report_cache[key] = report
        return report, False

    def _target_comparisons(self, symbol: str, target_exchange: str | None) -> dict[str, StrategyMarketComparison]:
        """Return target market comparisons keyed by strategy name."""
        if target_exchange is None:
            return {}
        service = StrategyMarketComparisonService(self.settings, factory_cls=self.market_compare_factory_cls)
        comparisons: list[StrategyMarketComparison] = []
        for strategy_name in CARRY_BASIS_STRATEGIES:
            result = service.compare(
                strategy_name=strategy_name,
                symbol=symbol,
                target_exchange=target_exchange,
            )
            comparisons.extend(result.comparisons)
        return {
            comparison.strategy_name: comparison
            for comparison in comparisons
            if comparison.strategy_name in CARRY_BASIS_STRATEGIES
        }


def _best_diagnostic(diagnostics: dict[str, Any]) -> dict[str, Any]:
    """Return the most relevant diagnostic candidate."""
    candidate = diagnostics.get("best_candidate")
    if isinstance(candidate, dict):
        return candidate
    return diagnostics


def _actions(strategy_name: str, diagnostic: dict[str, Any], has_opportunity: bool) -> list[str]:
    """Return conservative offline optimization actions."""
    reasons = set(_string_list(diagnostic.get("reasons")))
    gap = _decimal_or_default(diagnostic, "break_even_gap_usdt", Decimal("0"))
    actions: list[str] = []
    if gap > Decimal("0") or not has_opportunity:
        actions.append("keep_demo_blocked_until_break_even_gap_closes")
        actions.append("do_not_lower_demo_min_preflight_net_pnl_below_zero")
    if "net_profit_below_minimum" in reasons:
        actions.append("seek_stronger_spread_or_lower_execution_costs_before_demo")
    if "basis_below_minimum" in reasons or "futures_basis_below_minimum" in reasons:
        actions.append("wait_for_basis_above_configured_threshold")
    if "funding_annualized_below_minimum" in reasons:
        actions.append("wait_for_funding_above_configured_threshold")
    if "basis_hedge_cost_above_maximum" in reasons:
        actions.append("avoid_symbols_with_expensive_basis_hedge")
    if "insufficient_depth" in reasons:
        actions.append("reduce_candidate_universe_to_deeper_books")
    if not actions:
        actions.append("eligible_for_demo_preflight_after_standard_safety_gates")
    if strategy_name == "futures-perp-basis" and "futures_basis_data_unavailable" in reasons:
        actions.append("refresh_dated_futures_instrument_universe_before_demo")
    return sorted(set(actions))


def _suggested_fields(strategy_name: str) -> list[str]:
    """Return config fields worth reviewing offline for one strategy."""
    common = [
        "arbitrage.min_net_profit_pct",
        "arbitrage.funding_hedge_cost_pct",
    ]
    if strategy_name == "funding-carry-hedged":
        return [
            *common,
            "arbitrage.funding_min_annualized_pct",
            "arbitrage.funding_max_basis_hedge_cost_pct",
            "arbitrage.funding_holding_hours",
        ]
    if strategy_name == "spot-perp-carry":
        return [
            *common,
            "arbitrage.spot_perp_min_basis_pct",
            "arbitrage.funding_min_annualized_pct",
            "arbitrage.basis_holding_hours",
        ]
    return [
        *common,
        "arbitrage.futures_basis_min_basis_pct",
        "arbitrage.futures_basis_min_days_to_expiry",
        "arbitrage.funding_min_annualized_pct",
        "arbitrage.basis_holding_hours",
    ]


def _summary(cards: list[CarryBasisOptimizationCard]) -> dict[str, Any]:
    """Return aggregate optimization summary."""
    blocked = [card for card in cards if not card.demo_ready]
    max_gap = max((card.break_even_gap_usdt for card in cards), default=Decimal("0"))
    target_candidates = [card for card in cards if card.target_verdict == "demo_preflight_candidate"]
    high_priority = [card for card in cards if card.unlock_priority == "demo_candidate"]
    return {
        "strategy_count": len(cards),
        "demo_ready_count": len(cards) - len(blocked),
        "blocked_count": len(blocked),
        "max_break_even_gap_usdt": _money(max_gap),
        "target_demo_preflight_candidate_count": len(target_candidates),
        "high_priority_unlock_count": len(high_priority),
        "highest_priority": "demo_candidate" if high_priority else "high" if blocked else "observe",
        "guardrails": [
            "read_only_no_orders",
            "do_not_force_demo_when_break_even_gap_positive",
            "do_not_reduce_profit_safety_gates_from_optimizer_output",
        ],
    }


def _sweep_summary(
    reports: list[CarryBasisOptimizationReport],
    ranked_cards: list[CarryBasisOptimizationCard],
    observations: list[CarryBasisSweepObservation],
    total_card_count: int,
    min_quality_score: Decimal | None,
    request_budget_seconds: Decimal | None,
    per_symbol_timeout_seconds: Decimal | None,
    max_symbols: int | None,
    elapsed_seconds: Decimal,
    requested_symbol_count: int,
) -> dict[str, Any]:
    """Return aggregate optimization summary across symbols."""
    top = ranked_cards[0] if ranked_cards else None
    target_candidates = [card for card in ranked_cards if card.target_verdict == "demo_preflight_candidate"]
    high_priority = [card for card in ranked_cards if card.unlock_priority == "demo_candidate"]
    high_quality = [card for card in ranked_cards if card.quality_bucket == "high_quality"]
    skipped = [observation for observation in observations if observation.status.startswith("skipped_")]
    timeouts = [observation for observation in observations if observation.status == "timed_out"]
    failed = [observation for observation in observations if observation.status == "failed"]
    cached = [observation for observation in observations if observation.cache_hit]
    return {
        "symbol_count": len(reports),
        "requested_symbol_count": requested_symbol_count,
        "evaluated_symbol_count": len(reports),
        "skipped_symbol_count": len(skipped),
        "timeout_symbol_count": len(timeouts),
        "failed_symbol_count": len(failed),
        "cache_hit_count": len(cached),
        "card_count": len(ranked_cards),
        "total_card_count": total_card_count,
        "filtered_out_count": total_card_count - len(ranked_cards),
        "min_quality_score": _quality_quant(min_quality_score) if min_quality_score is not None else None,
        "max_symbols": max_symbols,
        "request_budget_seconds": _duration_quant(request_budget_seconds) if request_budget_seconds is not None else None,
        "per_symbol_timeout_seconds": _duration_quant(per_symbol_timeout_seconds) if per_symbol_timeout_seconds is not None else None,
        "elapsed_seconds": elapsed_seconds,
        "strategy_count": len(ranked_cards),
        "demo_ready_count": sum(report.summary["demo_ready_count"] for report in reports),
        "blocked_count": sum(report.summary["blocked_count"] for report in reports),
        "target_demo_preflight_candidate_count": len(target_candidates),
        "high_priority_unlock_count": len(high_priority),
        "high_quality_candidate_count": len(high_quality),
        "closest_break_even_gap_usdt": _money(top.break_even_gap_usdt) if top is not None else Decimal("0"),
        "top_symbol": top.symbol if top is not None else None,
        "top_strategy": top.strategy_name if top is not None else None,
        "highest_priority": top.unlock_priority if top is not None else "observe",
        "guardrails": [
            "read_only_no_orders",
            "rank_before_demo_window",
            "do_not_force_demo_without_demo_candidate",
        ],
    }


def _ranked_cards(reports: list[CarryBasisOptimizationReport]) -> list[CarryBasisOptimizationCard]:
    """Return cards ordered by unlock priority and break-even proximity."""
    cards = [card for report in reports for card in report.cards]
    return sorted(cards, key=_rank_key)


def _quality_filtered_cards(
    cards: list[CarryBasisOptimizationCard],
    min_quality_score: Decimal | None,
) -> list[CarryBasisOptimizationCard]:
    """Return cards that meet the optional quality floor."""
    if min_quality_score is None:
        return cards
    return [card for card in cards if card.quality_score >= min_quality_score]


def _rank_key(card: CarryBasisOptimizationCard) -> tuple[int, Decimal, Decimal, Decimal, str, str]:
    """Return deterministic ranking key for multi-symbol sweep cards."""
    priority_rank = {
        "demo_candidate": 0,
        "paper_candidate": 1,
        "observe_only": 2,
        "local_only": 3,
    }.get(card.unlock_priority, 4)
    return (
        priority_rank,
        -card.quality_score,
        card.break_even_gap_usdt,
        -card.target_delta_net_profit_usdt,
        card.symbol or "",
        card.strategy_name,
    )


def _normalized_symbols(symbols: list[str]) -> list[str]:
    """Return non-empty symbols while preserving caller order and uniqueness."""
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        candidate = symbol.strip()
        if not candidate or candidate in seen:
            continue
        normalized.append(candidate)
        seen.add(candidate)
    return normalized or ["BTC/USDT"]


def _limited_symbols(symbols: list[str], max_symbols: int | None) -> list[str]:
    """Return symbols capped by the optional caller budget."""
    if max_symbols is None:
        return symbols
    return symbols[: max(max_symbols, 0)]


def _remaining_budget(start: float, request_budget_seconds: Decimal | None) -> Decimal | None:
    """Return remaining sweep budget in seconds."""
    if request_budget_seconds is None:
        return None
    return max(request_budget_seconds - _raw_elapsed_since(start), Decimal("0"))


def _effective_symbol_timeout(
    *,
    per_symbol_timeout_seconds: Decimal | None,
    remaining_budget_seconds: Decimal | None,
) -> Decimal | None:
    """Return the effective timeout for the next symbol observation."""
    candidates = [
        value
        for value in (per_symbol_timeout_seconds, remaining_budget_seconds)
        if value is not None
    ]
    if not candidates:
        return None
    return min(candidates)


def _call_with_timeout(func: Callable[[], T], timeout_seconds: Decimal | None) -> T:
    """Run a read-only observation with an optional daemon-thread timeout."""
    if timeout_seconds is None:
        return func()
    if timeout_seconds <= Decimal("0"):
        raise SweepSymbolTimeout("symbol observation exceeded 0s timeout")
    results: queue.Queue[T | BaseException] = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            results.put(func())
        except BaseException as exc:  # pragma: no cover - surfaced in caller thread
            results.put(exc)

    thread = threading.Thread(target=worker, name="carry-basis-sweep-symbol", daemon=True)
    thread.start()
    thread.join(timeout=float(timeout_seconds))
    if thread.is_alive():
        raise SweepSymbolTimeout(f"symbol observation exceeded {timeout_seconds}s timeout")
    result = results.get_nowait()
    if isinstance(result, BaseException):
        raise result
    return result


def _raw_elapsed_since(start: float) -> Decimal:
    """Return raw elapsed wall-clock seconds."""
    return max(Decimal(str(time.monotonic() - start)), Decimal("0"))


def _elapsed_since(start: float) -> Decimal:
    """Return quantized elapsed wall-clock seconds."""
    return _duration_quant(_raw_elapsed_since(start))


def _duration_quant(value: Decimal) -> Decimal:
    """Quantize duration values for stable CLI output."""
    quantized = max(value, Decimal("0")).quantize(DURATION_QUANT)
    if quantized == quantized.to_integral_value():
        return quantized.quantize(Decimal("1"))
    return quantized.normalize()


def _basis_pct(diagnostic: dict[str, Any]) -> Decimal | None:
    """Return whichever basis percentage the diagnostic exposes."""
    for key in ("basis_pct", "futures_perp_basis_pct"):
        value = _optional_decimal(diagnostic, key)
        if value is not None:
            return value
    return None


def _funding_annualized(diagnostic: dict[str, Any]) -> Decimal | None:
    """Return nested funding annualized percentage when available."""
    carry = diagnostic.get("funding_carry")
    carry_payload: dict[str, Any] = carry if isinstance(carry, dict) else {}
    return _optional_decimal(carry_payload, "annualized_pct")


def _holding_cost(diagnostic: dict[str, Any]) -> Decimal:
    """Return nested funding holding cost when available."""
    carry = diagnostic.get("funding_carry")
    carry_payload: dict[str, Any] = carry if isinstance(carry, dict) else {}
    return _decimal_or_default(carry_payload, "holding_cost_usdt", Decimal("0"))


def _optional_decimal(payload: dict[str, Any], key: str) -> Decimal | None:
    """Return a Decimal when the field is present."""
    if key not in payload:
        return None
    value = payload[key]
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _decimal_or_default(payload: dict[str, Any], key: str, default: Decimal) -> Decimal:
    """Return Decimal from payload or default."""
    value = _optional_decimal(payload, key)
    return default if value is None else value


def _money(value: Decimal) -> Decimal:
    """Quantize money values for stable CLI output."""
    return value.quantize(MONEY_QUANT)


def _quality(
    *,
    unlock_priority: str,
    demo_ready: bool,
    reasons: list[str],
    net_profit_usdt: Decimal,
    min_required_net_profit_usdt: Decimal,
    break_even_gap_usdt: Decimal,
) -> tuple[Decimal, str, list[str]]:
    """Return a conservative quality score for ranking candidate cards."""
    score = Decimal("100")
    quality_reasons: list[str] = []
    if unlock_priority == "demo_candidate":
        quality_reasons.append("target_demo_candidate")
    elif unlock_priority == "paper_candidate":
        score -= Decimal("20")
        quality_reasons.append("target_paper_candidate")
    elif unlock_priority == "observe_only":
        score -= Decimal("40")
        quality_reasons.append("target_observe_only")
    else:
        score -= Decimal("50")
        quality_reasons.append("local_only")

    if demo_ready:
        quality_reasons.append("local_demo_ready")
    else:
        score -= Decimal("15")
        quality_reasons.append("local_not_demo_ready")

    if net_profit_usdt > Decimal("0"):
        quality_reasons.append("positive_net_profit")
    else:
        score -= Decimal("10")
        quality_reasons.append("non_positive_net_profit")

    score -= _gap_penalty(break_even_gap_usdt, min_required_net_profit_usdt)
    reason_penalties = {
        "net_profit_below_minimum": Decimal("10"),
        "funding_annualized_below_minimum": Decimal("8"),
        "basis_below_minimum": Decimal("8"),
        "futures_basis_below_minimum": Decimal("8"),
        "basis_hedge_cost_above_maximum": Decimal("12"),
        "insufficient_depth": Decimal("20"),
    }
    for reason in reasons:
        penalty = reason_penalties.get(reason)
        if penalty is None:
            continue
        score -= penalty
        quality_reasons.append(f"penalty:{reason}")

    clamped = min(max(score, Decimal("0")), Decimal("100"))
    return _quality_quant(clamped), _quality_bucket(clamped), sorted(set(quality_reasons))


def _gap_penalty(break_even_gap_usdt: Decimal, min_required_net_profit_usdt: Decimal) -> Decimal:
    """Return a bounded quality penalty for break-even gap distance."""
    if break_even_gap_usdt <= Decimal("0"):
        return Decimal("0")
    denominator = max(min_required_net_profit_usdt, MONEY_QUANT)
    return min(Decimal("30"), (break_even_gap_usdt / denominator * Decimal("30")).quantize(Decimal("0.01")))


def _quality_bucket(score: Decimal) -> str:
    """Return a stable quality bucket for operator filtering."""
    if score >= Decimal("80"):
        return "high_quality"
    if score >= Decimal("60"):
        return "medium_quality"
    if score >= Decimal("35"):
        return "watchlist"
    return "low_quality"


def _quality_quant(value: Decimal) -> Decimal:
    """Quantize quality scores for stable CLI output."""
    quantized = value.quantize(Decimal("0.01"))
    if quantized == quantized.to_integral_value():
        return quantized.quantize(Decimal("1"))
    return quantized.normalize()


def _string_list(value: Any) -> list[str]:
    """Return a list of strings from a JSON-like field."""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _optional_str(value: Any) -> str | None:
    """Return a string when a value is present."""
    if value is None:
        return None
    return str(value)


def _unlock_priority(comparison: StrategyMarketComparison | None) -> str:
    """Return conservative unlock priority from target-market comparison."""
    if comparison is None:
        return "local_only"
    if comparison.verdict == "demo_preflight_candidate":
        return "demo_candidate"
    if comparison.verdict == "paper_only":
        return "paper_candidate"
    return "observe_only"
