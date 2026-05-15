"""Same-size OKX demo sampling schedule orchestration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from trading_assistant.utils.serialization import to_jsonable


WindowRunner = Callable[[], dict[str, Any]]
Sleeper = Callable[[int], None]


class StrategyDemoSamplingScheduler:
    """Run bounded same-size demo windows until sampling should stop."""

    def __init__(self, window_runner: WindowRunner, sleeper: Sleeper) -> None:
        self.window_runner = window_runner
        self.sleeper = sleeper

    def run(
        self,
        strategy_name: str,
        target_strategy_names: list[str],
        windows: int,
        cycles_per_window: int,
        symbol: str,
        interval_seconds: int,
        size_stage: dict[str, Any],
    ) -> dict[str, Any]:
        """Run a bounded sampling schedule using the same demo size settings."""
        requested_windows = max(windows, 1)
        requested_cycles = max(cycles_per_window, 1)
        sleep_seconds = max(interval_seconds, 0)
        window_records: list[dict[str, Any]] = []
        windows_completed = 0
        stop_reason: str | None = None
        orders_attempted = False
        live_orders_sent = False

        for index in range(1, requested_windows + 1):
            raw_payload = self.window_runner()
            orchestration = _orchestration_payload(raw_payload)
            window_orders_attempted = bool(orchestration.get("orders_attempted"))
            window_live_orders_sent = bool(orchestration.get("live_orders_sent"))
            block_reasons = [str(reason) for reason in orchestration.get("block_reasons", [])]
            status = str(orchestration.get("status", "Unknown"))
            completed = bool(orchestration.get("completed"))
            orders_attempted = orders_attempted or window_orders_attempted
            live_orders_sent = live_orders_sent or window_live_orders_sent
            window_records.append(
                {
                    "window_index": index,
                    "status": status,
                    "completed": completed,
                    "orders_attempted": window_orders_attempted,
                    "live_orders_sent": window_live_orders_sent,
                    "block_reasons": block_reasons,
                    "payload": raw_payload,
                }
            )

            stop_reason = _stop_reason(status, completed, block_reasons, window_orders_attempted, window_live_orders_sent)
            if stop_reason is not None:
                break
            windows_completed += 1
            if index < requested_windows and sleep_seconds > 0:
                self.sleeper(sleep_seconds)

        return to_jsonable(
            {
                "status": "Completed" if windows_completed == requested_windows and stop_reason is None else "Stopped",
                "completed": windows_completed == requested_windows and stop_reason is None,
                "strategy_name": strategy_name,
                "target_strategy_names": target_strategy_names,
                "windows_requested": requested_windows,
                "windows_completed": windows_completed,
                "cycles_per_window": requested_cycles,
                "symbol": symbol,
                "interval_seconds": sleep_seconds,
                "same_size_enforced": True,
                "size_stage": size_stage,
                "orders_attempted": orders_attempted,
                "live_orders_sent": live_orders_sent,
                "stop_reason": stop_reason,
                "windows": window_records,
            }
        )


def _orchestration_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the nested demo-window orchestration payload."""
    nested = payload.get("strategy_demo_window_orchestration")
    if isinstance(nested, dict):
        return nested
    return payload


def _stop_reason(
    status: str,
    completed: bool,
    block_reasons: list[str],
    orders_attempted: bool,
    live_orders_sent: bool,
) -> str | None:
    """Return a schedule stop reason for one window result."""
    if live_orders_sent:
        return "live_order_detected"
    if block_reasons:
        return "precheck_blocked:" + ",".join(block_reasons)
    if status != "Executed" or not completed:
        return f"window_not_completed:{status}"
    if not orders_attempted:
        return "no_demo_orders_attempted"
    return None
