"""Rolling validation evidence reports for strategy runtime journals."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any

from trading_assistant.config.schema import StrategyRuntimeConfig
from trading_assistant.strategies.journal import StrategyJournal
from trading_assistant.strategies.models import ExecutionMode
from trading_assistant.strategies.registry import StrategyRegistry
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class StrategyValidationAggregate:
    """Aggregated validation evidence for one strategy or a report total."""

    strategy_name: str
    total_events: int = 0
    executed: int = 0
    skipped: int = 0
    blocked: int = 0
    wins: int = 0
    losses: int = 0
    realized_net_profit_usdt: Decimal = Decimal("0")
    skipped_preflight_net_pnl_usdt: Decimal = Decimal("0")
    expected_preflight_net_pnl_usdt: Decimal = Decimal("0")
    actual_cash_flow_net_pnl_usdt: Decimal = Decimal("0")
    account_equity_delta_usdt: Decimal = Decimal("0")
    account_reconciliation_gap_usdt: Decimal = Decimal("0")
    expected_actual_gap_usdt: Decimal = Decimal("0")
    max_abs_account_reconciliation_gap_usdt: Decimal = Decimal("0")
    max_abs_expected_actual_gap_usdt: Decimal = Decimal("0")
    account_equity_sample_count: int = 0
    expected_actual_sample_count: int = 0
    executed_preflight_missing: int = 0
    positive_cash_flow_negative_equity_delta: int = 0
    max_drawdown_usdt: Decimal = Decimal("0")
    receipt_incomplete: int = 0
    pnl_out_of_tolerance: int = 0
    residual_inventory_out_of_tolerance: int = 0
    max_residual_inventory_usdt: Decimal = Decimal("0")
    reason_counts: dict[str, int] = field(default_factory=dict)

    @property
    def win_rate_pct(self) -> Decimal:
        """Return executed win rate in percent."""
        if self.executed == 0:
            return Decimal("0")
        return (Decimal(self.wins) / Decimal(self.executed) * Decimal("100")).quantize(Decimal("0.01"))

    @property
    def execution_quality_passed(self) -> bool:
        """Return whether receipt, PnL, and residual checks have no failures."""
        return self.receipt_incomplete == 0 and self.pnl_out_of_tolerance == 0 and self.residual_inventory_out_of_tolerance == 0

    @property
    def scanned_quality_failures(self) -> bool:
        """Return whether the scanned window contains validation quality failures."""
        return not self.execution_quality_passed

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe aggregate."""
        return to_jsonable(
            {
                **self.__dict__,
                "win_rate_pct": self.win_rate_pct,
                "execution_quality_passed": self.execution_quality_passed,
            }
        )


