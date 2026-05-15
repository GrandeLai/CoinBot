"""Argparse command line interface for the crypto assistant."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

from trading_assistant.application import TradingAssistantApp
from trading_assistant.exceptions import TradingAssistantError
from trading_assistant.reporting.formatter import format_report_text
from trading_assistant.utils.serialization import to_jsonable


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser with nested commands."""
    parser = argparse.ArgumentParser(prog="crypto-assistant", description="Safe local crypto quantitative trading assistant")
    subcommands = parser.add_subparsers(dest="command")

    status = subcommands.add_parser("status", help="Show assistant status")
    _add_json(status)
    status.set_defaults(handler=_handle_status)

    config = subcommands.add_parser("config", help="Configuration commands")
    config_sub = config.add_subparsers(dest="config_command")
    config_validate = config_sub.add_parser("validate", help="Validate a YAML configuration file")
    config_validate.add_argument("--config", required=True, help="Path to YAML config")
    _add_json(config_validate)
    config_validate.set_defaults(handler=_handle_config_validate)

    exchange = subcommands.add_parser("exchange", help="Exchange commands")
    exchange_sub = exchange.add_subparsers(dest="exchange_command")
    exchange_list = exchange_sub.add_parser("list", help="List configured exchanges")
    exchange_list.add_argument("--config", help="Path to YAML config")
    _add_json(exchange_list)
    exchange_list.set_defaults(handler=_handle_exchange_list)
    exchange_ping = exchange_sub.add_parser("ping", help="Ping an exchange")
    exchange_ping.add_argument("--config", help="Path to YAML config")
    exchange_ping.add_argument("--exchange", required=True, help="Exchange name")
    _add_json(exchange_ping)
    exchange_ping.set_defaults(handler=_handle_exchange_ping)
    sandbox_check = exchange_sub.add_parser("sandbox-check", help="Run non-order sandbox validation checks")
    sandbox_check.add_argument("--config", help="Path to YAML config")
    sandbox_check.add_argument("--exchange", required=True, help="Exchange name")
    sandbox_check.add_argument("--symbol", default="BTC/USDT", help="Trading symbol, e.g. BTC/USDT")
    sandbox_check.add_argument("--include-private", action="store_true", help="Include private account read checks")
    _add_json(sandbox_check)
    sandbox_check.set_defaults(handler=_handle_exchange_sandbox_check)

    market = subcommands.add_parser("market", help="Market data commands")
    market_sub = market.add_subparsers(dest="market_command")
    ticker = market_sub.add_parser("ticker", help="Fetch ticker")
    ticker.add_argument("--config", help="Path to YAML config")
    ticker.add_argument("--exchange", required=True, help="Exchange name")
    ticker.add_argument("--symbol", required=True, help="Trading symbol, e.g. BTC/USDT")
    _add_json(ticker)
    ticker.set_defaults(handler=_handle_market_ticker)
    orderbook = market_sub.add_parser("orderbook", help="Fetch orderbook")
    orderbook.add_argument("--config", help="Path to YAML config")
    orderbook.add_argument("--exchange", required=True, help="Exchange name")
    orderbook.add_argument("--symbol", required=True, help="Trading symbol, e.g. BTC/USDT")
    _add_json(orderbook)
    orderbook.set_defaults(handler=_handle_market_orderbook)
    candles = market_sub.add_parser("candles", help="Fetch completed OHLCV candles")
    candles.add_argument("--config", help="Path to YAML config")
    candles.add_argument("--exchange", required=True, help="Exchange name")
    candles.add_argument("--symbol", required=True, help="Trading symbol, e.g. BTC/USDT")
    candles.add_argument("--bar", default="15m", help="Candle bar, e.g. 15m, 1H, 1D")
    candles.add_argument("--limit", type=int, default=100, help="Maximum candle rows")
    candles.add_argument("--history", action="store_true", help="Use historical candle endpoint when supported")
    _add_json(candles)
    candles.set_defaults(handler=_handle_market_candles)

    account = subcommands.add_parser("account", help="Account commands")
    account_sub = account.add_subparsers(dest="account_command")
    balance = account_sub.add_parser("balance", help="Fetch balances")
    balance.add_argument("--config", help="Path to YAML config")
    balance.add_argument("--exchange", required=True, help="Exchange name")
    _add_json(balance)
    balance.set_defaults(handler=_handle_account_balance)

    arbitrage = subcommands.add_parser("arbitrage", help="Arbitrage commands")
    arbitrage_sub = arbitrage.add_subparsers(dest="arbitrage_command")
    scan = arbitrage_sub.add_parser("scan", help="Scan arbitrage opportunities")
    scan.add_argument(
        "--type",
        required=True,
        choices=[
            "cross-exchange",
            "triangular",
            "triangular-multi-route",
            "funding-rate",
            "funding-carry-hedged",
            "spot-perp",
            "spot-perp-carry",
            "futures-perp-basis",
        ],
        help="Arbitrage type",
    )
    scan.add_argument("--symbol", help="Trading symbol")
    scan.add_argument("--exchange", help="Exchange name for single-exchange scans")
    _add_json(scan)
    scan.set_defaults(handler=_handle_arbitrage_scan)
    execute = arbitrage_sub.add_parser("execute", help="Dry-run execute an opportunity")
    execute.add_argument("--opportunity-id", required=True, help="Opportunity ID")
    execute.add_argument("--dry-run", action="store_true", help="Simulate without live orders")
    _add_json(execute)
    execute.set_defaults(handler=_handle_arbitrage_execute)

    agent = subcommands.add_parser("agent", help="Autonomous agent trading commands")
    agent_sub = agent.add_subparsers(dest="agent_command")
    live_readiness = agent_sub.add_parser("live-readiness", help="Check autonomous live-trading readiness")
    live_readiness.add_argument("--config", help="Path to YAML config")
    live_readiness_source = live_readiness.add_mutually_exclusive_group(required=True)
    live_readiness_source.add_argument("--opportunity-id", help="Opportunity ID")
    live_readiness_source.add_argument("--opportunity-file", help="Path to opportunity JSON file")
    _add_json(live_readiness)
    live_readiness.set_defaults(handler=_handle_agent_live_readiness)
    execute_live = agent_sub.add_parser("execute-live", help="Attempt autonomous live execution after strict safety gates")
    execute_live.add_argument("--config", help="Path to YAML config")
    execute_live_source = execute_live.add_mutually_exclusive_group(required=True)
    execute_live_source.add_argument("--opportunity-id", help="Opportunity ID")
    execute_live_source.add_argument("--opportunity-file", help="Path to opportunity JSON file")
    _add_json(execute_live)
    execute_live.set_defaults(handler=_handle_agent_execute_live)
    operation_catalog = agent_sub.add_parser("operation-catalog", help="List demo validation contracts for live-capable operations")
    _add_json(operation_catalog)
    operation_catalog.set_defaults(handler=_handle_agent_operation_catalog)

    backtest = subcommands.add_parser("backtest", help="Backtest commands")
    backtest_sub = backtest.add_subparsers(dest="backtest_command")
    run = backtest_sub.add_parser("run", help="Run deterministic mock backtest")
    run.add_argument("--config", help="Path to YAML config")
    _add_json(run)
    run.set_defaults(handler=_handle_backtest_run)

    report = subcommands.add_parser("report", help="Report commands")
    report_sub = report.add_subparsers(dest="report_command")
    generate = report_sub.add_parser("generate", help="Generate report")
    generate.add_argument("--type", default="daily", choices=["daily"], help="Report type")
    _add_json(generate)
    generate.set_defaults(handler=_handle_report_generate)

    workflow = subcommands.add_parser("workflow", help="End-to-end workflow commands")
    workflow_sub = workflow.add_subparsers(dest="workflow_command")
    workflow_run = workflow_sub.add_parser("run", help="Run mock -> backtest -> paper -> sandbox/live readiness route")
    workflow_run.add_argument("--config", help="Path to YAML config")
    workflow_run.add_argument("--symbol", default="BTC/USDT", help="Trading symbol, e.g. BTC/USDT")
    _add_json(workflow_run)
    workflow_run.set_defaults(handler=_handle_workflow_run)

    autopilot = subcommands.add_parser("autopilot", help="Detached paper/demo autopilot commands")
    autopilot_sub = autopilot.add_subparsers(dest="autopilot_command")
    autopilot_run = autopilot_sub.add_parser("run", help="Run detached paper/demo autopilot cycles")
    autopilot_run.add_argument("--config", help="Path to YAML config")
    autopilot_run.add_argument("--mode", choices=["paper", "demo"], default="paper", help="Autopilot execution mode")
    autopilot_run.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    autopilot_run.add_argument("--symbol", default="BTC/USDT", help="Trading symbol, e.g. BTC/USDT")
    autopilot_run.add_argument("--cycles", type=int, default=1, help="Autopilot cycles; 0 means run until stopped")
    autopilot_run.add_argument("--interval-seconds", type=int, help="Delay between cycles; defaults to config")
    autopilot_run.add_argument("--demo-cycles-per-window", type=int, default=3, help="Demo validation cycles per autopilot demo window")
    autopilot_run.add_argument("--target-exchange", default="okx", help="Target exchange for demo health and market checks")
    autopilot_run.add_argument("--report-limit", type=int, default=50, help="Number of recent validation events to inspect")
    autopilot_run.add_argument("--public-health-only", action="store_true", help="Skip private account read during demo health checks")
    _add_json(autopilot_run)
    autopilot_run.set_defaults(handler=_handle_autopilot_run)

    autopilot_status = autopilot_sub.add_parser("status", help="Show latest autopilot state")
    autopilot_status.add_argument("--config", help="Path to YAML config")
    _add_json(autopilot_status)
    autopilot_status.set_defaults(handler=_handle_autopilot_status)

    autopilot_report = autopilot_sub.add_parser("report", help="Show read-only autopilot report")
    autopilot_report.add_argument("--config", help="Path to YAML config")
    autopilot_report.add_argument("--mode", choices=["paper", "demo"], default="paper", help="Report execution mode")
    autopilot_report.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    autopilot_report.add_argument("--report-limit", type=int, default=50, help="Number of recent validation events to inspect")
    _add_json(autopilot_report)
    autopilot_report.set_defaults(handler=_handle_autopilot_report)

    strategy = subcommands.add_parser("strategy", help="Production strategy runtime commands")
    strategy_sub = strategy.add_subparsers(dest="strategy_command")
    strategy_list = strategy_sub.add_parser("list", help="List registered strategies")
    _add_json(strategy_list)
    strategy_list.set_defaults(handler=_handle_strategy_list)
    strategy_catalog = strategy_sub.add_parser("catalog", help="Show strategy platform catalog")
    strategy_catalog.add_argument("--config", help="Path to YAML config")
    _add_json(strategy_catalog)
    strategy_catalog.set_defaults(handler=_handle_strategy_catalog)
    strategy_scan = strategy_sub.add_parser("scan", help="Scan strategies through the platform controller")
    strategy_scan.add_argument("--config", help="Path to YAML config")
    strategy_scan.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    strategy_scan.add_argument("--symbol", default="BTC/USDT", help="Trading symbol, e.g. BTC/USDT")
    strategy_scan.add_argument("--exchange", help="Exchange name for single-exchange scans")
    strategy_scan.add_argument(
        "--route-mode",
        choices=["configured", "discovered"],
        default="configured",
        help="Triangular route source",
    )
    _add_json(strategy_scan)
    strategy_scan.set_defaults(handler=_handle_strategy_scan)
    strategy_discover_routes = strategy_sub.add_parser("discover-routes", help="Discover triangular routes from exchange instruments")
    strategy_discover_routes.add_argument("--config", help="Path to YAML config")
    strategy_discover_routes.add_argument("--exchange", default="mock", help="Exchange name")
    strategy_discover_routes.add_argument("--quote", default="USDT", help="Route quote asset")
    strategy_discover_routes.add_argument("--route-limit", type=int, default=100, help="Maximum accepted routes")
    _add_json(strategy_discover_routes)
    strategy_discover_routes.set_defaults(handler=_handle_strategy_discover_routes)
    strategy_opportunity_report = strategy_sub.add_parser("opportunity-report", help="Summarize read-only opportunity density evidence")
    strategy_opportunity_report.add_argument("--config", help="Path to YAML config")
    strategy_opportunity_report.add_argument("--window", default="24h", help="Journal window, e.g. 24h or 7d")
    _add_json(strategy_opportunity_report)
    strategy_opportunity_report.set_defaults(handler=_handle_strategy_opportunity_report)
    strategy_score = strategy_sub.add_parser("score", help="Score strategy opportunities and validation evidence")
    strategy_score.add_argument("--config", help="Path to YAML config")
    strategy_score.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    strategy_score.add_argument("--symbol", default="BTC/USDT", help="Trading symbol, e.g. BTC/USDT")
    _add_json(strategy_score)
    strategy_score.set_defaults(handler=_handle_strategy_score)
    strategy_market_compare = strategy_sub.add_parser("market-compare", help="Compare mock baseline scans with a target exchange")
    strategy_market_compare.add_argument("--config", help="Path to YAML config")
    strategy_market_compare.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    strategy_market_compare.add_argument("--symbol", default="BTC/USDT", help="Trading symbol, e.g. BTC/USDT")
    strategy_market_compare.add_argument("--target-exchange", help="Enabled target exchange to compare against the mock baseline")
    _add_json(strategy_market_compare)
    strategy_market_compare.set_defaults(handler=_handle_strategy_market_compare)
    strategy_portfolio_status = strategy_sub.add_parser("portfolio-status", help="Show strategy portfolio selection status")
    strategy_portfolio_status.add_argument("--config", help="Path to YAML config")
    strategy_portfolio_status.add_argument("--symbol", default="BTC/USDT", help="Trading symbol, e.g. BTC/USDT")
    _add_json(strategy_portfolio_status)
    strategy_portfolio_status.set_defaults(handler=_handle_strategy_portfolio_status)
    strategy_run = strategy_sub.add_parser("run", help="Run strategies through controlled paper/demo runtime")
    strategy_run.add_argument("--config", help="Path to YAML config")
    strategy_run.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    strategy_run.add_argument("--symbol", default="BTC/USDT", help="Trading symbol, e.g. BTC/USDT")
    strategy_run.add_argument("--max-cycles", type=int, default=1, help="Maximum cycles; 0 means run until stopped")
    strategy_run.add_argument("--interval-seconds", type=int, default=0, help="Delay between cycles")
    strategy_run.add_argument("--execution-mode", choices=["paper", "demo"], help="Execution mode; defaults to config")
    _add_json(strategy_run)
    strategy_run.set_defaults(handler=_handle_strategy_run)
    strategy_review = strategy_sub.add_parser("review", help="Review strategy journal and emit learning suggestions")
    strategy_review.add_argument("--config", help="Path to YAML config")
    strategy_review.add_argument("--execution-mode", choices=["paper", "demo"], help="Filter review to one execution mode")
    _add_json(strategy_review)
    strategy_review.set_defaults(handler=_handle_strategy_review)
    strategy_retrospective = strategy_sub.add_parser("retrospective", help="Refresh and show strategy retrospective memory")
    strategy_retrospective.add_argument("--config", help="Path to YAML config")
    strategy_retrospective.add_argument("--execution-mode", choices=["paper", "demo"], help="Filter retrospective refresh to one execution mode")
    _add_json(strategy_retrospective)
    strategy_retrospective.set_defaults(handler=_handle_strategy_retrospective)
    strategy_evolve = strategy_sub.add_parser("evolve", help="Refresh simulation-only strategy evolution and archive decisions")
    strategy_evolve.add_argument("--config", help="Path to YAML config")
    strategy_evolve.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    strategy_evolve.add_argument("--execution-mode", choices=["paper", "demo"], help="Filter evolution evidence to one execution mode")
    strategy_evolve.add_argument("--limit", type=int, default=50, help="Number of latest matching events considered for reporting")
    _add_json(strategy_evolve)
    strategy_evolve.set_defaults(handler=_handle_strategy_evolve)
    strategy_revival_window = strategy_sub.add_parser("revival-window", help="Run local-first OKX demo windows for revival candidates")
    strategy_revival_window.add_argument("--config", help="Path to YAML config")
    strategy_revival_window.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    strategy_revival_window.add_argument("--cycles", type=int, default=1, help="Number of OKX demo validation cycles per candidate")
    strategy_revival_window.add_argument("--symbol", default="BTC/USDT", help="Trading symbol, e.g. BTC/USDT")
    _add_json(strategy_revival_window)
    strategy_revival_window.set_defaults(handler=_handle_strategy_revival_window)
    strategy_candidate_backtest = strategy_sub.add_parser("candidate-backtest", help="Backtest strategy evolution parameter candidates in isolated configs")
    strategy_candidate_backtest.add_argument("--config", help="Path to YAML config")
    strategy_candidate_backtest.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    strategy_candidate_backtest.add_argument("--symbol", default="BTC/USDT", help="Trading symbol, e.g. BTC/USDT")
    strategy_candidate_backtest.add_argument("--limit", type=int, default=50, help="Number of latest journal events considered for candidate generation")
    _add_json(strategy_candidate_backtest)
    strategy_candidate_backtest.set_defaults(handler=_handle_strategy_candidate_backtest)
    strategy_validation_report = strategy_sub.add_parser("validation-report", help="Summarize recent strategy validation evidence")
    strategy_validation_report.add_argument("--config", help="Path to YAML config")
    strategy_validation_report.add_argument("--execution-mode", choices=["paper", "demo"], help="Filter report to one execution mode")
    strategy_validation_report.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    strategy_validation_report.add_argument("--limit", type=int, default=50, help="Number of latest matching journal events to summarize")
    _add_json(strategy_validation_report)
    strategy_validation_report.set_defaults(handler=_handle_strategy_validation_report)
    strategy_operator_brief = strategy_sub.add_parser("operator-brief", help="Show read-only operator safety and validation brief")
    strategy_operator_brief.add_argument("--config", help="Path to YAML config")
    strategy_operator_brief.add_argument("--execution-mode", choices=["paper", "demo"], help="Filter brief to one execution mode")
    strategy_operator_brief.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    strategy_operator_brief.add_argument("--limit", type=int, default=50, help="Number of latest matching journal events to summarize")
    _add_json(strategy_operator_brief)
    strategy_operator_brief.set_defaults(handler=_handle_strategy_operator_brief)
    strategy_pnl_attribution = strategy_sub.add_parser("pnl-attribution", help="Show read-only strategy PnL attribution ledger")
    strategy_pnl_attribution.add_argument("--config", help="Path to YAML config")
    strategy_pnl_attribution.add_argument("--execution-mode", choices=["paper", "demo"], help="Filter report to one execution mode")
    strategy_pnl_attribution.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    strategy_pnl_attribution.add_argument("--limit", type=int, default=50, help="Number of latest matching journal events to include")
    _add_json(strategy_pnl_attribution)
    strategy_pnl_attribution.set_defaults(handler=_handle_strategy_pnl_attribution)
    strategy_carry_basis_optimize = strategy_sub.add_parser("carry-basis-optimize", help="Show read-only carry/basis optimization diagnostics")
    strategy_carry_basis_optimize.add_argument("--config", help="Path to YAML config")
    strategy_carry_basis_optimize.add_argument("--symbol", default="BTC/USDT", help="Trading symbol, e.g. BTC/USDT")
    _add_json(strategy_carry_basis_optimize)
    strategy_carry_basis_optimize.set_defaults(handler=_handle_strategy_carry_basis_optimize)
    strategy_guard_status = strategy_sub.add_parser("guard-status", help="Show stateful strategy runtime guard status")
    strategy_guard_status.add_argument("--config", help="Path to YAML config")
    strategy_guard_status.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    strategy_guard_status.add_argument("--execution-mode", choices=["paper", "demo"], help="Filter guard status to one execution mode")
    _add_json(strategy_guard_status)
    strategy_guard_status.set_defaults(handler=_handle_strategy_guard_status)
    strategy_validate_demo = strategy_sub.add_parser("validate-demo", help="Validate strategies through tiny OKX demo submit/cancel checks")
    strategy_validate_demo.add_argument("--config", required=True, help="Path to OKX demo YAML config")
    strategy_validate_demo.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    strategy_validate_demo.add_argument("--symbol", default="BTC/USDT", help="Trading symbol used by the local first-layer validation")
    strategy_validate_demo.add_argument(
        "--allow-account-mode-switch",
        action="store_true",
        help="Allow OKX demo account to switch from spot mode to futures mode for swap validation",
    )
    _add_json(strategy_validate_demo)
    strategy_validate_demo.set_defaults(handler=_handle_strategy_validate_demo)
    strategy_validate_local = strategy_sub.add_parser("validate-local", help="Run local paper validation before demo promotion")
    strategy_validate_local.add_argument("--config", help="Path to YAML config")
    strategy_validate_local.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    strategy_validate_local.add_argument("--cycles", type=int, default=1, help="Number of local validation cycles")
    strategy_validate_local.add_argument("--symbol", default="BTC/USDT", help="Trading symbol, e.g. BTC/USDT")
    _add_json(strategy_validate_local)
    strategy_validate_local.set_defaults(handler=_handle_strategy_validate_local)
    strategy_validate_demo_window = strategy_sub.add_parser(
        "validate-demo-window",
        help="Run an OKX Demo Trading validation window before live-canary promotion",
    )
    strategy_validate_demo_window.add_argument("--config", required=True, help="Path to OKX demo YAML config")
    strategy_validate_demo_window.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    strategy_validate_demo_window.add_argument("--cycles", type=int, default=5, help="Number of demo validation cycles")
    strategy_validate_demo_window.add_argument("--symbol", default="BTC/USDT", help="Trading symbol, e.g. BTC/USDT")
    _add_json(strategy_validate_demo_window)
    strategy_validate_demo_window.set_defaults(handler=_handle_strategy_validate_demo_window)
    strategy_demo_window = strategy_sub.add_parser(
        "demo-window",
        help="Run a safety-gated OKX Demo Trading window orchestration",
    )
    strategy_demo_window.add_argument("--config", required=True, help="Path to OKX demo YAML config")
    strategy_demo_window.add_argument("--strategy", default="triangular-multi-route", help="Strategy name")
    strategy_demo_window.add_argument("--cycles", type=int, default=3, help="Number of demo validation cycles")
    strategy_demo_window.add_argument("--symbol", default="BTC/USDT", help="Trading symbol, e.g. BTC/USDT")
    strategy_demo_window.add_argument("--target-exchange", default="okx", help="Enabled target exchange for health and market checks")
    strategy_demo_window.add_argument("--report-limit", type=int, default=30, help="Number of rolling demo events to inspect before execution")
    strategy_demo_window.add_argument(
        "--public-health-only",
        action="store_true",
        help="Skip private account read during the no-order health check",
    )
    _add_json(strategy_demo_window)
    strategy_demo_window.set_defaults(handler=_handle_strategy_demo_window)
    strategy_demo_sampling = strategy_sub.add_parser(
        "demo-sampling",
        help="Run bounded same-size OKX Demo Trading sampling windows",
    )
    strategy_demo_sampling.add_argument("--config", required=True, help="Path to OKX demo YAML config")
    strategy_demo_sampling.add_argument("--strategy", default="triangular-multi-route", help="Strategy name")
    strategy_demo_sampling.add_argument("--windows", type=int, default=3, help="Number of demo windows")
    strategy_demo_sampling.add_argument("--cycles-per-window", type=int, default=3, help="Demo validation cycles per window")
    strategy_demo_sampling.add_argument("--interval-seconds", type=int, default=0, help="Delay between successful windows")
    strategy_demo_sampling.add_argument("--symbol", default="BTC/USDT", help="Trading symbol, e.g. BTC/USDT")
    strategy_demo_sampling.add_argument("--target-exchange", default="okx", help="Enabled target exchange for health and market checks")
    strategy_demo_sampling.add_argument("--report-limit", type=int, default=30, help="Number of rolling demo events to inspect before each window")
    strategy_demo_sampling.add_argument(
        "--public-health-only",
        action="store_true",
        help="Skip private account read during the no-order health check",
    )
    _add_json(strategy_demo_sampling)
    strategy_demo_sampling.set_defaults(handler=_handle_strategy_demo_sampling)
    strategy_promotion_status = strategy_sub.add_parser("promotion-status", help="Show local/demo/live-canary promotion status")
    strategy_promotion_status.add_argument("--config", help="Path to YAML config")
    strategy_promotion_status.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    _add_json(strategy_promotion_status)
    strategy_promotion_status.set_defaults(handler=_handle_strategy_promotion_status)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint returning a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 0
    try:
        payload, text = args.handler(args)
    except TradingAssistantError as exc:
        return _emit_error(exc, json_output=getattr(args, "json", False))
    except Exception as exc:  # pragma: no cover - defensive CLI safety net
        return _emit_error(exc, json_output=getattr(args, "json", False))
    _emit(payload, text, json_output=getattr(args, "json", False))
    return 0


