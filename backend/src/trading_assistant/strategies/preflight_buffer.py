"""Adaptive OKX demo preflight buffer from expected-vs-actual evidence."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from math import ceil
from typing import Any

from trading_assistant.config.schema import StrategyRuntimeConfig
from trading_assistant.strategies.journal import StrategyJournal
from trading_assistant.utils.serialization import to_jsonable


MONEY_QUANT = Decimal("0.000001")


class AdaptivePreflightBufferService:
    """Raise demo preflight thresholds when recent fills underperform estimates."""

    def __init__(self, config: StrategyRuntimeConfig) -> None:
        self.config = config
        self.journal = StrategyJournal(config.journal_path)

    def apply(self, strategy_name: str, preview: dict[str, Any]) -> dict[str, Any]:
        """Return a preview annotated with the adaptive effective threshold."""
        enriched = dict(preview)
        if not self.config.demo_preflight_adaptive_buffer_enabled:
            enriched["adaptive_preflight_buffer"] = _metadata(applied=False, reason="disabled")
            return to_jsonable(enriched)
        if enriched.get("strategy_family") == "directional":
            enriched["adaptive_preflight_buffer"] = _metadata(applied=False, reason="directional_preview")
            return to_jsonable(enriched)

        base_threshold = self._base_threshold(enriched)
        samples = self._expected_actual_gap_samples(strategy_name)
        sample_count = len(samples)
        if sample_count < self.config.demo_preflight_adaptive_buffer_min_samples:
            enriched["base_min_required_net_pnl_usdt"] = _money(base_threshold)
            enriched["min_required_net_pnl_usdt"] = _money(base_threshold)
            enriched["adaptive_preflight_buffer"] = _metadata(
                applied=False,
                reason="insufficient_samples",
                sample_count=sample_count,
                min_samples=self.config.demo_preflight_adaptive_buffer_min_samples,
                buffer_usdt=Decimal("0"),
                effective_min_required_net_pnl_usdt=base_threshold,
            )
            return to_jsonable(enriched)

        positive_gaps = [gap for gap in samples if gap > Decimal("0")]
        raw_buffer = _percentile(positive_gaps, self.config.demo_preflight_adaptive_buffer_quantile_pct)
        buffer = min(raw_buffer, self.config.demo_preflight_adaptive_buffer_max_usdt)
        effective_threshold = base_threshold + buffer
        net_pnl = Decimal(str(enriched.get("net_pnl_usdt", "0") or "0"))
        if bool(enriched.get("approved", False)) and net_pnl < effective_threshold:
            enriched["approved"] = False
            enriched["reason"] = "demo_preflight_buffer_not_met"
        enriched["base_min_required_net_pnl_usdt"] = _money(base_threshold)
        enriched["min_required_net_pnl_usdt"] = _money(effective_threshold)
        enriched["adaptive_preflight_buffer"] = _metadata(
            applied=buffer > Decimal("0"),
            reason="expected_actual_gap",
            sample_count=sample_count,
            positive_gap_sample_count=len(positive_gaps),
            min_samples=self.config.demo_preflight_adaptive_buffer_min_samples,
            quantile_pct=self.config.demo_preflight_adaptive_buffer_quantile_pct,
            lookback=self.config.demo_preflight_adaptive_buffer_lookback,
            raw_buffer_usdt=raw_buffer,
            buffer_usdt=buffer,
            capped=raw_buffer > buffer,
            base_min_required_net_pnl_usdt=base_threshold,
            effective_min_required_net_pnl_usdt=effective_threshold,
        )
        return to_jsonable(enriched)

    def _base_threshold(self, preview: dict[str, Any]) -> Decimal:
        """Return the configured baseline threshold already shown in the preview."""
        raw = preview.get("min_required_net_pnl_usdt")
        if raw is None or raw == "":
            return self.config.demo_min_preflight_net_pnl_usdt
        return max(Decimal(str(raw)), self.config.demo_min_preflight_net_pnl_usdt)

    def _expected_actual_gap_samples(self, strategy_name: str) -> list[Decimal]:
        """Return recent positive-or-negative expected minus actual cash-flow gaps."""
        events = [
            event
            for event in self.journal.read_events()
            if event.get("event") == "strategy_cycle"
            and event.get("execution_mode") == "demo"
            and event.get("decision") == "executed"
            and event.get("strategy_name") == strategy_name
        ]
        gaps: list[Decimal] = []
        for event in events[-self.config.demo_preflight_adaptive_buffer_lookback :]:
            execution = event.get("execution")
            execution_payload: dict[str, Any] = execution if isinstance(execution, dict) else {}
            preflight = execution_payload.get("preflight")
            preflight_payload: dict[str, Any] = preflight if isinstance(preflight, dict) else {}
            expected = _optional_decimal(preflight_payload, "net_pnl_usdt")
            if expected is None:
                continue
            pnl_validation = execution_payload.get("pnl_validation")
            pnl_payload: dict[str, Any] = pnl_validation if isinstance(pnl_validation, dict) else {}
            actual = _optional_decimal(pnl_payload, "cash_flow_net_pnl_usdt")
            if actual is None:
                actual = _optional_decimal(execution_payload, "net_pnl_usdt")
            if actual is None:
                actual = _optional_decimal(event, "net_profit")
            if actual is None:
                continue
            gaps.append(expected - actual)
        return gaps


def _percentile(values: list[Decimal], quantile_pct: Decimal) -> Decimal:
    """Return a nearest-rank percentile for non-negative slippage gaps."""
    if not values:
        return Decimal("0")
    ordered = sorted(values)
    pct = max(Decimal("0"), min(Decimal("100"), quantile_pct))
    index = max(0, min(len(ordered) - 1, ceil((Decimal(len(ordered)) * pct / Decimal("100"))) - 1))
    return ordered[index]


def _optional_decimal(payload: dict[str, Any], key: str) -> Decimal | None:
    """Return a Decimal if the payload contains a non-empty value."""
    if key not in payload:
        return None
    value = payload[key]
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _money(value: Decimal) -> str:
    """Render USDT values with the strategy journal's six-decimal precision."""
    return str(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))


def _metadata(**payload: Any) -> dict[str, Any]:
    """Return JSON-safe adaptive-buffer metadata."""
    return to_jsonable(payload)
