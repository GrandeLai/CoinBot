# Strategy Optimization Pressure Report

Date: 2026-05-10

## Scope

Implemented `R055 Retrospective-Driven Optimization Pressure`.

The goal is to turn repeated retrospective issues into machine-readable optimization guidance before the next strategy execution or parameter change. This specifically addresses the current repeated OKX demo issue where non-triangular strategies are skipped by `demo_preflight_not_profitable`.

## Implemented

- Added `optimization_pressure` to `StrategyRetrospectiveService` summaries.
- Added a `Strategy Optimization Pressure` section to `28-strategy-retrospective.md`.
- Added per-strategy guidance for repeated negative preflight:
  - observed net PnL
  - break-even gap in USDT
  - priority
  - strategy-specific action
  - config fields to review
  - hard guardrails
- Added tests for optimization pressure output and CLI presence.

## Current Findings

Command:

`UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy retrospective --config ../configs/okx.demo.example.yaml --json`

Result:

- Exit code: 0
- `optimization_pressure` items: 4
- All items are high priority because each repeated 10 times in the latest OKX demo snapshot.
- Current break-even gaps:
  - `cross-exchange`: `0.129325 USDT`
  - `funding-carry-hedged`: `0.258630 USDT`
  - `futures-perp-basis`: `0.258606 USDT`
  - `spot-perp-carry`: `0.258630 USDT`

## Guardrails

The guidance explicitly keeps these rules:

- Do not lower `strategy_runtime.demo_min_preflight_net_pnl_usdt` below zero.
- Do not force demo orders when preflight is negative.
- Run `strategy validate-local` before OKX demo execution.
- Do not increase demo size until repeated clean passes.
- Do not enable live trading or live-canary promotion from this signal alone.

## Tests

- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_retrospective_reports_optimization_pressure_for_repeated_preflight -q`
  - Result: `1 passed`
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/retrospective.py tests/unit/test_strategy_runtime.py`
  - Result: `All checks passed!`
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/strategies/retrospective.py`
  - Result: `Success: no issues found in 1 source file`

Full-suite results are recorded in `99-final-acceptance-report.md`.

Latest full-suite result after R055:

- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q`
  - Result: `282 passed in 8.83s`
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/`
  - Result: `All checks passed!`
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/`
  - Result: `Success: no issues found in 94 source files`

## Next Step

Use this pressure output before the next run:

1. Keep `triangular-multi-route` at current demo size.
2. Do not force the four negative-preflight strategies into OKX demo orders.
3. Improve carry/basis scanners by requiring their projected funding or basis edge to exceed the reported break-even gap plus configured fees, slippage, and holding cost.
4. Re-run local validation before another OKX demo window.
