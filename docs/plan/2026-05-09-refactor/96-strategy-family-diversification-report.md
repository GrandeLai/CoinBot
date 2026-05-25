# Strategy Family Diversification Report

Date: 2026-05-20

## Goal

Make strategy-family concentration explicit so validation effort can move beyond triangular arbitrage when carry/basis, hedged-maker, directional, grid, or portfolio families have viable candidates.

## Implementation

- Added `StrategyDiversificationService`.
- Added `strategy diversification-report`.
- Aggregates deterministic advisory-rank rows into families:
  - `triangular`
  - `carry_basis`
  - `cross_exchange`
  - `hedged_maker`
  - `directional`
  - `grid`
  - `portfolio`
- Each family row includes:
  - strategy list and counts
  - current candidate count
  - journal-observed demo candidate count
  - validation executions and realized PnL
  - candidate share percentage
  - advisory validation-budget share percentage
  - over-concentration flag
  - family-specific recommendations
- Report summary includes dominant family, over-concentrated families, candidate-family count, and total candidates.

## Safety Boundaries

- The feature is read-only.
- It reuses advisory ranking, validation report, opportunity density, and runtime guard evidence.
- It does not call the strategy runner, demo executor, broker, or live-agent executor.
- It does not write journal, retrospective, guard, or evolution state.
- Advisory budget caps do not bypass demo-window, risk, preflight, receipt, residual, or live gates.

## Verification

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_advisory_ranker.py::test_diversification_report_caps_family_validation_budget tests/integration/test_cli_core.py::test_cli_strategy_diversification_report_is_read_only -v
```

Result: first failed because `trading_assistant.strategies.diversification` and `strategy diversification-report` were missing, then passed after implementation.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_advisory_ranker.py tests/integration/test_cli_core.py::test_cli_strategy_diversification_report_is_read_only tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -v
```

Result: `5 passed`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/diversification.py src/trading_assistant/application.py src/trading_assistant/cli/main.py tests/unit/test_advisory_ranker.py tests/integration/test_cli_core.py
```

Result: `All checks passed!`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/strategies/diversification.py src/trading_assistant/application.py src/trading_assistant/cli/main.py
```

Result: `Success: no issues found in 3 source files`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy diversification-report --config ../configs/config.example.yaml --strategy all --symbol BTC/USDT --execution-mode paper --limit 20 --window 24h --max-family-share-pct 60 --json
```

Result: exit `0`; JSON reported `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, `family_count=7`, `candidate_family_count=6`, `total_candidate_count=11`, `max_family_share_pct=60`, `family_concentration_guard`, and per-family validation-budget shares capped at `16.67%` for candidate families.

## Later Extension

This report is extended by `docs/plan/2026-05-09-refactor/103-diversification-validation-queue-report.md`, which adds the read-only `validation_queue` shortlist for choosing non-triangular validation candidates before adding more triangular-only samples.
