# Carry/Basis Candidate Quality Report

Date: 2026-05-20

## Goal

Make carry/basis sweeps return higher-signal ranked candidates by adding deterministic quality scoring and an optional score floor.

## Implementation

- Added `quality_score`, `quality_bucket`, and `quality_reasons` to carry/basis optimization cards.
- Added sweep-level `--min-quality-score` support.
- Quality scoring considers:
  - target unlock priority
  - local demo readiness
  - positive or non-positive net PnL
  - break-even gap versus minimum required net PnL
  - blocker reasons such as low funding, low basis, insufficient depth, expensive hedge cost, and net profit below minimum
- Sweep summaries now include:
  - `total_card_count`
  - `filtered_out_count`
  - `min_quality_score`
  - `high_quality_candidate_count`
- Filtering affects only `ranked_cards`; per-symbol reports still include all cards and all blocker diagnostics.

## Safety Boundaries

- The feature is read-only.
- It does not call the strategy runner, demo executor, broker, or live-agent executor.
- It does not write journal, retrospective, guard, or evolution state.
- It does not mutate config or thresholds.
- Quality score is advisory and cannot bypass demo/live gates.

## Verification

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_optimization_sweeps_multiple_symbols_and_ranks_unlocks tests/integration/test_cli_core.py::test_cli_strategy_carry_basis_optimize_is_read_only -v
```

Result: first failed because `quality_score` and `--min-quality-score` were missing, then passed after implementation.

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
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy carry-basis-optimize --config ../configs/config.example.yaml --symbols BTC/USDT,ETH/USDT,SOL/USDT --target-exchange mock --min-quality-score 80 --json
```

Result: exit `0`; JSON reported `mode=sweep`, `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, `symbol_count=3`, `total_card_count=9`, `card_count=7`, `filtered_out_count=2`, `min_quality_score=80`, and `high_quality_candidate_count=7`.

## Next Step

Use `--min-quality-score 80` for operator-facing shortlists, then pass only true `demo_candidate` symbol/strategy pairs into the normal OKX Demo `demo-window` flow.
