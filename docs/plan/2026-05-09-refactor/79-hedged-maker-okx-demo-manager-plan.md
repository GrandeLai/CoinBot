# Hedged Maker OKX Demo Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stateful OKX Demo Trading order manager for `hedged-maker` maker quotes without enabling live trading or generic demo runtime promotion.

**Architecture:** Keep the existing `hedged-maker` scanner and `strategy run` path paper-only. Add a separate `HedgedMakerDemoOrderManager` that accepts an explicit hedged-maker opportunity JSON, checks OKX Demo/agent/risk/budget gates, persists own-order state, submits post-only maker quotes, cancels/replaces stale quotes, and submits a tiny OKX Demo hedge only after an observed maker fill.

**Tech Stack:** Python 3.12, Pydantic v2 settings, Decimal calculations, OKX REST provider behind an injected provider interface, argparse CLI, pytest, ruff, mypy.

---

## File Structure

- Create `backend/src/trading_assistant/strategies/hedged_maker_demo.py`
  - Owns demo-only gates, state persistence, post-only maker submission, fill reconciliation, hedge submission, and audit events.
- Modify `backend/src/trading_assistant/config/schema.py`
  - Add `hedged_maker.demo_state_path`.
- Modify `backend/src/trading_assistant/application.py`
  - Add `strategy_hedged_maker_demo(opportunity_file=...)`.
- Modify `backend/src/trading_assistant/cli/main.py`
  - Add `crypto-assistant strategy hedged-maker-demo --opportunity-file ... --json`.
- Modify `backend/src/trading_assistant/execution/operation_hub.py`
  - Add a demo-only operation contract for the hedged-maker demo manager.
- Modify `configs/config.example.yaml` and `configs/okx.demo.example.yaml`
  - Add demo state path and include `hedged-maker` in the OKX demo agent allowlist.
- Modify `README.md` and `docs/DESIGN.md`
  - Document the demo-only command, opportunity-file requirement, and that the generic strategy runtime remains paper-only for `hedged-maker`.
- Add `backend/tests/unit/test_hedged_maker_demo.py`
  - Focused manager tests with a fake OKX Demo provider.
- Modify `backend/tests/unit/test_config.py`, `backend/tests/unit/test_operation_hub.py`, and `backend/tests/integration/test_cli_core.py`
  - Cover config default, operation catalog, CLI help, and blocked-by-default behavior.
- Add `docs/plan/2026-05-09-refactor/80-hedged-maker-okx-demo-manager-report.md`
  - Record RED/GREEN/final verification.

## Task 1: RED Tests

- [x] Add unit tests proving the manager:
  - rejects default/dry-run settings before orders;
  - submits an OKX Demo `post_only` maker quote after all gates pass;
  - writes state under `hedged_maker.demo_state_path`;
  - hedges only newly observed maker fills;
  - cancels and replaces stale or repriced maker quotes;
  - appends a redacted agent audit event.
- [x] Add CLI/help and operation-catalog tests.
- [x] Run the focused tests and capture the expected failures for the phase report.

## Task 2: Manager Implementation

- [x] Add `HedgedMakerDemoOrderManager`.
- [x] Use `AgentLiveTradingGate` plus local checks for:
  - `trading.live_trading=false`;
  - `trading.dry_run=false`;
  - `trading.require_confirm_before_order=false`;
  - enabled OKX sandbox with `okx_demo=true`;
  - `agent_trading.enabled=true`;
  - `agent_trading.allow_demo_orders=true`;
  - `hedged-maker` strategy allowlist;
  - OKX credentials and `COINBOT_AGENT_OPERATOR_ID`;
  - provider `configured=true` and `demo=true`;
  - risk approval and execution-quality approval.
- [x] Persist active maker quote state and reconcile fills before replacement.
- [x] Submit maker quote as OKX spot `ordType=post_only`.
- [x] Submit hedge only for incremental maker fill quantity using a marketable OKX Demo spot limit.
- [x] Keep all output explicit: `demo_orders_sent`, `live_orders_sent=false`, order id suffixes only in summaries when possible.

## Task 3: CLI, Docs, And Validation

- [x] Wire the app and CLI command.
- [x] Add the demo-only operation contract.
- [x] Update config examples and docs.
- [x] Run focused tests, broader affected tests, `ruff`, and `mypy`.
- [x] Run CLI smoke commands that do not require real OKX credentials, and record any credential-gated command as safely blocked.
- [x] Commit as `feat: add hedged maker okx demo manager`.
