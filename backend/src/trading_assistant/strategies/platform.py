"""Strategy platform services for catalog, scan, score, and portfolio selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from trading_assistant.arbitrage.calculator import percent
from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.arbitrage.scanner import ArbitrageScanner
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.base import AccountSnapshot
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.exceptions import ExchangeError
from trading_assistant.strategies.evolution import archived_strategy_names
from trading_assistant.strategies.hedged_maker_candidate import HedgedMakerDemoCandidateService
from trading_assistant.strategies.models import StrategyDefinition, StrategyStats
from trading_assistant.strategies.registry import StrategyRegistry
from trading_assistant.strategies.retrospective import StrategyRetrospectiveService
from trading_assistant.strategies.review import StrategyReviewService
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class StrategyScanReport:
    """Scan result for one registered strategy."""

    strategy_name: str
    scanner_type: str
    status: str
    opportunities: list[ArbitrageOpportunity]
    notes: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyScoreCard:
    """Transparent scorecard used before portfolio selection."""

    strategy_name: str
    scanner_type: str
    status: str
    score: Decimal
    risk_level: str
    opportunity_count: int
    best_opportunity_id: str | None
    expected_net_profit: Decimal
    expected_net_profit_pct: Decimal
    win_rate_pct: Decimal
    paper_samples: int
    demo_samples: int
    sell_leg_available: bool
    balance_restrictions: list[str]
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyPortfolioStatus:
    """Capital-aware portfolio selection result."""

    selected_strategies: list[str]
    blocked_strategies: list[dict[str, Any]]
    score_cards: list[StrategyScoreCard]
    capital_limit_usdt: Decimal
    max_concurrent_strategies: int
    min_score: Decimal

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


class StrategyCatalog:
    """Expose canonical strategy metadata and compatibility aliases."""

    def __init__(self, registry: StrategyRegistry | None = None) -> None:
        self.registry = registry or StrategyRegistry()

    def list(self) -> list[StrategyDefinition]:
        """Return canonical strategy definitions."""
        return self.registry.list()

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe catalog payload."""
        return {
            "strategies": [strategy.to_dict() for strategy in self.registry.list()],
            "aliases": self.registry.aliases(),
        }


