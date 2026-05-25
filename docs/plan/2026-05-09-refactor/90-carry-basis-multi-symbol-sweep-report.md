# Carry/Basis Multi-Symbol Sweep Report

Date: 2026-05-20

## Goal

Avoid repeatedly hitting OKX Demo preflight with the same blocked symbol by ranking carry/basis target-unlock diagnostics across multiple symbols first.

## Implementation

- Added `CarryBasisOptimizationSweep` and `CarryBasisOptimizationService.sweep()`.
- Added `--symbols` to `crypto-assistant strategy carry-basis-optimize`.
- Preserved the existing single-symbol `--symbol` response when `--symbols` is not supplied.
- Sweep output includes:
  - `mode=sweep`
  - requested `symbols`
  - per-symbol `reports`
  - global `ranked_cards`
  - summary fields for symbol count, card count, candidate counts, top symbol, top strategy, and closest break-even gap
- Ranking orders cards by:
  - `demo_candidate`
  - `paper_candidate`
  - `observe_only`
  - `local_only`
  - then break-even gap and deterministic tie-breakers
- Tightened `funding-carry-hedged` scanner wiring so symbol-specific scans and diagnostics respect the requested symbol instead of always ranking the full funding universe.
- Scoped carry/basis target comparison to the three carry/basis strategies instead of invoking all registered strategy scans.

## Safety Boundaries

- The sweep is read-only.
- It does not call the strategy runner, demo executor, broker, or live-agent executor.
- It does not write journal, retrospective, guard, or evolution state.
- It does not mutate config or thresholds.
- It reports `orders_sent=false` and `live_orders_sent=false`.
- It is an input to future demo-window selection, not a demo order path.

## Verification

```bash
cd backend && uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_optimization_sweeps_multiple_symbols_and_ranks_unlocks -v
```

Result: first failed with `AttributeError: 'CarryBasisOptimizationService' object has no attribute 'sweep'`, then passed after implementation.

```bash
cd backend && uv run pytest tests/integration/test_cli_core.py::test_cli_strategy_carry_basis_optimize_is_read_only -v
```

Result: first failed because `--symbols` was not accepted, then passed after CLI wiring.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_optimization_sweeps_multiple_symbols_and_ranks_unlocks tests/unit/test_strategy_platform.py::test_carry_basis_optimization_merges_target_market_unlock_diagnostics tests/unit/test_strategy_platform.py::test_carry_basis_optimization_reports_break_even_gaps_without_trading tests/integration/test_cli_core.py::test_cli_strategy_carry_basis_optimize_is_read_only -v
```

Result: `4 passed`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/carry_basis_optimizer.py src/trading_assistant/arbitrage/funding_carry_hedged.py src/trading_assistant/arbitrage/scanner.py src/trading_assistant/strategies/platform.py src/trading_assistant/application.py src/trading_assistant/cli/main.py tests/unit/test_strategy_platform.py tests/integration/test_cli_core.py
```

Result: `All checks passed!`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/strategies/carry_basis_optimizer.py src/trading_assistant/arbitrage/funding_carry_hedged.py src/trading_assistant/arbitrage/scanner.py src/trading_assistant/strategies/platform.py src/trading_assistant/application.py src/trading_assistant/cli/main.py
```

Result: `Success: no issues found in 6 source files`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy carry-basis-optimize --config ../configs/config.example.yaml --symbols BTC/USDT,ETH/USDT,SOL/USDT --target-exchange mock --json
```

Result: exit `0`; JSON reported `mode=sweep`, `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, `symbol_count=3`, `card_count=9`, `target_demo_preflight_candidate_count=7`, and `high_priority_unlock_count=7`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy carry-basis-optimize --config ../configs/okx.demo.example.yaml --symbols BTC/USDT --target-exchange okx --json
```

Result: exit `0`; JSON reported `mode=sweep`, `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, `symbol_count=1`, `card_count=3`, `target_demo_preflight_candidate_count=0`, `high_priority_unlock_count=0`, `top_strategy=futures-perp-basis`, and closest break-even gap about `0.073483` USDT.

## OKX Multi-Symbol Observation

An attempted OKX read-only sweep over `BTC/USDT,ETH/USDT,SOL/USDT` and an earlier six-symbol sweep were manually terminated after exceeding the normal single-symbol diagnostic window. No orders were attempted. The likely cause is serial OKX public endpoint latency across spot/perp/futures/funding reads.

Follow-up: add request budgeting or bounded per-symbol timeout before using wide OKX sweeps as an operator routine.

## Next Step

Use the sweep locally or with a small OKX symbol set to identify `demo_candidate` cards. Only pass a symbol/strategy pair into OKX Demo `demo-window` when the sweep reports `unlock_priority=demo_candidate` and the normal safety gates remain clean.
