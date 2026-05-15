"""Read-only carry and basis scanner optimization diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.strategies.platform import StrategyController
from trading_assistant.utils.serialization import to_jsonable


CARRY_BASIS_STRATEGIES = ["funding-carry-hedged", "spot-perp-carry", "futures-perp-basis"]
MONEY_QUANT = Decimal("0.000001")


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

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report."""
        return {
            "read_only": self.read_only,
            "orders_sent": self.orders_sent,
            "live_orders_sent": self.live_orders_sent,
            "symbol": self.symbol,
            "cards": [card.to_dict() for card in self.cards],
            "summary": to_jsonable(self.summary),
        }


class CarryBasisOptimizationService:
    """Summarize carry/basis scanner diagnostics without sending orders."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges
        self.controller = StrategyController(settings, exchanges)

    def report(self, symbol: str = "BTC/USDT") -> CarryBasisOptimizationReport:
        """Return offline optimization cards for carry and basis strategies."""
        cards: list[CarryBasisOptimizationCard] = []
        for strategy_name in CARRY_BASIS_STRATEGIES:
            scan = self.controller.scan(strategy_name=strategy_name, symbol=symbol)[0]
            diagnostic = _best_diagnostic(scan.diagnostics)
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
                )
            )
        return CarryBasisOptimizationReport(
            read_only=True,
            orders_sent=False,
            live_orders_sent=False,
            symbol=symbol,
            cards=cards,
            summary=_summary(cards),
        )


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
    return {
        "strategy_count": len(cards),
        "demo_ready_count": len(cards) - len(blocked),
        "blocked_count": len(blocked),
        "max_break_even_gap_usdt": _money(max_gap),
        "highest_priority": "high" if blocked else "observe",
        "guardrails": [
            "read_only_no_orders",
            "do_not_force_demo_when_break_even_gap_positive",
            "do_not_reduce_profit_safety_gates_from_optimizer_output",
        ],
    }


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
