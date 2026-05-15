# Autopilot Runtime Design

## Purpose

Build a Codex-independent autopilot loop for CoinBot that can run from a shell, cron, launchd, systemd, or another external process without relying on Codex automations. The first release covers paper trading and OKX Demo Trading only. It must not automatically dispatch live orders.

The runtime should answer the operator question: "Can CoinBot keep scanning, validating, executing safe paper/demo cycles, and reporting evidence by itself?"

## Scope

In scope:

- A new `crypto-assistant autopilot` CLI command group.
- `autopilot run` for bounded or unbounded paper/demo cycles.
- `autopilot status` for the latest persisted runtime state.
- `autopilot report` for the latest state plus validation/operator evidence.
- A persisted state file under `logs/`, configurable through `strategy_runtime`.
- Hard safety stops when a live-order signal appears in a paper/demo payload.
- Reuse of existing strategy runtime, demo-window orchestration, runtime guard, validation report, and operator brief services.
- README and `docs/DESIGN.md` updates for the new operator workflow.

Out of scope:

- Automatic live order dispatch.
- A web dashboard, REST control API, task queue, or daemon installer.
- Editing strategy parameters automatically.
- Replacing existing `strategy run`, `strategy demo-window`, or `strategy demo-sampling` commands.
- Non-OKX broker execution.

## CLI Contract

The new command group:

```bash
crypto-assistant autopilot run \
  --config ../configs/config.example.yaml \
  --mode paper \
  --strategy all \
  --symbol BTC/USDT \
  --cycles 0 \
  --interval-seconds 60 \
  --json

crypto-assistant autopilot run \
  --config ../configs/okx.demo.example.yaml \
  --mode demo \
  --strategy triangular-multi-route \
  --symbol BTC/USDT \
  --cycles 0 \
  --interval-seconds 300 \
  --demo-cycles-per-window 3 \
  --target-exchange okx \
  --json

crypto-assistant autopilot status --config ../configs/config.example.yaml --json
crypto-assistant autopilot report --config ../configs/config.example.yaml --mode paper --json
```

`--cycles 0` means run until stopped, matching the existing strategy runner convention. Tests should use bounded cycles.

## Architecture

Add a focused `trading_assistant.autopilot` package:

- `models.py`: dataclasses for autopilot mode, cycle records, run result, state, and report.
- `state.py`: JSON state store with atomic replace writes.
- `runtime.py`: orchestration loop for paper and demo modes.

Wire it through the existing service facade and CLI:

- `TradingAssistantApp.autopilot_run(...)`
- `TradingAssistantApp.autopilot_status(...)`
- `TradingAssistantApp.autopilot_report(...)`
- CLI handlers under `backend/src/trading_assistant/cli/main.py`

The CLI stays thin. Business rules live in the new autopilot runtime service.

## Paper Mode Flow

Each paper cycle runs:

1. `StrategyRunner.run(..., max_cycles=1, execution_mode="paper")`
2. `strategy_validation_report(execution_mode="paper", strategy_name=...)`
3. `strategy_operator_brief(execution_mode="paper", strategy_name=...)`
4. state persistence with cycle status, decisions, risk reasons, and summary metrics

Paper mode must always use dry-run/paper execution through existing services. It must never call `AgentLiveExecutionService` or `OKXLiveBroker`.

## Demo Mode Flow

Each demo cycle runs:

1. OKX demo config readiness check through existing application guard.
2. `strategy_demo_window(...)`, which already performs sandbox health, runtime guard status, read-only market comparison, rolling validation, local validation, demo preflight, and OKX Demo Trading execution.
3. `strategy_validation_report(execution_mode="demo", strategy_name=...)`
4. `strategy_operator_brief(execution_mode="demo", strategy_name=...)`
5. state persistence with orchestration status, block reasons, order-attempt signal, and live-order signal

Demo mode may send tiny OKX Demo Trading orders only through existing demo gates. It must never use the OKX live profile.

## Safety Rules

The autopilot runtime must enforce these rules:

- Accepted modes are only `paper` and `demo`.
- Paper mode fails if `settings.trading.live_trading` is true.
- Demo mode requires the existing OKX demo config readiness checks.
- Any payload containing `live_orders_sent=true` stops the run immediately and records `stopped_reason="live_order_detected"`.
- Consecutive blocked cycles are counted. If the configured limit is reached, the run stops with `stopped_reason="max_consecutive_blocked_cycles"`.
- State output must not contain credential values.
- The runtime must not call `agent execute-live`, `AgentLiveExecutionService`, or any live broker.
- Live readiness may appear only as report evidence, not as an execution action.

## Configuration

Add optional fields to `StrategyRuntimeConfig` because autopilot is part of the strategy runtime surface:

```yaml
strategy_runtime:
  autopilot_state_path: logs/autopilot-state.json
  autopilot_default_interval_seconds: 60
  autopilot_max_consecutive_blocked_cycles: 3
  autopilot_stop_on_live_signal: true
```

These defaults keep behavior deterministic for local use. The runtime should also accept CLI overrides for cycle count, interval, mode, strategy, symbol, demo cycles per window, target exchange, and report limit.

## State File

The state file stores only operational metadata:

```json
{
  "status": "Running | Completed | Stopped | Failed | NeverRun",
  "mode": "paper",
  "strategy_name": "all",
  "symbol": "BTC/USDT",
  "cycles_requested": 1,
  "cycles_completed": 1,
  "last_cycle_at": "2026-05-15T00:00:00Z",
  "stopped_reason": null,
  "consecutive_blocked_cycles": 0,
  "live_orders_sent": false,
  "orders_attempted": false,
  "last_payload_summary": {
    "decision_counts": {"executed": 1, "blocked": 0, "skipped": 0},
    "block_reasons": []
  }
}
```

Atomic writes should use a temporary file in the same directory followed by replace, so interrupted writes do not corrupt the state.

## Reporting

`autopilot report` returns:

- latest autopilot state
- guard status
- validation report
- operator brief
- promotion status when available
- `orders_sent=false` for paper report contexts when no demo order was attempted
- `live_orders_sent=false` unless a safety stop recorded otherwise

The report is read-only. It must not mutate journal, retrospective, evolution, or exchange state.

## Failure Handling

Expected failures should become structured cycle records:

- health gate blocked
- runtime guard cooldown
- no opportunity
- local validation not passed
- demo preflight not profitable
- market data failure
- exchange rate-limit failure

Unexpected exceptions should persist a `Failed` state with the exception type and sanitized message before returning a CLI error.

## Testing

Use TDD. Add focused tests for:

- paper autopilot completes one bounded cycle and persists state
- paper autopilot refuses to run when live trading is enabled
- demo autopilot stops on a simulated live-order signal
- blocked-cycle limit stops the run after the configured threshold
- state store survives missing state file and writes atomically
- CLI exposes `autopilot run`, `autopilot status`, and `autopilot report` with JSON output

Run targeted tests first, then broader backend checks:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_autopilot_runtime.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

## Acceptance Criteria

- `crypto-assistant autopilot run --mode paper --cycles 1 --json` completes without live orders and writes state.
- `crypto-assistant autopilot run --mode demo --cycles 1 --json` uses the existing OKX Demo Trading orchestration and blocks or executes only through demo gates.
- `crypto-assistant autopilot status --json` works before and after a run.
- `crypto-assistant autopilot report --json` returns state plus validation/operator evidence without sending orders.
- Safe defaults remain unchanged: live trading disabled, dry-run enabled, mock exchange enabled.
- No production code path introduced by autopilot can call the live broker.