def _add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")


def _app(args: argparse.Namespace) -> TradingAssistantApp:
    return TradingAssistantApp(config_path=getattr(args, "config", None))


def _handle_status(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).status()
    return payload, f"status={payload['status']} dry_run={payload['safety']['dry_run']}"


def _handle_config_validate(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).validate_config()
    return payload, "config valid"


def _handle_exchange_list(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).exchange_list()
    names = ", ".join(item["name"] for item in payload["exchanges"] if item["enabled"])
    return payload, f"enabled exchanges: {names}"


def _handle_exchange_ping(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).exchange_ping(args.exchange)
    return payload, f"{args.exchange}: ok={payload['ok']}"


def _handle_exchange_sandbox_check(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).exchange_sandbox_check(args.exchange, args.symbol, include_private=args.include_private)
    result = payload["sandbox_check"]
    return payload, f"{args.exchange} sandbox_ok={result['ok']} live_orders_sent={result['live_orders_sent']}"


def _handle_market_ticker(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).market_ticker(args.exchange, args.symbol)
    ticker = payload["ticker"]
    return payload, f"{ticker['exchange']} {ticker['symbol']} bid={ticker['bid']} ask={ticker['ask']}"


def _handle_market_orderbook(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).market_orderbook(args.exchange, args.symbol)
    orderbook = payload["orderbook"]
    return payload, f"{orderbook['exchange']} {orderbook['symbol']} bids={len(orderbook['bids'])} asks={len(orderbook['asks'])}"


