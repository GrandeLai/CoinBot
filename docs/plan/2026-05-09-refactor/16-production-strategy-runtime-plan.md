# Production Strategy Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development for code changes and verification-before-completion before completion claims. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a safe strategy runtime that productionizes the four existing arbitrage strategies through controlled looping, position caps, order lifecycle plans, journaling, review, and advisory learning.

**Architecture:** Add a `trading_assistant.strategies` package above the current arbitrage scanners. Keep scanner math untouched; the new layer orchestrates and records decisions. CLI remains thin and calls `TradingAssistantApp`.

**Tech Stack:** Python 3.12, dataclasses, Pydantic settings, Decimal arithmetic, JSONL journal, pytest, argparse.

---

### Task 1: Strategy Registry And Config

**Files:**
- Modify: `backend/src/trading_assistant/config/schema.py`
- Create: `backend/src/trading_assistant/strategies/models.py`
- Create: `backend/src/trading_assistant/strategies/registry.py`
- Test: `backend/tests/unit/test_strategy_runtime.py`

- [x] Add `StrategyRuntimeConfig` with safe paper defaults.
- [x] Add dataclasses for strategy definitions and runtime outputs.
- [x] Register `cross-exchange`, `triangular`, `funding-rate`, and `spot-perp`.
- [x] Verify registry returns all four strategies.

### Task 2: Position And Order Lifecycle Policy

**Files:**
- Create: `backend/src/trading_assistant/strategies/policy.py`
- Test: `backend/tests/unit/test_strategy_runtime.py`

- [x] Implement capital cap checks per opportunity.
- [x] Implement max-open-order and TTL lifecycle plan.
- [x] Return explicit cancel/reprice instructions for each planned order.
- [x] Verify low capital limits block execution.

### Task 3: Journal, Runner, And Review

**Files:**
- Create: `backend/src/trading_assistant/strategies/journal.py`
- Create: `backend/src/trading_assistant/strategies/runner.py`
- Create: `backend/src/trading_assistant/strategies/review.py`
- Test: `backend/tests/unit/test_strategy_runtime.py`

- [x] Implement append-only JSONL event writing with no secret output.
- [x] Run bounded cycles for one strategy or all strategies.
- [x] Execute approved opportunities through existing dry-run/paper execution.
- [x] Read journal events and compute per-strategy counts, approvals, blocks, simulated PnL, and suggestions.

### Task 4: CLI And Application Integration

**Files:**
- Modify: `backend/src/trading_assistant/application.py`
- Modify: `backend/src/trading_assistant/cli/main.py`
- Create: `backend/src/trading_assistant/strategies/demo_validation.py`
- Test: `backend/tests/integration/test_cli_core.py`

- [x] Add `strategy list`.
- [x] Add `strategy run`.
- [x] Add `strategy review`.
- [x] Add `strategy validate-demo` for manually gated OKX Demo Trading submit/cancel checks.
- [x] Add explicit `--allow-account-mode-switch` for demo-only swap validation account setup.
- [x] Add controlled `strategy run --execution-mode demo` OKX Demo Trading canary execution and PnL capture.
- [x] Verify JSON output and help behavior.

### Task 5: Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/DESIGN.md`
- Modify: `docs/plan/2026-05-09-refactor/02-acceptance-checklist.md`
- Modify: `docs/plan/2026-05-09-refactor/03-traceability-matrix.md`
- Modify: `docs/plan/2026-05-09-refactor/13-phase-9-report.md`
- Modify: `docs/plan/2026-05-09-refactor/99-final-acceptance-report.md`

- [x] Document commands and safety posture.
- [x] Add traceability row for production strategy runtime.
- [x] Add traceability row for OKX strategy demo validation and resolve the external swap account-mode blocker after `acctLv=3` validation.
- [x] Add traceability row and report for OKX demo strategy execution PnL.
- [x] Run targeted strategy tests.
- [x] Run full backend tests, ruff, and mypy.
