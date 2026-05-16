"""Read-only hedged-maker paper lifecycle evaluation reports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from trading_assistant.config.schema import Settings
from trading_assistant.strategies.journal import StrategyJournal
from trading_assistant.utils.serialization import to_jsonable


MONEY_QUANT = Decimal("0.000001")
PCT_QUANT = Decimal("0.01")
OPEN_STATE_STATUSES = {"open", "partial_open", "cancel_pending"}
FILL_STATUSES = {"filled_and_hedged", "partially_filled_and_hedged"}


@dataclass(frozen=True)
class HedgedMakerPaperEvaluationEntry:
    """One hedged-maker paper lifecycle evidence row."""

    event_index: int
    selected_opportunity_id: str | None
    decision: str
    lifecycle_status: str
    active_order_count: int
    expected_net_profit_usdt: Decimal
    realized_net_profit_usdt: Decimal
    fill_ratio_pct: Decimal | None
    filled_quantity: Decimal | None
    remaining_quantity: Decimal | None
    adverse_selection: bool | None
    hedge_slippage_multiplier: Decimal | None
    canceled_order_count: int

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe entry."""
        return to_jsonable(self)


@dataclass(frozen=True)
class HedgedMakerPaperEvaluationSummary:
    """Aggregate hedged-maker paper lifecycle evidence."""

    total_events: int
    executed_events: int
    lifecycle_counts: dict[str, int]
    fill_events: int
    partial_fill_events: int
    adverse_selection_events: int
    cancel_pending_events: int
    total_expected_net_profit_usdt: Decimal
    total_realized_net_profit_usdt: Decimal
    average_fill_ratio_pct: Decimal
    max_hedge_slippage_multiplier: Decimal
    state_order_counts: dict[str, int]
    active_state_orders: int

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe summary."""
        return to_jsonable(self)


@dataclass(frozen=True)
class HedgedMakerPaperEvaluationReport:
    """Read-only report over hedged-maker paper journal and state evidence."""

    journal_path: str
    paper_state_path: str
    requested_limit: int
    scanned_events: int
    read_only: bool
    orders_sent: bool
    live_orders_sent: bool
    summary: HedgedMakerPaperEvaluationSummary
    entries: list[HedgedMakerPaperEvaluationEntry]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report."""
        return {
            "journal_path": self.journal_path,
            "paper_state_path": self.paper_state_path,
            "requested_limit": self.requested_limit,
            "scanned_events": self.scanned_events,
            "read_only": self.read_only,
            "orders_sent": self.orders_sent,
            "live_orders_sent": self.live_orders_sent,
            "summary": self.summary.to_dict(),
            "entries": [entry.to_dict() for entry in self.entries],
            "recommendations": self.recommendations,
        }


