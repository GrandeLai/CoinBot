"""Isolated candidate-parameter backtests for strategy evolution."""

from __future__ import annotations

import tempfile
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from trading_assistant.config.schema import Settings
from trading_assistant.directional.backtest import DirectionalBacktestEngine
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.strategies.evolution import StrategyEvolutionService
from trading_assistant.strategies.registry import StrategyRegistry
from trading_assistant.strategies.runner import StrategyRunner
from trading_assistant.utils.serialization import to_jsonable


class StrategyCandidateBacktestService:
    """Evaluate evolution parameter candidates in isolated config copies."""

    def __init__(self, settings: Settings, exchanges: ExchangeFactory) -> None:
        self.settings = settings
        self.exchanges = exchanges
        self.registry = StrategyRegistry()

    def run(self, strategy_name: str = "all", symbol: str = "BTC/USDT", limit: int = 50) -> dict[str, Any]:
        """Run candidate backtests without mutating checked-in configs or sending orders."""
        evolution = StrategyEvolutionService(self.settings.strategy_runtime).refresh(
            strategy_name=strategy_name,
            execution_mode="paper",
            limit=limit,
        )
        candidates = [
            candidate
            for candidate in evolution.get("parameter_candidates", [])
            if strategy_name == "all" or candidate.get("strategy_name") in {definition.name for definition in self.registry.expand(strategy_name)}
        ]
        results = [self._evaluate_candidate(dict(candidate), symbol) for candidate in candidates]
        return {
            "strategy_name": strategy_name,
            "symbol": symbol,
            "limit": limit,
            "orders_sent": False,
            "live_orders_sent": False,
            "checked_in_config_modified": False,
            "candidate_count": len(results),
            "candidates": results,
            "evolution_report_path": evolution.get("report_path"),
        }

    def _evaluate_candidate(self, candidate: dict[str, Any], symbol: str) -> dict[str, Any]:
        strategy_name = str(candidate["strategy_name"])
        with tempfile.TemporaryDirectory(prefix="coinbot-candidate-") as directory:
            baseline_settings = self.settings.model_copy(deep=True)
            candidate_settings = self.settings.model_copy(deep=True)
            _isolate_runtime_paths(baseline_settings, Path(directory), "baseline")
            _isolate_runtime_paths(candidate_settings, Path(directory), "candidate")
            applied = _apply_overrides(candidate_settings, dict(candidate.get("parameter_overrides", {})))
            temporary_config = Path(directory) / f"{candidate['candidate_id']}.yaml"
            temporary_config.write_text(
                yaml.safe_dump(to_jsonable(candidate_settings.model_dump(mode="json")), sort_keys=True),
                encoding="utf-8",
            )
            materialized = temporary_config.exists()
            baseline = self._score_strategy(baseline_settings, strategy_name, symbol)
            candidate_score = self._score_strategy(candidate_settings, strategy_name, symbol)
        delta = candidate_score["net_profit_usdt"] - baseline["net_profit_usdt"]
        return {
            "candidate_id": candidate["candidate_id"],
            "strategy_name": strategy_name,
            "source_status": candidate.get("source_status"),
            "parameter_overrides": candidate.get("parameter_overrides", {}),
            "applied_overrides": applied,
            "temporary_config_materialized": materialized,
            "temporary_config_persisted": False,
            "baseline_net_profit_usdt": baseline["net_profit_usdt"],
            "candidate_net_profit_usdt": candidate_score["net_profit_usdt"],
            "delta_net_profit_usdt": delta,
            "baseline_metrics": baseline["metrics"],
            "candidate_metrics": candidate_score["metrics"],
            "accepted_for_demo_probe": candidate_score["net_profit_usdt"] > Decimal("0") and delta >= Decimal("0"),
        }

    def _score_strategy(self, settings: Settings, strategy_name: str, symbol: str) -> dict[str, Any]:
        definition = self.registry.get(strategy_name)
        if definition.category == "directional":
            exchange_name = settings.directional.exchange if settings.directional.exchange in ExchangeFactory(settings).list_enabled() else "mock"
            candles = ExchangeFactory(settings).get(exchange_name).get_candles(
                symbol,
                bar=settings.directional.bar,
                limit=settings.directional.candles_limit,
            )
            result = DirectionalBacktestEngine(
                notional_usdt=settings.directional.max_position_value_usdt,
                fee_pct=settings.directional.fee_pct,
                slippage_pct=settings.directional.slippage_pct,
            ).run(strategy_name, symbol=symbol, exchange=exchange_name, candles=candles)
            return {
                "net_profit_usdt": result.net_pnl_usdt,
                "metrics": result.to_dict(),
            }
        run = StrategyRunner(settings, ExchangeFactory(settings)).run(
            strategy_name=strategy_name,
            max_cycles=1,
            interval_seconds=0,
            execution_mode="paper",
            symbol=symbol,
        )
        net = sum((item.net_profit for item in run.results if item.decision == "executed"), Decimal("0"))
        return {
            "net_profit_usdt": net,
            "metrics": {
                "cycles_completed": run.cycles_completed,
                "executed": sum(1 for item in run.results if item.decision == "executed"),
                "skipped": sum(1 for item in run.results if item.decision == "skipped"),
                "blocked": sum(1 for item in run.results if item.decision == "blocked"),
            },
        }


