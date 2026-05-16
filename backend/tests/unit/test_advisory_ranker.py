"""Tests for the read-only strategy advisory ranker."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from trading_assistant.config.loader import load_settings
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.base import utcnow
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.strategies.advisory_ranker import StrategyAdvisoryRankerService


ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_CONFIG = ROOT / "configs" / "config.example.yaml"


def test_advisory_ranker_prioritizes_profitable_paper_evidence(tmp_path: Path) -> None:
    settings = load_settings(EXAMPLE_CONFIG)
    _use_temp_runtime_paths(settings, tmp_path)
    _write_strategy_events(Path(settings.strategy_runtime.journal_path), "smart-dca-basket", count=2, net_profit=Decimal("1.25"))

    report = StrategyAdvisoryRankerService(settings, ExchangeFactory(settings)).rank(
        strategy_name="smart-dca-basket",
        symbol="SOL/USDT",
        execution_mode="paper",
        limit=10,
        window="24h",
    )

    assert report.read_only is True
    assert report.orders_sent is False
    assert report.live_orders_sent is False
    assert report.model_policy["name"] == "deterministic_evidence_ranker"
    assert report.model_policy["external_model_called"] is False
    assert report.rankings[0].strategy_name == "smart-dca-basket"
    assert report.rankings[0].recommendation == "prioritize_paper_validation"
    assert report.rankings[0].validation_executed == 2
    assert report.rankings[0].validation_win_rate_pct == Decimal("100.00")
    assert "positive_validation_pnl" in report.rankings[0].reasons


def test_advisory_ranker_keeps_demo_unsupported_strategy_paper_only(tmp_path: Path) -> None:
    settings = load_settings(EXAMPLE_CONFIG)
    _use_temp_runtime_paths(settings, tmp_path)

    report = StrategyAdvisoryRankerService(settings, ExchangeFactory(settings)).rank(
        strategy_name="smart-dca-basket",
        symbol="SOL/USDT",
        execution_mode="demo",
        limit=10,
        window="24h",
    )

    row = report.rankings[0]
    assert row.strategy_name == "smart-dca-basket"
    assert row.recommendation == "paper_only"
    assert "demo_not_supported" in row.reasons
    assert report.model_policy["llm_direct_ordering_allowed"] is False


def _write_strategy_events(path: Path, strategy_name: str, *, count: int, net_profit: Decimal) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for index in range(count):
        rows.append(
            json.dumps(
                {
                    "event": "strategy_cycle",
                    "created_at": utcnow().isoformat(),
                    "cycle": index + 1,
                    "strategy_name": strategy_name,
                    "decision": "executed",
                    "execution_mode": "paper",
                    "opportunities_found": 1,
                    "selected_opportunity_id": f"{strategy_name}-{index}",
                    "risk_approved": True,
                    "risk_reasons": [],
                    "net_profit": str(net_profit),
                    "execution": {
                        "status": "simulated",
                        "dry_run": True,
                        "orders": [],
                        "net_profit": str(net_profit),
                    },
                }
            )
        )
    path.write_text("\n".join(rows), encoding="utf-8")


def _use_temp_runtime_paths(settings: Settings, tmp_path: Path) -> None:
    settings.strategy_runtime.journal_path = str(tmp_path / "strategy-events.jsonl")
    settings.strategy_runtime.runtime_guard_path = str(tmp_path / "strategy-runtime-guard.json")
    settings.strategy_runtime.retrospective_path = str(tmp_path / "strategy-retrospective.md")
    settings.strategy_runtime.retrospective_state_path = str(tmp_path / "strategy-retrospective.state.json")
    settings.strategy_runtime.evolution_state_path = str(tmp_path / "strategy-evolution.state.json")
    settings.strategy_runtime.evolution_report_path = str(tmp_path / "strategy-evolution.md")
