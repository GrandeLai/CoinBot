# Autopilot Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Codex-independent `crypto-assistant autopilot` loop for paper and OKX Demo Trading automation, with persisted state, reporting, and hard no-live-dispatch safety.

**Architecture:** Add a small `trading_assistant.autopilot` package that owns runtime models, state persistence, and orchestration. The package receives application callbacks for existing strategy, demo-window, validation, guard, and operator-brief services, so it reuses current safe trading paths instead of duplicating execution logic. Wire the runtime through `TradingAssistantApp` and thin argparse CLI handlers.

**Tech Stack:** Python 3.12, argparse, Pydantic v2 config, dataclasses, Decimal-safe serialization, pytest, ruff, mypy.

---

## File Map

- Create `backend/src/trading_assistant/autopilot/__init__.py`: package exports.
- Create `backend/src/trading_assistant/autopilot/models.py`: dataclasses and type aliases for autopilot state, cycle records, run results, reports, and injected service callbacks.
- Create `backend/src/trading_assistant/autopilot/state.py`: atomic JSON state store.
- Create `backend/src/trading_assistant/autopilot/runtime.py`: paper/demo autopilot loop and payload summarizers.
- Create `backend/tests/unit/test_autopilot_runtime.py`: unit tests for state, paper flow, demo safety stop, blocked-cycle stop, and live-trading refusal.
- Modify `backend/src/trading_assistant/config/schema.py`: add autopilot runtime config fields and validators.
- Modify `configs/config.example.yaml` and `configs/okx.demo.example.yaml`: document safe defaults.
- Modify `backend/src/trading_assistant/application.py`: add `autopilot_run`, `autopilot_status`, and `autopilot_report` facade methods.
- Modify `backend/src/trading_assistant/cli/main.py`: add `autopilot run|status|report` commands.
- Modify `backend/tests/integration/test_cli_core.py`: add JSON CLI coverage.
- Modify `README.md` and `docs/DESIGN.md`: describe detached paper/demo autopilot operation and safety limits.
- Modify `docs/plan/2026-05-09-refactor/02-acceptance-checklist.md` and `03-traceability-matrix.md`: add traceability and acceptance rows.
- Create `docs/plan/2026-05-09-refactor/61-autopilot-runtime-report.md`: implementation report with validation commands/results.

---

### Task 1: Add Autopilot Config Defaults

**Files:**
- Modify: `backend/src/trading_assistant/config/schema.py`
- Modify: `configs/config.example.yaml`
- Modify: `configs/okx.demo.example.yaml`
- Test: `backend/tests/unit/test_config.py`

- [ ] **Step 1: Write failing config test**

Add this test to `backend/tests/unit/test_config.py`:

```python
def test_strategy_runtime_autopilot_defaults_are_safe() -> None:
    settings = load_settings(EXAMPLE_CONFIG)

    assert settings.strategy_runtime.autopilot_state_path == "logs/autopilot-state.json"
    assert settings.strategy_runtime.autopilot_default_interval_seconds == 60
    assert settings.strategy_runtime.autopilot_max_consecutive_blocked_cycles == 3
    assert settings.strategy_runtime.autopilot_stop_on_live_signal is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_config.py::test_strategy_runtime_autopilot_defaults_are_safe -v
```

Expected: FAIL with `AttributeError` or Pydantic validation output showing the autopilot fields do not exist.

- [ ] **Step 3: Implement config fields**

In `StrategyRuntimeConfig` in `backend/src/trading_assistant/config/schema.py`, add these fields after `validation_allow_live_canary`:

```python
    autopilot_state_path: str = "logs/autopilot-state.json"
    autopilot_default_interval_seconds: int = 60
    autopilot_max_consecutive_blocked_cycles: int = 3
    autopilot_stop_on_live_signal: bool = True
```

Add `autopilot_default_interval_seconds` and `autopilot_max_consecutive_blocked_cycles` to the `positive_strategy_ints` validator list.

- [ ] **Step 4: Update example configs**

Add this block under `strategy_runtime` in `configs/config.example.yaml` and `configs/okx.demo.example.yaml`:

```yaml
  autopilot_state_path: logs/autopilot-state.json
  autopilot_default_interval_seconds: 60
  autopilot_max_consecutive_blocked_cycles: 3
  autopilot_stop_on_live_signal: true
```

For `configs/okx.demo.example.yaml`, use a separate state path so demo runs do not overwrite paper state:

```yaml
  autopilot_state_path: logs/okx-demo-autopilot-state.json
```

- [ ] **Step 5: Run config tests**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_config.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/trading_assistant/config/schema.py configs/config.example.yaml configs/okx.demo.example.yaml backend/tests/unit/test_config.py
git commit -m "feat: add autopilot runtime config"
```

---

### Task 2: Add Autopilot Models And State Store

**Files:**
- Create: `backend/src/trading_assistant/autopilot/__init__.py`
- Create: `backend/src/trading_assistant/autopilot/models.py`
- Create: `backend/src/trading_assistant/autopilot/state.py`
- Test: `backend/tests/unit/test_autopilot_runtime.py`

- [ ] **Step 1: Write failing state tests**

Create `backend/tests/unit/test_autopilot_runtime.py` with:

```python
"""Unit tests for detached autopilot runtime orchestration."""

from __future__ import annotations

import json
from pathlib import Path

