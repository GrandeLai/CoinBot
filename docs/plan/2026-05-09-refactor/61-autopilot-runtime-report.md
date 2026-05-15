# Autopilot Runtime Report

## Summary

Implemented `crypto-assistant autopilot run|status|report` for Codex-independent paper and OKX Demo Trading automation. The runtime reuses the existing strategy runner, demo-window orchestration, runtime guard, validation report, and operator brief services.

## Safety

- Autopilot modes are limited to `paper` and `demo`.
- Paper autopilot refuses live-trading configs.
- Demo autopilot refuses live-trading configs and uses existing OKX demo-window gates when run through the application facade.
- Any `live_orders_sent=true` signal stops the run and persists `stopped_reason=live_order_detected`.
- Autopilot does not call `agent execute-live`, `AgentLiveExecutionService`, `OKXLiveBroker`, or non-OKX brokers.

## Verification

Commands run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_autopilot_runtime.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py::test_cli_autopilot_run_status_and_report -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
UV_CACHE_DIR=.uv-cache uv run crypto-assistant autopilot run --config ../configs/config.example.yaml --mode paper --strategy cross-exchange --cycles 1 --interval-seconds 0 --json
```

Results:

- `tests/unit/test_autopilot_runtime.py`: 8 passed
- `test_cli_autopilot_run_status_and_report`: 1 passed
- `tests/integration/test_cli_core.py`: 20 passed
- `ruff check`: passed
- `mypy`: success, no issues in 119 source files
- Paper CLI smoke: exit 0, `autopilot_run.status=Completed`, `cycles_completed=1`, `live_orders_sent=false`