class HedgedMakerPaperEvaluationReportService:
    """Build read-only paper evaluation reports for hedged-maker evidence."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.journal = StrategyJournal(settings.strategy_runtime.journal_path)
        self.paper_state_path = Path(settings.hedged_maker.paper_state_path)

    def report(self, limit: int = 50) -> HedgedMakerPaperEvaluationReport:
        """Return a paper-only hedged-maker evaluation report."""
        requested_limit = max(limit, 1)
        events = [
            event
            for event in self.journal.read_events()
            if event.get("event") == "strategy_cycle"
            and event.get("strategy_name") == "hedged-maker"
            and event.get("execution_mode") == "paper"
        ]
        window = events[-requested_limit:]
        entries = [self._entry(index, event) for index, event in enumerate(window, start=1)]
        state_counts = self._state_counts()
        summary = _summary(entries, state_counts)
        return HedgedMakerPaperEvaluationReport(
            journal_path=self.settings.strategy_runtime.journal_path,
            paper_state_path=self.settings.hedged_maker.paper_state_path,
            requested_limit=requested_limit,
            scanned_events=len(window),
            read_only=True,
            orders_sent=False,
            live_orders_sent=False,
            summary=summary,
            entries=entries,
            recommendations=_recommendations(summary),
        )

    def _entry(self, index: int, event: dict[str, Any]) -> HedgedMakerPaperEvaluationEntry:
        execution = _mapping(event.get("execution"))
        lifecycle = _mapping(execution.get("hedged_maker_lifecycle"))
        paper_order = _mapping(lifecycle.get("paper_order"))
        hedge_order = _mapping(lifecycle.get("hedge_order"))
        fill_quality = _mapping(hedge_order.get("fill_quality"))
        return HedgedMakerPaperEvaluationEntry(
            event_index=index,
            selected_opportunity_id=_optional_str(event.get("selected_opportunity_id")),
            decision=str(event.get("decision", "unknown")),
            lifecycle_status=str(lifecycle.get("status", execution.get("status", "unknown"))),
            active_order_count=_int(lifecycle.get("active_order_count")),
            expected_net_profit_usdt=_money(_decimal_or_default(lifecycle, "expected_net_profit_usdt", _decimal_or_default(execution, "expected_net_profit", Decimal("0")))),
            realized_net_profit_usdt=_money(_decimal_or_default(lifecycle, "realized_net_profit_usdt", _decimal_or_default(event, "net_profit", Decimal("0")))),
            fill_ratio_pct=_optional_decimal(fill_quality, "fill_ratio_pct"),
            filled_quantity=_optional_decimal(fill_quality, "filled_quantity") or _optional_decimal(paper_order, "filled_quantity"),
            remaining_quantity=_optional_decimal(paper_order, "remaining_quantity"),
            adverse_selection=_optional_bool(hedge_order.get("adverse_selection")) if hedge_order else None,
            hedge_slippage_multiplier=_optional_decimal(hedge_order, "hedge_slippage_multiplier"),
            canceled_order_count=len(lifecycle.get("canceled_order_ids", [])) if isinstance(lifecycle.get("canceled_order_ids"), list) else 0,
        )

    def _state_counts(self) -> dict[str, int]:
        if not self.paper_state_path.exists():
            return {}
        payload = json.loads(self.paper_state_path.read_text(encoding="utf-8") or "{}")
        orders = payload.get("orders", []) if isinstance(payload, dict) else []
        counts: dict[str, int] = {}
        if not isinstance(orders, list):
            return counts
        for order in orders:
            if not isinstance(order, dict):
                continue
            status = str(order.get("status", "unknown"))
            counts[status] = counts.get(status, 0) + 1
        return counts


def _summary(entries: list[HedgedMakerPaperEvaluationEntry], state_counts: dict[str, int]) -> HedgedMakerPaperEvaluationSummary:
    lifecycle_counts: dict[str, int] = {}
    fill_ratios = [entry.fill_ratio_pct for entry in entries if entry.fill_ratio_pct is not None]
    hedge_multipliers = [entry.hedge_slippage_multiplier for entry in entries if entry.hedge_slippage_multiplier is not None]
    for entry in entries:
        lifecycle_counts[entry.lifecycle_status] = lifecycle_counts.get(entry.lifecycle_status, 0) + 1
    return HedgedMakerPaperEvaluationSummary(
        total_events=len(entries),
        executed_events=sum(1 for entry in entries if entry.decision == "executed"),
        lifecycle_counts=lifecycle_counts,
        fill_events=sum(1 for entry in entries if entry.lifecycle_status in FILL_STATUSES or entry.fill_ratio_pct is not None),
        partial_fill_events=sum(1 for entry in entries if entry.lifecycle_status == "partially_filled_and_hedged"),
        adverse_selection_events=sum(1 for entry in entries if entry.adverse_selection is True),
        cancel_pending_events=sum(1 for entry in entries if entry.lifecycle_status == "cancel_pending"),
        total_expected_net_profit_usdt=_money(sum((entry.expected_net_profit_usdt for entry in entries), Decimal("0"))),
        total_realized_net_profit_usdt=_money(sum((entry.realized_net_profit_usdt for entry in entries), Decimal("0"))),
        average_fill_ratio_pct=_pct(sum(fill_ratios, Decimal("0")) / Decimal(len(fill_ratios))) if fill_ratios else Decimal("0"),
        max_hedge_slippage_multiplier=max(hedge_multipliers, default=Decimal("0")),
        state_order_counts=state_counts,
        active_state_orders=sum(count for status, count in state_counts.items() if status in OPEN_STATE_STATUSES),
    )


def _recommendations(summary: HedgedMakerPaperEvaluationSummary) -> list[str]:
    recommendations: list[str] = []
    if summary.total_events == 0:
        recommendations.append("Collect hedged-maker paper samples before evaluating maker dispatch quality.")
    if summary.adverse_selection_events:
        recommendations.append("adverse-selection samples detected; review quote aggressiveness and hedge slippage assumptions before any sandbox maker order manager.")
    if summary.partial_fill_events:
        recommendations.append("Partial fills are present; keep queue-position evidence in paper reports before demo design.")
    if summary.cancel_pending_events:
        recommendations.append("Cancel-pending samples are present; validate cancel latency handling before exchange dispatch.")
    if summary.total_realized_net_profit_usdt < Decimal("0"):
        recommendations.append("Realized paper PnL is negative in the selected window; do not promote hedged-maker dispatch.")
    if not recommendations:
        recommendations.append("Hedged-maker paper evidence is clean in the selected window; continue collecting samples across regimes.")
    return recommendations


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _optional_decimal(payload: dict[str, Any], key: str) -> Decimal | None:
    if key not in payload:
        return None
    value = payload[key]
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _decimal_or_default(payload: dict[str, Any], key: str, default: Decimal) -> Decimal:
    value = _optional_decimal(payload, key)
    return default if value is None else value


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _int(value: object) -> int:
    return int(str(value or "0"))


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT)


def _pct(value: Decimal) -> Decimal:
    return value.quantize(PCT_QUANT)
