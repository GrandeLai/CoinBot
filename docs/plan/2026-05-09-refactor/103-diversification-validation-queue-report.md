# Diversification Validation Queue Report

Date: 2026-05-20

## Goal

Make the strategy-family diversification report immediately actionable by returning a deterministic validation queue that prefers non-triangular candidates before adding more triangular-only samples.

## Implementation

- Extended `StrategyDiversificationReport` with `validation_queue`.
- Added `StrategyValidationQueueItem`.
- Queue rows include:
  - rank
  - strategy name and family
  - execution mode
  - recommended advisory stage
  - advisory score
  - family validation-budget share
  - family candidate share
  - current opportunity count
  - recent opportunity-density count
  - demo candidate count
  - validation execution count and PnL
  - runtime guard cooldown state
  - next action
  - reasons
- Queue sorting:
  - non-triangular family first when non-triangular candidate evidence exists
  - current opportunity before historical-only evidence
  - higher family validation budget
  - higher advisory score
  - higher validation PnL
  - stable advisory rank and strategy name
- Report summary now includes `validation_queue_count`, `non_triangular_queue_count`, `triangular_queue_count`, and `queue_policy`.
- CLI text summary includes the queue count.

## Safety Boundaries

- The feature is read-only.
- It reuses advisory ranking, validation report, opportunity density, and runtime guard evidence.
- It does not call the strategy runner, demo executor, hedged-maker demo manager, broker, live-agent executor, or exchange APIs.
- It does not write journal, retrospective, guard, or evolution state.
- Queue actions are recommendations only and cannot bypass demo-window, risk, preflight, receipt, residual, or live gates.

## Verification

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_advisory_ranker.py::test_diversification_report_builds_non_triangular_validation_queue tests/integration/test_cli_core.py::test_cli_strategy_diversification_report_is_read_only -q
```

Result: first failed with missing `validation_queue` and queue summary fields, then passed after implementation.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_advisory_ranker.py tests/integration/test_cli_core.py::test_cli_strategy_diversification_report_is_read_only tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -q
```

Result: `6 passed`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/diversification.py src/trading_assistant/cli/main.py tests/unit/test_advisory_ranker.py tests/integration/test_cli_core.py
```

Result: `All checks passed!`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/strategies/diversification.py src/trading_assistant/cli/main.py
```

Result: `Success: no issues found in 2 source files`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy diversification-report --config ../configs/config.example.yaml --strategy all --symbol BTC/USDT --execution-mode paper --limit 20 --window 24h --max-family-share-pct 60 --json
```

Result: exit `0`; JSON reported `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, `validation_queue_count=9`, `non_triangular_queue_count=8`, `triangular_queue_count=1`, `queue_policy=family_budget_capped_non_triangular_first`, first queue family `directional`, and triangular action `hold_triangular_within_family_cap`.

## Next Step

Use `validation_queue` as the pre-window candidate shortlist, then run the normal paper/demo validation commands for the selected non-triangular candidates without relaxing preflight or risk gates.

## Later Extension

This report is extended by `docs/plan/2026-05-09-refactor/105-validation-queue-quality-floor-report.md`, which adds deterministic queue quality scores and `--min-queue-quality-score` filtering.
