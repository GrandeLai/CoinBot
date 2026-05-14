"""Post-trade review and advisory learning for strategy runtime."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from trading_assistant.config.schema import StrategyRuntimeConfig
from trading_assistant.strategies.journal import StrategyJournal
from trading_assistant.strategies.models import ExecutionMode, LearningSuggestion, StrategyReviewReport, StrategyStats


class StrategyReviewService:
    """Review recorded strategy events and emit conservative suggestions."""

    def __init__(self, config: StrategyRuntimeConfig) -> None:
        self.config = config
        self.journal = StrategyJournal(config.journal_path)

    def review(self, execution_mode: ExecutionMode | None = None) -> StrategyReviewReport:
        """Return review statistics and learning suggestions."""
        events = self.journal.read_events()
        stats: dict[str, StrategyStats] = {}
        for event in events:
            if event.get("event") != "strategy_cycle":
                continue
            if execution_mode is not None and event.get("execution_mode") != execution_mode:
                continue
            name = str(event.get("strategy_name", "unknown"))
            current = stats.get(name, StrategyStats(strategy_name=name))
            net_profit = Decimal(str(event.get("net_profit", "0")))
            decision = str(event.get("decision", "skipped"))
            executed = current.executed + (1 if decision == "executed" else 0)
            blocked = current.blocked + (1 if decision == "blocked" else 0)
            skipped = current.skipped + (1 if decision == "skipped" else 0)
            wins = current.wins + (1 if decision == "executed" and net_profit > 0 else 0)
            losses = current.losses + (1 if decision == "executed" and net_profit <= 0 else 0)
            total = current.total + 1
            win_rate = (Decimal(wins) / Decimal(executed) * Decimal("100")).quantize(Decimal("0.01")) if executed else Decimal("0")
            realized_profit = net_profit if decision == "executed" else Decimal("0")
            stats[name] = replace(
                current,
                total=total,
                executed=executed,
                blocked=blocked,
                skipped=skipped,
                wins=wins,
                losses=losses,
                net_profit=current.net_profit + realized_profit,
                win_rate_pct=win_rate,
            )
        suggestions = self._suggest(stats)
        return StrategyReviewReport(
            total_events=sum(item.total for item in stats.values()),
            strategy_stats=stats,
            suggestions=suggestions,
            journal_path=self.config.journal_path,
        )

    def _suggest(self, stats: dict[str, StrategyStats]) -> list[LearningSuggestion]:
        """Return advisory-only learning suggestions."""
        if not self.config.learning_enabled:
            return []
        suggestions: list[LearningSuggestion] = []
        for item in stats.values():
            if item.executed >= self.config.review_min_samples and item.win_rate_pct < self.config.min_review_win_rate_pct:
                suggestions.append(
                    LearningSuggestion(
                        strategy_name=item.strategy_name,
                        action="increase_min_profit_threshold",
                        reason=f"Win rate {item.win_rate_pct}% is below review threshold {self.config.min_review_win_rate_pct}%.",
                        severity="warning",
                    )
                )
            if item.blocked > item.executed:
                suggestions.append(
                    LearningSuggestion(
                        strategy_name=item.strategy_name,
                        action="reduce_position_cap",
                        reason="Blocked decisions exceed executed decisions; lower capital or tune thresholds before increasing autonomy.",
                        severity="info",
                    )
                )
        return suggestions
