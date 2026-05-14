"""Unit tests for OKX-first spot directional strategy expansion."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from trading_assistant.config.loader import load_settings
from trading_assistant.directional.backtest import DirectionalBacktestEngine
from trading_assistant.directional.indicators import atr, bollinger_bands, donchian_channel, ema, rsi
from trading_assistant.directional.models import DirectionalPositionLifecycle, DirectionalSignal
from trading_assistant.directional.scanner import DirectionalOpportunityScanner
from trading_assistant.directional.strategies import TrendBreakoutStrategy
from trading_assistant.exchanges.base import Candle
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.strategies.registry import StrategyRegistry


ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_CONFIG = ROOT / "configs" / "config.example.yaml"


def test_directional_registry_adds_group_and_aggregate_alias() -> None:
    registry = StrategyRegistry()

    directional = registry.expand("directional-all")
    names = {definition.name for definition in directional}

    assert names >= {
        "trend-breakout",
        "mean-reversion-spot",
        "volatility-squeeze-breakout",
        "momentum-rotation",
        "orderbook-imbalance-scalp",
    }
    assert all(definition.category == "directional" for definition in directional)
    assert registry.get("directional-all").scanner_type == "directional-all"
    assert "orderbook-imbalance-scalp" not in registry.demo_validation_names()


def test_directional_indicators_use_decimal_outputs() -> None:
    candles = _trend_candles(count=40)
    closes = [candle.close for candle in candles]

    assert ema(closes, period=10)[-1] > ema(closes, period=20)[-1]
    assert Decimal("0") <= rsi(closes, period=14)[-1] <= Decimal("100")
    assert atr(candles, period=14)[-1] > Decimal("0")
    middle, upper, lower, bandwidth = bollinger_bands(closes, period=20)
    assert upper[-1] > middle[-1] > lower[-1]
    assert bandwidth[-1] > Decimal("0")
    high, low = donchian_channel(candles, period=20)
    assert high[-1] >= max(candle.high for candle in candles[-20:])
    assert low[-1] <= min(candle.low for candle in candles[-20:])


def test_trend_breakout_ignores_incomplete_breakout_candle() -> None:
    candles = _trend_candles(count=60)[:-1]
    incomplete_breakout = Candle(
        exchange="mock",
        symbol="BTC/USDT",
        bar="15m",
        open=Decimal("21000"),
        high=Decimal("23500"),
        low=Decimal("20950"),
        close=Decimal("23400"),
        volume=Decimal("5000"),
        timestamp=candles[-1].timestamp + timedelta(minutes=15),
        complete=False,
    )

    signal = TrendBreakoutStrategy().generate_signal([*candles, incomplete_breakout], symbol="BTC/USDT", exchange="mock")

    assert signal.signal == "hold"
    assert "incomplete_candle_ignored" in signal.reason_codes


def test_directional_signal_and_lifecycle_are_json_safe() -> None:
    signal = DirectionalSignal(
        strategy_name="trend-breakout",
        symbol="BTC/USDT",
        exchange="mock",
        signal="buy",
        confidence=Decimal("0.72"),
        expected_edge_pct=Decimal("1.20"),
        stop_loss_pct=Decimal("0.80"),
        take_profit_pct=Decimal("1.80"),
        time_limit_minutes=90,
        reason_codes=["ema_trend", "donchian_breakout"],
    )
    lifecycle = DirectionalPositionLifecycle(
        strategy_name="trend-breakout",
        symbol="BTC/USDT",
        exchange="mock",
        state="planned",
        entry_signal=signal,
    )

    payload = lifecycle.to_dict()

    assert payload["state"] == "planned"
    assert payload["entry_signal"]["signal"] == "buy"
    assert payload["entry_signal"]["expected_edge_pct"] == "1.20"


def test_directional_scanner_wraps_buy_signal_as_opportunity(tmp_path: Path) -> None:
    settings = load_settings(EXAMPLE_CONFIG)
    settings.strategy_runtime.journal_path = str(tmp_path / "strategy-events.jsonl")
    scanner = DirectionalOpportunityScanner(settings, ExchangeFactory(settings))

    opportunities, diagnostics = scanner.scan("trend-breakout", symbol="BTC/USDT", exchange="mock")

    assert diagnostics["approved"] is True
    assert opportunities
    best = opportunities[0]
    assert best.strategy_type == "trend-breakout"
    assert best.buy_exchange == "mock"
    assert best.sell_exchange is None
    assert best.net_profit > Decimal("0")
    assert best.metadata["directional_signal"]["signal"] == "buy"
    assert Decimal(str(best.metadata["backtest"]["profit_factor"])) >= Decimal("1.10")


def test_directional_backtest_reports_fee_adjusted_metrics() -> None:
    candles = _trend_candles(count=120)

    result = DirectionalBacktestEngine().run("trend-breakout", "BTC/USDT", "mock", candles)

    assert result.total_trades >= 1
    assert result.net_pnl_usdt > Decimal("0")
    assert result.profit_factor >= Decimal("1.10")
    assert result.max_drawdown_pct <= Decimal("5")
    assert result.account_equity_attribution["strategy_pnl_usdt"] == result.net_pnl_usdt


def _trend_candles(count: int) -> list[Candle]:
    start = datetime(2026, 5, 11, tzinfo=UTC)
    candles: list[Candle] = []
    price = Decimal("20000")
    for index in range(count):
        if index < count - 1 and index != count // 2:
            price += Decimal("8")
            close = price
            high = close + Decimal("20")
            volume = Decimal("1000") + Decimal(index)
        else:
            close = price + Decimal("350")
            high = close + Decimal("50")
            volume = Decimal("2500")
        candles.append(
            Candle(
                exchange="mock",
                symbol="BTC/USDT",
                bar="15m",
                open=price - Decimal("10"),
                high=high,
                low=price - Decimal("30"),
                close=close,
                volume=volume,
                timestamp=start + timedelta(minutes=15 * index),
                complete=True,
            )
        )
        price = close
    return candles