class StrategyController:
    """Generate opportunities from registered strategy definitions."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory, registry: StrategyRegistry | None = None) -> None:
        self.settings = settings
        self.exchanges = exchanges
        self.registry = registry or StrategyRegistry()
        self.scanner = ArbitrageScanner(settings, exchanges)

    def scan(
        self,
        strategy_name: str = "all",
        symbol: str = "BTC/USDT",
        exchange: str | None = None,
        route_mode: str = "configured",
    ) -> list[StrategyScanReport]:
        """Scan one or all strategies without executing orders."""
        reports: list[StrategyScanReport] = []
        for definition in self._enabled_definitions(strategy_name):
            if definition.status == "deferred":
                reports.append(
                    StrategyScanReport(
                        strategy_name=definition.name,
                        scanner_type=definition.scanner_type,
                        status=definition.status,
                        opportunities=[],
                        notes=definition.notes,
                    )
                )
                continue
            opportunities = self._scan_definition(definition, symbol, exchange=exchange, route_mode=route_mode)
            diagnostics = self._diagnose_definition(definition, symbol, exchange=exchange)
            reports.append(
                StrategyScanReport(
                    strategy_name=definition.name,
                    scanner_type=definition.scanner_type,
                    status=definition.status,
                    opportunities=opportunities,
                    notes=definition.notes,
                    diagnostics=diagnostics,
                )
            )
        return reports

    def _scan_definition(
        self,
        definition: StrategyDefinition,
        symbol: str,
        exchange: str | None = None,
        route_mode: str = "configured",
    ) -> list[ArbitrageOpportunity]:
        try:
            if definition.category == "directional":
                return self.scanner.scan(definition.scanner_type, symbol=symbol, exchange=exchange or self._preferred_single_exchange())
            if definition.scanner_type in {"triangular", "triangular-multi-route"}:
                return self.scanner.scan(
                    definition.scanner_type,
                    exchange=exchange or self._preferred_single_exchange(),
                    route_mode=route_mode,
                )
            if definition.scanner_type in {
                "funding-carry-hedged",
                "spot-perp-carry",
                "futures-perp-basis",
                "range-grid",
                "smart-dca-basket",
                "hedged-maker",
            }:
                return self.scanner.scan(definition.scanner_type, symbol=symbol, exchange=exchange or self._preferred_single_exchange())
            return self.scanner.scan(definition.scanner_type, symbol=symbol)
        except ExchangeError:
            return []

    def _diagnose_definition(self, definition: StrategyDefinition, symbol: str, exchange: str | None = None) -> dict[str, Any]:
        diagnostic_exchange = exchange or self._preferred_single_exchange()
        try:
            if definition.category == "directional":
                return self.scanner.diagnose(definition.scanner_type, symbol=symbol, exchange=diagnostic_exchange)
            if definition.scanner_type in {"funding-carry-hedged"}:
                return self.scanner.diagnose(definition.scanner_type, symbol=symbol, exchange=diagnostic_exchange)
            if definition.scanner_type in {"spot-perp-carry", "futures-perp-basis"}:
                return self.scanner.diagnose(definition.scanner_type, symbol=symbol, exchange=diagnostic_exchange)
            if definition.scanner_type == "hedged-maker" and diagnostic_exchange == "okx":
                return HedgedMakerDemoCandidateService(self.settings, self.exchanges).candidate(
                    symbol=symbol,
                    target_exchange=diagnostic_exchange,
                ).to_dict()
            if definition.scanner_type in {"range-grid", "smart-dca-basket", "hedged-maker"}:
                return self.scanner.diagnose(definition.scanner_type, symbol=symbol, exchange=diagnostic_exchange)
        except ExchangeError as exc:
            return {"approved": False, "reasons": [f"diagnostic_error:{exc}"]}
        return {}

    def _enabled_definitions(self, strategy_name: str) -> list[StrategyDefinition]:
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
        """Return the configured single-exchange scan target."""
        enabled = self.exchanges.list_enabled()
        if "mock" in enabled:
            return "mock"
        if "okx" in enabled:
            return "okx"
        return enabled[0] if enabled else "mock"


class StrategyScoreService:
    """Score registered strategies using scan quality, history, and balance restrictions."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory, registry: StrategyRegistry | None = None) -> None:
        self.settings = settings
        self.exchanges = exchanges
        self.registry = registry or StrategyRegistry()
        self.controller = StrategyController(settings, exchanges, self.registry)

    def score(self, strategy_name: str = "all", symbol: str = "BTC/USDT") -> list[StrategyScoreCard]:
        """Return scorecards for one or all strategies."""
        paper_stats = StrategyReviewService(self.settings.strategy_runtime).review(execution_mode="paper").strategy_stats
        demo_stats = StrategyReviewService(self.settings.strategy_runtime).review(execution_mode="demo").strategy_stats
        reports = self.controller.scan(strategy_name=strategy_name, symbol=symbol)
        return [
            self._score_report(
                report,
                paper_stats=self._stats_for(report.strategy_name, paper_stats),
                demo_stats=self._stats_for(report.strategy_name, demo_stats),
            )
            for report in reports
        ]

    def _score_report(
        self,
        report: StrategyScanReport,
        paper_stats: StrategyStats | None,
        demo_stats: StrategyStats | None,
    ) -> StrategyScoreCard:
        definition = self.registry.get(report.strategy_name)
        reasons: list[str] = []
        if report.status == "deferred":
            reasons.append("strategy_deferred")
        if report.strategy_name in archived_strategy_names(self.settings.strategy_runtime):
            reasons.append("strategy_archived_by_evolution")
        if not report.opportunities:
            reasons.append("no_opportunity")
            reasons.extend(_diagnostic_score_reasons(report.diagnostics))
        best = max(report.opportunities, key=lambda item: item.net_profit, default=None)
        expected_profit = best.net_profit if best else Decimal("0")
        expected_profit_pct = percent(best.net_profit, best.required_capital) if best else Decimal("0")
        balance = self._balance_restrictions(definition, best)
        if not balance["sell_leg_available"]:
            reasons.append("sell_leg_unavailable")
        reasons.extend(balance["balance_restrictions"])
        reasons.extend(self._retrospective_pressure_reasons(report.strategy_name))
        paper_samples = paper_stats.executed if paper_stats else 0
        demo_samples = demo_stats.executed if demo_stats else 0
        win_rate = paper_stats.win_rate_pct if paper_stats else Decimal("0")
        score = self._calculate_score(best, win_rate, paper_samples, demo_samples, bool(balance["sell_leg_available"]), reasons)
        return StrategyScoreCard(
            strategy_name=report.strategy_name,
            scanner_type=report.scanner_type,
            status=report.status,
            score=score,
            risk_level=definition.risk_level,
            opportunity_count=len(report.opportunities),
            best_opportunity_id=best.opportunity_id if best else None,
            expected_net_profit=expected_profit,
            expected_net_profit_pct=expected_profit_pct,
            win_rate_pct=win_rate,
            paper_samples=paper_samples,
            demo_samples=demo_samples,
            sell_leg_available=bool(balance["sell_leg_available"]),
            balance_restrictions=list(balance["balance_restrictions"]),
            reasons=sorted(set(reasons)),
        )

    def _calculate_score(
        self,
        opportunity: ArbitrageOpportunity | None,
        win_rate_pct: Decimal,
        paper_samples: int,
        demo_samples: int,
        sell_leg_available: bool,
        reasons: list[str],
    ) -> Decimal:
        score = Decimal("0")
        if opportunity is not None:
            net_profit_pct = percent(opportunity.net_profit, opportunity.required_capital)
            score += Decimal("30")
            score += min(max(net_profit_pct, Decimal("0")) * Decimal("5"), Decimal("25"))
            score += min(opportunity.confidence * Decimal("20"), Decimal("20"))
            score += (Decimal("1") - opportunity.risk_score) * Decimal("15")
        if paper_samples:
            score += min((win_rate_pct / Decimal("100")) * Decimal("10"), Decimal("10"))
        if demo_samples:
            required_demo = Decimal(self.settings.strategy_runtime.validation_min_demo_executions)
            score += min((Decimal(demo_samples) / required_demo) * Decimal("10"), Decimal("10"))
        if not sell_leg_available:
            score -= Decimal("25")
        if any(reason.startswith("balance_locked") for reason in reasons):
            score -= Decimal("10")
        if "repeated_demo_preflight_not_profitable" in reasons:
            score -= self.settings.strategy_runtime.retrospective_demo_preflight_score_penalty
        if "strategy_archived_by_evolution" in reasons:
            score -= self.settings.strategy_runtime.evolution_archive_score_penalty
        return max(Decimal("0"), min(score.quantize(Decimal("0.01")), Decimal("100")))

    def _retrospective_pressure_reasons(self, strategy_name: str) -> list[str]:
        """Return score reasons from repeated retrospective optimization pressure."""
        summary = StrategyRetrospectiveService(self.settings.strategy_runtime).before_summary()
        reasons: list[str] = []
        for item in _as_dicts(summary.get("optimization_pressure", [])):
            if item.get("strategy_name") != strategy_name:
                continue
            if item.get("execution_mode") != "demo":
                continue
            if item.get("category") != "preflight_not_profitable":
                continue
            if item.get("priority") != "high":
                continue
            reasons.append("repeated_demo_preflight_not_profitable")
            gap = item.get("break_even_gap_usdt")
            if gap is not None:
                reasons.append(f"demo_break_even_gap_usdt:{gap}")
        return reasons

    def _balance_restrictions(self, definition: StrategyDefinition, opportunity: ArbitrageOpportunity | None) -> dict[str, Any]:
        if opportunity is None:
            return {"sell_leg_available": True, "balance_restrictions": []}
        if definition.scanner_type != "cross-exchange":
            return {"sell_leg_available": True, "balance_restrictions": []}
        restrictions: list[str] = []
        sell_available = True
        snapshots: dict[str, AccountSnapshot] = {}
        for leg in opportunity.metadata.get("legs", []):
            if leg.get("side") != "sell" or leg.get("market", "spot") != "spot":
                continue
            exchange_name = str(leg.get("exchange") or opportunity.sell_exchange or "")
            symbol = str(leg.get("symbol") or opportunity.symbol)
            base_asset = symbol.split("/")[0]
            if exchange_name not in snapshots:
                snapshots[exchange_name] = self.exchanges.get(exchange_name).get_balances()
            balance = snapshots[exchange_name].balance_for(base_asset)
            if balance.locked > 0:
                restrictions.append(f"balance_locked:{exchange_name}:{base_asset}")
            if balance.free <= 0:
                restrictions.append(f"sell_leg_no_free_balance:{exchange_name}:{base_asset}")
                sell_available = False
        return {"sell_leg_available": sell_available, "balance_restrictions": restrictions}

    def _stats_for(self, strategy_name: str, stats: dict[str, StrategyStats]) -> StrategyStats | None:
        if strategy_name in stats:
            return stats[strategy_name]
        definition = self.registry.get(strategy_name)
        for alias in definition.aliases:
            if alias in stats:
                return stats[alias]
        if definition.execution_alias and definition.execution_alias in stats:
            return stats[definition.execution_alias]
        return None


