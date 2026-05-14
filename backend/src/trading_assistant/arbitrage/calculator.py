"""Decimal-based arbitrage calculation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from trading_assistant.exchanges.base import OrderBook


@dataclass(frozen=True)
class DepthFillEstimate:
    """Orderbook depth-weighted fill estimate."""

    requested_notional: Decimal
    filled_notional: Decimal
    filled_base: Decimal
    average_price: Decimal
    reference_price: Decimal
    slippage_pct: Decimal
    complete: bool


@dataclass(frozen=True)
class SpreadPersistence:
    """Spread persistence check result."""

    passed: bool
    window_count: int
    minimum_spread_pct: Decimal
    average_spread_pct: Decimal


@dataclass(frozen=True)
class FundingCarry:
    """Funding carry projection over a holding period."""

    projected_funding_usdt: Decimal
    holding_cost_usdt: Decimal
    net_carry_usdt: Decimal
    annualized_pct: Decimal


def calculate_fee(notional: Decimal, fee_pct: Decimal, legs: int = 1) -> Decimal:
    """Calculate total fees for one notional across N legs."""
    return notional * fee_pct * Decimal(legs)


def calculate_tiered_fee(notional: Decimal, maker_fee_pct: Decimal, taker_fee_pct: Decimal, maker_ratio: Decimal) -> Decimal:
    """Calculate blended maker/taker fee for a notional."""
    bounded_maker_ratio = min(max(maker_ratio, Decimal("0")), Decimal("1"))
    maker_notional = notional * bounded_maker_ratio
    taker_notional = notional - maker_notional
    return maker_notional * maker_fee_pct + taker_notional * taker_fee_pct


def calculate_slippage(notional: Decimal, slippage_pct: Decimal, legs: int = 1) -> Decimal:
    """Calculate conservative slippage estimate."""
    return notional * slippage_pct * Decimal(legs)


def estimate_depth_fill(orderbook: OrderBook, side: Literal["bid", "ask"], quote_notional: Decimal) -> DepthFillEstimate:
    """Estimate average execution price and slippage from visible orderbook depth."""
    levels = orderbook.asks if side == "ask" else orderbook.bids
    reference_price = orderbook.best_ask.price if side == "ask" else orderbook.best_bid.price
    remaining = quote_notional
    filled_notional = Decimal("0")
    filled_base = Decimal("0")
    for level in levels:
        if remaining <= 0:
            break
        level_notional = level.notional
        take_notional = min(remaining, level_notional)
        filled_notional += take_notional
        filled_base += take_notional / level.price
        remaining -= take_notional
    average_price = filled_notional / filled_base if filled_base else Decimal("0")
    if reference_price == 0 or average_price == 0:
        slippage_pct = Decimal("0")
    elif side == "ask":
        slippage_pct = ((average_price - reference_price) / reference_price) * Decimal("100")
    else:
        slippage_pct = ((reference_price - average_price) / reference_price) * Decimal("100")
    return DepthFillEstimate(
        requested_notional=quote_notional,
        filled_notional=filled_notional,
        filled_base=filled_base,
        average_price=average_price,
        reference_price=reference_price,
        slippage_pct=max(slippage_pct, Decimal("0")),
        complete=filled_notional >= quote_notional,
    )


def has_sufficient_depth(orderbook: OrderBook, side: Literal["bid", "ask"], required_notional: Decimal) -> bool:
    """Return whether a side has enough visible depth."""
    return orderbook.depth_notional(side, levels=5) >= required_notional


def calculate_transfer_cost(notional: Decimal, fixed_withdrawal_fee_usdt: Decimal, delay_risk_pct: Decimal) -> Decimal:
    """Estimate cross-venue transfer/withdrawal and delay-risk cost."""
    return fixed_withdrawal_fee_usdt + notional * delay_risk_pct


def calculate_latency_drift_cost(notional: Decimal, latency_ms: int, drift_bps_per_second: Decimal) -> Decimal:
    """Estimate price-drift cost from expected exchange/API latency."""
    seconds = Decimal(latency_ms) / Decimal("1000")
    return notional * (drift_bps_per_second / Decimal("10000")) * seconds


def calculate_spread_persistence(spread_samples_pct: list[Decimal], min_spread_pct: Decimal, required_windows: int) -> SpreadPersistence:
    """Check whether recent spread samples stayed above the configured threshold."""
    samples = spread_samples_pct[-required_windows:]
    if not samples:
        return SpreadPersistence(False, 0, Decimal("0"), Decimal("0"))
    minimum = min(samples)
    average = sum(samples, Decimal("0")) / Decimal(len(samples))
    return SpreadPersistence(
        passed=len(samples) >= required_windows and all(sample >= min_spread_pct for sample in samples),
        window_count=len(samples),
        minimum_spread_pct=minimum,
        average_spread_pct=average,
    )


def calculate_funding_carry(
    capital: Decimal,
    funding_rate: Decimal,
    holding_hours: Decimal,
    settlement_interval_hours: Decimal,
    hedge_cost_pct: Decimal,
) -> FundingCarry:
    """Estimate funding carry net of hedge/holding cost."""
    settlement_count = holding_hours / settlement_interval_hours if settlement_interval_hours else Decimal("0")
    projected_funding = capital * funding_rate * settlement_count
    holding_cost = capital * hedge_cost_pct
    annualized_pct = Decimal("0")
    if settlement_interval_hours:
        annualized_pct = funding_rate * (Decimal("365") * Decimal("24") / settlement_interval_hours) * Decimal("100")
    return FundingCarry(
        projected_funding_usdt=projected_funding,
        holding_cost_usdt=holding_cost,
        net_carry_usdt=projected_funding - holding_cost,
        annualized_pct=annualized_pct,
    )


def calculate_risk_score(profit_pct: Decimal, slippage_pct: Decimal, depth_usdt: Decimal) -> Decimal:
    """Return bounded risk score where lower is safer."""
    depth_penalty = Decimal("0.35") if depth_usdt < Decimal("5000") else Decimal("0.05")
    slippage_penalty = min(slippage_pct * Decimal("5"), Decimal("0.4"))
    profit_credit = min(profit_pct / Decimal("2"), Decimal("0.3"))
    score = Decimal("0.35") + depth_penalty + slippage_penalty - profit_credit
    return max(Decimal("0"), min(score, Decimal("1")))


def percent(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Return percentage with zero guard."""
    if denominator == 0:
        return Decimal("0")
    return (numerator / denominator) * Decimal("100")
