"""Stateful safety guard for long-running strategy execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from trading_assistant.config.schema import StrategyRuntimeConfig
from trading_assistant.strategies.models import ExecutionMode, StrategyDecision
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class RuntimeGuardDecision:
    """Decision returned before a strategy cycle is allowed to run."""

    approved: bool
    reasons: list[str]
    strategy_name: str
    execution_mode: ExecutionMode
    cooldown_until: datetime | None = None
    cooldown_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe decision."""
        return to_jsonable(self)


class StrategyRuntimeGuard:
    """Persist consecutive failures/losses and enforce cooldowns across runs."""

    def __init__(self, config: StrategyRuntimeConfig) -> None:
        self.config = config
        self.path = Path(config.runtime_guard_path)

    def evaluate(
        self,
        strategy_name: str,
        execution_mode: ExecutionMode,
        now: datetime | None = None,
    ) -> RuntimeGuardDecision:
        """Return whether a strategy cycle may run now."""
        current_time = now or _utcnow()
        if not self.config.runtime_guard_enabled:
            return RuntimeGuardDecision(True, [], strategy_name, execution_mode)
        entry = self._entry(strategy_name, execution_mode)
        cooldown_until = _parse_time(entry.get("cooldown_until"))
        if cooldown_until is not None and cooldown_until > current_time:
            return RuntimeGuardDecision(
                approved=False,
                reasons=["runtime_guard_cooldown"],
                strategy_name=strategy_name,
                execution_mode=execution_mode,
                cooldown_until=cooldown_until,
                cooldown_active=True,
            )
        return RuntimeGuardDecision(True, [], strategy_name, execution_mode, cooldown_until=cooldown_until)

    def record(
        self,
        strategy_name: str,
        execution_mode: ExecutionMode,
        decision: StrategyDecision,
        net_profit: Decimal,
        reasons: list[str],
        now: datetime | None = None,
    ) -> None:
        """Record one strategy result and update persistent guard state."""
        if not self.config.runtime_guard_enabled:
            return
        current_time = now or _utcnow()
        data = self._read()
        key = _key(strategy_name, execution_mode)
        entry = dict(data.get(key, {}))
        consecutive_failures = int(entry.get("consecutive_failures", 0))
        consecutive_losses = int(entry.get("consecutive_losses", 0))
        consecutive_market_data_failures = int(entry.get("consecutive_market_data_failures", 0))
        consecutive_rate_limit_failures = int(entry.get("consecutive_rate_limit_failures", 0))
        cooldown_until: datetime | None = _parse_time(entry.get("cooldown_until"))
        last_reason = entry.get("last_reason")
        is_market_data_failure = _has_market_data_failure(reasons)
        is_rate_limit_failure = _has_rate_limit_failure(reasons)

        if decision == "executed" and net_profit >= 0:
            consecutive_failures = 0
            consecutive_losses = 0
            consecutive_market_data_failures = 0
            consecutive_rate_limit_failures = 0
            cooldown_until = None
            last_reason = "profitable_execution"
        elif decision == "executed" and net_profit < 0:
            consecutive_failures += 1
            consecutive_losses += 1
            consecutive_market_data_failures = 0
            consecutive_rate_limit_failures = 0
            last_reason = "negative_execution_pnl"
        elif decision == "blocked":
            consecutive_failures += 1
            consecutive_market_data_failures = consecutive_market_data_failures + 1 if is_market_data_failure else 0
            consecutive_rate_limit_failures = consecutive_rate_limit_failures + 1 if is_rate_limit_failure else 0
            last_reason = ",".join(reasons) if reasons else "blocked"
        else:
            consecutive_market_data_failures = consecutive_market_data_failures + 1 if is_market_data_failure else 0
            consecutive_rate_limit_failures = consecutive_rate_limit_failures + 1 if is_rate_limit_failure else 0
            last_reason = ",".join(reasons) if reasons else "skipped"

        if (
            consecutive_failures >= self.config.max_consecutive_execution_failures
            or consecutive_losses >= self.config.max_consecutive_losses
            or consecutive_market_data_failures >= self.config.max_consecutive_market_data_failures
            or consecutive_rate_limit_failures >= self.config.max_consecutive_rate_limit_failures
        ):
            cooldown_until = current_time + timedelta(seconds=self.config.failure_cooldown_seconds)

        data[key] = {
            "strategy_name": strategy_name,
            "execution_mode": execution_mode,
            "consecutive_failures": consecutive_failures,
            "consecutive_losses": consecutive_losses,
            "consecutive_market_data_failures": consecutive_market_data_failures,
            "consecutive_rate_limit_failures": consecutive_rate_limit_failures,
            "cooldown_until": cooldown_until.isoformat() if cooldown_until is not None else None,
            "cooldown_seconds": self.config.failure_cooldown_seconds,
            "last_reason": last_reason,
            "last_net_profit": str(net_profit),
            "updated_at": current_time.isoformat(),
        }
        self._write(data)

    def status(
        self,
        strategy_names: list[str] | None = None,
        execution_mode: ExecutionMode | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Return machine-readable guard state."""
        current_time = now or _utcnow()
        data = self._read()
        entries = []
        for key, raw_entry in sorted(data.items()):
            entry = dict(raw_entry)
            strategy_name = str(entry.get("strategy_name", key.split(":", 1)[-1]))
            entry_mode = str(entry.get("execution_mode", key.split(":", 1)[0]))
            if strategy_names is not None and strategy_name not in strategy_names:
                continue
            if execution_mode is not None and entry_mode != execution_mode:
                continue
            entries.append(self._render_entry(entry, current_time))

        known = {f"{item['execution_mode']}:{item['strategy_name']}" for item in entries}
        for strategy_name in strategy_names or []:
            modes: list[ExecutionMode] = [execution_mode] if execution_mode is not None else ["paper", "demo"]
            for mode in modes:
                if f"{mode}:{strategy_name}" in known:
                    continue
                entries.append(
                    self._render_entry(
                        {
                            "strategy_name": strategy_name,
                            "execution_mode": mode,
                            "consecutive_failures": 0,
                            "consecutive_losses": 0,
                            "consecutive_market_data_failures": 0,
                            "consecutive_rate_limit_failures": 0,
                            "cooldown_until": None,
                            "last_reason": None,
                            "last_net_profit": "0",
                            "updated_at": None,
                        },
                        current_time,
                    )
                )

        return {
            "enabled": self.config.runtime_guard_enabled,
            "guard_path": str(self.path),
            "max_consecutive_execution_failures": self.config.max_consecutive_execution_failures,
            "max_consecutive_losses": self.config.max_consecutive_losses,
            "max_consecutive_market_data_failures": self.config.max_consecutive_market_data_failures,
            "max_consecutive_rate_limit_failures": self.config.max_consecutive_rate_limit_failures,
            "failure_cooldown_seconds": self.config.failure_cooldown_seconds,
            "entries": entries,
        }

    def _entry(self, strategy_name: str, execution_mode: ExecutionMode) -> dict[str, Any]:
        return dict(self._read().get(_key(strategy_name, execution_mode), {}))

    def _render_entry(self, entry: dict[str, Any], now: datetime) -> dict[str, Any]:
        cooldown_until = _parse_time(entry.get("cooldown_until"))
        return {
            "strategy_name": entry.get("strategy_name"),
            "execution_mode": entry.get("execution_mode"),
            "consecutive_failures": int(entry.get("consecutive_failures", 0)),
            "consecutive_losses": int(entry.get("consecutive_losses", 0)),
            "consecutive_market_data_failures": int(entry.get("consecutive_market_data_failures", 0)),
            "consecutive_rate_limit_failures": int(entry.get("consecutive_rate_limit_failures", 0)),
            "cooldown_until": cooldown_until,
            "cooldown_active": cooldown_until is not None and cooldown_until > now,
            "last_reason": entry.get("last_reason"),
            "last_net_profit": entry.get("last_net_profit", "0"),
            "updated_at": _parse_time(entry.get("updated_at")),
        }

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        if not isinstance(payload, dict):
            return {}
        return {str(key): dict(value) for key, value in payload.items() if isinstance(value, dict)}

    def _write(self, data: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(to_jsonable(data), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _key(strategy_name: str, execution_mode: ExecutionMode) -> str:
    return f"{execution_mode}:{strategy_name}"


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _has_market_data_failure(reasons: list[str]) -> bool:
    """Return whether reasons describe bad or unavailable exchange market data."""
    return any(_is_market_data_reason(reason) for reason in reasons)


def _has_rate_limit_failure(reasons: list[str]) -> bool:
    """Return whether reasons describe exchange rate limiting."""
    return any(_is_rate_limit_reason(reason) for reason in reasons)


def _is_market_data_reason(reason: str) -> bool:
    normalized = reason.lower()
    return any(
        marker in normalized
        for marker in (
            "market_data",
            "market-data",
            "local_scan_error",
            "exchange_error",
            "ticker",
            "orderbook",
            "order_book",
            "funding",
            "instrument",
            "no futures market",
            "unable to fetch",
            "okx api",
        )
    )


def _is_rate_limit_reason(reason: str) -> bool:
    normalized = reason.lower()
    return any(
        marker in normalized
        for marker in (
            "rate_limit",
            "rate limit",
            "too many requests",
            "429",
            "51011",
            "50011",
        )
    )
