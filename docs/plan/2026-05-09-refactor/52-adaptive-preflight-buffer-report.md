# Phase 52 - Adaptive Demo Preflight Buffer

## Goal

Improve the OKX Demo Trading sampling path by requiring extra preflight PnL margin when recent executed demo samples show that actual cash-flow PnL underperformed the no-order preflight estimate.

## Implementation

- Added `AdaptivePreflightBufferService` in `backend/src/trading_assistant/strategies/preflight_buffer.py`.
- The service reads only the append-only strategy journal and computes positive `expected - actual_cash_flow` gaps from recent executed demo events.
- `StrategyRunner` now annotates each demo preflight with `adaptive_preflight_buffer` metadata and applies the effective threshold before any OKX Demo Trading order can be sent.
- Directional lifecycle previews are explicitly skipped because directional entry/hold previews do not represent immediate arbitrage PnL.
- Added runtime config fields:
  - `demo_preflight_adaptive_buffer_enabled`
  - `demo_preflight_adaptive_buffer_min_samples`
  - `demo_preflight_adaptive_buffer_quantile_pct`
  - `demo_preflight_adaptive_buffer_lookback`
  - `demo_preflight_adaptive_buffer_max_usdt`

## Safety Boundaries

- No live trading gates were changed.
- No exchange API calls were added to the buffer calculation.
- The buffer can only raise the effective demo preflight threshold; it cannot lower `demo_min_preflight_net_pnl_usdt`.
- Demo orders still require local validation, OKX demo mode, operator/demo permissions, risk approval, preflight approval, and runtime guard approval.
- The feature is read-only with respect to strategy parameters and does not mutate configs from runtime observations.

## Verification

```bash
cd backend && uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_runner_blocks_demo_when_adaptive_preflight_buffer_not_met tests/unit/test_strategy_runtime.py::test_strategy_runner_allows_demo_when_adaptive_preflight_buffer_is_met tests/unit/test_strategy_runtime.py::test_adaptive_preflight_buffer_skips_directional_lifecycle_previews -v
```

Result: `3 passed`.

```bash
cd backend && uv run pytest tests/unit/test_strategy_runtime.py -v
```

Result: `55 passed`.

```bash
cd backend && uv run ruff check src/ tests/
```

Result: `All checks passed!`.

```bash
cd backend && uv run mypy src/
```

Result: `Success: no issues found in 111 source files`.

```bash
cd backend && uv run pytest tests/ -v
```

Result: `324 passed`.

## Next Step

Proceed to the same-size OKX demo sampling scheduler/window runner. It should use the existing `strategy demo-window` orchestration plus this adaptive buffer so low-margin samples are blocked before any demo order attempt.
