# Phase 55 - Carry/Basis Offline Optimizer

## Goal

Add a read-only offline optimizer for carry and basis strategies that explains why they should stay in local optimization or become demo-preflight candidates, without forcing OKX demo orders or editing strategy thresholds.

## Implementation

- Added `CarryBasisOptimizationService` in `backend/src/trading_assistant/strategies/carry_basis_optimizer.py`.
- Added `crypto-assistant strategy carry-basis-optimize`.
- The report covers:
  - `funding-carry-hedged`
  - `spot-perp-carry`
  - `futures-perp-basis`
- It reuses existing scanner diagnostics and reports:
  - net PnL
  - configured minimum required PnL
  - break-even gap
  - net PnL percentage
  - observed basis percentage
  - observed funding annualized percentage
  - fee, slippage, holding-cost, and basis-hedge-cost components
  - suggested config fields for offline review
  - conservative actions and guardrails

## Safety Boundaries

- No exchange order path was added.
- No config mutation was added.
- No OKX demo or live dispatch was added.
- Positive break-even gaps produce `keep_demo_blocked_until_break_even_gap_closes`.
- Output explicitly reports `read_only=true`, `orders_sent=false`, and `live_orders_sent=false`.

## Verification

```bash
cd backend && uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_optimization_reports_break_even_gaps_without_trading tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history tests/integration/test_cli_core.py::test_cli_strategy_carry_basis_optimize_is_read_only -v
```

Result: `3 passed`.

```bash
cd backend && uv run ruff check src/ tests/
```

Result: `All checks passed!`.

```bash
cd backend && uv run mypy src/
```

Result: `Success: no issues found in 114 source files`.

```bash
cd backend && uv run pytest tests/ -v
```

Result: `332 passed`.

## Next Step

Proceed to directional managed exits. The carry/basis strategies now have an offline diagnostics path; directional strategies still need better reverse-signal exit handling before they should receive more demo attention.
