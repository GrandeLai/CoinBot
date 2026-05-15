"""Read-only strategy-level PnL attribution ledger from runtime journals."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from trading_assistant.config.schema import StrategyRuntimeConfig
from trading_assistant.strategies.journal import StrategyJournal
from trading_assistant.strategies.registry import StrategyRegistry
from trading_assistant.utils.serialization import to_jsonable


MONEY_QUANT = Decimal("0.000001")


@dataclass(frozen=True)
class StrategyPnlAttributionEntry:
    """One strategy-cycle PnL attribution ledger row."""

    event_index: int
    strategy_name: str
    execution_mode: str
    decision: str
    selected_opportunity_id: str | None
    realized_event_net_profit_usdt: Decimal
    expected_preflight_net_pnl_usdt: Decimal | None
    strategy_cash_flow_net_pnl_usdt: Decimal
    account_equity_delta_usdt: Decimal | None
    account_attribution_gap_usdt: Decimal | None
    residual_inventory_usdt: Decimal
    residual_inventory_within_tolerance: bool | None
    pnl_within_tolerance: bool | None
    classification: str

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe ledger entry."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyPnlAttributionSummary:
    """Aggregate PnL attribution over the selected ledger window."""

    total_entries: int
    executed_entries: int
    strategy_cash_flow_net_pnl_usdt: Decimal
    account_equity_delta_usdt: Decimal
    account_attribution_gap_usdt: Decimal
    max_residual_inventory_usdt: Decimal
    positive_cash_flow_negative_equity_delta: int

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe summary."""
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyPnlAttributionReport:
    """Read-only PnL attribution report."""

    journal_path: str
    execution_mode: str | None
    strategy_name: str
    requested_limit: int
    scanned_events: int
    orders_sent: bool
    live_orders_sent: bool
    summary: StrategyPnlAttributionSummary
    entries: list[StrategyPnlAttributionEntry]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report."""
        return {
            "journal_path": self.journal_path,
            "execution_mode": self.execution_mode,
            "strategy_name": self.strategy_name,
            "requested_limit": self.requested_limit,
            "scanned_events": self.scanned_events,
            "orders_sent": self.orders_sent,
            "live_orders_sent": self.live_orders_sent,
            "summary": self.summary.to_dict(),
            "entries": [entry.to_dict() for entry in self.entries],
            "recommendations": self.recommendations,
        }


class StrategyPnlAttributionService:
    """Build a read-only ledger that separates strategy PnL from account movement."""

    def __init__(self, config: StrategyRuntimeConfig) -> None:
        self.config = config
        self.journal = StrategyJournal(config.journal_path)

    def report(
        self,
        execution_mode: str | None = None,
        strategy_name: str = "all",
        limit: int = 50,
    ) -> StrategyPnlAttributionReport:
        """Return a strategy-level PnL attribution report from recent journal events."""
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
        entries = [self._entry(index, event) for index, event in enumerate(window, start=1)]
        summary = _summary(entries)
        return StrategyPnlAttributionReport(
            journal_path=self.config.journal_path,
            execution_mode=execution_mode,
            strategy_name=strategy_name,
            requested_limit=requested_limit,
            scanned_events=len(window),
            orders_sent=False,
            live_orders_sent=False,
            summary=summary,
            entries=entries,
            recommendations=_recommendations(summary),
        )

    def _entry(self, index: int, event: dict[str, Any]) -> StrategyPnlAttributionEntry:
        """Convert one journal event into an attribution row."""
        execution = event.get("execution")
        execution_payload: dict[str, Any] = execution if isinstance(execution, dict) else {}
        pnl_validation = execution_payload.get("pnl_validation")
        pnl_payload: dict[str, Any] = pnl_validation if isinstance(pnl_validation, dict) else {}
        preflight = execution_payload.get("preflight")
        preflight_payload: dict[str, Any] = preflight if isinstance(preflight, dict) else {}
        decision = str(event.get("decision", "skipped"))
        net_profit = _money(_decimal_or_default(event, "net_profit", Decimal("0")))
        cash_flow = _money(_decimal_or_default(pnl_payload, "cash_flow_net_pnl_usdt", net_profit if decision == "executed" else Decimal("0")))
        equity_delta = _optional_money(pnl_payload, "equity_delta_usdt")
        gap = _money(equity_delta - cash_flow) if equity_delta is not None else None
        residual = _money(_decimal_or_default(pnl_payload, "residual_inventory_usdt", Decimal("0")))
        return StrategyPnlAttributionEntry(
            event_index=index,
            strategy_name=str(event.get("strategy_name", "unknown")),
            execution_mode=str(event.get("execution_mode", "unknown")),
            decision=decision,
            selected_opportunity_id=_optional_str(event.get("selected_opportunity_id")),
            realized_event_net_profit_usdt=net_profit,
            expected_preflight_net_pnl_usdt=_optional_money(preflight_payload, "net_pnl_usdt"),
            strategy_cash_flow_net_pnl_usdt=cash_flow,
            account_equity_delta_usdt=equity_delta,
            account_attribution_gap_usdt=gap,
            residual_inventory_usdt=residual,
            residual_inventory_within_tolerance=_optional_bool(pnl_payload.get("residual_inventory_within_tolerance")),
            pnl_within_tolerance=_optional_bool(pnl_payload.get("within_tolerance")),
            classification=_classification(decision, cash_flow, equity_delta, pnl_payload),
        )


def _summary(entries: list[StrategyPnlAttributionEntry]) -> StrategyPnlAttributionSummary:
    """Aggregate PnL attribution ledger rows."""
    executed = [entry for entry in entries if entry.decision == "executed"]
    equity_values = [entry.account_equity_delta_usdt for entry in executed if entry.account_equity_delta_usdt is not None]
    gap_values = [entry.account_attribution_gap_usdt for entry in executed if entry.account_attribution_gap_usdt is not None]
    return StrategyPnlAttributionSummary(
        total_entries=len(entries),
        executed_entries=len(executed),
        strategy_cash_flow_net_pnl_usdt=_money(sum((entry.strategy_cash_flow_net_pnl_usdt for entry in executed), Decimal("0"))),
        account_equity_delta_usdt=_money(sum(equity_values, Decimal("0"))),
        account_attribution_gap_usdt=_money(sum(gap_values, Decimal("0"))),
        max_residual_inventory_usdt=max((entry.residual_inventory_usdt for entry in entries), default=Decimal("0")),
        positive_cash_flow_negative_equity_delta=sum(
            1
            for entry in executed
            if entry.strategy_cash_flow_net_pnl_usdt > Decimal("0")
            and entry.account_equity_delta_usdt is not None
            and entry.account_equity_delta_usdt < Decimal("0")
        ),
    )


def _recommendations(summary: StrategyPnlAttributionSummary) -> list[str]:
    """Return conservative operator recommendations for attribution gaps."""
    recommendations: list[str] = []
    if summary.positive_cash_flow_negative_equity_delta:
        recommendations.append("Account equity moved negative while strategy cash-flow PnL was positive; isolate external balance, inventory, and mark-to-market effects before increasing demo size.")
    if summary.max_residual_inventory_usdt > Decimal("0"):
        recommendations.append("Residual inventory is present; keep strategy cash-flow PnL separate from account-level mark-to-market movement.")
    if summary.executed_entries == 0:
        recommendations.append("No executed strategy samples in the selected window.")
    if not recommendations:
        recommendations.append("Strategy cash-flow and account-equity attribution are clean in the selected window.")
    return recommendations


def _classification(
    decision: str,
    cash_flow: Decimal,
    equity_delta: Decimal | None,
    pnl_payload: dict[str, Any],
) -> str:
    """Classify how much account movement can be attributed to the strategy."""
    if decision != "executed":
        return "skipped_no_cash_flow"
    if equity_delta is None:
        return "strategy_cash_flow_only"
    if cash_flow > Decimal("0") and equity_delta < Decimal("0"):
        return "positive_cash_flow_negative_equity_delta"
    if pnl_payload.get("within_tolerance") is False:
        return "account_equity_diverged"
    return "account_equity_matched"


def _expanded_strategy_names(strategy_name: str) -> set[str]:
    """Return concrete strategy names for filtering."""
    if strategy_name == "all":
        return set()
    try:
        return {definition.name for definition in StrategyRegistry().expand(strategy_name)}
    except Exception:
        return {strategy_name}


def _optional_decimal(payload: dict[str, Any], key: str) -> Decimal | None:
    """Return Decimal value when a payload field is present."""
    if key not in payload:
        return None
    value = payload[key]
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _decimal_or_default(payload: dict[str, Any], key: str, default: Decimal) -> Decimal:
    """Return Decimal from payload or a default."""
    value = _optional_decimal(payload, key)
    return default if value is None else value


def _optional_money(payload: dict[str, Any], key: str) -> Decimal | None:
    """Return quantized Decimal value when present."""
    value = _optional_decimal(payload, key)
    return None if value is None else _money(value)


def _money(value: Decimal) -> Decimal:
    """Quantize money values to journal precision."""
    return value.quantize(MONEY_QUANT)


def _optional_bool(value: Any) -> bool | None:
    """Return bool only when the source field is present."""
    if value is None:
        return None
    return bool(value)


def _optional_str(value: Any) -> str | None:
    """Return a string only when a field is present."""
    if value is None:
        return None
    return str(value)
