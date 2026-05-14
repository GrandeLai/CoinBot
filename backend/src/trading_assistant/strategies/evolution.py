"""Strategy survival, archive, and revival governance for simulated validation."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from trading_assistant.config.schema import StrategyRuntimeConfig
from trading_assistant.strategies.models import ExecutionMode, StrategyStats
from trading_assistant.strategies.registry import StrategyRegistry
from trading_assistant.utils.serialization import to_jsonable


EvolutionStatus = Literal["champion", "active", "watchlist", "probation", "archived", "revive_candidate"]
EvolutionAction = Literal["promote", "keep", "demote", "archive", "revive_candidate"]


@dataclass(frozen=True)
class StrategyEvolutionDecision:
    """One strategy's current survival decision."""

    strategy_name: str
    status: EvolutionStatus
    action: EvolutionAction
    evidence_mode: ExecutionMode | None
    samples: int
    win_rate_pct: Decimal
    net_profit_usdt: Decimal
    reason_codes: list[str] = field(default_factory=list)
    next_simulation_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe decision."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyParameterCandidate:
    """One simulated parameter mutation proposal for future validation."""

    candidate_id: str
    strategy_name: str
    source_status: EvolutionStatus
    parameter_overrides: dict[str, str]
    rationale: str
    simulation_plan: list[str]
    safety_constraints: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe candidate."""
        return to_jsonable(self)


class StrategyEvolutionService:
    """Maintain a simulated strategy evolution state without changing live gates."""

    def __init__(self, config: StrategyRuntimeConfig, registry: StrategyRegistry | None = None) -> None:
        self.config = config
        self.registry = registry or StrategyRegistry()
        self.state_path = _resolve_repo_path(config.evolution_state_path)
        self.report_path = _resolve_repo_path(config.evolution_report_path)

    def refresh(
        self,
        strategy_name: str = "all",
        execution_mode: ExecutionMode | None = None,
        limit: int = 50,
        market_regime: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Refresh the evolution state from simulated paper/demo journals."""
        if not self.config.evolution_enabled:
            return self._disabled_summary(strategy_name, execution_mode, limit)
        state = self._read_state()
        decisions = self._decisions(strategy_name=strategy_name, execution_mode=execution_mode, limit=limit)
        regime_snapshot = market_regime or _market_regime_from_journal(
            self.config,
            self.registry,
            strategy_name=strategy_name,
            execution_mode=execution_mode,
            limit=limit,
        )
        parameter_candidates = _parameter_candidates(decisions, regime_snapshot)
        data = dict(state)
        rows = data.setdefault("strategies", {})
        if not isinstance(rows, dict):
            rows = {}
            data["strategies"] = rows
        now = _utcnow()
        for decision in decisions:
            rows[decision.strategy_name] = {
                "strategy_name": decision.strategy_name,
                "status": decision.status,
                "action": decision.action,
                "reason_codes": decision.reason_codes,
                "evidence_mode": decision.evidence_mode,
                "samples": decision.samples,
                "win_rate_pct": str(decision.win_rate_pct),
                "net_profit_usdt": str(decision.net_profit_usdt),
                "updated_at": now.isoformat(),
            }
        data["version"] = 1
        data["updated_at"] = now.isoformat()
        data["market_regime"] = to_jsonable(regime_snapshot)
        data["parameter_candidates"] = to_jsonable(parameter_candidates)
        self._write_state(data)
        summary = self._summary(strategy_name, execution_mode, limit, decisions, regime_snapshot, parameter_candidates)
        self._write_report(summary)
        return summary

    def update_after_payload(
        self,
        source: str,
        payload: dict[str, Any],
        strategy_name: str = "all",
        execution_mode: ExecutionMode | None = None,
    ) -> dict[str, Any]:
        """Refresh after a run/validation payload and annotate the source."""
        summary = self.refresh(strategy_name=strategy_name, execution_mode=execution_mode)
        summary["source"] = source
        summary["observed_payload_keys"] = sorted(payload.keys())
        return summary

    def archived_names(self) -> set[str]:
        """Return strategies currently archived by the evolution state."""
        return archived_strategy_names(self.config)

    @staticmethod
    def archived_strategy_names(config: StrategyRuntimeConfig) -> set[str]:
        """Return archived strategy names for a runtime config."""
        return archived_strategy_names(config)

    def _decisions(
        self,
        strategy_name: str,
        execution_mode: ExecutionMode | None,
        limit: int,
    ) -> list[StrategyEvolutionDecision]:
        paper_stats = _stats_from_journal(self.config, execution_mode="paper", limit=limit)
        demo_stats = _stats_from_journal(self.config, execution_mode="demo", limit=limit)
        archived = archived_strategy_names(self.config)
        names = self.registry.names() if strategy_name == "all" else [definition.name for definition in self.registry.expand(strategy_name)]
        decisions = [
            self._decision_for(name, paper_stats, demo_stats, archived, execution_mode)
            for name in names
        ]
        return sorted(decisions, key=lambda item: (item.status == "archived", -item.net_profit_usdt, item.strategy_name))

    def _decision_for(
        self,
        strategy_name: str,
        paper_stats: dict[str, StrategyStats],
        demo_stats: dict[str, StrategyStats],
        archived: set[str],
        execution_mode: ExecutionMode | None,
    ) -> StrategyEvolutionDecision:
        paper = _stats_for(self.registry, strategy_name, paper_stats)
        demo = _stats_for(self.registry, strategy_name, demo_stats)
        mode, stats = _select_evidence(paper, demo, execution_mode)
        samples = stats.executed if stats is not None else 0
        win_rate = stats.win_rate_pct if stats is not None else Decimal("0")
        net_profit = stats.net_profit if stats is not None else Decimal("0")
        passed = (
            samples >= self.config.review_min_samples
            and win_rate >= self.config.min_review_win_rate_pct
            and net_profit >= self.config.evolution_min_net_profit_usdt
        )
        enough_samples = samples >= self.config.review_min_samples
        reasons: list[str] = []
        if samples == 0:
            reasons.append("no_simulated_samples")
        elif not enough_samples:
            reasons.append(f"minimum_samples_not_met:{samples}<{self.config.review_min_samples}")
        if enough_samples and win_rate < self.config.min_review_win_rate_pct:
            reasons.append("win_rate_below_threshold")
        if enough_samples and net_profit < self.config.evolution_min_net_profit_usdt:
            reasons.append("net_profit_below_threshold")

        if strategy_name in archived and passed:
            return StrategyEvolutionDecision(
                strategy_name=strategy_name,
                status="revive_candidate",
                action="revive_candidate",
                evidence_mode=mode,
                samples=samples,
                win_rate_pct=win_rate,
                net_profit_usdt=net_profit,
                reason_codes=["archived_strategy_recovered_in_simulation"],
                next_simulation_steps=_next_steps("revive_candidate"),
            )
        if strategy_name in archived and not passed:
            return StrategyEvolutionDecision(
                strategy_name=strategy_name,
                status="archived",
                action="keep",
                evidence_mode=mode,
                samples=samples,
                win_rate_pct=win_rate,
                net_profit_usdt=net_profit,
                reason_codes=["strategy_archived_by_evolution", *reasons],
                next_simulation_steps=_next_steps("archived"),
            )
        if enough_samples and not passed:
            return StrategyEvolutionDecision(
                strategy_name=strategy_name,
                status="archived",
                action="archive",
                evidence_mode=mode,
                samples=samples,
                win_rate_pct=win_rate,
                net_profit_usdt=net_profit,
                reason_codes=reasons,
                next_simulation_steps=_next_steps("archived"),
            )
        if passed:
            status: EvolutionStatus = "champion" if mode == "demo" else "active"
            return StrategyEvolutionDecision(
                strategy_name=strategy_name,
                status=status,
                action="promote",
                evidence_mode=mode,
                samples=samples,
                win_rate_pct=win_rate,
                net_profit_usdt=net_profit,
                reason_codes=["simulated_profitability_passed"],
                next_simulation_steps=_next_steps(status),
            )
        return StrategyEvolutionDecision(
            strategy_name=strategy_name,
            status="watchlist",
            action="keep",
            evidence_mode=mode,
            samples=samples,
            win_rate_pct=win_rate,
            net_profit_usdt=net_profit,
            reason_codes=reasons,
            next_simulation_steps=_next_steps("watchlist"),
        )

    def _summary(
        self,
        strategy_name: str,
        execution_mode: ExecutionMode | None,
        limit: int,
        decisions: list[StrategyEvolutionDecision],
        market_regime: dict[str, Any],
        parameter_candidates: list[StrategyParameterCandidate],
    ) -> dict[str, Any]:
        rendered = [decision.to_dict() for decision in decisions]
        return {
            "enabled": self.config.evolution_enabled,
            "strategy_name": strategy_name,
            "execution_mode": execution_mode,
            "limit": limit,
            "state_path": str(self.state_path),
            "report_path": str(self.report_path),
            "orders_sent": False,
            "live_orders_sent": False,
            "simulation_only": True,
            "policy": {
                "min_samples": self.config.review_min_samples,
                "min_win_rate_pct": self.config.min_review_win_rate_pct,
                "min_net_profit_usdt": self.config.evolution_min_net_profit_usdt,
                "archive_is_soft": True,
                "parameter_candidates_are_advisory": True,
            },
            "market_regime": market_regime,
            "decisions": rendered,
            "parameter_candidates": [candidate.to_dict() for candidate in parameter_candidates],
            "promoted_strategies": [item.strategy_name for item in decisions if item.action == "promote"],
            "archived_strategies": [item.strategy_name for item in decisions if item.status == "archived"],
            "revive_candidates": [item.strategy_name for item in decisions if item.status == "revive_candidate"],
            "ranked_strategies": [item.strategy_name for item in sorted(decisions, key=lambda item: item.net_profit_usdt, reverse=True)],
            "updated_at": _utcnow(),
        }

    def _disabled_summary(self, strategy_name: str, execution_mode: ExecutionMode | None, limit: int) -> dict[str, Any]:
        return {
            "enabled": False,
            "strategy_name": strategy_name,
            "execution_mode": execution_mode,
            "limit": limit,
            "state_path": str(self.state_path),
            "report_path": str(self.report_path),
            "orders_sent": False,
            "live_orders_sent": False,
            "simulation_only": True,
            "market_regime": {"tag": "unknown", "source": "disabled", "sample_count": 0, "strategy_tags": {}},
            "decisions": [],
            "parameter_candidates": [],
            "archived_strategies": [],
            "revive_candidates": [],
            "updated_at": _utcnow(),
        }

    def _read_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"version": 1, "strategies": {}}
        payload = json.loads(self.state_path.read_text(encoding="utf-8") or "{}")
        if not isinstance(payload, dict):
            return {"version": 1, "strategies": {}}
        payload.setdefault("version", 1)
        payload.setdefault("strategies", {})
        return payload

    def _write_state(self, data: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(to_jsonable(data), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _write_report(self, summary: dict[str, Any]) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        decisions = [dict(item) for item in summary["decisions"]]
        archived = [item for item in decisions if item["status"] == "archived"]
        revive = [item for item in decisions if item["status"] == "revive_candidate"]
        promoted = [item for item in decisions if item["action"] == "promote"]
        candidates = [dict(item) for item in summary["parameter_candidates"]]
        regime = dict(summary["market_regime"])
        lines = [
            "# Strategy Evolution",
            "",
            f"Updated at: {summary['updated_at']}",
            "",
            "This report is simulation-only. It never enables live trading and never sends live orders.",
            "",
            "## Market Regime",
            "",
            f"- Tag: {regime.get('tag', 'unknown')}",
            f"- Source: {regime.get('source', 'unknown')}",
            f"- Sample Count: {regime.get('sample_count', 0)}",
            "",
            "## Promoted Strategies",
            "",
            *_render_rows(promoted),
            "",
            "## Archived Strategies",
            "",
            *_render_rows(archived),
            "",
            "## Revival Candidates",
            "",
            *_render_rows(revive),
            "",
            "## Parameter Candidates",
            "",
            *_render_candidate_rows(candidates),
            "",
            "## All Decisions",
            "",
            *_render_rows(decisions),
            "",
        ]
        self.report_path.write_text("\n".join(lines), encoding="utf-8")


def archived_strategy_names(config: StrategyRuntimeConfig) -> set[str]:
    """Return archived strategy names from the persisted evolution state."""
    if not config.evolution_enabled:
        return set()
    path = _resolve_repo_path(config.evolution_state_path)
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8") or "{}")
    rows = payload.get("strategies", {}) if isinstance(payload, dict) else {}
    if not isinstance(rows, dict):
        return set()
    return {
        str(name)
        for name, row in rows.items()
        if isinstance(row, dict) and row.get("status") == "archived"
    }


def revival_candidate_names(config: StrategyRuntimeConfig, strategy_name: str = "all", registry: StrategyRegistry | None = None) -> list[str]:
    """Return persisted revival-candidate strategy names, filtered by request."""
    if not config.evolution_enabled:
        return []
    path = _resolve_repo_path(config.evolution_state_path)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8") or "{}")
    rows = payload.get("strategies", {}) if isinstance(payload, dict) else {}
    if not isinstance(rows, dict):
        return []
    strategy_registry = registry or StrategyRegistry()
    requested = set(strategy_registry.names() if strategy_name == "all" else [definition.name for definition in strategy_registry.expand(strategy_name)])
    return [
        str(name)
        for name, row in rows.items()
        if str(name) in requested and isinstance(row, dict) and row.get("status") == "revive_candidate"
    ]


def _stats_from_journal(
    config: StrategyRuntimeConfig,
    execution_mode: ExecutionMode,
    limit: int,
) -> dict[str, StrategyStats]:
    from dataclasses import replace

    from trading_assistant.strategies.journal import StrategyJournal

    events = [
        event
        for event in StrategyJournal(config.journal_path).read_events()
        if event.get("event") == "strategy_cycle" and event.get("execution_mode") == execution_mode
    ][-max(limit, 1) :]
    stats: dict[str, StrategyStats] = {}
    for event in events:
        name = str(event.get("strategy_name", "unknown"))
        current = stats.get(name, StrategyStats(strategy_name=name))
        decision = str(event.get("decision", "skipped"))
        net_profit = Decimal(str(event.get("net_profit", "0")))
        executed = current.executed + (1 if decision == "executed" else 0)
        wins = current.wins + (1 if decision == "executed" and net_profit > 0 else 0)
        losses = current.losses + (1 if decision == "executed" and net_profit <= 0 else 0)
        win_rate = (Decimal(wins) / Decimal(executed) * Decimal("100")).quantize(Decimal("0.01")) if executed else Decimal("0")
        stats[name] = replace(
            current,
            total=current.total + 1,
            executed=executed,
            blocked=current.blocked + (1 if decision == "blocked" else 0),
            skipped=current.skipped + (1 if decision == "skipped" else 0),
            wins=wins,
            losses=losses,
            net_profit=current.net_profit + (net_profit if decision == "executed" else Decimal("0")),
            win_rate_pct=win_rate,
        )
    return stats


def _recent_strategy_events(
    config: StrategyRuntimeConfig,
    execution_mode: ExecutionMode | None,
    limit: int,
) -> list[dict[str, Any]]:
    from trading_assistant.strategies.journal import StrategyJournal

    events = [
        event
        for event in StrategyJournal(config.journal_path).read_events()
        if event.get("event") == "strategy_cycle"
        and (execution_mode is None or event.get("execution_mode") == execution_mode)
    ]
    return events[-max(limit, 1) :]


def _market_regime_from_journal(
    config: StrategyRuntimeConfig,
    registry: StrategyRegistry,
    strategy_name: str,
    execution_mode: ExecutionMode | None,
    limit: int,
) -> dict[str, Any]:
    requested = set(registry.names() if strategy_name == "all" else [definition.name for definition in registry.expand(strategy_name)])
    events = [
        event
        for event in _recent_strategy_events(config, execution_mode=execution_mode, limit=limit)
        if str(event.get("strategy_name", "")) in requested
    ]
    tags: list[str] = []
    strategy_tags: dict[str, str] = {}
    volatility_tags: list[str] = []
    for event in events:
        regime = event.get("market_regime")
        tag = "unknown"
        volatility = "unknown"
        if isinstance(regime, dict):
            tag = str(regime.get("tag") or regime.get("regime") or "unknown")
            volatility = str(regime.get("volatility") or "unknown")
        elif isinstance(regime, str) and regime:
            tag = regime
        if tag == "unknown":
            tag = _infer_regime_from_event(event)
        tags.append(tag)
        volatility_tags.append(volatility)
        strategy_tags[str(event.get("strategy_name", "unknown"))] = tag
    tag_counts = Counter(tags)
    dominant = tag_counts.most_common(1)[0][0] if tag_counts else "unknown"
    volatility_counts = Counter(item for item in volatility_tags if item != "unknown")
    return {
        "tag": dominant,
        "source": "journal" if events else "none",
        "sample_count": len(events),
        "tag_counts": dict(tag_counts),
        "volatility": volatility_counts.most_common(1)[0][0] if volatility_counts else "unknown",
        "strategy_tags": strategy_tags,
    }


def _infer_regime_from_event(event: dict[str, Any]) -> str:
    strategy = str(event.get("strategy_name", ""))
    decision = str(event.get("decision", ""))
    net_profit = Decimal(str(event.get("net_profit", "0")))
    if strategy in {"trend-breakout", "momentum-rotation", "volatility-squeeze-breakout"} and decision == "executed" and net_profit > 0:
        return "trend_up"
    if strategy == "mean-reversion-spot" and decision == "executed" and net_profit > 0:
        return "range"
    return "unknown"


def _parameter_candidates(
    decisions: list[StrategyEvolutionDecision],
    market_regime: dict[str, Any],
) -> list[StrategyParameterCandidate]:
    candidates: list[StrategyParameterCandidate] = []
    for decision in decisions:
        if decision.action == "promote":
            continue
        overrides = _candidate_overrides(decision.strategy_name)
        candidate_id = f"{decision.strategy_name}-{decision.status}-candidate-v1"
        candidates.append(
            StrategyParameterCandidate(
                candidate_id=candidate_id,
                strategy_name=decision.strategy_name,
                source_status=decision.status,
                parameter_overrides=overrides,
                rationale=_candidate_rationale(decision, market_regime),
                simulation_plan=[
                    "Apply overrides only in an isolated simulated config copy.",
                    "Run local paper validation before any OKX demo revival window.",
                    "Compare validation-report expected PnL, cash-flow PnL, drawdown, receipts, and residual inventory.",
                ],
                safety_constraints=[
                    "Do not edit live config automatically.",
                    "Do not lower live or demo safety gates to make the candidate pass.",
                    "Do not send OKX demo orders unless local validation passes.",
                ],
            )
        )
    return candidates


def _candidate_overrides(strategy_name: str) -> dict[str, str]:
    if strategy_name == "spot-perp-carry":
        return {
            "arbitrage.spot_perp_min_basis_pct": "increase_by_0.02",
            "arbitrage.basis_holding_hours": "reduce_by_25_percent",
        }
    if strategy_name == "funding-carry-hedged":
        return {
            "arbitrage.funding_min_annualized_pct": "increase_by_5",
            "arbitrage.funding_max_basis_hedge_cost_pct": "reduce_by_20_percent",
        }
    if strategy_name == "futures-perp-basis":
        return {
            "arbitrage.futures_basis_min_basis_pct": "increase_by_0.02",
            "arbitrage.futures_basis_min_days_to_expiry": "increase_by_1",
        }
    if strategy_name in {"triangular-multi-route", "triangular"}:
        return {
            "arbitrage.min_route_depth_usdt": "increase_by_20_percent",
            "arbitrage.slippage_pct": "stress_test_plus_0.00005",
        }
    if strategy_name in {"trend-breakout", "mean-reversion-spot", "volatility-squeeze-breakout", "momentum-rotation", "orderbook-imbalance-scalp"}:
        return {
            "directional.min_profit_factor": "increase_by_0.05",
            "directional.max_backtest_drawdown_pct": "reduce_by_1",
            "directional.demo_max_order_value_usdt": "keep_current_or_lower",
        }
    return {
        "arbitrage.min_net_profit_pct": "increase_by_0.05",
        "arbitrage.trade_size_usdt": "reduce_by_50_percent_for_probe",
    }


def _candidate_rationale(decision: StrategyEvolutionDecision, market_regime: dict[str, Any]) -> str:
    regime = str(market_regime.get("tag", "unknown"))
    reasons = ", ".join(decision.reason_codes) or "insufficient evidence"
    return (
        f"Generated from {decision.status} state under market_regime={regime}; "
        f"recent samples={decision.samples}, win_rate={decision.win_rate_pct}, "
        f"net_profit={decision.net_profit_usdt}, reasons={reasons}."
    )


def _stats_for(registry: StrategyRegistry, strategy_name: str, stats: dict[str, StrategyStats]) -> StrategyStats | None:
    if strategy_name in stats:
        return stats[strategy_name]
    definition = registry.get(strategy_name)
    for alias in definition.aliases:
        if alias in stats:
            return stats[alias]
    if definition.execution_alias and definition.execution_alias in stats:
        return stats[definition.execution_alias]
    return None


def _select_evidence(
    paper: StrategyStats | None,
    demo: StrategyStats | None,
    execution_mode: ExecutionMode | None,
) -> tuple[ExecutionMode | None, StrategyStats | None]:
    if execution_mode == "paper":
        return "paper", paper
    if execution_mode == "demo":
        return "demo", demo
    if demo is not None and demo.executed > 0:
        return "demo", demo
    if paper is not None and paper.executed > 0:
        return "paper", paper
    return None, paper or demo


def _next_steps(status: str) -> list[str]:
    if status == "archived":
        return [
            "Keep out of portfolio selection.",
            "Run small paper revival probes before any OKX demo attempt.",
            "Restore only after simulated samples meet win-rate and net-profit thresholds.",
        ]
    if status == "revive_candidate":
        return [
            "Run a bounded paper validation window.",
            "If paper remains profitable, run an OKX demo window at existing small size.",
            "Do not increase size until validation-report quality remains clean.",
        ]
    if status in {"champion", "active"}:
        return [
            "Keep collecting same-size simulated samples.",
            "Compare expected preflight PnL with actual cash-flow PnL before size changes.",
        ]
    return [
        "Collect more paper samples.",
        "Do not force OKX demo orders until local validation passes.",
    ]


def _render_rows(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["- None"]
    return [
        "- {strategy}: status={status}, action={action}, samples={samples}, win_rate={win_rate_pct}, net_profit={net_profit_usdt}, reasons={reasons}".format(
            strategy=row["strategy_name"],
            status=row["status"],
            action=row["action"],
            samples=row["samples"],
            win_rate_pct=row["win_rate_pct"],
            net_profit_usdt=row["net_profit_usdt"],
            reasons=",".join(row["reason_codes"]),
        )
        for row in rows
    ]


def _render_candidate_rows(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["- None"]
    rendered = []
    for row in rows:
        overrides = ", ".join(f"{key}={value}" for key, value in dict(row["parameter_overrides"]).items())
        rendered.append(
            "- {candidate_id}: strategy={strategy}, status={status}, overrides={overrides}".format(
                candidate_id=row["candidate_id"],
                strategy=row["strategy_name"],
                status=row["source_status"],
                overrides=overrides,
            )
        )
    return rendered


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _resolve_repo_path(path: str) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        return raw
    return Path(__file__).resolve().parents[4] / raw