def _handle_market_candles(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).market_candles(args.exchange, args.symbol, args.bar, args.limit, history=args.history)
    return payload, f"{args.exchange} {args.symbol} candles={len(payload['candles'])}"


def _handle_account_balance(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).account_balance(args.exchange)
    return payload, f"{args.exchange} balances loaded"


def _handle_arbitrage_scan(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).arbitrage_scan(args.type, symbol=args.symbol, exchange=args.exchange)
    return payload, f"opportunities={len(payload['opportunities'])}"


def _handle_arbitrage_execute(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).arbitrage_execute(args.opportunity_id, dry_run=args.dry_run or None)
    return payload, f"execution={payload['execution']['status']} dry_run={payload['execution']['dry_run']}"


def _handle_agent_live_readiness(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).agent_live_readiness(opportunity_id=args.opportunity_id, opportunity_file=args.opportunity_file)
    readiness = payload["agent_live_readiness"]
    return payload, f"agent_live_ready={readiness['ready']}"


def _handle_agent_execute_live(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).agent_execute_live(opportunity_id=args.opportunity_id, opportunity_file=args.opportunity_file)
    return payload, "agent live execution requested"


def _handle_agent_operation_catalog(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).agent_operation_catalog()
    missing = len(payload["operation_catalog"]["missing_demo_validation"])
    return payload, f"operation catalog loaded missing_demo_validation={missing}"


