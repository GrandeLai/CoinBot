# Hedged Maker Budget State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Include hedged-maker paper lifecycle state in strategy capital/order budgets so active, partial, and cancel-pending maker quotes constrain projected quote capacity.

**Architecture:** Extend `StrategyPolicy.evaluate` from single-opportunity checks to projected budget checks: current active order/capital state plus the incremental order/capital required by the current opportunity. Add read-only hedged-maker budget-state extraction to `HedgedMakerPaperLifecycleService`, then pass that state from `StrategyRunner` before hedged-maker budget evaluation.

**Tech Stack:** Python 3.12, Decimal, dataclasses, existing strategy lifecycle/policy/runner modules, pytest, ruff, mypy.

---

## Design

- Budget decisions expose:
  - current active order count
  - projected open order count
  - current active strategy capital
  - projected strategy capital
- Generic strategies keep existing behavior through defaults:
  - `active_orders=0`
  - `active_capital_usdt=0`
  - `additional_orders=1`
  - `additional_capital_usdt=opportunity.required_capital`
- `max_open_orders_per_strategy` checks projected orders, not only existing orders.
- `max_strategy_capital_usdt` checks projected capital, not only one opportunity.
- Hedged-maker budget state reads `hedged_maker.paper_state_path` without mutating it.
- Hedged-maker active statuses:
  - `open`
  - `partial_open`
  - `cancel_pending` before `cancel_effective_at`
- Expired TTL quotes, stale quotes, and completed cancel-pending quotes are excluded from budget state because the lifecycle service will cancel/complete them on the next apply.
- Matching active hedged-maker quotes consume current capital and order count but do not add incremental projected order/capital for the same symbol/maker/hedge opportunity.
- Non-matching active quotes count as existing budget usage and the current opportunity adds one projected order/capital slot.

## Files

- Modify `backend/src/trading_assistant/strategies/models.py`
- Modify `backend/src/trading_assistant/strategies/policy.py`
- Modify `backend/src/trading_assistant/strategies/hedged_maker_lifecycle.py`
- Modify `backend/src/trading_assistant/strategies/runner.py`
- Update tests:
  - `backend/tests/unit/test_strategy_runtime.py`
  - `backend/tests/unit/test_hedged_maker_lifecycle.py`
  - `backend/tests/integration/test_cli_core.py`
- Update docs:
  - `README.md`
  - `docs/DESIGN.md`
  - `docs/plan/2026-05-09-refactor/02-acceptance-checklist.md`
  - `docs/plan/2026-05-09-refactor/03-traceability-matrix.md`
  - add `docs/plan/2026-05-09-refactor/78-hedged-maker-budget-state-report.md`

## Tasks

- [x] Add RED tests for projected strategy capital and projected order count in `StrategyPolicy`.
- [x] Add RED lifecycle budget-state tests for `open`, `partial_open`, `cancel_pending`, expired, and matching/non-matching orders.
- [x] Add RED CLI/runtime test proving hedged-maker budget payload reports active/projected state.
- [x] Extend `StrategyBudgetDecision` with active/projected capital and projected order fields.
- [x] Extend `StrategyPolicy.evaluate` with projected budget arguments while preserving defaults.
- [x] Add `HedgedMakerPaperBudgetState` and `budget_state()` to `HedgedMakerPaperLifecycleService`.
- [x] Wire hedged-maker budget state into `StrategyRunner`.
- [x] Update README, DESIGN, acceptance checklist, traceability matrix, and phase report.
- [x] Run verification:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_strategy_runtime.py tests/unit/test_hedged_maker_lifecycle.py tests/integration/test_cli_core.py -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

- [ ] Commit:

```bash
git add README.md docs/DESIGN.md docs/plan/2026-05-09-refactor/02-acceptance-checklist.md docs/plan/2026-05-09-refactor/03-traceability-matrix.md docs/plan/2026-05-09-refactor/77-hedged-maker-budget-state-plan.md docs/plan/2026-05-09-refactor/78-hedged-maker-budget-state-report.md backend/src/trading_assistant/strategies/models.py backend/src/trading_assistant/strategies/policy.py backend/src/trading_assistant/strategies/hedged_maker_lifecycle.py backend/src/trading_assistant/strategies/runner.py backend/tests/unit/test_strategy_runtime.py backend/tests/unit/test_hedged_maker_lifecycle.py backend/tests/integration/test_cli_core.py
git commit -m "feat: include hedged maker state in budget"
```
