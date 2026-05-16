# Advisory Ranker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only ML/LLM-ready advisory ranker that prioritizes strategies from deterministic evidence without sending orders, calling external model APIs, or mutating configs.

**Architecture:** Build a `StrategyAdvisoryRankerService` that composes existing scan scorecards, rolling validation evidence, opportunity-density metrics, and runtime guard state. The first implementation is deterministic and labels the model policy as `deterministic_evidence_ranker`; future ML/LLM integrations must consume this evidence layer and remain advisory only.

**Tech Stack:** Python 3.12, dataclasses, Decimal scoring, argparse CLI, pytest, ruff, mypy.

---

## File Structure

- Create `backend/src/trading_assistant/strategies/advisory_ranker.py`
  - Owns advisory scoring, reason codes, next-step recommendations, and read-only report serialization.
- Modify `backend/src/trading_assistant/application.py`
  - Add `strategy_advisory_rank(...)`.
- Modify `backend/src/trading_assistant/cli/main.py`
  - Add `crypto-assistant strategy advisory-rank --strategy ... --symbol ... --execution-mode ... --limit ... --window ... --json`.
- Modify `README.md` and `docs/DESIGN.md`
  - Document the advisory-only ranker and its no-order model policy.
- Update `docs/plan/2026-05-09-refactor/02-acceptance-checklist.md` and `03-traceability-matrix.md`.
- Add/modify tests:
  - Add `backend/tests/unit/test_advisory_ranker.py`.
  - Update `backend/tests/integration/test_cli_core.py`.

## Task 1: RED Tests

- [x] Add a unit test proving profitable paper evidence produces a ranked advisory row with `read_only=true`, `orders_sent=false`, and deterministic model policy metadata.
- [x] Add a unit test proving demo-unsupported strategies are marked `paper_only`/`demo_not_supported` instead of being recommended for demo orders.
- [x] Add an integration test for `strategy advisory-rank --json`.
- [x] Add CLI help coverage.
- [x] Run focused tests and record the expected missing-module or missing-command failure.

## Task 2: Ranker Implementation

- [x] Implement dataclasses for one ranking row and the full advisory report.
- [x] Combine:
  - strategy scorecards from `StrategyScoreService`;
  - rolling validation aggregates from `StrategyValidationReportService`;
  - opportunity-density buckets from `OpportunityDensityService`;
  - cooldown status from `StrategyRuntimeGuard`.
- [x] Calculate a bounded deterministic advisory score with reason codes.
- [x] Emit conservative recommendations:
  - `prioritize_paper_validation`
  - `collect_more_samples`
  - `paper_only`
  - `wait_for_runtime_guard_cooldown`
  - `watchlist`
- [x] Include explicit safety metadata: no external LLM call, no order dispatch, no config mutation, no live authority.

## Task 3: CLI, Docs, And Validation

- [x] Wire app and CLI.
- [x] Update docs, acceptance checklist, and traceability matrix.
- [x] Run focused tests, affected regression tests, `ruff`, and `mypy`.
- [x] Run CLI smoke for `strategy advisory-rank --json` and `--help`.
- [x] Write `docs/plan/2026-05-09-refactor/84-advisory-ranker-report.md`.
- [ ] Commit as `feat: add advisory strategy ranker`.
