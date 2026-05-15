# Phase 53 - Same-Size Demo Sampling Scheduler

## Goal

Add a bounded same-size OKX Demo Trading sampling scheduler so repeated evidence collection uses the safer `strategy demo-window` precheck path instead of ad hoc repeated commands.

## Implementation

- Added `StrategyDemoSamplingScheduler` in `backend/src/trading_assistant/validation/demo_sampling_scheduler.py`.
- Added `crypto-assistant strategy demo-sampling`.
- The scheduler repeats `strategy demo-window` for a bounded number of windows using the same configured demo size stage:
  - `demo_order_size_multiplier`
  - `demo_max_order_value_usdt`
- It sleeps only between successful order-attempt windows.
- It stops immediately on:
  - precheck block reasons from `strategy demo-window`
  - windows that complete without demo order attempts
  - any live-order signal, which should remain impossible under the existing gates
- The command preserves the existing OKX demo config gate and refuses safe default config before any scheduler work starts.

## Safety Boundaries

- No new broker, exchange, or order-dispatch path was added.
- The scheduler delegates to `strategy demo-window`, which already runs OKX sandbox health, runtime guard status, market comparison, validation report, local validation, and demo-window validation.
- Live trading remains disabled by default and still requires the separate autonomous/live gates.
- The scheduler is bounded by `--windows`; it is not a background daemon.

## Verification

```bash
cd backend && uv run pytest tests/unit/test_demo_sampling_scheduler.py tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history tests/integration/test_cli_core.py::test_cli_strategy_demo_sampling_blocks_with_safe_default_config -v
```

Result: `5 passed`.

```bash
cd backend && uv run ruff check src/ tests/
```

Result: `All checks passed!`.

```bash
cd backend && uv run mypy src/
```

Result: `Success: no issues found in 112 source files`.

```bash
cd backend && uv run pytest tests/ -v
```

Result: `328 passed`.

## Next Step

Proceed to strategy-level PnL attribution. The scheduler now provides bounded same-size collection; the next improvement should separate strategy cash-flow PnL from account-wide inventory and mark-to-market movement.
