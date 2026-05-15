# Phase 54 - Strategy PnL Attribution Ledger

## Goal

Add a read-only strategy-level PnL attribution ledger so OKX demo evidence can separate strategy order cash-flow from whole-account equity movement and unrelated inventory mark-to-market effects.

## Implementation

- Added `StrategyPnlAttributionService` in `backend/src/trading_assistant/strategies/pnl_attribution.py`.
- Added `crypto-assistant strategy pnl-attribution`.
- The report reads only `strategy_runtime.journal_path` and emits:
  - preflight expected PnL
  - realized event net profit
  - strategy order cash-flow PnL
  - account-equity delta
  - account attribution gap
  - residual inventory
  - PnL and residual tolerance flags
  - row-level attribution classification
- The report always returns `orders_sent=false` and `live_orders_sent=false`.

## Safety Boundaries

- No exchange API calls were added.
- No broker/order dispatch path was added.
- No runtime guard, strategy parameter, or config mutation was added.
- Live trading gates remain unchanged.

## Verification

```bash
cd backend && uv run pytest tests/unit/test_pnl_attribution.py tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history tests/integration/test_cli_core.py::test_cli_strategy_pnl_attribution_reads_journal_without_trading -v
```

Result: `3 passed`.

```bash
cd backend && uv run ruff check src/ tests/
```

Result: `All checks passed!`.

```bash
cd backend && uv run mypy src/
```

Result: `Success: no issues found in 113 source files`.

```bash
cd backend && uv run pytest tests/ -v
```

Result: `330 passed`.

## Next Step

Proceed to carry/basis offline optimization. The new ledger gives cleaner demo evidence, while the next phase should improve scanner thresholds and diagnostics for strategies that are still blocked by non-profitable preflight.
