# Hedged Maker Paper Evaluation Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `hedged-maker` paper evaluation report that summarizes maker quote lifecycle, fill quality, adverse selection, and paper PnL evidence from journal/state files.

**Architecture:** Follow the existing `validation-report`, `opportunity-report`, and `pnl-attribution` pattern: create one focused strategy report service that reads `StrategyJournal` and the persisted `hedged_maker.paper_state_path` without mutating runtime state or touching exchanges. Expose it through `TradingAssistantApp` and `crypto-assistant strategy hedged-maker-report --json`.

**Tech Stack:** Python 3.12, dataclasses, Decimal, argparse CLI, existing `StrategyJournal`, Pydantic settings, pytest, ruff, mypy.

---

## Design

- Report scope is paper-only and strategy-specific.
- Inputs:
  - `strategy_runtime.journal_path`
  - `hedged_maker.paper_state_path`
  - optional CLI `--limit`
- Journal filtering:
  - `event == "strategy_cycle"`
  - `strategy_name == "hedged-maker"`
  - `execution_mode == "paper"`
- State evaluation:
  - count current open, partial-open, cancel-pending, filled, canceled, and replaced paper orders
  - report active quote count separately from historical journal sample count
- Per-event evidence:
  - lifecycle status
  - active order count
  - expected paper edge
  - realized paper PnL
  - fill ratio and filled/remaining quantity when present
  - adverse-selection flag and slippage multiplier when a simulated hedge exists
  - canceled order ids
- Aggregate evidence:
  - lifecycle status counts
  - executed cycle count
  - fill/partial-fill/adverse-selection counts
  - total expected edge and realized paper PnL
  - average fill ratio across fills with quality metadata
  - max hedge slippage multiplier
  - current state order counts
- Safety:
  - `read_only=true`
  - `orders_sent=false`
  - `live_orders_sent=false`
  - no exchange reads
  - no journal/state writes
- Recommendations are conservative and advisory:
  - no samples: collect paper samples first
  - adverse selections: review quote aggressiveness and hedge slippage assumptions
  - partial fills: keep queue/partial-fill evidence before demo design
  - negative realized PnL: do not promote maker dispatch
  - cancel-pending samples: review cancel latency before sandbox order-manager work

## Files

- Create `backend/src/trading_assistant/strategies/hedged_maker_report.py`
- Modify `backend/src/trading_assistant/application.py`
- Modify `backend/src/trading_assistant/cli/main.py`
- Add tests in `backend/tests/unit/test_hedged_maker_report.py`
- Update `backend/tests/integration/test_cli_core.py`
- Update docs:
  - `README.md`
  - `docs/DESIGN.md`
  - `docs/plan/2026-05-09-refactor/02-acceptance-checklist.md`
  - `docs/plan/2026-05-09-refactor/03-traceability-matrix.md`
  - add `docs/plan/2026-05-09-refactor/76-hedged-maker-paper-evaluation-report.md`

## Tasks

- [x] Add RED unit test for aggregating hedged-maker paper journal/state evidence.
- [x] Add RED CLI integration test for `strategy hedged-maker-report --json` and `--help`.
- [x] Implement `HedgedMakerPaperEvaluationReportService`.
- [x] Wire the service into `TradingAssistantApp`.
- [x] Add CLI parser and handler for `strategy hedged-maker-report`.
- [x] Update README, DESIGN, acceptance checklist, and traceability matrix.
- [x] Add phase report with verification results.
- [x] Run verification:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_report.py tests/integration/test_cli_core.py -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy hedged-maker-report --config ../configs/config.example.yaml --limit 10 --json
```

- [ ] Commit:

```bash
git add README.md docs/DESIGN.md docs/plan/2026-05-09-refactor/02-acceptance-checklist.md docs/plan/2026-05-09-refactor/03-traceability-matrix.md docs/plan/2026-05-09-refactor/75-hedged-maker-paper-evaluation-report-plan.md docs/plan/2026-05-09-refactor/76-hedged-maker-paper-evaluation-report.md backend/src/trading_assistant/strategies/hedged_maker_report.py backend/src/trading_assistant/application.py backend/src/trading_assistant/cli/main.py backend/tests/unit/test_hedged_maker_report.py backend/tests/integration/test_cli_core.py
git commit -m "feat: add hedged maker paper evaluation report"
```
