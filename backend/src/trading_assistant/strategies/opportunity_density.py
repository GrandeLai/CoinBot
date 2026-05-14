"""Read-only opportunity-density reporting for strategy journals."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from trading_assistant.config.schema import StrategyRuntimeConfig
from trading_assistant.strategies.journal import StrategyJournal
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class OpportunityDensityBucket:
    """Aggregated opportunity-density metrics for one strategy."""

    strategy_name: str
    scan_count: int = 0
    opportunity_count: int = 0
    demo_preflight_candidate_count: int = 0
    executed_count: int = 0
    avg_expected_edge_usdt: Decimal = Decimal("0")
    avg_realized_pnl_usdt: Decimal = Decimal("0")
    expected_vs_actual_gap_usdt: Decimal = Decimal("0")
    skipped_by_reason: dict[str, int] = field(default_factory=dict)
    break_even_gap_usdt: Decimal = Decimal("0")

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe bucket."""
        return to_jsonable(self)


@dataclass(frozen=True)
class OpportunityDensityReport:
    """Opportunity-density report payload."""

    journal_path: str
    window: str
    window_started_at: datetime
    scan_count: int
    opportunity_count: int
    demo_preflight_candidate_count: int
    preflight_pass_rate_pct: Decimal
    executed_count: int
    skipped_by_reason: dict[str, int]
    avg_expected_edge_usdt: Decimal
    avg_realized_pnl_usdt: Decimal
    expected_vs_actual_gap_usdt: Decimal
    account_equity_delta_usdt: Decimal
    by_strategy: dict[str, OpportunityDensityBucket]
    route_distribution: dict[str, int]
    symbol_distribution: dict[str, int]
    candidate_observation_pool: list[dict[str, Any]]
    demo_size_stage_readiness: dict[str, Any]
    read_only: bool = True
    orders_sent: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report."""
        return to_jsonable(
            {
                "journal_path": self.journal_path,
                "window": self.window,
                "window_started_at": self.window_started_at,
                "scan_count": self.scan_count,
                "opportunity_count": self.opportunity_count,
                "demo_preflight_candidate_count": self.demo_preflight_candidate_count,
                "preflight_pass_rate_pct": self.preflight_pass_rate_pct,
                "executed_count": self.executed_count,
                "skipped_by_reason": self.skipped_by_reason,
                "avg_expected_edge_usdt": self.avg_expected_edge_usdt,
                "avg_realized_pnl_usdt": self.avg_realized_pnl_usdt,
                "expected_vs_actual_gap_usdt": self.expected_vs_actual_gap_usdt,
                "account_equity_delta_usdt": self.account_equity_delta_usdt,
                "by_strategy": {name: bucket.to_dict() for name, bucket in self.by_strategy.items()},
                "route_distribution": self.route_distribution,
                "symbol_distribution": self.symbol_distribution,
                "candidate_observation_pool": self.candidate_observation_pool,
                "demo_size_stage_readiness": self.demo_size_stage_readiness,
                "read_only": self.read_only,
                "orders_sent": self.orders_sent,
            }
        )


class OpportunityDensityService:
    """Aggregate scan, preflight, and realized-PnL evidence without trading."""

    def __init__(self, config: StrategyRuntimeConfig) -> None:
        self.config = config
        self.journal = StrategyJournal(config.journal_path)

    def report(self, window: str = "24h") -> OpportunityDensityReport:
        """Return a read-only opportunity-density report."""
        started_at = datetime.now(tz=UTC) - _parse_window(window)
        events = [
            event
            for event in self.journal.read_events()
            if event.get("event") == "strategy_cycle" and _event_time(event) >= started_at
        ]
        by_strategy_raw: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in events:
            by_strategy_raw[str(event.get("strategy_name", "unknown"))].append(event)
        buckets = {name: _bucket(name, strategy_events) for name, strategy_events in sorted(by_strategy_raw.items())}
        expected_values = _expected_values(events)
        realized_values = [_decimal(event.get("net_profit")) for event in events if event.get("decision") == "executed"]
        skipped_reasons = Counter(reason for event in events for reason in _event_reasons(event))
        candidate_count = sum(1 for event in events if _is_demo_preflight_candidate(event))
        scan_count = len(events)
        expected_sum = sum(expected_values, Decimal("0"))
        realized_sum = sum(realized_values, Decimal("0"))
        return OpportunityDensityReport(
            journal_path=self.config.journal_path,
            window=window,
            window_started_at=started_at,
            scan_count=scan_count,
            opportunity_count=sum(int(event.get("opportunities_found", 0)) for event in events),
            demo_preflight_candidate_count=candidate_count,
            preflight_pass_rate_pct=(Decimal(candidate_count) / Decimal(scan_count) * Decimal("100")).quantize(Decimal("0.01"))
            if scan_count
            else Decimal("0"),
            executed_count=len(realized_values),
            skipped_by_reason=dict(sorted(skipped_reasons.items())),
            avg_expected_edge_usdt=_average(expected_values),
            avg_realized_pnl_usdt=_average(realized_values),
            expected_vs_actual_gap_usdt=realized_sum - expected_sum,
            account_equity_delta_usdt=sum((_equity_delta(event) for event in events), Decimal("0")),
            by_strategy=buckets,
            route_distribution=_route_distribution(events),
            symbol_distribution=_symbol_distribution(events),
            candidate_observation_pool=_candidate_observation_pool(events),
            demo_size_stage_readiness=_demo_size_stage_readiness(events),
        )


def _bucket(name: str, events: list[dict[str, Any]]) -> OpportunityDensityBucket:
    expected_values = _expected_values(events)
    realized_values = [_decimal(event.get("net_profit")) for event in events if event.get("decision") == "executed"]
    expected_sum = sum(expected_values, Decimal("0"))
    realized_sum = sum(realized_values, Decimal("0"))
    skipped_reasons = Counter(reason for event in events for reason in _event_reasons(event))
    return OpportunityDensityBucket(
        strategy_name=name,
        scan_count=len(events),
        opportunity_count=sum(int(event.get("opportunities_found", 0)) for event in events),
        demo_preflight_candidate_count=sum(1 for event in events if _is_demo_preflight_candidate(event)),
        executed_count=len(realized_values),
        avg_expected_edge_usdt=_average(expected_values),
        avg_realized_pnl_usdt=_average(realized_values),
        expected_vs_actual_gap_usdt=realized_sum - expected_sum,
        skipped_by_reason=dict(sorted(skipped_reasons.items())),
        break_even_gap_usdt=sum((_break_even_gap(event) for event in events), Decimal("0")),
    )


def _expected_values(events: list[dict[str, Any]]) -> list[Decimal]:
    values: list[Decimal] = []
    for event in events:
        value = _expected_edge(event)
        if value is not None:
            values.append(value)
    return values


def _parse_window(window: str) -> timedelta:
    normalized = window.strip().lower()
    if normalized.endswith("h"):
        return timedelta(hours=max(int(normalized[:-1]), 1))
    if normalized.endswith("d"):
        return timedelta(days=max(int(normalized[:-1]), 1))
    return timedelta(hours=max(int(normalized), 1))


def _event_time(event: dict[str, Any]) -> datetime:
    raw = event.get("created_at")
    if not raw:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _event_reasons(event: dict[str, Any]) -> list[str]:
    raw = event.get("risk_reasons", [])
    return [str(reason) for reason in raw] if isinstance(raw, list) else [str(raw)]


def _execution(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("execution")
    return raw if isinstance(raw, dict) else {}


def _preflight(event: dict[str, Any]) -> dict[str, Any]:
    raw = _execution(event).get("preflight")
    return raw if isinstance(raw, dict) else {}


def _pnl_validation(event: dict[str, Any]) -> dict[str, Any]:
    raw = _execution(event).get("pnl_validation")
    return raw if isinstance(raw, dict) else {}


def _expected_edge(event: dict[str, Any]) -> Decimal | None:
    preflight = _preflight(event)
    if "net_pnl_usdt" in preflight:
        return _decimal(preflight.get("net_pnl_usdt"))
    if event.get("execution_mode") == "paper":
        return _decimal(event.get("net_profit"))
    return None


def _is_demo_preflight_candidate(event: dict[str, Any]) -> bool:
    if event.get("execution_mode") != "demo":
        return False
    preflight = _preflight(event)
    return event.get("decision") == "executed" or bool(preflight.get("approved", False))


def _equity_delta(event: dict[str, Any]) -> Decimal:
    return _decimal(_pnl_validation(event).get("equity_delta_usdt"))


def _break_even_gap(event: dict[str, Any]) -> Decimal:
    if event.get("decision") != "skipped":
        return Decimal("0")
    if "demo_preflight_not_profitable" not in _event_reasons(event):
        return Decimal("0")
    return max(abs(_decimal(event.get("net_profit"))), Decimal("0"))


def _candidate_observation_pool(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        reasons = _event_reasons(event)
        if event.get("decision") != "skipped" or not reasons:
            continue
        rows.append(
            {
                "strategy_name": str(event.get("strategy_name", "unknown")),
                "execution_mode": str(event.get("execution_mode", "unknown")),
                "reason": reasons[0],
                "break_even_gap_usdt": _break_even_gap(event),
                "net_profit_usdt": _decimal(event.get("net_profit")),
                "selected_opportunity_id": event.get("selected_opportunity_id"),
            }
        )
    return to_jsonable(rows[-50:])


def _demo_size_stage_readiness(events: list[dict[str, Any]]) -> dict[str, Any]:
    demo_events = [event for event in events if event.get("execution_mode") == "demo"]
    executed = [event for event in demo_events if event.get("decision") == "executed"]
    preflight_missing = sum(1 for event in executed if "net_pnl_usdt" not in _preflight(event))
    receipt_incomplete = sum(1 for event in executed if _receipt_complete(event) is False)
    pnl_failures = sum(1 for event in executed if _pnl_validation(event).get("within_tolerance") is False)
    residual_failures = sum(1 for event in executed if _pnl_validation(event).get("residual_inventory_within_tolerance") is False)
    reasons: list[str] = []
    if len(executed) < 30:
        reasons.append("less_than_30_recent_demo_executions")
    if preflight_missing:
        reasons.append("executed_preflight_missing")
    if receipt_incomplete:
        reasons.append("receipt_incomplete")
    if pnl_failures:
        reasons.append("pnl_tolerance_failure")
    if residual_failures:
        reasons.append("residual_inventory_out_of_tolerance")
    return {
        "stage_1_2x_eligible": not reasons,
        "current_stage": "Stage 0",
        "executed_count": len(executed),
        "executed_preflight_missing": preflight_missing,
        "receipt_incomplete": receipt_incomplete,
        "pnl_tolerance_failure": pnl_failures,
        "residual_inventory_out_of_tolerance": residual_failures,
        "reasons": reasons,
    }


def _receipt_complete(event: dict[str, Any]) -> bool | None:
    raw = _pnl_validation(event).get("exchange_receipts")
    if not isinstance(raw, dict):
        return None
    complete = raw.get("complete")
    return bool(complete) if complete is not None else None


def _route_distribution(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for event in events:
        route = _route_from_event(event)
        if route:
            counts[route] += 1
    return dict(sorted(counts.items()))


def _symbol_distribution(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for event in events:
        symbol = _symbol_from_event(event)
        if symbol:
            counts[symbol] += 1
    return dict(sorted(counts.items()))


def _route_from_event(event: dict[str, Any]) -> str | None:
    selected = str(event.get("selected_opportunity_id") or "")
    marker = "triangular-multi-route-"
    if marker in selected:
        return selected.split(marker, 1)[1]
    local_validation = _execution(event).get("local_validation")
    if isinstance(local_validation, dict):
        selected = str(local_validation.get("selected_opportunity_id") or "")
        if marker in selected:
            return selected.split(marker, 1)[1]
    return None


def _symbol_from_event(event: dict[str, Any]) -> str | None:
    selected = str(event.get("selected_opportunity_id") or "")
    if selected.startswith("directional-"):
        parts = selected.split("-")
        if len(parts) >= 3:
            return f"{parts[-2].upper()}/{parts[-1].upper()}"
    local_validation = _execution(event).get("local_validation")
    if isinstance(local_validation, dict):
        selected = str(local_validation.get("selected_opportunity_id") or "")
        if "btc-usdt" in selected:
            return "BTC/USDT"
    return None


def _average(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    return (sum(values, Decimal("0")) / Decimal(len(values))).quantize(Decimal("0.000001"))


def _decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))
