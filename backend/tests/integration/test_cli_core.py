"""Integration tests for the trading assistant CLI."""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

import pytest

from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.cli.main import main


ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_CONFIG = ROOT / "configs" / "config.example.yaml"


def _invoke(args: Sequence[str], capsys) -> tuple[int, dict]:
    code = main([*args, "--json"])
    captured = capsys.readouterr()
    assert captured.err == ""
    return code, json.loads(captured.out)


def test_cli_config_exchange_market_account_arbitrage_execution_and_report(capsys) -> None:
    code, payload = _invoke(["config", "validate", "--config", str(EXAMPLE_CONFIG)], capsys)
    assert code == 0
    assert payload["valid"] is True

    code, payload = _invoke(["exchange", "ping", "--exchange", "mock"], capsys)
    assert code == 0
    assert payload["ok"] is True

    code, payload = _invoke(["exchange", "ping", "--config", str(EXAMPLE_CONFIG), "--exchange", "mock"], capsys)
    assert code == 0
    assert payload["ok"] is True

    code, payload = _invoke(["market", "ticker", "--exchange", "mock", "--symbol", "BTC/USDT"], capsys)
    assert code == 0
    assert payload["ticker"]["symbol"] == "BTC/USDT"

    code, payload = _invoke(["market", "ticker", "--config", str(EXAMPLE_CONFIG), "--exchange", "mock", "--symbol", "BTC/USDT"], capsys)
    assert code == 0
    assert payload["ticker"]["symbol"] == "BTC/USDT"

    code, payload = _invoke(["market", "orderbook", "--exchange", "mock", "--symbol", "BTC/USDT"], capsys)
    assert code == 0
    assert payload["orderbook"]["bids"]

    code, payload = _invoke(
        ["market", "candles", "--config", str(EXAMPLE_CONFIG), "--exchange", "mock", "--symbol", "BTC/USDT", "--bar", "15m", "--limit", "80"],
        capsys,
    )
    assert code == 0
    assert payload["candles"]
    assert payload["candles"][0]["complete"] is True

    code, payload = _invoke(["account", "balance", "--config", str(EXAMPLE_CONFIG), "--exchange", "mock"], capsys)
    assert code == 0
    assert payload["account"]["balances"]["USDT"]["free"] == "10000"

    code, payload = _invoke(["arbitrage", "scan", "--type", "cross-exchange", "--symbol", "BTC/USDT"], capsys)
    assert code == 0
    assert payload["opportunities"][0]["opportunity_id"] == "test-opportunity"

    code, payload = _invoke(["arbitrage", "execute", "--opportunity-id", "test-opportunity", "--dry-run"], capsys)
    assert code == 0
    assert payload["execution"]["status"] == "simulated"

    code, payload = _invoke(["report", "generate", "--type", "daily"], capsys)
    assert code == 0
    assert payload["report"]["type"] == "daily"


