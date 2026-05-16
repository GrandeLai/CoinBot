# Hedged Maker Budget State Report

Date: 2026-05-16

## Summary

Added lifecycle-aware budget accounting for hedged-maker paper quotes. Strategy budget decisions now distinguish current active orders/capital from projected orders/capital, and hedged-maker reads its persisted paper quote state before budget evaluation.

## Implementation

- Extended `StrategyBudgetDecision` with:
  - `projected_open_orders`
  - `active_capital_usdt`
  - `projected_strategy_capital_usdt`
- Extended `StrategyPolicy.evaluate` with projected-budget inputs while preserving defaults for existing strategies.
- Added `HedgedMakerPaperBudgetState`.
- Added `HedgedMakerPaperLifecycleService.budget_state()`.
- Budget-active hedged-maker statuses:
  - `open`
  - `partial_open`
  - `cancel_pending` before `cancel_effective_at`
- Excluded expired TTL quotes, stale quotes, and completed cancel-pending quotes from budget occupancy because the lifecycle state machine will cancel or complete them on apply.
- Wired `StrategyRunner` so hedged-maker budget evaluation uses paper state before order lifecycle apply.
- Matching active hedged-maker quotes consume current order/capital budget but do not add incremental projected order/capital for the same symbol/maker/hedge opportunity.

## Safety

- This is still paper-only lifecycle accounting.
- No exchange APIs are called while computing budget state.
- No journal or paper state files are mutated by `budget_state()`.
- Demo/live support for `hedged-maker` remains disabled.
- Real order gates are unchanged.

## Verification

RED:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_policy_uses_projected_order_and_capital_budget tests/unit/test_hedged_maker_lifecycle.py::test_hedged_maker_lifecycle_budget_state_counts_active_non_expired_quotes tests/integration/test_cli_core.py::test_cli_strategy_hedged_maker_scans_and_runs_in_paper -v
```

Result:

- `StrategyPolicy.evaluate()` rejected the new projected-budget arguments.
- `HedgedMakerPaperLifecycleService` had no `budget_state()`.
- CLI hedged-maker budget payload still reported `active_orders=0` on the second paper run.

Focused GREEN:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_policy_uses_projected_order_and_capital_budget tests/unit/test_hedged_maker_lifecycle.py::test_hedged_maker_lifecycle_budget_state_counts_active_non_expired_quotes tests/integration/test_cli_core.py::test_cli_strategy_hedged_maker_scans_and_runs_in_paper -v
```

Result: `3 passed in 0.43s`.

Final verification:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_strategy_runtime.py tests/unit/test_hedged_maker_lifecycle.py tests/integration/test_cli_core.py -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

Result:

- `92 passed in 8.00s`
- `All checks passed!`
- `Success: no issues found in 125 source files`

## Follow-up

Next ordered item: implement an OKX Demo hedged-maker stateful order manager behind demo-only gates and operation-catalog coverage.
