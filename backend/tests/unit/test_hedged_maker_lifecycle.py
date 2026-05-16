"""Tests for stateful hedged-maker paper lifecycle simulation."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from trading_assistant.config.loader import load_settings
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.strategies.hedged_maker import HedgedMakerStrategyService
from trading_assistant.strategies.hedged_maker_lifecycle import HedgedMakerPaperLifecycleService
from trading_assistant.strategies.policy import StrategyPolicy


ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_CONFIG = ROOT / "configs" / "config.example.yaml"
NOW = datetime(2026, 5, 16, 0, 0, tzinfo=UTC)


def test_hedged_maker_lifecycle_creates_open_paper_quote(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    opportunity = _opportunity(settings)
    service = HedgedMakerPaperLifecycleService(settings, ExchangeFactory(settings))

    result = service.apply(opportunity, StrategyPolicy(settings.strategy_runtime).lifecycle_plan(), now=NOW)

    assert result.status == "quoted"
    assert result.paper_only is True
    assert result.orders_sent is False
    assert result.live_orders_sent is False
    assert result.realized_net_profit_usdt == Decimal("0")
    state = service.read_state()
    open_orders = [order for order in state["orders"] if order["status"] == "open"]
    assert len(open_orders) == 1
    assert open_orders[0]["opportunity_id"] == opportunity.opportunity_id
    assert open_orders[0]["maker_order_type"] == "limit_post_only"


def test_hedged_maker_lifecycle_keeps_existing_quote_inside_reprice_threshold(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    opportunity = _opportunity(settings)
    service = HedgedMakerPaperLifecycleService(settings, ExchangeFactory(settings))
    lifecycle = StrategyPolicy(settings.strategy_runtime).lifecycle_plan()

    first = service.apply(opportunity, lifecycle, now=NOW)
    second = service.apply(opportunity, lifecycle, now=NOW + timedelta(seconds=5))

    assert first.status == "quoted"
    assert second.status == "active_quote_unchanged"
    assert second.active_order_count == 1
    state = service.read_state()
    assert len([order for order in state["orders"] if order["status"] == "open"]) == 1


def test_hedged_maker_lifecycle_replaces_expired_quote(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    opportunity = _opportunity(settings)
    service = HedgedMakerPaperLifecycleService(settings, ExchangeFactory(settings))
    lifecycle = StrategyPolicy(settings.strategy_runtime).lifecycle_plan()

    first = service.apply(opportunity, lifecycle, now=NOW)
    second = service.apply(opportunity, lifecycle, now=NOW + timedelta(seconds=settings.strategy_runtime.order_ttl_seconds + 1))

    assert second.status == "replaced_after_ttl"
    assert first.paper_order["order_id"] in second.canceled_order_ids
    state = service.read_state()
    assert len([order for order in state["orders"] if order["status"] == "canceled"]) == 1
    assert len([order for order in state["orders"] if order["status"] == "open"]) == 1


def test_hedged_maker_lifecycle_fills_existing_crossed_quote_and_records_hedge(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    opportunity = _opportunity(settings)
    state_path = Path(settings.hedged_maker.paper_state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "orders": [
                    {
                        "order_id": "seed-crossed-buy",
                        "opportunity_id": opportunity.opportunity_id,
                        "symbol": opportunity.symbol,
                        "maker_exchange": "mock",
                        "hedge_exchange": "mock_alt",
                        "maker_side": "buy",
                        "hedge_side": "sell",
                        "maker_order_type": "limit_post_only",
                        "hedge_order_type": "taker_market_preview",
                        "price": "60000",
                        "quantity": "0.002",
                        "expected_net_profit_usdt": "0.55",
                        "status": "open",
                        "created_at": NOW.isoformat(),
                        "updated_at": NOW.isoformat(),
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    service = HedgedMakerPaperLifecycleService(settings, ExchangeFactory(settings))

    result = service.apply(
        opportunity,
        StrategyPolicy(settings.strategy_runtime).lifecycle_plan(),
        now=NOW + timedelta(seconds=1),
    )

    assert result.status == "filled_and_hedged"
    assert result.paper_order["order_id"] == "seed-crossed-buy"
    assert result.hedge_order is not None
    assert result.hedge_order["side"] == "sell"
    assert result.realized_net_profit_usdt < Decimal("0")
    state = service.read_state()
    filled_orders = [order for order in state["orders"] if order["status"] == "filled"]
    assert len(filled_orders) == 1
    assert filled_orders[0]["realized_net_profit_usdt"] == str(result.realized_net_profit_usdt)


def _settings(tmp_path: Path):
    settings = load_settings(EXAMPLE_CONFIG)
    settings.hedged_maker.paper_state_path = str(tmp_path / "hedged-maker-paper-state.json")
    settings.strategy_runtime.order_ttl_seconds = 30
    settings.strategy_runtime.reprice_threshold_pct = Decimal("0.05")
    return settings


def _opportunity(settings):
    return HedgedMakerStrategyService(settings, ExchangeFactory(settings)).scan(
        symbol="BTC/USDT",
        maker_exchange="mock",
        hedge_exchange="mock_alt",
    )[0]