def _handle_backtest_run(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).backtest_run()
    return payload, f"backtest trades={payload['backtest']['metrics']['trades']}"


def _handle_report_generate(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).report_generate(args.type)
    return payload, format_report_text(payload["report"])


def _handle_workflow_run(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).workflow_run(symbol=args.symbol)
    workflow = payload["workflow"]
    return payload, f"workflow completed={workflow['completed']} live_ready={workflow['live_ready']}"


def _handle_autopilot_run(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).autopilot_run(
        mode=args.mode,
        strategy_name=args.strategy,
        symbol=args.symbol,
        cycles=args.cycles,
        interval_seconds=args.interval_seconds,
        demo_cycles_per_window=args.demo_cycles_per_window,
        target_exchange=args.target_exchange,
        report_limit=args.report_limit,
        include_private_health=not args.public_health_only,
    )
    result = payload["autopilot_run"]
    return payload, f"autopilot status={result['status']} cycles={result['cycles_completed']} stopped_reason={result['stopped_reason']}"


def _handle_autopilot_status(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).autopilot_status()
    state = payload["autopilot_status"]
    return payload, f"autopilot status={state['status']} cycles={state['cycles_completed']}"


def _handle_autopilot_report(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).autopilot_report(
        mode=args.mode,
        strategy_name=args.strategy,
        report_limit=args.report_limit,
    )
    report = payload["autopilot_report"]
    return payload, f"autopilot report status={report['state']['status']} live_orders_sent={report['live_orders_sent']}"