from trading_assistant.autopilot.models import AutopilotState
from trading_assistant.autopilot.state import AutopilotStateStore


def test_autopilot_state_store_returns_never_run_when_missing(tmp_path: Path) -> None:
    store = AutopilotStateStore(tmp_path / "autopilot-state.json")

    state = store.read()

    assert state.status == "NeverRun"
    assert state.cycles_completed == 0
    assert state.live_orders_sent is False


def test_autopilot_state_store_writes_json_atomically(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "autopilot-state.json"
    store = AutopilotStateStore(path)
    state = AutopilotState(
        status="Completed",
        mode="paper",
        strategy_name="all",
        symbol="BTC/USDT",
        cycles_requested=1,
        cycles_completed=1,
        stopped_reason=None,
        consecutive_blocked_cycles=0,
        live_orders_sent=False,
        orders_attempted=False,
        last_payload_summary={"decision_counts": {"executed": 1}},
    )

    store.write(state)

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["status"] == "Completed"
    assert raw["mode"] == "paper"
    assert raw["last_payload_summary"]["decision_counts"]["executed"] == 1
    assert not list(path.parent.glob("*.tmp"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_autopilot_runtime.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'trading_assistant.autopilot'`.

- [ ] **Step 3: Implement models**

Create `backend/src/trading_assistant/autopilot/models.py`:

```python
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
```

Create `backend/src/trading_assistant/autopilot/__init__.py`:

```python
"""Detached paper/demo autopilot runtime."""

from trading_assistant.autopilot.models import AutopilotMode, AutopilotRunResult, AutopilotState
from trading_assistant.autopilot.runtime import AutopilotRuntime
from trading_assistant.autopilot.state import AutopilotStateStore

__all__ = ["AutopilotMode", "AutopilotRunResult", "AutopilotRuntime", "AutopilotState", "AutopilotStateStore"]
```

- [ ] **Step 4: Implement state store**

Create `backend/src/trading_assistant/autopilot/state.py`:

```python
"""State persistence for detached autopilot runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trading_assistant.autopilot.models import AutopilotState


class AutopilotStateStore:
    """Read and atomically write the latest autopilot state."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read(self) -> AutopilotState:
        """Return persisted state or a NeverRun state when no file exists."""
        if not self.path.exists():
            return AutopilotState(status="NeverRun")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return AutopilotState(**_state_payload(payload))

    def write(self, state: AutopilotState) -> None:
        """Write state with a same-directory temp file followed by replace."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_name(f".{self.path.name}.tmp")
        tmp_path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self.path)


def _state_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = set(AutopilotState.__dataclass_fields__)
    return {key: value for key, value in payload.items() if key in allowed}
```

- [ ] **Step 5: Run state tests**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_autopilot_runtime.py::test_autopilot_state_store_returns_never_run_when_missing tests/unit/test_autopilot_runtime.py::test_autopilot_state_store_writes_json_atomically -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/trading_assistant/autopilot backend/tests/unit/test_autopilot_runtime.py
git commit -m "feat: add autopilot state store"
```

---

### Task 3: Implement Paper Autopilot Runtime

**Files:**
- Create: `backend/src/trading_assistant/autopilot/runtime.py`
- Modify: `backend/tests/unit/test_autopilot_runtime.py`

- [ ] **Step 1: Write failing paper runtime tests**

Append to `backend/tests/unit/test_autopilot_runtime.py`:

```python
from trading_assistant.autopilot.runtime import AutopilotRuntime
from trading_assistant.config.loader import load_settings
from trading_assistant.config.schema import TradingConfig


ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_CONFIG = ROOT / "configs" / "config.example.yaml"


def test_paper_autopilot_completes_one_cycle_and_persists_state(tmp_path: Path) -> None:
    settings = load_settings(EXAMPLE_CONFIG)
    settings.strategy_runtime.autopilot_state_path = str(tmp_path / "autopilot-state.json")
    runtime = AutopilotRuntime(
        settings=settings,
        state_store=AutopilotStateStore(settings.strategy_runtime.autopilot_state_path),
        paper_runner=lambda: {
            "strategy_run": {
                "completed": True,
                "results": [
                    {"decision": "executed", "risk_reasons": [], "execution": {"dry_run": True, "live_orders_sent": False}}
                ],
            }
        },
        validation_reporter=lambda mode, strategy, limit: {"strategy_validation_report": {"total": {"executed": 1}}},
        operator_brief=lambda mode, strategy, limit: {"strategy_operator_brief": {"read_only": True, "live_orders_sent": False}},
        guard_status=lambda mode, strategy: {"strategy_guard_status": {"entries": []}},
        promotion_status=lambda strategy: {"strategy_promotion_status": []},
        sleeper=lambda seconds: None,
    )

    result = runtime.run(
        mode="paper",
        strategy_name="all",
        symbol="BTC/USDT",
        cycles=1,
        interval_seconds=0,
        demo_cycles_per_window=1,
        report_limit=10,
    )

    assert result.status == "Completed"
    assert result.cycles_completed == 1
    assert result.live_orders_sent is False
    assert result.orders_attempted is False
    state = AutopilotStateStore(settings.strategy_runtime.autopilot_state_path).read()
    assert state.status == "Completed"
    assert state.last_payload_summary["decision_counts"]["executed"] == 1


def test_paper_autopilot_refuses_live_trading_config(tmp_path: Path) -> None:
    settings = load_settings(EXAMPLE_CONFIG)
    settings.strategy_runtime.autopilot_state_path = str(tmp_path / "autopilot-state.json")
    settings.trading = TradingConfig(live_trading=True, dry_run=False, require_confirm_before_order=False)
    runtime = AutopilotRuntime(
        settings=settings,
        state_store=AutopilotStateStore(settings.strategy_runtime.autopilot_state_path),
        paper_runner=lambda: {"strategy_run": {"completed": True, "results": []}},
        validation_reporter=lambda mode, strategy, limit: {"strategy_validation_report": {}},
        operator_brief=lambda mode, strategy, limit: {"strategy_operator_brief": {}},
        guard_status=lambda mode, strategy: {"strategy_guard_status": {"entries": []}},
        promotion_status=lambda strategy: {"strategy_promotion_status": []},
        sleeper=lambda seconds: None,
    )

    result = runtime.run(
        mode="paper",
        strategy_name="all",
        symbol="BTC/USDT",
        cycles=1,
        interval_seconds=0,
        demo_cycles_per_window=1,
        report_limit=10,
    )

    assert result.status == "Stopped"
    assert result.stopped_reason == "paper_live_trading_enabled"
    assert AutopilotStateStore(settings.strategy_runtime.autopilot_state_path).read().status == "Stopped"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_autopilot_runtime.py::test_paper_autopilot_completes_one_cycle_and_persists_state tests/unit/test_autopilot_runtime.py::test_paper_autopilot_refuses_live_trading_config -v
```

Expected: FAIL with `ModuleNotFoundError` for `trading_assistant.autopilot.runtime` or missing `AutopilotRuntime`.

- [ ] **Step 3: Implement paper runtime**

Create `backend/src/trading_assistant/autopilot/runtime.py`:

```python
"""Detached paper/demo autopilot runtime."""

from __future__ import annotations

from typing import Any

from trading_assistant.autopilot.models import (
    AutopilotCycleRecord,
    AutopilotMode,
    AutopilotReport,
    AutopilotRunResult,
    AutopilotState,
    GuardStatusProducer,
    OperatorBriefProducer,
    PayloadProducer,
    PromotionStatusProducer,
    Sleeper,
    ValidationReporter,
)
from trading_assistant.autopilot.state import AutopilotStateStore
from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.base import utcnow
from trading_assistant.strategies.models import ExecutionMode


class AutopilotRuntime:
    """Run bounded or unbounded paper/demo autopilot cycles."""

    def __init__(
        self,
        *,
        settings: Settings,
        state_store: AutopilotStateStore,
        paper_runner: PayloadProducer,
        validation_reporter: ValidationReporter,
        operator_brief: OperatorBriefProducer,
        guard_status: GuardStatusProducer,
        promotion_status: PromotionStatusProducer,
        sleeper: Sleeper,
        demo_runner: PayloadProducer | None = None,
    ) -> None:
        self.settings = settings
        self.state_store = state_store
        self.paper_runner = paper_runner
        self.demo_runner = demo_runner
        self.validation_reporter = validation_reporter
        self.operator_brief = operator_brief
        self.guard_status = guard_status
        self.promotion_status = promotion_status
        self.sleeper = sleeper

    def run(
        self,
        *,
        mode: AutopilotMode,
        strategy_name: str,
        symbol: str,
        cycles: int,
        interval_seconds: int | None,
        demo_cycles_per_window: int,
        report_limit: int,
    ) -> AutopilotRunResult:
        """Run autopilot cycles and persist state after every decision."""
        requested = max(cycles, 0)
        sleep_seconds = max(
            interval_seconds if interval_seconds is not None else self.settings.strategy_runtime.autopilot_default_interval_seconds,
            0,
        )
        if mode == "paper" and self.settings.trading.live_trading:
            return self._stopped_before_cycle(mode, strategy_name, symbol, requested, "paper_live_trading_enabled")

        records: list[AutopilotCycleRecord] = []
        cycles_completed = 0
        consecutive_blocked = 0
        live_orders_sent = False
        orders_attempted = False
        stopped_reason: str | None = None
        self._write_state("Running", mode, strategy_name, symbol, requested, 0, None, 0, False, False, {})

        cycle = 0
        while requested == 0 or cycle < requested:
            cycle += 1
            try:
                payload = self.paper_runner() if mode == "paper" else self._run_demo_payload()
                validation = self.validation_reporter(_execution_mode(mode), strategy_name, report_limit)
                brief = self.operator_brief(_execution_mode(mode), strategy_name, report_limit)
                merged_payload = {**payload, **validation, **brief}
                record = _cycle_record(cycle, mode, merged_payload)
            except Exception as exc:
                failed_state = AutopilotState(
                    status="Failed",
                    mode=mode,
                    strategy_name=strategy_name,
                    symbol=symbol,
                    cycles_requested=requested,
                    cycles_completed=cycles_completed,
                    stopped_reason="exception",
                    consecutive_blocked_cycles=consecutive_blocked,
                    live_orders_sent=live_orders_sent,
                    orders_attempted=orders_attempted,
                    error_type=exc.__class__.__name__,
                    error_message=str(exc),
                    last_cycle_at=utcnow().isoformat(),
                )
                self.state_store.write(failed_state)
                raise

            records.append(record)
            cycles_completed = cycle
            live_orders_sent = live_orders_sent or record.live_orders_sent
            orders_attempted = orders_attempted or record.orders_attempted
            consecutive_blocked = consecutive_blocked + 1 if record.blocked else 0
            stopped_reason = _stop_reason(record, consecutive_blocked, self.settings.strategy_runtime.autopilot_max_consecutive_blocked_cycles)
            self._write_state(
                "Stopped" if stopped_reason else "Running",
                mode,
                strategy_name,
                symbol,
                requested,
                cycles_completed,
                stopped_reason,
                consecutive_blocked,
                live_orders_sent,
                orders_attempted,
                record.payload_summary,
            )
            if stopped_reason is not None:
                break
            if requested == 0 or cycle < requested:
                self.sleeper(sleep_seconds)

        status = "Stopped" if stopped_reason else "Completed"
        self._write_state(
            status,
            mode,
            strategy_name,
            symbol,
            requested,
            cycles_completed,
            stopped_reason,
            consecutive_blocked,
            live_orders_sent,
            orders_attempted,
            records[-1].payload_summary if records else {},
        )
        return AutopilotRunResult(
            status=status,
            mode=mode,
            strategy_name=strategy_name,
            symbol=symbol,
            cycles_requested=requested,
            cycles_completed=cycles_completed,
            stopped_reason=stopped_reason,
            live_orders_sent=live_orders_sent,
            orders_attempted=orders_attempted,
            state_path=str(self.state_store.path),
            cycles=records,
            summary=f"Autopilot {status.lower()} after {cycles_completed} cycle(s) in {mode} mode.",
        )

    def report(self, *, mode: AutopilotMode, strategy_name: str, report_limit: int) -> AutopilotReport:
        """Return a read-only report from state and existing evidence services."""
        execution_mode = _execution_mode(mode)
        state = self.state_store.read().to_dict()
        guard = self.guard_status(execution_mode, strategy_name)
        validation = self.validation_reporter(execution_mode, strategy_name, report_limit)
        brief = self.operator_brief(execution_mode, strategy_name, report_limit)
        promotion = self.promotion_status(strategy_name)
        return AutopilotReport(
            state=state,
            guard=guard,
            validation=validation,
            operator_brief=brief,
            promotion_status=promotion,
            orders_sent=bool(state.get("orders_attempted")),
            live_orders_sent=bool(state.get("live_orders_sent")),
        )

    def _run_demo_payload(self) -> dict[str, Any]:
        if self.demo_runner is None:
            raise RuntimeError("demo_runner is required for demo autopilot mode")
        return self.demo_runner()

    def _stopped_before_cycle(
        self,
        mode: AutopilotMode,
        strategy_name: str,
        symbol: str,
        cycles_requested: int,
        reason: str,
    ) -> AutopilotRunResult:
        self._write_state("Stopped", mode, strategy_name, symbol, cycles_requested, 0, reason, 0, False, False, {})
        return AutopilotRunResult(
            status="Stopped",
            mode=mode,
            strategy_name=strategy_name,
            symbol=symbol,
            cycles_requested=cycles_requested,
            cycles_completed=0,
            stopped_reason=reason,
            live_orders_sent=False,
            orders_attempted=False,
            state_path=str(self.state_store.path),
            cycles=[],
            summary=f"Autopilot stopped before execution: {reason}.",
        )

    def _write_state(
        self,
        status: str,
        mode: AutopilotMode,
        strategy_name: str,
        symbol: str,
        cycles_requested: int,
        cycles_completed: int,
        stopped_reason: str | None,
        consecutive_blocked: int,
        live_orders_sent: bool,
        orders_attempted: bool,
        payload_summary: dict[str, Any],
    ) -> None:
        self.state_store.write(
            AutopilotState(
                status=status,  # type: ignore[arg-type]
                mode=mode,
                strategy_name=strategy_name,
                symbol=symbol,
                cycles_requested=cycles_requested,
                cycles_completed=cycles_completed,
                stopped_reason=stopped_reason,
                consecutive_blocked_cycles=consecutive_blocked,
                live_orders_sent=live_orders_sent,
                orders_attempted=orders_attempted,
                last_payload_summary=payload_summary,
                last_cycle_at=utcnow().isoformat(),
            )
        )
```

Add helper functions in the same file:

```python
def _execution_mode(mode: AutopilotMode) -> ExecutionMode:
    return "demo" if mode == "demo" else "paper"


def _cycle_record(cycle: int, mode: AutopilotMode, payload: dict[str, Any]) -> AutopilotCycleRecord:
    summary = _payload_summary(payload)
    live_orders_sent = _nested_truthy(payload, "live_orders_sent")
    orders_attempted = _nested_truthy(payload, "orders_attempted") or _nested_truthy(payload, "demo_orders_sent")
    blocked = bool(summary["block_reasons"]) or summary["decision_counts"].get("executed", 0) == 0
    return AutopilotCycleRecord(
        cycle=cycle,
        mode=mode,
        status="Blocked" if blocked else "Executed",
        completed=not blocked,
        live_orders_sent=live_orders_sent,
        orders_attempted=orders_attempted,
        blocked=blocked,
        block_reasons=summary["block_reasons"],
        payload_summary=summary,
    )


def _payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    results = _strategy_results(payload)
    decision_counts = {"executed": 0, "blocked": 0, "skipped": 0}
    block_reasons: list[str] = []
    for result in results:
        decision = str(result.get("decision", ""))
        if decision in decision_counts:
            decision_counts[decision] += 1
        block_reasons.extend(str(reason) for reason in result.get("risk_reasons", []) if reason)
    orchestration = payload.get("strategy_demo_window_orchestration")
    if isinstance(orchestration, dict):
        block_reasons.extend(str(reason) for reason in orchestration.get("block_reasons", []) if reason)
        if orchestration.get("status") == "Executed":
            decision_counts["executed"] += 1
        elif orchestration.get("status") == "Blocked":
            decision_counts["blocked"] += 1
    return {
        "decision_counts": decision_counts,
        "block_reasons": sorted(set(block_reasons)),
    }


def _strategy_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    run = payload.get("strategy_run")
    if isinstance(run, dict):
        return [item for item in run.get("results", []) if isinstance(item, dict)]
    orchestration = payload.get("strategy_demo_window_orchestration")
    if isinstance(orchestration, dict):
        demo_window = orchestration.get("demo_window")
        if isinstance(demo_window, dict):
            nested_run = demo_window.get("strategy_run")
            if isinstance(nested_run, dict):
                return [item for item in nested_run.get("results", []) if isinstance(item, dict)]
    return []


def _nested_truthy(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return bool(value.get(key)) or any(_nested_truthy(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_nested_truthy(item, key) for item in value)
    return False


def _stop_reason(record: AutopilotCycleRecord, consecutive_blocked: int, max_blocked: int) -> str | None:
    if record.live_orders_sent:
        return "live_order_detected"
    if consecutive_blocked >= max_blocked:
        return "max_consecutive_blocked_cycles"
    return None
```

- [ ] **Step 4: Run paper runtime tests**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_autopilot_runtime.py -v
```

Expected: PASS for state and paper runtime tests.

- [ ] **Step 5: Commit**

```bash
git add backend/src/trading_assistant/autopilot/runtime.py backend/tests/unit/test_autopilot_runtime.py
git commit -m "feat: add paper autopilot runtime"
```

---

### Task 4: Add Demo Safety And Blocked-Cycle Stops

**Files:**
- Modify: `backend/src/trading_assistant/autopilot/runtime.py`
- Modify: `backend/tests/unit/test_autopilot_runtime.py`

- [ ] **Step 1: Write failing demo safety tests**

Append to `backend/tests/unit/test_autopilot_runtime.py`:

```python
def test_demo_autopilot_stops_on_live_order_signal(tmp_path: Path) -> None:
    settings = load_settings(EXAMPLE_CONFIG)
    settings.strategy_runtime.autopilot_state_path = str(tmp_path / "autopilot-state.json")
    runtime = AutopilotRuntime(
        settings=settings,
        state_store=AutopilotStateStore(settings.strategy_runtime.autopilot_state_path),
        paper_runner=lambda: {"strategy_run": {"completed": True, "results": []}},
        demo_runner=lambda: {
            "strategy_demo_window_orchestration": {
                "status": "Executed",
                "completed": True,
                "orders_attempted": True,
                "live_orders_sent": True,
                "block_reasons": [],
            }
        },
        validation_reporter=lambda mode, strategy, limit: {"strategy_validation_report": {"total": {"executed": 1}}},
        operator_brief=lambda mode, strategy, limit: {"strategy_operator_brief": {"read_only": True}},
        guard_status=lambda mode, strategy: {"strategy_guard_status": {"entries": []}},
        promotion_status=lambda strategy: {"strategy_promotion_status": []},
        sleeper=lambda seconds: None,
    )

    result = runtime.run(
        mode="demo",
        strategy_name="triangular-multi-route",
        symbol="BTC/USDT",
        cycles=3,
        interval_seconds=0,
        demo_cycles_per_window=1,
        report_limit=10,
    )

    assert result.status == "Stopped"
    assert result.stopped_reason == "live_order_detected"
    assert result.cycles_completed == 1
    assert result.live_orders_sent is True


def test_autopilot_stops_after_consecutive_blocked_cycles(tmp_path: Path) -> None:
    settings = load_settings(EXAMPLE_CONFIG)
    settings.strategy_runtime.autopilot_state_path = str(tmp_path / "autopilot-state.json")
    settings.strategy_runtime.autopilot_max_consecutive_blocked_cycles = 2
    runtime = AutopilotRuntime(
        settings=settings,
        state_store=AutopilotStateStore(settings.strategy_runtime.autopilot_state_path),
        paper_runner=lambda: {
            "strategy_run": {
                "completed": True,
                "results": [
                    {"decision": "skipped", "risk_reasons": ["no_opportunity"], "execution": None}
                ],
            }
        },
        validation_reporter=lambda mode, strategy, limit: {"strategy_validation_report": {"total": {"executed": 0}}},
        operator_brief=lambda mode, strategy, limit: {"strategy_operator_brief": {"read_only": True}},
        guard_status=lambda mode, strategy: {"strategy_guard_status": {"entries": []}},
        promotion_status=lambda strategy: {"strategy_promotion_status": []},
        sleeper=lambda seconds: None,
    )

    result = runtime.run(
        mode="paper",
        strategy_name="all",
        symbol="BTC/USDT",
        cycles=5,
        interval_seconds=0,
        demo_cycles_per_window=1,
        report_limit=10,
    )

    assert result.status == "Stopped"
    assert result.stopped_reason == "max_consecutive_blocked_cycles"
    assert result.cycles_completed == 2
    assert result.cycles[-1].block_reasons == ["no_opportunity"]
```

- [ ] **Step 2: Run tests to verify any missing behavior fails**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_autopilot_runtime.py::test_demo_autopilot_stops_on_live_order_signal tests/unit/test_autopilot_runtime.py::test_autopilot_stops_after_consecutive_blocked_cycles -v
```

Expected: FAIL if demo payload summaries or consecutive-blocked stopping are incomplete.

- [ ] **Step 3: Complete runtime stop behavior**

Update `_cycle_record`, `_payload_summary`, `_nested_truthy`, and `_stop_reason` so:

- nested `live_orders_sent=true` always produces `live_order_detected`
- nested `orders_attempted=true` or `demo_orders_sent=true` sets `orders_attempted`
- demo orchestration `status="Blocked"` adds block reasons
- two or more consecutive blocked paper/demo cycles stop at the configured threshold

Use the helper implementations from Task 3 if they are not already present.

- [ ] **Step 4: Run autopilot unit tests**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_autopilot_runtime.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/trading_assistant/autopilot/runtime.py backend/tests/unit/test_autopilot_runtime.py
git commit -m "feat: stop autopilot on unsafe or blocked cycles"
```

---

### Task 5: Wire Application Facade

**Files:**
- Modify: `backend/src/trading_assistant/application.py`
- Modify: `backend/tests/unit/test_autopilot_runtime.py`

- [ ] **Step 1: Write failing facade test**

Append to `backend/tests/unit/test_autopilot_runtime.py`:

```python
from trading_assistant.application import TradingAssistantApp


def test_application_autopilot_run_status_and_report(tmp_path: Path) -> None:
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
    app = TradingAssistantApp(config_path=config_path)

    run_payload = app.autopilot_run(
        mode="paper",
        strategy_name="cross-exchange",
        symbol="BTC/USDT",
        cycles=1,
        interval_seconds=0,
        demo_cycles_per_window=1,
        target_exchange="okx",
        report_limit=10,
        include_private_health=False,
    )
    status_payload = app.autopilot_status()
    report_payload = app.autopilot_report(mode="paper", strategy_name="cross-exchange", report_limit=10)

    assert run_payload["autopilot_run"]["status"] == "Completed"
    assert status_payload["autopilot_status"]["status"] == "Completed"
    assert report_payload["autopilot_report"]["state"]["status"] == "Completed"
    assert report_payload["autopilot_report"]["live_orders_sent"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_autopilot_runtime.py::test_application_autopilot_run_status_and_report -v
```

Expected: FAIL with `AttributeError: 'TradingAssistantApp' object has no attribute 'autopilot_run'`.

- [ ] **Step 3: Implement application methods**

In `backend/src/trading_assistant/application.py`, add imports:

```python
from trading_assistant.autopilot import AutopilotRuntime, AutopilotStateStore
from trading_assistant.autopilot.models import AutopilotMode
```

Add methods to `TradingAssistantApp`:

```python
    def autopilot_run(
        self,
        *,
        mode: AutopilotMode,
        strategy_name: str,
        symbol: str,
        cycles: int,
        interval_seconds: int | None,
        demo_cycles_per_window: int,
        target_exchange: str,
        report_limit: int,
        include_private_health: bool,
    ) -> dict[str, Any]:
        """Run detached paper/demo autopilot cycles."""
        runtime = self._autopilot_runtime(
            mode=mode,
            strategy_name=strategy_name,
            symbol=symbol,
            demo_cycles_per_window=demo_cycles_per_window,
            target_exchange=target_exchange,
            report_limit=report_limit,
            include_private_health=include_private_health,
        )
        result = runtime.run(
            mode=mode,
            strategy_name=strategy_name,
            symbol=symbol,
            cycles=cycles,
            interval_seconds=interval_seconds,
            demo_cycles_per_window=demo_cycles_per_window,
            report_limit=report_limit,
        )
        return {"autopilot_run": result.to_dict()}

    def autopilot_status(self) -> dict[str, Any]:
        """Return persisted autopilot status."""
        store = AutopilotStateStore(self.settings.strategy_runtime.autopilot_state_path)
        return {"autopilot_status": store.read().to_dict()}

    def autopilot_report(
        self,
        *,
        mode: AutopilotMode,
        strategy_name: str,
        report_limit: int,
    ) -> dict[str, Any]:
        """Return read-only autopilot state and validation evidence."""
        runtime = self._autopilot_runtime(
            mode=mode,
            strategy_name=strategy_name,
            symbol="BTC/USDT",
            demo_cycles_per_window=1,
            target_exchange="okx",
            report_limit=report_limit,
            include_private_health=False,
        )
        return {"autopilot_report": runtime.report(mode=mode, strategy_name=strategy_name, report_limit=report_limit).to_dict()}

    def _autopilot_runtime(
        self,
        *,
        mode: AutopilotMode,
        strategy_name: str,
        symbol: str,
        demo_cycles_per_window: int,
        target_exchange: str,
        report_limit: int,
        include_private_health: bool,
    ) -> AutopilotRuntime:
        return AutopilotRuntime(
            settings=self.settings,
            state_store=AutopilotStateStore(self.settings.strategy_runtime.autopilot_state_path),
            paper_runner=lambda: self.strategy_run(
                strategy_name=strategy_name,
                max_cycles=1,
                interval_seconds=0,
                execution_mode="paper",
                symbol=symbol,
            ),
            demo_runner=lambda: self.strategy_demo_window(
                strategy_name=strategy_name,
                cycles=demo_cycles_per_window,
                symbol=symbol,
                target_exchange=target_exchange,
                report_limit=report_limit,
                include_private_health=include_private_health,
            ),
            validation_reporter=lambda execution_mode, strategy, limit: self.strategy_validation_report(
                execution_mode=execution_mode,
                strategy_name=strategy,
                limit=limit,
            ),
            operator_brief=lambda execution_mode, strategy, limit: self.strategy_operator_brief(
                execution_mode=execution_mode,
                strategy_name=strategy,
                limit=limit,
            ),
            guard_status=lambda execution_mode, strategy: self.strategy_guard_status(
                strategy_name=strategy,
                execution_mode=execution_mode,
            ),
            promotion_status=lambda strategy: self.strategy_promotion_status(strategy_name=strategy),
            sleeper=sleep,
        )
```

- [ ] **Step 4: Run facade test**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_autopilot_runtime.py::test_application_autopilot_run_status_and_report -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/trading_assistant/application.py backend/tests/unit/test_autopilot_runtime.py
git commit -m "feat: expose autopilot application facade"
```

---

### Task 6: Add CLI Commands

**Files:**
- Modify: `backend/src/trading_assistant/cli/main.py`
- Modify: `backend/tests/integration/test_cli_core.py`

- [ ] **Step 1: Write failing CLI tests**

Append to `backend/tests/integration/test_cli_core.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py::test_cli_autopilot_run_status_and_report -v
```

Expected: FAIL because `autopilot` is not a recognized command.

- [ ] **Step 3: Implement parser wiring**

In `build_parser()` in `backend/src/trading_assistant/cli/main.py`, add before `strategy = subcommands.add_parser(...)`:

```python
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
```

Add handlers near the other `_handle_*` functions:

```python
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
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py::test_cli_autopilot_run_status_and_report -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/trading_assistant/cli/main.py backend/tests/integration/test_cli_core.py
git commit -m "feat: add autopilot cli commands"
```

---

### Task 7: Sync Docs And Traceability

**Files:**
- Modify: `README.md`
- Modify: `docs/DESIGN.md`
- Modify: `docs/plan/2026-05-09-refactor/02-acceptance-checklist.md`
- Modify: `docs/plan/2026-05-09-refactor/03-traceability-matrix.md`
- Create: `docs/plan/2026-05-09-refactor/61-autopilot-runtime-report.md`

- [ ] **Step 1: Update README**

Add an "Autopilot Runtime" section near the strategy runtime documentation:

```markdown
## Autopilot Runtime

`crypto-assistant autopilot` is the detached paper/demo loop for running CoinBot without Codex automations. It can be launched by a shell, cron, launchd, systemd, or another process manager.

Paper mode never sends exchange orders:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run crypto-assistant autopilot run \
  --config ../configs/config.example.yaml \
  --mode paper \
  --strategy all \
  --cycles 0 \
  --interval-seconds 60 \
  --json
```

OKX Demo mode uses the existing demo-window gates and may send only tiny OKX Demo Trading orders:

```bash
UV_CACHE_DIR=.uv-cache uv run crypto-assistant autopilot run \
  --config ../configs/okx.demo.example.yaml \
  --mode demo \
  --strategy triangular-multi-route \
  --cycles 0 \
  --interval-seconds 300 \
  --demo-cycles-per-window 3 \
  --target-exchange okx \
  --json
```

Status and reports are read-only:

```bash
uv run crypto-assistant autopilot status --config ../configs/config.example.yaml --json
uv run crypto-assistant autopilot report --config ../configs/config.example.yaml --mode paper --json
```

Autopilot does not call `agent execute-live` or any live broker. If a paper/demo payload ever reports `live_orders_sent=true`, autopilot stops and persists `stopped_reason=live_order_detected`.
```

- [ ] **Step 2: Update docs/DESIGN.md**

Add `autopilot run|status|report` to the Local CLI list and add a short paragraph under the strategy validation section:

```markdown
The detached autopilot runtime is exposed through `crypto-assistant autopilot run|status|report`. It wraps existing paper and OKX Demo Trading paths so an external process manager can run bounded or continuous paper/demo cycles without Codex. It persists state under `strategy_runtime.autopilot_state_path`, produces read-only status/report payloads, and stops immediately if any paper/demo payload reports `live_orders_sent=true`. It never calls `agent execute-live` or a live broker.
```

- [ ] **Step 3: Update traceability matrix**

Add a new row to `03-traceability-matrix.md`:

```markdown
| R073 | Detached Autopilot Runtime | Add a Codex-independent paper/OKX-demo autopilot loop with persisted status and read-only report commands while keeping live dispatch out of scope | `backend/src/trading_assistant/autopilot/*`, `backend/src/trading_assistant/application.py`, `backend/src/trading_assistant/cli/main.py`, `backend/src/trading_assistant/config/schema.py`, `configs/config.example.yaml`, `configs/okx.demo.example.yaml`, `README.md`, `docs/DESIGN.md`, `docs/plan/2026-05-09-refactor/59-autopilot-runtime-design.md`, `docs/plan/2026-05-09-refactor/61-autopilot-runtime-report.md` | `backend/tests/unit/test_autopilot_runtime.py`, `backend/tests/integration/test_cli_core.py` | `crypto-assistant autopilot run --mode paper --cycles 1 --json`; `crypto-assistant autopilot status --json`; `crypto-assistant autopilot report --mode paper --json` | Done | Autopilot reuses existing paper/demo gates, writes `logs/autopilot-state.json`, stops on live-order signals, and never calls live broker dispatch. |
```

- [ ] **Step 4: Update acceptance checklist**

Add checked items under Core Loop and CLI Commands:

```markdown
- [x] Detached autopilot runtime can run bounded or continuous paper cycles outside Codex and persist state.
- [x] Detached autopilot runtime can invoke OKX Demo Trading windows through existing demo gates without enabling live trading.
- [x] Autopilot status and report commands are read-only and expose persisted state plus validation/operator evidence.
- [x] Autopilot stops immediately if a paper/demo payload reports `live_orders_sent=true`.
```

```markdown
- [x] `crypto-assistant autopilot run --config configs/config.example.yaml --mode paper --strategy all --cycles 1 --interval-seconds 0 --json`
- [x] `crypto-assistant autopilot status --config configs/config.example.yaml --json`
- [x] `crypto-assistant autopilot report --config configs/config.example.yaml --mode paper --strategy all --json`
```

- [ ] **Step 5: Add implementation report**

Create `docs/plan/2026-05-09-refactor/61-autopilot-runtime-report.md`:

```markdown
# Autopilot Runtime Report

## Summary

Implemented `crypto-assistant autopilot run|status|report` for Codex-independent paper and OKX Demo Trading automation. The runtime reuses the existing strategy runner, demo-window orchestration, runtime guard, validation report, and operator brief services.

## Safety

- Autopilot modes are limited to `paper` and `demo`.
- Paper autopilot refuses live-trading configs.
- Demo autopilot uses existing OKX demo readiness and demo-window gates.
- Any `live_orders_sent=true` signal stops the run and persists `stopped_reason=live_order_detected`.
- Autopilot does not call `agent execute-live`, `AgentLiveExecutionService`, `OKXLiveBroker`, or non-OKX brokers.

## Verification

Commands run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_autopilot_runtime.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py::test_cli_autopilot_run_status_and_report -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

Results:

- `tests/unit/test_autopilot_runtime.py`: passed
- `test_cli_autopilot_run_status_and_report`: passed
- `ruff check`: passed
- `mypy`: passed
```

- [ ] **Step 6: Commit**

```bash
git add README.md docs/DESIGN.md docs/plan/2026-05-09-refactor/02-acceptance-checklist.md docs/plan/2026-05-09-refactor/03-traceability-matrix.md docs/plan/2026-05-09-refactor/61-autopilot-runtime-report.md
git commit -m "docs: document autopilot runtime"
```

---

### Task 8: Final Verification

**Files:**
- All files modified in Tasks 1-7.

- [ ] **Step 1: Run focused unit tests**

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_autopilot_runtime.py -v
```

Expected: PASS.

- [ ] **Step 2: Run CLI integration test**

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py::test_cli_autopilot_run_status_and_report -v
```

Expected: PASS.

- [ ] **Step 3: Run broader CLI integration file**

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py -v
```

Expected: PASS.

- [ ] **Step 4: Run lint**

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
```

Expected: PASS.

- [ ] **Step 5: Run type check**

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

Expected: PASS.

- [ ] **Step 6: Run one real CLI smoke in paper mode**

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run crypto-assistant autopilot run \
  --config ../configs/config.example.yaml \
  --mode paper \
  --strategy cross-exchange \
  --cycles 1 \
  --interval-seconds 0 \
  --json
```

Expected: exit 0, `autopilot_run.status=Completed`, `live_orders_sent=false`.

- [ ] **Step 7: Inspect git diff for unintended live dispatch**

```bash
git diff -- backend/src/trading_assistant/autopilot backend/src/trading_assistant/application.py backend/src/trading_assistant/cli/main.py | rg "execute-live|AgentLiveExecutionService|OKXLiveBroker|agent_execute_live"
```

Expected: no output from autopilot implementation paths.

- [ ] **Step 8: Commit final verification report updates**

If validation results in `61-autopilot-runtime-report.md` need adjustment, update that file with exact observed results and run:

```bash
git add docs/plan/2026-05-09-refactor/61-autopilot-runtime-report.md
git commit -m "docs: record autopilot verification"
```

---

## Self-Review

Spec coverage:

- Codex-independent CLI loop: Tasks 5-6.
- Paper mode: Task 3 and Task 6.
- OKX Demo mode: Task 4 and Task 5.
- Persisted state: Task 2.
- Status/report commands: Task 5 and Task 6.
- Safety stop on live-order signal: Task 4.
- Config defaults: Task 1.
- Docs and traceability: Task 7.

Placeholder scan:

- No `TBD`, `TODO`, or empty implementation steps are used.
- Every code-changing task includes concrete test and implementation snippets.

Type consistency:

- CLI mode names use `paper` and `demo`.
- `AutopilotMode` matches the CLI choices.
- Application methods return payload keys `autopilot_run`, `autopilot_status`, and `autopilot_report`, matching CLI tests.