def test_cli_invalid_exchange_returns_nonzero_and_json_error(capsys) -> None:
    code = main(["exchange", "ping", "--exchange", "missing", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code != 0
    assert payload["error"]["type"] == "ExchangeError"
    assert "Unknown exchange" in payload["error"]["message"]


def test_cli_okx_sandbox_check_requires_enabled_exchange(capsys) -> None:
    code = main(["exchange", "sandbox-check", "--exchange", "okx", "--symbol", "BTC/USDT", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code != 0
    assert payload["error"]["type"] == "ExchangeError"
    assert "Exchange is disabled: okx" in payload["error"]["message"]


def test_cli_workflow_run_returns_full_route(capsys) -> None:
    code = main(["workflow", "run", "--config", str(EXAMPLE_CONFIG), "--symbol", "BTC/USDT", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["workflow"]["completed"] is True
    assert payload["workflow"]["paper_trading"]["execution"]["dry_run"] is True
    assert payload["workflow"]["sandbox_readiness"]["ready"] is True
    assert payload["workflow"]["live_readiness"]["ready"] is False
    assert payload["workflow"]["agent_live_readiness"]["ready"] is False


def test_cli_backtest_realistic_walk_forward_and_bias_check(capsys) -> None:
    code, payload = _invoke(
        [
            "backtest",
            "run",
            "--config",
            str(EXAMPLE_CONFIG),
            "--strategy",
            "trend-breakout",
            "--symbol",
            "BTC/USDT",
            "--exchange",
            "mock",
        ],
        capsys,
    )
    assert code == 0
    assert payload["backtest"]["read_only"] is True
    assert payload["backtest"]["orders_sent"] is False
    assert payload["backtest"]["live_orders_sent"] is False
    assert payload["backtest"]["fill_model"]["completed_candles_only"] is True

    code, payload = _invoke(
        [
            "backtest",
            "walk-forward",
            "--config",
            str(EXAMPLE_CONFIG),
            "--strategy",
            "trend-breakout",
            "--symbol",
            "BTC/USDT",
            "--exchange",
            "mock",
            "--windows",
            "2",
        ],
        capsys,
    )
    assert code == 0
    assert payload["backtest_walk_forward"]["read_only"] is True
    assert payload["backtest_walk_forward"]["orders_sent"] is False
    assert len(payload["backtest_walk_forward"]["windows"]) == 2

    code, payload = _invoke(
        [
            "backtest",
            "bias-check",
            "--config",
            str(EXAMPLE_CONFIG),
            "--strategy",
            "trend-breakout",
            "--symbol",
            "BTC/USDT",
            "--exchange",
            "mock",
        ],
        capsys,
    )
    assert code == 0
    assert payload["backtest_bias_check"]["orders_sent"] is False
    assert payload["backtest_bias_check"]["passed"] is True


def test_cli_autopilot_run_status_and_report(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "autopilot.yaml"
    config_path.write_text(
        f"""
strategy_runtime:
  journal_path: {tmp_path / "strategy-events.jsonl"}
  runtime_guard_path: {tmp_path / "strategy-runtime-guard.json"}
  retrospective_path: {tmp_path / "strategy-retrospective.md"}
  retrospective_state_path: {tmp_path / "strategy-retrospective.state.json"}
  evolution_state_path: {tmp_path / "strategy-evolution.state.json"}
  evolution_report_path: {tmp_path / "strategy-evolution.md"}
  autopilot_state_path: {tmp_path / "autopilot-state.json"}
  review_min_samples: 1
""".strip(),
        encoding="utf-8",
    )

    code, payload = _invoke(
        [
            "autopilot",
            "run",
            "--config",
            str(config_path),
            "--mode",
            "paper",
            "--strategy",
            "cross-exchange",
            "--cycles",
            "1",
            "--interval-seconds",
            "0",
        ],
        capsys,
    )
    assert code == 0
    assert payload["autopilot_run"]["status"] == "Completed"
    assert payload["autopilot_run"]["live_orders_sent"] is False

    code, payload = _invoke(["autopilot", "status", "--config", str(config_path)], capsys)
    assert code == 0
    assert payload["autopilot_status"]["status"] == "Completed"

    code, payload = _invoke(
        ["autopilot", "report", "--config", str(config_path), "--mode", "paper", "--strategy", "cross-exchange"],
        capsys,
    )
    assert code == 0
    assert payload["autopilot_report"]["state"]["status"] == "Completed"
    assert payload["autopilot_report"]["live_orders_sent"] is False


def test_cli_agent_live_readiness_blocks_by_default(capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COINBOT_AGENT_TRADING_ENABLED", "false")
    monkeypatch.setenv("COINBOT_AGENT_ALLOW_LIVE_ORDERS", "false")

    code = main(["agent", "live-readiness", "--config", str(EXAMPLE_CONFIG), "--opportunity-id", "test-opportunity", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["agent_live_readiness"]["ready"] is False
    assert "agent_trading_disabled" in payload["agent_live_readiness"]["reasons"]


def test_cli_agent_execute_live_blocks_by_default(capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COINBOT_AGENT_TRADING_ENABLED", "false")
    monkeypatch.setenv("COINBOT_AGENT_ALLOW_LIVE_ORDERS", "false")

    code = main(["agent", "execute-live", "--config", str(EXAMPLE_CONFIG), "--opportunity-id", "test-opportunity", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code != 0
    assert payload["error"]["type"] == "SafetyError"
    assert "agent_trading_disabled" in payload["error"]["message"]


def test_cli_agent_live_readiness_accepts_opportunity_file(tmp_path: Path, capsys) -> None:
    opportunity_path = tmp_path / "okx-opportunity.json"
    opportunity_path.write_text(json.dumps(_okx_opportunity_payload()), encoding="utf-8")

    code = main(["agent", "live-readiness", "--config", str(EXAMPLE_CONFIG), "--opportunity-file", str(opportunity_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["agent_live_readiness"]["ready"] is False
    assert "mock_exchange_involved" not in payload["agent_live_readiness"]["reasons"]
    assert "exchange_disabled" in payload["agent_live_readiness"]["reasons"]


def test_cli_agent_execute_live_accepts_opportunity_file_and_blocks_before_provider(tmp_path: Path, capsys) -> None:
    opportunity_path = tmp_path / "okx-opportunity.json"
    opportunity_path.write_text(json.dumps(_okx_opportunity_payload()), encoding="utf-8")

    code = main(["agent", "execute-live", "--config", str(EXAMPLE_CONFIG), "--opportunity-file", str(opportunity_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code != 0
    assert payload["error"]["type"] == "SafetyError"
    assert "exchange_disabled" in payload["error"]["message"]


def test_cli_agent_operation_catalog_reports_demo_validation(capsys) -> None:
    code = main(["agent", "operation-catalog", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    catalog = payload["operation_catalog"]
    assert catalog["missing_demo_validation"] == []
    operation_ids = {operation["operation_id"] for operation in catalog["operations"]}
    assert "okx.sandbox_check" in operation_ids
    assert "okx.agent_spot_limit_order" in operation_ids
    for operation in catalog["operations"]:
        if operation["live_supported"]:
            assert operation["demo_supported"] is True
            assert operation["demo_config"] == "configs/okx.demo.example.yaml"
            assert "--config configs/okx.demo.example.yaml" in operation["demo_command"]


def test_cli_strategy_list_run_and_review(tmp_path: Path, capsys) -> None:
    journal_path = tmp_path / "strategy-events.jsonl"
    retrospective_path = tmp_path / "strategy-retrospective.md"
    retrospective_state_path = tmp_path / "strategy-retrospective.state.json"
    config_path = tmp_path / "strategy.yaml"
    config_path.write_text(
        f"""
strategy_runtime:
  journal_path: {journal_path}
  runtime_guard_path: {tmp_path / "strategy-runtime-guard.json"}
  retrospective_path: {retrospective_path}
  retrospective_state_path: {retrospective_state_path}
  evolution_state_path: {tmp_path / "strategy-evolution.state.json"}
  evolution_report_path: {tmp_path / "strategy-evolution.md"}
  review_min_samples: 1
""".strip(),
        encoding="utf-8",
    )

    code, payload = _invoke(["strategy", "list"], capsys)
    assert code == 0
    assert {strategy["name"] for strategy in payload["strategies"]} >= {
        "cross-exchange",
        "triangular-multi-route",
        "funding-carry-hedged",
        "spot-perp-carry",
        "futures-perp-basis",
    }

    code, payload = _invoke(["strategy", "catalog", "--config", str(config_path)], capsys)
    assert code == 0
    assert payload["strategy_catalog"]["aliases"]["triangular"] == "triangular-multi-route"
    directional_names = {
        strategy["name"]
        for strategy in payload["strategy_catalog"]["strategies"]
        if strategy["category"] == "directional"
    }
    assert directional_names >= {"trend-breakout", "mean-reversion-spot", "volatility-squeeze-breakout", "momentum-rotation"}

    code, payload = _invoke(["strategy", "scan", "--config", str(config_path), "--strategy", "all", "--symbol", "BTC/USDT"], capsys)
    assert code == 0
    assert {report["strategy_name"] for report in payload["strategy_scan"]} >= {"triangular-multi-route", "spot-perp-carry"}
    assert sum(len(report["opportunities"]) for report in payload["strategy_scan"]) >= 5
    spot_perp_scan = next(report for report in payload["strategy_scan"] if report["strategy_name"] == "spot-perp-carry")
    assert "diagnostics" in spot_perp_scan
    assert "net_profit_usdt" in spot_perp_scan["diagnostics"]

    code, payload = _invoke(["strategy", "score", "--config", str(config_path), "--strategy", "all"], capsys)
    assert code == 0
    assert len(payload["strategy_score"]) >= 5

    code, payload = _invoke(["strategy", "scan", "--config", str(config_path), "--strategy", "directional-all", "--symbol", "BTC/USDT"], capsys)
    assert code == 0
    assert {report["strategy_name"] for report in payload["strategy_scan"]} >= {
        "trend-breakout",
        "mean-reversion-spot",
        "volatility-squeeze-breakout",
        "momentum-rotation",
        "orderbook-imbalance-scalp",
    }
    assert sum(len(report["opportunities"]) for report in payload["strategy_scan"]) >= 1

    code, payload = _invoke(["strategy", "score", "--config", str(config_path), "--strategy", "directional-all", "--symbol", "BTC/USDT"], capsys)
    assert code == 0
    assert len(payload["strategy_score"]) == 5
    assert any(card["best_opportunity_id"] for card in payload["strategy_score"])

    code, payload = _invoke(
        [
            "strategy",
            "run",
            "--config",
            str(config_path),
            "--strategy",
            "directional-all",
            "--max-cycles",
            "1",
            "--interval-seconds",
            "0",
            "--execution-mode",
            "paper",
        ],
        capsys,
    )
    assert code == 0
    assert payload["strategy_run"]["completed"] is True
    assert any(result["decision"] == "executed" for result in payload["strategy_run"]["results"])

    code, payload = _invoke(["strategy", "market-compare", "--config", str(config_path), "--strategy", "all", "--target-exchange", "mock"], capsys)
    assert code == 0
    comparison = payload["strategy_market_compare"]
    assert comparison["read_only"] is True
    assert comparison["orders_sent"] is False
    assert comparison["target_exchange"] == "mock"
    assert len(comparison["comparisons"]) >= 5

    code, payload = _invoke(["strategy", "discover-routes", "--config", str(config_path), "--exchange", "mock", "--quote", "USDT"], capsys)
    assert code == 0
    route_report = payload["strategy_discover_routes"]
    assert route_report["read_only"] is True
    assert route_report["orders_sent"] is False
    assert route_report["accepted_routes"]

    code, payload = _invoke(
        [
            "strategy",
            "scan",
            "--config",
            str(config_path),
            "--strategy",
            "triangular-multi-route",
            "--exchange",
            "mock",
            "--route-mode",
            "discovered",
        ],
        capsys,
    )
    assert code == 0
    assert payload["strategy_scan"][0]["opportunities"]

    code, payload = _invoke(["strategy", "portfolio-status", "--config", str(config_path)], capsys)
    assert code == 0
    assert payload["strategy_portfolio_status"]["selected_strategies"]

    code, payload = _invoke(
        [
            "strategy",
            "run",
            "--config",
            str(config_path),
            "--strategy",
            "all",
            "--max-cycles",
            "1",
            "--interval-seconds",
            "0",
            "--execution-mode",
            "paper",
        ],
        capsys,
    )
    assert code == 0
    assert payload["strategy_run"]["completed"] is True
    assert payload["strategy_run"]["cycles_completed"] == 1
    assert payload["retrospective_before"]["enabled"] is True
    assert payload["retrospective_after"]["retrospective_path"] == str(retrospective_path)
    assert payload["retrospective_path"] == str(retrospective_path)
    assert journal_path.exists()
    assert retrospective_path.exists()
    assert retrospective_state_path.exists()

    code, payload = _invoke(["strategy", "review", "--config", str(config_path)], capsys)
    assert code == 0
    assert payload["strategy_review"]["total_events"] >= 1
    assert "cross-exchange" in payload["strategy_review"]["strategy_stats"]
    assert "retrospective_summary" in payload

    code, payload = _invoke(["strategy", "review", "--config", str(config_path), "--execution-mode", "paper"], capsys)
    assert code == 0
    assert payload["strategy_review"]["total_events"] >= 1

    code, payload = _invoke(["strategy", "retrospective", "--config", str(config_path)], capsys)
    assert code == 0
    assert payload["strategy_retrospective"]["retrospective_path"] == str(retrospective_path)
    assert "optimization_pressure" in payload["strategy_retrospective"]

    code, payload = _invoke(["strategy", "validation-report", "--config", str(config_path), "--execution-mode", "paper"], capsys)
    assert code == 0
    assert payload["strategy_validation_report"]["scanned_events"] >= 1
    assert payload["strategy_validation_report"]["total"]["executed"] >= 1
    assert "recommendations" in payload["strategy_validation_report"]

    code, payload = _invoke(["strategy", "opportunity-report", "--config", str(config_path), "--window", "24h"], capsys)
    assert code == 0
    opportunity_report = payload["strategy_opportunity_report"]
    assert opportunity_report["read_only"] is True
    assert opportunity_report["orders_sent"] is False
    assert opportunity_report["scan_count"] >= 1
    assert "by_strategy" in opportunity_report

    code, payload = _invoke(["strategy", "guard-status", "--config", str(config_path), "--execution-mode", "paper"], capsys)
    assert code == 0
    assert payload["strategy_guard_status"]["enabled"] is True
    assert {entry["strategy_name"] for entry in payload["strategy_guard_status"]["entries"]} >= {
        "cross-exchange",
        "triangular-multi-route",
        "funding-carry-hedged",
        "spot-perp-carry",
        "futures-perp-basis",
    }

    code, payload = _invoke(
        [
            "strategy",
            "validate-local",
            "--config",
            str(config_path),
            "--strategy",
            "all",
            "--cycles",
            "1",
        ],
        capsys,
    )
    assert code == 0
    assert payload["local_validation"]["status"] in {"Pass", "Needs More Samples"}
    assert payload["strategy_run"]["execution_mode"] == "paper"
    assert payload["retrospective_after"]["retrospective_path"] == str(retrospective_path)

    code, payload = _invoke(["strategy", "promotion-status", "--config", str(config_path), "--strategy", "all"], capsys)
    assert code == 0
    assert payload["strategy_promotion_status"]
    assert all(item["live"]["status"] == "Fail" for item in payload["strategy_promotion_status"])


def test_cli_portfolio_status_applies_retrospective_pressure(tmp_path: Path, capsys) -> None:
    state_path = tmp_path / "retrospective.state.json"
    config_path = tmp_path / "strategy.yaml"
    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "2026-05-10T00:00:00+00:00",
                "recent_runs": [],
                "issues": {
                    "spot-perp-carry|demo|preflight_not_profitable|demo_preflight_not_profitable": {
                        "issue_id": "ri-test",
                        "dedupe_key": "spot-perp-carry|demo|preflight_not_profitable|demo_preflight_not_profitable",
                        "strategy_name": "spot-perp-carry",
                        "execution_mode": "demo",
                        "category": "preflight_not_profitable",
                        "reason": "demo_preflight_not_profitable",
                        "severity": "warning",
                        "status": "open",
                        "occurrences": 10,
                        "first_seen_at": "2026-05-10T00:00:00+00:00",
                        "last_seen_at": "2026-05-10T00:00:00+00:00",
                        "recommendation": "Review spread and cost thresholds before another demo attempt.",
                        "last_context": {"net_profit": "-0.258630", "decision": "skipped"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    config_path.write_text(
        f"""
strategy_runtime:
  journal_path: {tmp_path / "strategy-events.jsonl"}
  retrospective_path: {tmp_path / "retrospective.md"}
  retrospective_state_path: {state_path}
  evolution_state_path: {tmp_path / "evolution.state.json"}
  evolution_report_path: {tmp_path / "evolution.md"}
  retrospective_demo_preflight_score_penalty: "30"
""".strip(),
        encoding="utf-8",
    )

    code, payload = _invoke(["strategy", "portfolio-status", "--config", str(config_path), "--symbol", "BTC/USDT"], capsys)

    assert code == 0
    score_cards = payload["strategy_portfolio_status"]["score_cards"]
    spot_perp = next(card for card in score_cards if card["strategy_name"] == "spot-perp-carry")
    assert Decimal(spot_perp["score"]) < Decimal("50")
    assert "repeated_demo_preflight_not_profitable" in spot_perp["reasons"]
    assert "demo_break_even_gap_usdt:0.258630" in spot_perp["reasons"]


def test_cli_strategy_universe_regime_and_exit_commands(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "strategy.yaml"
    config_path.write_text(
        f"""
strategy_runtime:
  journal_path: {tmp_path / "strategy-events.jsonl"}
  runtime_guard_path: {tmp_path / "strategy-runtime-guard.json"}
  retrospective_path: {tmp_path / "strategy-retrospective.md"}
  retrospective_state_path: {tmp_path / "strategy-retrospective.state.json"}
  evolution_state_path: {tmp_path / "strategy-evolution.state.json"}
  evolution_report_path: {tmp_path / "strategy-evolution.md"}
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as universe_help_exit:
        main(["strategy", "universe", "--help"])
    universe_help = capsys.readouterr()
    assert universe_help_exit.value.code == 0
    assert "--exchange" in universe_help.out

    with pytest.raises(SystemExit) as exit_help_exit:
        main(["strategy", "exit-optimize", "--help"])
    exit_help = capsys.readouterr()
    assert exit_help_exit.value.code == 0
    assert "--strategy" in exit_help.out

    code, payload = _invoke(["strategy", "universe", "--config", str(config_path), "--exchange", "mock"], capsys)
    assert code == 0
    assert payload["strategy_universe"]["read_only"] is True
    assert payload["strategy_universe"]["orders_sent"] is False
    assert payload["strategy_universe"]["accepted_symbols"]

    code, payload = _invoke(
        ["strategy", "regime-report", "--config", str(config_path), "--exchange", "mock", "--symbol", "BTC/USDT"],
        capsys,
    )
    assert code == 0
    assert payload["strategy_regime_report"]["symbol"] == "BTC/USDT"
    assert payload["strategy_regime_report"]["accepted"] is True

    code, payload = _invoke(
        ["strategy", "exit-optimize", "--config", str(config_path), "--strategy", "trend-breakout", "--symbol", "BTC/USDT", "--exchange", "mock"],
        capsys,
    )
    assert code == 0
    assert payload["strategy_exit_optimization"]["read_only"] is True
    assert payload["strategy_exit_optimization"]["orders_sent"] is False
    assert payload["strategy_exit_optimization"]["candidates"]

    code, payload = _invoke(
        ["strategy", "position-report", "--config", str(config_path), "--strategy", "trend-breakout", "--symbol", "BTC/USDT", "--exchange", "mock"],
        capsys,
    )
    assert code == 0
    assert payload["strategy_position_report"]["read_only"] is True
    assert payload["strategy_position_report"]["live_orders_sent"] is False


def test_cli_strategy_range_grid_scans_and_runs_in_paper(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "range-grid.yaml"
    config_path.write_text(
        f"""
universe:
  trend_return_threshold_pct: "100"
  range_volatility_max_pct: "10"
range_grid:
  max_range_width_pct: "20"
  min_grid_spacing_pct: "0.50"
strategy_runtime:
  journal_path: {tmp_path / "strategy-events.jsonl"}
  runtime_guard_path: {tmp_path / "strategy-runtime-guard.json"}
  retrospective_path: {tmp_path / "strategy-retrospective.md"}
  retrospective_state_path: {tmp_path / "strategy-retrospective.state.json"}
  evolution_state_path: {tmp_path / "strategy-evolution.state.json"}
  evolution_report_path: {tmp_path / "strategy-evolution.md"}
""".strip(),
        encoding="utf-8",
    )

    code, payload = _invoke(
        ["strategy", "scan", "--config", str(config_path), "--strategy", "range-grid", "--symbol", "BTC/USDT", "--exchange", "mock"],
        capsys,
    )
    assert code == 0
    report = payload["strategy_scan"][0]
    assert report["strategy_name"] == "range-grid"
    assert report["opportunities"]
    assert report["opportunities"][0]["metadata"]["paper_only"] is True

    code, payload = _invoke(
        [
            "strategy",
            "run",
            "--config",
            str(config_path),
            "--strategy",
            "range-grid",
            "--symbol",
            "BTC/USDT",
            "--max-cycles",
            "1",
            "--interval-seconds",
            "0",
            "--execution-mode",
            "paper",
        ],
        capsys,
    )
    assert code == 0
    result = payload["strategy_run"]["results"][0]
    assert result["strategy_name"] == "range-grid"
    assert result["decision"] == "executed"
    assert result["execution"]["dry_run"] is True


def test_cli_strategy_hedged_maker_scans_and_runs_in_paper(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "hedged-maker.yaml"
    config_path.write_text(
        f"""
strategy_runtime:
  journal_path: {tmp_path / "strategy-events.jsonl"}
  runtime_guard_path: {tmp_path / "strategy-runtime-guard.json"}
  retrospective_path: {tmp_path / "strategy-retrospective.md"}
  retrospective_state_path: {tmp_path / "strategy-retrospective.state.json"}
  evolution_state_path: {tmp_path / "strategy-evolution.state.json"}
  evolution_report_path: {tmp_path / "strategy-evolution.md"}
hedged_maker:
  paper_state_path: {tmp_path / "hedged-maker-paper-state.json"}
""".strip(),
        encoding="utf-8",
    )

    code, payload = _invoke(
        ["strategy", "scan", "--config", str(config_path), "--strategy", "hedged-maker", "--symbol", "BTC/USDT", "--exchange", "mock"],
        capsys,
    )
    assert code == 0
    report = payload["strategy_scan"][0]
    assert report["strategy_name"] == "hedged-maker"
    assert report["opportunities"]
    assert report["opportunities"][0]["metadata"]["paper_only"] is True
    assert report["opportunities"][0]["metadata"]["maker_order_type"] == "limit_post_only"

    code, payload = _invoke(
        [
            "strategy",
            "run",
            "--config",
            str(config_path),
            "--strategy",
            "hedged-maker",
            "--symbol",
            "BTC/USDT",
            "--max-cycles",
            "1",
            "--interval-seconds",
            "0",
            "--execution-mode",
            "paper",
        ],
        capsys,
    )
    assert code == 0
    result = payload["strategy_run"]["results"][0]
    assert result["strategy_name"] == "hedged-maker"
    assert result["decision"] == "executed"
    assert result["execution"]["dry_run"] is True
    lifecycle = result["execution"]["hedged_maker_lifecycle"]
    assert lifecycle["status"] == "quoted"
    assert lifecycle["orders_sent"] is False
    assert lifecycle["live_orders_sent"] is False
    assert lifecycle["realized_net_profit_usdt"] == "0"
    assert (tmp_path / "hedged-maker-paper-state.json").exists()
    assert payload["retrospective_after"]["open_issue_count"] == 0


def test_cli_strategy_retrospective_empty_history(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "strategy.yaml"
    config_path.write_text(
        f"""
strategy_runtime:
  journal_path: {tmp_path / "empty-strategy-events.jsonl"}
  runtime_guard_path: {tmp_path / "empty-runtime-guard.json"}
  retrospective_path: {tmp_path / "empty-retrospective.md"}
  retrospective_state_path: {tmp_path / "empty-retrospective.state.json"}
  evolution_state_path: {tmp_path / "empty-evolution.state.json"}
  evolution_report_path: {tmp_path / "empty-evolution.md"}
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as help_exit:
        main(["strategy", "retrospective", "--help"])
    help_output = capsys.readouterr()
    assert help_exit.value.code == 0
    assert "--json" in help_output.out

    with pytest.raises(SystemExit) as report_help_exit:
        main(["strategy", "validation-report", "--help"])
    report_help_output = capsys.readouterr()
    assert report_help_exit.value.code == 0
    assert "--limit" in report_help_output.out

    with pytest.raises(SystemExit) as pnl_help_exit:
        main(["strategy", "pnl-attribution", "--help"])
    pnl_help_output = capsys.readouterr()
    assert pnl_help_exit.value.code == 0
    assert "--execution-mode" in pnl_help_output.out

    with pytest.raises(SystemExit) as operator_brief_help_exit:
        main(["strategy", "operator-brief", "--help"])
    operator_brief_help_output = capsys.readouterr()
    assert operator_brief_help_exit.value.code == 0
    assert "--limit" in operator_brief_help_output.out

    with pytest.raises(SystemExit) as carry_basis_help_exit:
        main(["strategy", "carry-basis-optimize", "--help"])
    carry_basis_help_output = capsys.readouterr()
    assert carry_basis_help_exit.value.code == 0
    assert "--symbol" in carry_basis_help_output.out

    with pytest.raises(SystemExit) as opportunity_help_exit:
        main(["strategy", "opportunity-report", "--help"])
    opportunity_help_output = capsys.readouterr()
    assert opportunity_help_exit.value.code == 0
    assert "--window" in opportunity_help_output.out

    with pytest.raises(SystemExit) as discover_routes_help_exit:
        main(["strategy", "discover-routes", "--help"])
    discover_routes_help_output = capsys.readouterr()
    assert discover_routes_help_exit.value.code == 0
    assert "--quote" in discover_routes_help_output.out

    with pytest.raises(SystemExit) as compare_help_exit:
        main(["strategy", "market-compare", "--help"])
    compare_help_output = capsys.readouterr()
    assert compare_help_exit.value.code == 0
    assert "--target-exchange" in compare_help_output.out

    with pytest.raises(SystemExit) as evolve_help_exit:
        main(["strategy", "evolve", "--help"])
    evolve_help_output = capsys.readouterr()
    assert evolve_help_exit.value.code == 0
    assert "--execution-mode" in evolve_help_output.out

    with pytest.raises(SystemExit) as revival_help_exit:
        main(["strategy", "revival-window", "--help"])
    revival_help_output = capsys.readouterr()
    assert revival_help_exit.value.code == 0
    assert "--cycles" in revival_help_output.out

    with pytest.raises(SystemExit) as demo_window_help_exit:
        main(["strategy", "demo-window", "--help"])
    demo_window_help_output = capsys.readouterr()
    assert demo_window_help_exit.value.code == 0
    assert "--public-health-only" in demo_window_help_output.out

    with pytest.raises(SystemExit) as demo_sampling_help_exit:
        main(["strategy", "demo-sampling", "--help"])
    demo_sampling_help_output = capsys.readouterr()
    assert demo_sampling_help_exit.value.code == 0
    assert "--cycles-per-window" in demo_sampling_help_output.out

    with pytest.raises(SystemExit) as candidate_help_exit:
        main(["strategy", "candidate-backtest", "--help"])
    candidate_help_output = capsys.readouterr()
    assert candidate_help_exit.value.code == 0
    assert "--limit" in candidate_help_output.out

    code, payload = _invoke(["strategy", "retrospective", "--config", str(config_path)], capsys)

    assert code == 0
    assert payload["strategy_retrospective"]["open_issue_count"] == 0
    assert payload["strategy_retrospective"]["top_open_issues"] == []
    assert payload["strategy_retrospective"]["optimization_pressure"] == []

    code, payload = _invoke(["strategy", "validation-report", "--config", str(config_path), "--limit", "10"], capsys)
    assert code == 0
    assert payload["strategy_validation_report"]["scanned_events"] == 0
    assert payload["strategy_validation_report"]["total"]["executed"] == 0

    code, payload = _invoke(["strategy", "opportunity-report", "--config", str(config_path), "--window", "24h"], capsys)
    assert code == 0
    assert payload["strategy_opportunity_report"]["scan_count"] == 0
    assert payload["strategy_opportunity_report"]["orders_sent"] is False

    code, payload = _invoke(["strategy", "evolve", "--config", str(config_path), "--limit", "10"], capsys)
    assert code == 0
    assert payload["strategy_evolution"]["orders_sent"] is False
    assert payload["strategy_evolution"]["live_orders_sent"] is False
    assert payload["strategy_evolution"]["decisions"]

    code, payload = _invoke(["strategy", "revival-window", "--config", str(config_path), "--cycles", "1"], capsys)
    assert code == 0
    assert payload["strategy_revival_window"]["candidates"] == []
    assert payload["strategy_revival_window"]["orders_sent"] is False
    assert payload["strategy_revival_window"]["live_orders_sent"] is False

    code, payload = _invoke(["strategy", "candidate-backtest", "--config", str(config_path), "--strategy", "trend-breakout", "--limit", "10"], capsys)
    assert code == 0
    assert payload["strategy_candidate_backtest"]["orders_sent"] is False
    assert payload["strategy_candidate_backtest"]["live_orders_sent"] is False
    assert payload["strategy_candidate_backtest"]["checked_in_config_modified"] is False
    assert payload["strategy_candidate_backtest"]["candidates"]


def test_cli_strategy_pnl_attribution_reads_journal_without_trading(tmp_path: Path, capsys) -> None:
    journal_path = tmp_path / "strategy-events.jsonl"
    journal_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "strategy_cycle",
                        "execution_mode": "demo",
                        "strategy_name": "triangular-multi-route",
                        "decision": "executed",
                        "net_profit": "0.20",
                        "execution": {
                            "preflight": {"net_pnl_usdt": "0.18"},
                            "pnl_validation": {
                                "cash_flow_net_pnl_usdt": "0.20",
                                "equity_delta_usdt": "0.23",
                                "within_tolerance": True,
                                "residual_inventory_usdt": "0.01",
                                "residual_inventory_within_tolerance": True,
                            },
                        },
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "strategy.yaml"
    config_path.write_text(f"strategy_runtime:\n  journal_path: {journal_path}\n", encoding="utf-8")

    code, payload = _invoke(
        [
            "strategy",
            "pnl-attribution",
            "--config",
            str(config_path),
            "--execution-mode",
            "demo",
            "--strategy",
            "triangular-multi-route",
            "--json",
        ],
        capsys,
    )

    assert code == 0
    report = payload["strategy_pnl_attribution"]
    assert report["orders_sent"] is False
    assert report["live_orders_sent"] is False
    assert report["summary"]["strategy_cash_flow_net_pnl_usdt"] == "0.200000"


def test_cli_strategy_operator_brief_is_read_only(tmp_path: Path, capsys) -> None:
    journal_path = tmp_path / "strategy-events.jsonl"
    config_path = tmp_path / "strategy.yaml"
    config_path.write_text(
        f"""
strategy_runtime:
  journal_path: {journal_path}
  runtime_guard_path: {tmp_path / "strategy-runtime-guard.json"}
  demo_strategy_size_overrides:
    cross-exchange:
      order_size_multiplier: "1"
      max_order_value_usdt: "10"
""".strip(),
        encoding="utf-8",
    )
    journal_path.write_text(
        json.dumps(
            {
                "event": "strategy_cycle",
                "execution_mode": "demo",
                "strategy_name": "cross-exchange",
                "decision": "executed",
                "net_profit": "0.12",
                "risk_reasons": [],
                "execution": {
                    "demo_orders_sent": True,
                    "live_orders_sent": False,
                    "pnl_validation": {"within_tolerance": True, "residual_inventory_within_tolerance": True},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    code, payload = _invoke(
        ["strategy", "operator-brief", "--config", str(config_path), "--execution-mode", "demo", "--strategy", "all"],
        capsys,
    )

    assert code == 0
    brief = payload["strategy_operator_brief"]
    assert brief["orders_sent"] is False
    assert brief["live_orders_sent"] is False
    assert brief["safety"]["live_trading"] is False
    assert brief["size_stage"]["demo_order_size_multiplier"] == "1"
    assert brief["size_stage"]["demo_strategy_size_overrides"]["cross-exchange"]["max_order_value_usdt"] == "10"
    assert brief["validation"]["total"]["executed"] == 1
    assert "live_canary_disabled" in brief["recommendations"]


def test_cli_strategy_carry_basis_optimize_is_read_only(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "strategy.yaml"
    config_path.write_text(
        f"""
strategy_runtime:
  journal_path: {tmp_path / "strategy-events.jsonl"}
  runtime_guard_path: {tmp_path / "runtime-guard.json"}
  retrospective_path: {tmp_path / "retrospective.md"}
  retrospective_state_path: {tmp_path / "retrospective.state.json"}
""".strip(),
        encoding="utf-8",
    )

    code, payload = _invoke(
        ["strategy", "carry-basis-optimize", "--config", str(config_path), "--symbol", "BTC/USDT", "--json"],
        capsys,
    )

    assert code == 0
    report = payload["strategy_carry_basis_optimization"]
    assert report["read_only"] is True
    assert report["orders_sent"] is False
    assert report["live_orders_sent"] is False
    assert {card["strategy_name"] for card in report["cards"]} == {
        "funding-carry-hedged",
        "spot-perp-carry",
        "futures-perp-basis",
    }


def test_cli_strategy_validate_demo_blocks_with_safe_default_config(capsys) -> None:
    code = main(["strategy", "validate-demo", "--config", str(EXAMPLE_CONFIG), "--strategy", "all", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code != 0
    assert payload["error"]["type"] == "SafetyError"
    assert "enabled OKX sandbox" in payload["error"]["message"]


def test_cli_strategy_validate_demo_window_blocks_with_safe_default_config(capsys) -> None:
    code = main(["strategy", "validate-demo-window", "--config", str(EXAMPLE_CONFIG), "--strategy", "all", "--cycles", "1", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code != 0
    assert payload["error"]["type"] == "SafetyError"
    assert "enabled OKX sandbox" in payload["error"]["message"]


def test_cli_strategy_demo_window_blocks_with_safe_default_config(capsys) -> None:
    code = main(["strategy", "demo-window", "--config", str(EXAMPLE_CONFIG), "--strategy", "triangular-multi-route", "--cycles", "1", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code != 0
    assert payload["error"]["type"] == "SafetyError"
    assert "enabled OKX sandbox" in payload["error"]["message"]


def test_cli_strategy_demo_sampling_blocks_with_safe_default_config(capsys) -> None:
    code = main(["strategy", "demo-sampling", "--config", str(EXAMPLE_CONFIG), "--strategy", "triangular-multi-route", "--windows", "1", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code != 0
    assert payload["error"]["type"] == "SafetyError"
    assert "enabled OKX sandbox" in payload["error"]["message"]


def _okx_opportunity_payload() -> dict:
    opportunity = ArbitrageOpportunity(
        opportunity_id="okx-file-opportunity",
        strategy_type="cross-exchange",
        symbol="BTC/USDT",
        buy_exchange="okx",
        sell_exchange="okx",
        expected_profit=Decimal("2.0"),
        expected_profit_pct=Decimal("2.0"),
        estimated_fee=Decimal("0.2"),
        estimated_slippage=Decimal("0.01"),
        required_capital=Decimal("100"),
        net_profit=Decimal("1.79"),
        risk_score=Decimal("0.2"),
        confidence=Decimal("0.85"),
        metadata={
            "quantity": "0.002",
            "execution_quality": {
                "spread_persistence": {"passed": True},
                "depth_fill": {
                    "buy": {"complete": True},
                    "sell": {"complete": True},
                },
            },
            "legs": [
                {"exchange": "okx", "side": "buy", "market": "spot", "symbol": "BTC/USDT", "price": "50010"},
                {"exchange": "okx", "side": "sell", "market": "spot", "symbol": "BTC/USDT", "price": "50280"},
            ],
        },
    )
    return opportunity.to_dict()