def _as_dicts(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    return [dict(item) for item in values if isinstance(item, dict)]


def _diagnostic_score_reasons(diagnostics: dict[str, Any]) -> list[str]:
    """Return score-card reasons from scan diagnostics."""
    if not diagnostics:
        return []
    raw_candidate = diagnostics.get("best_candidate")
    candidate: dict[str, Any] = raw_candidate if isinstance(raw_candidate, dict) else diagnostics
    reasons: list[str] = []
    for reason in _string_list(candidate.get("reasons")):
        reasons.append(f"scan_diagnostic:{reason}")
    gap = candidate.get("break_even_gap_usdt")
    if gap is not None:
        reasons.append(f"scan_break_even_gap_usdt:{gap}")
    net_profit = candidate.get("net_profit_usdt")
    if net_profit is not None:
        reasons.append(f"scan_candidate_net_profit_usdt:{net_profit}")
    return reasons


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


class StrategyPortfolioService:
    """Select a bounded set of strategies from current scorecards."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory, registry: StrategyRegistry | None = None) -> None:
        self.settings = settings
        self.exchanges = exchanges
        self.registry = registry or StrategyRegistry()
        self.score_service = StrategyScoreService(settings, exchanges, self.registry)

    def status(self, strategy_name: str = "all", symbol: str = "BTC/USDT") -> StrategyPortfolioStatus:
        """Return portfolio selection status."""
        cards = self.score_service.score(strategy_name=strategy_name, symbol=symbol)
        selected: list[str] = []
        blocked: list[dict[str, Any]] = []
        for card in sorted(cards, key=lambda item: item.score, reverse=True):
            if card.status != "active":
                blocked.append({"strategy_name": card.strategy_name, "reasons": ["strategy_not_active", *card.reasons]})
                continue
            if "strategy_archived_by_evolution" in card.reasons:
                blocked.append({"strategy_name": card.strategy_name, "reasons": card.reasons})
                continue
            if card.score < self.settings.strategy_runtime.portfolio_min_score:
                blocked.append({"strategy_name": card.strategy_name, "reasons": ["score_below_minimum", *card.reasons]})
                continue
            if not card.sell_leg_available:
                blocked.append({"strategy_name": card.strategy_name, "reasons": ["sell_leg_unavailable", *card.reasons]})
                continue
            if len(selected) >= self.settings.strategy_runtime.portfolio_max_concurrent_strategies:
                blocked.append({"strategy_name": card.strategy_name, "reasons": ["portfolio_concurrency_limit"]})
                continue
            selected.append(card.strategy_name)
        return StrategyPortfolioStatus(
            selected_strategies=selected,
            blocked_strategies=blocked,
            score_cards=cards,
            capital_limit_usdt=self.settings.strategy_runtime.max_strategy_capital_usdt,
            max_concurrent_strategies=self.settings.strategy_runtime.portfolio_max_concurrent_strategies,
            min_score=self.settings.strategy_runtime.portfolio_min_score,
        )
