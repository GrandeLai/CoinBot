"""OKX Demo Trading revival windows for softly archived strategies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from trading_assistant.config.schema import Settings
from trading_assistant.exceptions import SafetyError
from trading_assistant.exchanges.factory import ExchangeFactory
from trading_assistant.strategies.evolution import revival_candidate_names
from trading_assistant.validation.service import StrategyValidationService


ValidationFactory = Callable[[Settings, ExchangeFactory], StrategyValidationService]


class StrategyRevivalWindowService:
    """Run local-first demo validation windows only for revival candidates."""

    def __init__(
        self,
        settings: Settings,
        exchanges: ExchangeFactory,
        validation_service_factory: ValidationFactory | None = None,
    ) -> None:
        self.settings = settings
        self.exchanges = exchanges
        self.validation_service_factory = validation_service_factory or (
            lambda settings, exchanges: StrategyValidationService(settings, exchanges)
        )

    def run(self, strategy_name: str = "all", cycles: int = 1, symbol: str = "BTC/USDT") -> dict[str, Any]:
        """Run local validation then demo window for current revival candidates."""
        candidates = revival_candidate_names(self.settings.strategy_runtime, strategy_name=strategy_name)
        summary: dict[str, Any] = {
            "enabled": self.settings.strategy_runtime.evolution_enabled,
            "strategy_name": strategy_name,
            "cycles": cycles,
            "symbol": symbol,
            "local_first": True,
            "simulation_only": False,
            "candidates": candidates,
            "results": [],
            "orders_sent": False,
            "live_orders_sent": False,
            "reason": None if candidates else "no_revival_candidates",
        }
        if not candidates:
            return summary
        self._assert_okx_demo_config_ready()
        validation = self.validation_service_factory(self.settings, self.exchanges)
        demo_attempted = False
        for candidate in candidates:
            local_payload = validation.validate_local(strategy_name=candidate, cycles=1, symbol=symbol)
            local_validation = dict(local_payload.get("local_validation", {}))
            if local_validation.get("status") != "Pass":
                summary["results"].append(
                    {
                        "strategy_name": candidate,
                        "decision": "skipped",
                        "reason": "local_validation_not_passed",
                        "local_validation": local_validation,
                    }
                )
                continue
            demo_attempted = True
            demo_payload = validation.validate_demo_window(strategy_name=candidate, cycles=cycles, symbol=symbol)
            summary["results"].append(
                {
                    "strategy_name": candidate,
                    "decision": "demo_window_attempted",
                    "local_validation": local_validation,
                    **demo_payload,
                }
            )
            if _payload_sent_orders(demo_payload):
                summary["orders_sent"] = True
            if _payload_sent_live_orders(demo_payload):
                summary["live_orders_sent"] = True
        summary["demo_window_attempted"] = demo_attempted
        return summary

    def _assert_okx_demo_config_ready(self) -> None:
        okx = self.settings.exchanges.get("okx")
        if self.settings.trading.live_trading:
            raise SafetyError("strategy revival window requires trading.live_trading=false")
        if okx is None or not okx.enabled or not okx.sandbox or okx.okx_demo is not True:
            raise SafetyError("strategy revival window requires enabled OKX sandbox with okx_demo=true")
        if not self.settings.agent_trading.allow_demo_orders:
            raise SafetyError("strategy revival window requires agent_trading.allow_demo_orders=true")


def _payload_sent_orders(payload: dict[str, Any]) -> bool:
    run = payload.get("strategy_run", {})
    if not isinstance(run, dict):
        return False
    for result in run.get("results", []):
        if not isinstance(result, dict):
            continue
        execution = result.get("execution") or {}
        if isinstance(execution, dict) and execution.get("demo_orders_sent") is True:
            return True
    return False


def _payload_sent_live_orders(payload: dict[str, Any]) -> bool:
    run = payload.get("strategy_run", {})
    if not isinstance(run, dict):
        return False
    for result in run.get("results", []):
        if not isinstance(result, dict):
            continue
        execution = result.get("execution") or {}
        if isinstance(execution, dict) and execution.get("live_orders_sent") is True:
            return True
    return False
