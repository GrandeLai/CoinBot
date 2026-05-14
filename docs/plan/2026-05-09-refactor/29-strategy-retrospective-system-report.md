# Strategy Retrospective System Report

Date: 2026-05-10

## Scope

Implemented `R054 Strategy Retrospective System`: an automatic, deterministic, non-blocking review memory for strategy execution and validation.

The system is advisory only. It reads strategy evidence, writes retrospective artifacts, and surfaces reminders. It does not submit orders, edit strategy parameters, enable OKX demo/live gates, or block OKX demo sampling by itself.

## Implemented

- Added `StrategyRetrospectiveService`.
- Added config:
  - `strategy_runtime.retrospective_enabled`
  - `strategy_runtime.retrospective_path`
  - `strategy_runtime.retrospective_state_path`
  - `strategy_runtime.retrospective_repeat_warning_threshold`
- Added `crypto-assistant strategy retrospective --config ... --json`.
- Added JSON fields to `strategy run`, `strategy validate-local`, and `strategy validate-demo-window`:
  - `retrospective_before`
  - `retrospective_after`
  - `retrospective_path`
- Added `retrospective_summary` to `strategy review --json`.
- Added `optimization_pressure` to retrospective summaries and Markdown, including observed net PnL, break-even gap, strategy-specific action, config fields to review, and safety guardrails.
- Added generated retrospective artifacts:
  - `docs/plan/2026-05-09-refactor/28-strategy-retrospective.md`
  - `docs/plan/2026-05-09-refactor/28-strategy-retrospective.state.json`
- Preserved the manual notes section between:
  - `<!-- RETROSPECTIVE_MANUAL_NOTES_START -->`
  - `<!-- RETROSPECTIVE_MANUAL_NOTES_END -->`

## Issue Classification

The first implementation records these issue categories:

- `preflight_not_profitable`
- `blocked_decision`
- `execution_loss`
- `leg_not_filled_abort`
- `receipt_incomplete`
- `pnl_out_of_tolerance`
- `residual_inventory_out_of_tolerance`
- `open_risk_after_run`
- `runtime_guard_cooldown`
- `insufficient_samples`
- `validation_failed`
- `market_data_failure`
- `rate_limit_failure`

Issues are deduplicated by:

`strategy_name + execution_mode + category + reason`

Repeated issues are escalated from `info` to `warning` after the configured threshold. Standalone retrospective refreshes use a recent-journal snapshot and do not inflate occurrence counts merely because the operator or Agent viewed the retrospective.

## Current Retrospective Snapshot

Command:

`UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy retrospective --config ../configs/okx.demo.example.yaml --json`

Result:

- Exit code: 0
- Open issues: 4
- Repeated issues: 4
- Highest severity: `warning`
- Current open issue class: `demo_preflight_not_profitable` on the non-executed OKX demo strategies in the latest journal snapshot.
- Live orders sent: none.
- Demo/live gates changed: none.

## Tests Added

- Unit tests:
  - Generate issues from journal events.
  - Deduplicate same-class issues.
  - Escalate repeated issues at threshold.
  - Avoid occurrence inflation on repeated retrospective refresh.
  - Classify receipt, PnL, residual inventory, and open-risk issues.
  - Preserve marker-protected manual notes.
  - Resolve relative retrospective paths from the repository root.
- Integration tests:
  - `strategy retrospective --json`.
  - Empty-history retrospective summary.
  - `strategy run --execution-mode paper --json` returns retrospective before/after/path.
  - `strategy review --json` returns retrospective summary.
  - `strategy retrospective --help` exits with code 0.
- E2E update:
  - Strategy platform e2e uses isolated retrospective paths so tests do not mutate repository docs.

## Verification Commands

- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_retrospective_deduplicates_and_escalates_repeated_issues tests/unit/test_strategy_runtime.py::test_strategy_retrospective_refresh_does_not_increment_existing_snapshot tests/unit/test_strategy_runtime.py::test_strategy_retrospective_classifies_receipt_pnl_residual_and_open_risk tests/integration/test_cli_core.py::test_cli_strategy_list_run_and_review tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -q`
  - Result: `5 passed in 0.45s`
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/retrospective.py tests/unit/test_strategy_runtime.py tests/integration/test_cli_core.py`
  - Result: `All checks passed!`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy retrospective --config ../configs/okx.demo.example.yaml --json`
  - Result: exit 0, retrospective document and state updated under the refactor directory with `optimization_pressure`.

Full-suite verification results are recorded in `99-final-acceptance-report.md`.

Latest full-suite result after this change:

- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q`
  - Result: `281 passed in 6.37s`
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/`
  - Result: `All checks passed!`
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/`
  - Result: `Success: no issues found in 94 source files`

## Safety Assessment

- Does not call OKX APIs.
- Does not send orders.
- Does not change execution mode.
- Does not edit strategy config.
- Does not enable live trading.
- Does not bypass local validation, demo preflight, runtime guard, risk approval, receipt checks, residual-inventory checks, or open-risk checks.
- Keeps retrospective documents under `docs/plan/2026-05-09-refactor/`.

## Follow-Up

- Add optional category-specific owner/priority metadata if the retrospective grows beyond current table form.
- Add a rolling aggregate command once there are enough demo windows to summarize by market regime.
- Keep live-canary promotion disabled until the existing three-layer validation and retrospective evidence support a separate operator decision.
