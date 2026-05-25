# Carry/Basis Bounded Observer Report

Date: 2026-05-20

## Goal

Reduce dependence on triangular-arbitrage profitability by making non-triangular carry/basis candidate discovery bounded, repeatable, and diagnosable across multiple OKX symbols.

## Implementation

- Added sweep observations with per-symbol status:
  - `completed`
  - `cached`
  - `skipped_request_budget`
  - `timed_out`
  - `failed`
- Added sweep summary fields:
  - `requested_symbol_count`
  - `evaluated_symbol_count`
  - `skipped_symbol_count`
  - `timeout_symbol_count`
  - `failed_symbol_count`
  - `cache_hit_count`
  - `max_symbols`
  - `request_budget_seconds`
  - `per_symbol_timeout_seconds`
  - `elapsed_seconds`
- Added read-only CLI controls:
  - `--max-symbols`
  - `--request-budget-seconds`
  - `--per-symbol-timeout-seconds`
- Added in-process report caching for repeated symbol/target pairs within one optimizer service lifetime.

## Safety Boundaries

- The feature is read-only.
- It does not call the strategy runner, demo executor, broker, or live-agent executor.
- It does not write journal, retrospective, guard, or evolution state.
- It does not mutate config or thresholds.
- A completed observer card still must pass the normal `demo-window`, runtime guard, risk, preflight, receipt, residual, and live gates before any order path.

## Verification

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_optimization_sweep_respects_observation_budget tests/unit/test_strategy_platform.py::test_carry_basis_optimization_sweep_classifies_symbol_timeouts tests/integration/test_cli_core.py::test_cli_strategy_carry_basis_optimize_is_read_only -v
```

Result: first failed because sweep budget parameters and CLI flags were missing, then passed after implementation.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_optimization_reports_break_even_gaps_without_trading tests/unit/test_strategy_platform.py::test_carry_basis_optimization_merges_target_market_unlock_diagnostics tests/unit/test_strategy_platform.py::test_carry_basis_optimization_sweeps_multiple_symbols_and_ranks_unlocks tests/unit/test_strategy_platform.py::test_carry_basis_optimization_sweep_respects_observation_budget tests/unit/test_strategy_platform.py::test_carry_basis_optimization_sweep_classifies_symbol_timeouts tests/integration/test_cli_core.py::test_cli_strategy_carry_basis_optimize_is_read_only -v
```

Result: `6 passed`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/carry_basis_optimizer.py src/trading_assistant/application.py src/trading_assistant/cli/main.py tests/unit/test_strategy_platform.py tests/integration/test_cli_core.py
```

Result: `All checks passed!`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/strategies/carry_basis_optimizer.py src/trading_assistant/application.py src/trading_assistant/cli/main.py
```

Result: `Success: no issues found in 3 source files`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy carry-basis-optimize --config ../configs/config.example.yaml --symbols BTC/USDT,ETH/USDT,SOL/USDT --target-exchange mock --min-quality-score 80 --max-symbols 2 --request-budget-seconds 30 --per-symbol-timeout-seconds 10 --json
```

Result: exit `0`; JSON reported `mode=sweep`, `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, `symbol_count=2`, `requested_symbol_count=2`, `skipped_symbol_count=0`, `timeout_symbol_count=0`, `failed_symbol_count=0`, `request_budget_seconds=30`, `per_symbol_timeout_seconds=10`, and two `completed` observations.

```bash
git diff --check
```

Result: no whitespace errors.

## Next Step

Use bounded OKX sweeps as the Phase A observer layer, then implement strategy-family diversification reporting and validation-budget caps.
