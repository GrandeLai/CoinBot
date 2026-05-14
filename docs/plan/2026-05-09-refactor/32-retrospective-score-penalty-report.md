# Retrospective-Aware Strategy Scoring Report

Date: 2026-05-10

## Scope

Implemented a real optimization step from the latest paper/demo review: repeated OKX demo `preflight_not_profitable` issues are no longer only narrative retrospective notes. They now feed into strategy scorecards and portfolio selection.

No OKX Demo Trading orders were sent for this change. No live trading gate was enabled.

## Implementation

- Added `strategy_runtime.retrospective_demo_preflight_score_penalty`, defaulting to `30`.
- Added the setting to `configs/config.example.yaml`, `configs/okx.demo.example.yaml`, and `configs/okx.live.example.yaml`.
- Added `execution_mode` to `optimization_pressure` items so scoring can distinguish demo pressure from local paper evidence.
- Updated `StrategyScoreService` to read retrospective `optimization_pressure` before scoring.
- Repeated high-priority demo `preflight_not_profitable` issues now add:
  - `repeated_demo_preflight_not_profitable`
  - `demo_break_even_gap_usdt:<gap>`
- The configured penalty can push affected strategies below `strategy_runtime.portfolio_min_score`.

## Current Portfolio Effect

Command:

`UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy portfolio-status --config ../configs/config.example.yaml --symbol BTC/USDT --json`

Result: exit 0.

Current selected strategy:

- `triangular-multi-route`

Currently blocked by repeated OKX demo preflight pressure:

| Strategy | Score | Break-Even Gap | Block Reason |
| --- | ---: | ---: | --- |
| `cross-exchange` | `40.15` | `0.129325 USDT` | `score_below_minimum`, `repeated_demo_preflight_not_profitable` |
| `spot-perp-carry` | `38.34` | `0.258630 USDT` | `score_below_minimum`, `repeated_demo_preflight_not_profitable` |
| `funding-carry-hedged` | `37.18` | `0.258630 USDT` | `score_below_minimum`, `repeated_demo_preflight_not_profitable` |
| `futures-perp-basis` | `36.17` | `0.258606 USDT` | `score_below_minimum`, `repeated_demo_preflight_not_profitable` |

## Tests

- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_platform.py tests/unit/test_config.py tests/unit/test_strategy_runtime.py::test_strategy_retrospective_reports_optimization_pressure_for_repeated_preflight tests/integration/test_cli_core.py::test_cli_portfolio_status_applies_retrospective_pressure -q`
  - Result: `14 passed in 0.43s`.
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/platform.py src/trading_assistant/strategies/retrospective.py src/trading_assistant/config/schema.py tests/unit/test_strategy_platform.py tests/unit/test_config.py tests/unit/test_strategy_runtime.py tests/integration/test_cli_core.py`
  - Result: `All checks passed!`.
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/strategies/platform.py src/trading_assistant/strategies/retrospective.py src/trading_assistant/config/schema.py`
  - Result: `Success: no issues found in 3 source files`.
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q`
  - Result: `284 passed in 8.41s`.
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/`
  - Result: `All checks passed!`.
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/`
  - Result: `Success: no issues found in 94 source files`.

## Safety

- This change only changes scan/score/portfolio selection behavior.
- It does not submit orders.
- It does not lower `demo_min_preflight_net_pnl_usdt`.
- It does not modify strategy thresholds automatically.
- It does not enable OKX demo execution or live trading.
- It makes the next run more conservative by excluding strategies whose repeated demo preflight remains negative.
- Refactor document scan: `find docs/plan -maxdepth 1 -type f -print` returned no files.
- Hardcoded secret scan returned no matches.
- Live-switch scan found only the known OKX live example, OKX demo dry-run-off config, historical report command text, and unit-test fixtures.
