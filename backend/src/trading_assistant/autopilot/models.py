"""Domain models for detached paper/demo autopilot runs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from trading_assistant.exchanges.base import utcnow
from trading_assistant.strategies.models import ExecutionMode
from trading_assistant.utils.serialization import to_jsonable


AutopilotMode = Literal["paper", "demo"]
AutopilotStatus = Literal["NeverRun", "Running", "Completed", "Stopped", "Failed"]
PayloadProducer = Callable[[], dict[str, Any]]
ValidationReporter = Callable[[ExecutionMode, str, int], dict[str, Any]]
OperatorBriefProducer = Callable[[ExecutionMode, str, int], dict[str, Any]]
GuardStatusProducer = Callable[[ExecutionMode, str], dict[str, Any]]
PromotionStatusProducer = Callable[[str], dict[str, Any]]
Sleeper = Callable[[int], None]


@dataclass(frozen=True)
class AutopilotCycleRecord:
    """One paper/demo autopilot cycle summary."""

    cycle: int
    mode: AutopilotMode
    status: str
    completed: bool
    live_orders_sent: bool
    orders_attempted: bool
    blocked: bool
    block_reasons: list[str] = field(default_factory=list)
    payload_summary: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe cycle data."""
        return to_jsonable(self)


@dataclass(frozen=True)
class AutopilotState:
    """Persisted latest autopilot status."""

    status: AutopilotStatus
    mode: AutopilotMode | None = None
    strategy_name: str = "all"
    symbol: str = "BTC/USDT"
    cycles_requested: int = 0
    cycles_completed: int = 0
    stopped_reason: str | None = None
    consecutive_blocked_cycles: int = 0
    live_orders_sent: bool = False
    orders_attempted: bool = False
    last_payload_summary: dict[str, Any] = field(default_factory=dict)
    last_cycle_at: str | None = None
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe state data."""
        return to_jsonable(self)


@dataclass(frozen=True)
class AutopilotRunResult:
    """Result returned by one autopilot run invocation."""

    status: AutopilotStatus
    mode: AutopilotMode
    strategy_name: str
    symbol: str
    cycles_requested: int
    cycles_completed: int
    stopped_reason: str | None
    live_orders_sent: bool
    orders_attempted: bool
    state_path: str
    cycles: list[AutopilotCycleRecord]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe run result."""
        return to_jsonable(self)


@dataclass(frozen=True)
class AutopilotReport:
    """Read-only autopilot report."""

    state: dict[str, Any]
    guard: dict[str, Any]
    validation: dict[str, Any]
    operator_brief: dict[str, Any]
    promotion_status: dict[str, Any] | None
    orders_sent: bool
    live_orders_sent: bool

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report."""
        return to_jsonable(self)
