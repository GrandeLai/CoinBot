# Demo Window Orchestrator Report

Date: 2026-05-14

## Goal

Add a safer operator entrypoint for repeated OKX Demo Trading windows. The command should run no-order health and evidence gates before delegating to the existing `validate-demo-window` execution path, so local network or OKX health failures do not get recorded as strategy market-data failures.

## Implementation

- Added `StrategyDemoWindowOrchestrator` in `backend/src/trading_assistant/validation/demo_window_orchestrator.py`.
- Added `crypto-assistant strategy demo-window`.
- Prechecks run in this order:
  1. OKX sandbox health check.
  2. Runtime guard status.
  3. Read-only `strategy market-compare`.
  4. Read-only `strategy validation-report`.
  5. Existing `strategy validate-demo-window` only if all gates pass.
- Health exceptions are captured as `health_check_failed` and block before the strategy runner.
- The orchestrator reports `orders_attempted=false` and `live_orders_sent=false` for blocked precheck paths.

## Safety Notes

- No live trading gates were enabled or weakened.
- The command still requires the OKX demo profile and the existing demo-order safety conditions.
- The command does not clear runtime guard state; it only reads guard status before execution.
- `validate-demo-window` remains the only execution path used after prechecks pass, preserving local validation, receipt checks, residual inventory checks, and post-run open-risk checks.

## Verification

| Command | Result |
| --- | --- |
| `UV_CACHE_DIR=../.uv-cache ../.venv/bin/pytest tests/unit/test_demo_window_orchestrator.py tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history tests/integration/test_cli_core.py::test_cli_strategy_demo_window_blocks_with_safe_default_config -q` | Pass: 6 tests. |
| `uv run pytest tests/ -v` | Pass: 321 tests. |
| `uv run ruff check src/ tests/` | Pass. |
| `uv run mypy src/` | Pass: no issues in 110 source files. |