@dataclass(frozen=True)
class StrategyRollingValidationReport:
    """Rolling validation evidence report over the most recent journal events."""

    journal_path: str
    execution_mode: ExecutionMode | None
    strategy_name: str
    requested_limit: int
    scanned_events: int
    total: StrategyValidationAggregate
    by_strategy: dict[str, StrategyValidationAggregate]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report."""
        return to_jsonable(
            {
                "journal_path": self.journal_path,
                "execution_mode": self.execution_mode,
                "strategy_name": self.strategy_name,
                "requested_limit": self.requested_limit,
                "scanned_events": self.scanned_events,
                "total": self.total.to_dict(),
                "by_strategy": {name: aggregate.to_dict() for name, aggregate in self.by_strategy.items()},
                "recommendations": self.recommendations,
            }
        )


class StrategyValidationReportService:
    """Build read-only rolling validation reports from the strategy journal."""

    def __init__(self, config: StrategyRuntimeConfig) -> None:
        self.config = config
        self.journal = StrategyJournal(config.journal_path)

    def report(
        self,
        execution_mode: ExecutionMode | None = None,
        strategy_name: str = "all",
        limit: int = 50,
    ) -> StrategyRollingValidationReport:
        """Return a rolling report over the most recent matching strategy-cycle events."""
        requested_limit = max(limit, 1)
        strategy_names = _expanded_strategy_names(strategy_name)
        events = [
            event
            for event in self.journal.read_events()
            if event.get("event") == "strategy_cycle"
            and (execution_mode is None or event.get("execution_mode") == execution_mode)
            and (strategy_name == "all" or str(event.get("strategy_name")) in strategy_names)
        ]
        window = events[-requested_limit:]
        total = StrategyValidationAggregate(strategy_name="all")
        by_strategy: dict[str, StrategyValidationAggregate] = {}
        running_pnl: dict[str, Decimal] = {"all": Decimal("0")}
        peak_pnl: dict[str, Decimal] = {"all": Decimal("0")}
        for event in window:
            name = str(event.get("strategy_name", "unknown"))
            aggregate = by_strategy.get(name, StrategyValidationAggregate(strategy_name=name))
            aggregate, running_pnl[name], peak_pnl[name] = self._apply_event(
                aggregate,
                event,
                running_pnl.get(name, Decimal("0")),
                peak_pnl.get(name, Decimal("0")),
            )
            total, running_pnl["all"], peak_pnl["all"] = self._apply_event(
                total,
                event,
                running_pnl["all"],
                peak_pnl["all"],
            )
            by_strategy[name] = aggregate
        return StrategyRollingValidationReport(
            journal_path=self.config.journal_path,
            execution_mode=execution_mode,
            strategy_name=strategy_name,
            requested_limit=requested_limit,
            scanned_events=len(window),
            total=total,
            by_strategy=by_strategy,
            recommendations=_recommend(total, by_strategy),
        )

    def _apply_event(
        self,
        aggregate: StrategyValidationAggregate,
        event: dict[str, Any],
        running_pnl: Decimal,
        peak_pnl: Decimal,
    ) -> tuple[StrategyValidationAggregate, Decimal, Decimal]:
        """Add one journal event into an aggregate."""
        decision = str(event.get("decision", "skipped"))
        net_profit = Decimal(str(event.get("net_profit", "0")))
        execution = event.get("execution")
        execution_payload: dict[str, Any] = execution if isinstance(execution, dict) else {}
        pnl_validation = execution_payload.get("pnl_validation")
        pnl_payload: dict[str, Any] = pnl_validation if isinstance(pnl_validation, dict) else {}
        lifecycle_payload = execution_payload.get("position_lifecycle")
        position_lifecycle: dict[str, Any] = lifecycle_payload if isinstance(lifecycle_payload, dict) else {}
        managed_open_directional = (
            execution_payload.get("strategy_family") == "directional"
            and position_lifecycle.get("state") == "open"
            and pnl_payload.get("method") == "managed_directional_open_position"
        )
        receipts = pnl_payload.get("exchange_receipts")
        receipt_payload: dict[str, Any] = receipts if isinstance(receipts, dict) else {}
        raw_reasons = event.get("risk_reasons", [])
        event_reasons = [str(reason) for reason in raw_reasons] if isinstance(raw_reasons, list) else []
        reason_counts = dict(aggregate.reason_counts)
        for key in event_reasons:
            reason_counts[key] = reason_counts.get(key, 0) + 1
        realized_net_profit = aggregate.realized_net_profit_usdt
        skipped_preflight_net_pnl = aggregate.skipped_preflight_net_pnl_usdt
        expected_preflight_net_pnl = aggregate.expected_preflight_net_pnl_usdt
        actual_cash_flow_net_pnl = aggregate.actual_cash_flow_net_pnl_usdt
        account_equity_delta = aggregate.account_equity_delta_usdt
        account_reconciliation_gap = aggregate.account_reconciliation_gap_usdt
        expected_actual_gap = aggregate.expected_actual_gap_usdt
        max_abs_account_gap = aggregate.max_abs_account_reconciliation_gap_usdt
        max_abs_expected_gap = aggregate.max_abs_expected_actual_gap_usdt
        account_equity_samples = aggregate.account_equity_sample_count
        expected_actual_samples = aggregate.expected_actual_sample_count
        executed_preflight_missing = aggregate.executed_preflight_missing
        positive_cash_flow_negative_equity_delta = aggregate.positive_cash_flow_negative_equity_delta
        wins = aggregate.wins
        losses = aggregate.losses
        if decision == "executed":
            realized_net_profit += net_profit
            cash_flow = _decimal_or_default(pnl_payload, "cash_flow_net_pnl_usdt", net_profit)
            actual_cash_flow_net_pnl += cash_flow
            equity_delta = _optional_decimal(pnl_payload, "equity_delta_usdt")
            if equity_delta is not None:
                account_equity_samples += 1
                account_equity_delta += equity_delta
                account_gap = equity_delta - cash_flow
                account_reconciliation_gap += account_gap
                max_abs_account_gap = max(max_abs_account_gap, abs(account_gap))
                if cash_flow > 0 and equity_delta < 0:
                    positive_cash_flow_negative_equity_delta += 1
            preflight_payload = execution_payload.get("preflight")
            preflight: dict[str, Any] = preflight_payload if isinstance(preflight_payload, dict) else {}
            expected = _optional_decimal(preflight, "net_pnl_usdt")
            if expected is None:
                executed_preflight_missing += 1
            else:
                expected_actual_samples += 1
                expected_preflight_net_pnl += expected
                expected_gap = cash_flow - expected
                expected_actual_gap += expected_gap
                max_abs_expected_gap = max(max_abs_expected_gap, abs(expected_gap))
            running_pnl += net_profit
            peak_pnl = max(peak_pnl, running_pnl)
            if not managed_open_directional:
                wins += 1 if net_profit > 0 else 0
                losses += 1 if net_profit <= 0 else 0
        elif "demo_preflight_not_profitable" in event_reasons:
            skipped_preflight_net_pnl += net_profit
        residual_inventory = Decimal(str(pnl_payload.get("residual_inventory_usdt", "0")))
        max_drawdown = max(aggregate.max_drawdown_usdt, peak_pnl - running_pnl)
        return (
            replace(
                aggregate,
                total_events=aggregate.total_events + 1,
                executed=aggregate.executed + (1 if decision == "executed" else 0),
                skipped=aggregate.skipped + (1 if decision == "skipped" else 0),
                blocked=aggregate.blocked + (1 if decision == "blocked" else 0),
                wins=wins,
                losses=losses,
                realized_net_profit_usdt=realized_net_profit,
                skipped_preflight_net_pnl_usdt=skipped_preflight_net_pnl,
                expected_preflight_net_pnl_usdt=expected_preflight_net_pnl,
                actual_cash_flow_net_pnl_usdt=actual_cash_flow_net_pnl,
                account_equity_delta_usdt=account_equity_delta,
                account_reconciliation_gap_usdt=account_reconciliation_gap,
                expected_actual_gap_usdt=expected_actual_gap,
                max_abs_account_reconciliation_gap_usdt=max_abs_account_gap,
                max_abs_expected_actual_gap_usdt=max_abs_expected_gap,
                account_equity_sample_count=account_equity_samples,
                expected_actual_sample_count=expected_actual_samples,
                executed_preflight_missing=executed_preflight_missing,
                positive_cash_flow_negative_equity_delta=positive_cash_flow_negative_equity_delta,
                max_drawdown_usdt=max_drawdown,
                receipt_incomplete=aggregate.receipt_incomplete + (1 if receipt_payload.get("complete") is False else 0),
                pnl_out_of_tolerance=aggregate.pnl_out_of_tolerance + (1 if pnl_payload.get("within_tolerance") is False else 0),
                residual_inventory_out_of_tolerance=aggregate.residual_inventory_out_of_tolerance
                + (1 if pnl_payload.get("residual_inventory_within_tolerance") is False else 0),
                max_residual_inventory_usdt=max(aggregate.max_residual_inventory_usdt, residual_inventory),
                reason_counts=reason_counts,
            ),
            running_pnl,
            peak_pnl,
        )


def _recommend(total: StrategyValidationAggregate, by_strategy: dict[str, StrategyValidationAggregate]) -> list[str]:
    """Return conservative recommendations from aggregate evidence."""
    recommendations: list[str] = []
    if total.scanned_quality_failures:
        recommendations.append("Resolve receipt, PnL, or residual-inventory validation failures before increasing demo size.")
    if total.positive_cash_flow_negative_equity_delta:
        recommendations.append("Account equity moved negative while strategy cash-flow PnL was positive; reconcile balances, positions, and external cash flows before trusting PnL.")
    if total.executed_preflight_missing:
        recommendations.append("Some executed events are missing approved preflight estimates; exclude them from expected-vs-actual promotion evidence.")
    if total.executed == 0:
        recommendations.append("No executed events in the selected window; improve scan/preflight conditions before demo execution.")
    if total.max_drawdown_usdt > Decimal("0"):
        recommendations.append("Review drawdown and loss events before any position-size increase.")
    for name, aggregate in sorted(by_strategy.items()):
        if aggregate.skipped > aggregate.executed and aggregate.reason_counts.get("demo_preflight_not_profitable", 0) > 0:
            recommendations.append(f"{name}: keep blocked from demo execution until preflight net PnL turns positive.")
    if not recommendations:
        recommendations.append("Keep collecting same-size samples across more market conditions before any size increase.")
    return recommendations


def _optional_decimal(payload: dict[str, Any], key: str) -> Decimal | None:
    """Return Decimal value when a payload field is present."""
    if key not in payload:
        return None
    value = payload[key]
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _decimal_or_default(payload: dict[str, Any], key: str, default: Decimal) -> Decimal:
    """Return Decimal value from payload or a default."""
    value = _optional_decimal(payload, key)
    return default if value is None else value


def _expanded_strategy_names(strategy_name: str) -> set[str]:
    """Return concrete names for aggregate strategy filters."""
    if strategy_name == "all":
        return set()
    try:
        return {definition.name for definition in StrategyRegistry().expand(strategy_name)}
    except Exception:
        return {strategy_name}
