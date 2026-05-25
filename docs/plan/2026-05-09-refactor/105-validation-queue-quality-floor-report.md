# Validation Queue Quality Floor Report

Date: 2026-05-20

## Goal

Improve the actionable quality of validation candidates without hiding the full family concentration picture or changing any paper/demo/live execution gates.

## Implementation

- Added `quality_score`, `quality_bucket`, and `quality_reasons` to every `validation_queue` item.
- Added `min_queue_quality_score` to `StrategyDiversificationService.report`.
- Added `--min-queue-quality-score` to `strategy diversification-report`.
- Queue filtering is applied after quality scoring and before summary counts.
- Filtered queue items are renumbered so ranks remain contiguous.
- Family rows remain unfiltered.
- Summary now reports:
  - `unfiltered_validation_queue_count`
  - `filtered_validation_queue_count`
  - `high_quality_queue_count`
  - `min_queue_quality_score`

## Quality Model

- Rewards:
  - high advisory score
  - current opportunity evidence
  - recent density or demo candidate evidence
  - validation samples
  - positive validation PnL
  - validation win-rate evidence
  - non-triangular diversification value
- Penalizes:
  - runtime guard cooldown
  - repeated demo preflight pressure
  - observed demo break-even gaps
  - validation quality failures
  - watchlist or paper-only advisory stages

## Safety Boundaries

- The feature is read-only.
- It reuses advisory ranking, validation report, opportunity density, and runtime guard evidence.
- It does not call the strategy runner, demo executor, hedged-maker demo manager, broker, live-agent executor, or exchange APIs.
- It does not write journal, retrospective, guard, or evolution state.
- Quality filtering affects only the queue shortlist. It does not mutate config, family diagnostics, portfolio selection, strategy ranking, or any safety gate.

## Verification

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_advisory_ranker.py::test_diversification_report_builds_non_triangular_validation_queue tests/unit/test_advisory_ranker.py::test_diversification_report_filters_validation_queue_by_quality tests/integration/test_cli_core.py::test_cli_strategy_diversification_report_is_read_only -q
```

Result: first failed because quality fields, service parameter, and CLI flag were missing; passed after implementation.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_advisory_ranker.py tests/integration/test_cli_core.py::test_cli_strategy_diversification_report_is_read_only tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -q
```

Result: `7 passed`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/diversification.py src/trading_assistant/application.py src/trading_assistant/cli/main.py tests/unit/test_advisory_ranker.py tests/integration/test_cli_core.py
```

Result: `All checks passed!`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/strategies/diversification.py src/trading_assistant/application.py src/trading_assistant/cli/main.py
```

Result: `Success: no issues found in 3 source files`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy diversification-report --config ../configs/config.example.yaml --strategy all --symbol BTC/USDT --execution-mode paper --limit 20 --window 24h --max-family-share-pct 60 --min-queue-quality-score 80 --json
```

Result: exit `0`; JSON reported `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, `validation_queue_count=4`, `unfiltered_validation_queue_count=9`, `filtered_validation_queue_count=5`, `non_triangular_queue_count=3`, `triangular_queue_count=1`, `high_quality_queue_count=4`, and `min_queue_quality_score=80`.

## Next Step

Use `--min-queue-quality-score 80` for normal validation-window shortlist planning. If the queue becomes empty, lower the floor only for observation planning; do not lower preflight, risk, receipt, residual, demo, or live gates.