def _isolate_runtime_paths(settings: Settings, directory: Path, prefix: str) -> None:
    settings.strategy_runtime.journal_path = str(directory / f"{prefix}-strategy-events.jsonl")
    settings.strategy_runtime.runtime_guard_path = str(directory / f"{prefix}-runtime-guard.json")
    settings.strategy_runtime.retrospective_path = str(directory / f"{prefix}-retrospective.md")
    settings.strategy_runtime.retrospective_state_path = str(directory / f"{prefix}-retrospective.state.json")
    settings.strategy_runtime.evolution_state_path = str(directory / f"{prefix}-evolution.state.json")
    settings.strategy_runtime.evolution_report_path = str(directory / f"{prefix}-evolution.md")


def _apply_overrides(settings: Settings, overrides: dict[str, str]) -> dict[str, str]:
    applied: dict[str, str] = {}
    for path, instruction in overrides.items():
        current = _get_nested(settings, path)
        updated = _apply_instruction(current, instruction)
        _set_nested(settings, path, updated)
        applied[path] = str(updated)
    return applied


def _get_nested(settings: Settings, path: str) -> object:
    cursor: object = settings
    for part in path.split("."):
        cursor = getattr(cursor, part)
    return cursor


def _set_nested(settings: Settings, path: str, value: object) -> None:
    parts = path.split(".")
    cursor: object = settings
    for part in parts[:-1]:
        cursor = getattr(cursor, part)
    setattr(cursor, parts[-1], value)


def _apply_instruction(current: object, instruction: str) -> object:
    value = deepcopy(current)
    if isinstance(value, Decimal):
        return _apply_decimal_instruction(value, instruction)
    if isinstance(value, int):
        decimal_result = _apply_decimal_instruction(Decimal(value), instruction)
        return max(int(decimal_result), 1)
    return value


def _apply_decimal_instruction(value: Decimal, instruction: str) -> Decimal:
    if instruction.startswith("increase_by_") and instruction.endswith("_percent"):
        pct = Decimal(instruction.removeprefix("increase_by_").removesuffix("_percent"))
        return value * (Decimal("1") + pct / Decimal("100"))
    if instruction.startswith("reduce_by_") and instruction.endswith("_percent"):
        pct = Decimal(instruction.removeprefix("reduce_by_").removesuffix("_percent"))
        return max(value * (Decimal("1") - pct / Decimal("100")), Decimal("0"))
    if instruction.startswith("increase_by_"):
        return value + Decimal(instruction.removeprefix("increase_by_"))
    if instruction.startswith("reduce_by_"):
        return max(value - Decimal(instruction.removeprefix("reduce_by_")), Decimal("0"))
    if instruction.startswith("stress_test_plus_"):
        return value + Decimal(instruction.removeprefix("stress_test_plus_"))
    return value