def _handle_strategy_list(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_list()
    return payload, f"strategies={len(payload['strategies'])}"


def _handle_strategy_catalog(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_catalog()
    catalog = payload["strategy_catalog"]
    return payload, f"strategy_catalog strategies={len(catalog['strategies'])} aliases={len(catalog['aliases'])}"


def _handle_strategy_scan(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_scan(
        strategy_name=args.strategy,
        symbol=args.symbol,
        exchange=args.exchange,
        route_mode=args.route_mode,
    )
    opportunity_count = sum(len(report["opportunities"]) for report in payload["strategy_scan"])
    return payload, f"strategy_scan reports={len(payload['strategy_scan'])} opportunities={opportunity_count}"


def _handle_strategy_discover_routes(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_discover_routes(
        exchange=args.exchange,
        quote=args.quote,
        route_limit=args.route_limit,
    )
    report = payload["strategy_discover_routes"]
    return payload, (
        f"strategy_discover_routes exchange={report['exchange']} "
        f"accepted={len(report['accepted_routes'])} filtered={len(report['filtered_routes'])}"
    )


def _handle_strategy_opportunity_report(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_opportunity_report(window=args.window)
    report = payload["strategy_opportunity_report"]
    return payload, (
        f"strategy_opportunity_report scans={report['scan_count']} "
        f"candidates={report['demo_preflight_candidate_count']} executed={report['executed_count']}"
    )


def _handle_strategy_score(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_score(strategy_name=args.strategy, symbol=args.symbol)
    return payload, f"strategy_score cards={len(payload['strategy_score'])}"


def _handle_strategy_market_compare(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_market_compare(
        strategy_name=args.strategy,
        symbol=args.symbol,
        target_exchange=args.target_exchange,
    )
    result = payload["strategy_market_compare"]
    candidates = sum(1 for item in result["comparisons"] if item["verdict"] == "demo_preflight_candidate")
    return payload, f"strategy_market_compare target={result['target_exchange']} demo_preflight_candidates={candidates}"


def _handle_strategy_portfolio_status(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_portfolio_status(symbol=args.symbol)
    status = payload["strategy_portfolio_status"]
    return payload, f"strategy_portfolio selected={len(status['selected_strategies'])} blocked={len(status['blocked_strategies'])}"


def _handle_strategy_run(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_run(
        strategy_name=args.strategy,
        max_cycles=args.max_cycles,
        interval_seconds=args.interval_seconds,
        execution_mode=args.execution_mode,
        symbol=args.symbol,
    )
    result = payload["strategy_run"]
    return payload, f"strategy_run completed={result['completed']} cycles={result['cycles_completed']}"


def _handle_strategy_review(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_review(execution_mode=args.execution_mode)
    return payload, f"strategy_review events={payload['strategy_review']['total_events']}"


def _handle_strategy_retrospective(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_retrospective(execution_mode=args.execution_mode)
    summary = payload["strategy_retrospective"]
    return payload, f"strategy_retrospective open_issues={summary['open_issue_count']}"


def _handle_strategy_evolve(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_evolve(
        strategy_name=args.strategy,
        execution_mode=args.execution_mode,
        limit=args.limit,
    )
    summary = payload["strategy_evolution"]
    return payload, (
        f"strategy_evolution archived={len(summary['archived_strategies'])} "
        f"revive_candidates={len(summary['revive_candidates'])}"
    )


def _handle_strategy_revival_window(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_revival_window(
        strategy_name=args.strategy,
        cycles=args.cycles,
        symbol=args.symbol,
    )
    summary = payload["strategy_revival_window"]
    return payload, (
        f"strategy_revival_window candidates={len(summary['candidates'])} "
        f"demo_window_attempted={summary.get('demo_window_attempted', False)}"
    )


def _handle_strategy_candidate_backtest(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_candidate_backtest(
        strategy_name=args.strategy,
        symbol=args.symbol,
        limit=args.limit,
    )
    summary = payload["strategy_candidate_backtest"]
    return payload, (
        f"strategy_candidate_backtest candidates={summary['candidate_count']} "
        f"orders_sent={summary['orders_sent']}"
    )


def _handle_strategy_validation_report(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_validation_report(
        execution_mode=args.execution_mode,
        strategy_name=args.strategy,
        limit=args.limit,
    )
    report = payload["strategy_validation_report"]
    total = report["total"]
    return payload, f"strategy_validation_report events={report['scanned_events']} executed={total['executed']}"


def _handle_strategy_operator_brief(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_operator_brief(
        execution_mode=args.execution_mode,
        strategy_name=args.strategy,
        limit=args.limit,
    )
    brief = payload["strategy_operator_brief"]
    cooldowns = sum(1 for entry in brief["guard"]["entries"] if entry["cooldown_active"])
    return payload, (
        f"strategy_operator_brief read_only={brief['read_only']} "
        f"cooldowns={cooldowns} recommendations={len(brief['recommendations'])}"
    )


def _handle_strategy_pnl_attribution(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_pnl_attribution(
        execution_mode=args.execution_mode,
        strategy_name=args.strategy,
        limit=args.limit,
    )
    report = payload["strategy_pnl_attribution"]
    summary = report["summary"]
    return payload, (
        f"strategy_pnl_attribution entries={summary['total_entries']} "
        f"cash_flow={summary['strategy_cash_flow_net_pnl_usdt']}"
    )


def _handle_strategy_carry_basis_optimize(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_carry_basis_optimize(symbol=args.symbol)
    report = payload["strategy_carry_basis_optimization"]
    summary = report["summary"]
    return payload, (
        f"strategy_carry_basis_optimization blocked={summary['blocked_count']} "
        f"demo_ready={summary['demo_ready_count']}"
    )


def _handle_strategy_guard_status(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_guard_status(strategy_name=args.strategy, execution_mode=args.execution_mode)
    status = payload["strategy_guard_status"]
    active = sum(1 for entry in status["entries"] if entry["cooldown_active"])
    return payload, f"strategy_guard entries={len(status['entries'])} cooldown_active={active}"


def _handle_strategy_validate_demo(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_validate_demo(
        strategy_name=args.strategy,
        allow_account_mode_switch=args.allow_account_mode_switch,
        symbol=args.symbol,
    )
    result = payload["strategy_demo_validation"]
    return payload, f"strategy_demo_validation completed={result['completed']}"


def _handle_strategy_validate_local(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_validate_local(
        strategy_name=args.strategy,
        cycles=args.cycles,
        symbol=args.symbol,
    )
    result = payload["local_validation"]
    return payload, f"local_validation status={result['status']} executed={result['metrics']['executed']}"


def _handle_strategy_validate_demo_window(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_validate_demo_window(
        strategy_name=args.strategy,
        cycles=args.cycles,
        symbol=args.symbol,
    )
    result = payload["demo_window_validation"]
    return payload, f"demo_window_validation status={result['status']} executed={result['metrics']['executed']}"


def _handle_strategy_demo_window(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_demo_window(
        strategy_name=args.strategy,
        cycles=args.cycles,
        symbol=args.symbol,
        target_exchange=args.target_exchange,
        report_limit=args.report_limit,
        include_private_health=not args.public_health_only,
    )
    result = payload["strategy_demo_window_orchestration"]
    return payload, f"strategy_demo_window status={result['status']} orders_attempted={result['orders_attempted']}"


def _handle_strategy_demo_sampling(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_demo_sampling(
        strategy_name=args.strategy,
        windows=args.windows,
        cycles_per_window=args.cycles_per_window,
        interval_seconds=args.interval_seconds,
        symbol=args.symbol,
        target_exchange=args.target_exchange,
        report_limit=args.report_limit,
        include_private_health=not args.public_health_only,
    )
    result = payload["strategy_demo_sampling"]
    return payload, (
        f"strategy_demo_sampling status={result['status']} "
        f"windows_completed={result['windows_completed']} stop_reason={result['stop_reason']}"
    )


def _handle_strategy_promotion_status(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    payload = _app(args).strategy_promotion_status(strategy_name=args.strategy)
    statuses = payload["strategy_promotion_status"]
    promotable = sum(1 for item in statuses if item["promotable_to_live_canary"])
    return payload, f"strategy_promotion_status strategies={len(statuses)} promotable_to_live_canary={promotable}"


def _emit(payload: dict[str, Any], text: str, json_output: bool) -> None:
    """Print command output."""
    if json_output:
        print(json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2))
    else:
        print(text)


def _emit_error(exc: Exception, json_output: bool) -> int:
    """Print a clear error and return non-zero exit code."""
    code = getattr(exc, "exit_code", 1)
    if json_output:
        print(
            json.dumps(
                {"error": {"type": exc.__class__.__name__, "message": str(exc)}},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"{exc.__class__.__name__}: {exc}", file=sys.stderr)
    return int(code)
