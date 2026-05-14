# PnL Reconciliation Audit

Date: 2026-05-11

## Goal

Re-check whether reported strategy profit is aligned with actual account movement, and prevent the common error of mixing:

- preflight expected PnL
- strategy/order cash-flow PnL
- account equity delta
- residual inventory value
- whole-account external cash-flow changes

## Findings

Current OKX demo journal already records account-level PnL validation for executed demo events:

- `cash_flow_net_pnl_usdt`
- `equity_before_usdt`
- `equity_after_usdt`
- `equity_delta_usdt`
- `difference_usdt`
- `residual_inventory_usdt`
- `exchange_receipts`

However, executed historical events did not preserve the approved preflight estimate that caused the order to be sent. That means older executed events can prove cash-flow/account reconciliation, but they cannot prove expected-vs-actual PnL alignment.

## Current Evidence

Latest 20 executed OKX demo events:

- Executed events: `20`.
- Sum event net profit: `10.063914 USDT`.
- Sum cash-flow PnL: `10.063914 USDT`.
- Sum account equity delta: `11.872038 USDT`.
- Sum account reconciliation gap: `1.808116 USDT`.
- Max absolute per-event account gap: `0.091073 USDT`.
- Max residual inventory: `0.058822 USDT`.
- All events within PnL tolerance: `true`.
- All residual inventory checks within tolerance: `true`.
- All exchange receipts complete: `true`.
- Approved preflight preserved on these historical executed events: `false`.

Latest 30 demo events after report enhancement:

- Executed: `16`.
- Skipped: `14`.
- Realized net profit: `3.706793 USDT`.
- Actual cash-flow PnL: `3.706793 USDT`.
- Account equity delta: `5.150647 USDT`.
- Account reconciliation gap: `1.443854 USDT`.
- Max absolute account reconciliation gap: `0.090500 USDT`.
- Positive cash-flow PnL while account equity delta was negative: `0`.
- Executed events missing approved preflight estimate: `16`.

Interpretation:

- The current demo evidence does not show the specific failure mode where strategy PnL is positive but account equity is negative.
- Cash-flow PnL and recorded event PnL are aligned.
- Account equity delta is higher than cash-flow PnL in the current window, likely because small residual BTC/ETH inventory is valued in the account-equity delta.
- Older executed events are not sufficient for expected-vs-actual promotion evidence because preflight estimates were not persisted.

## Fix Implemented

Code changes:

- `StrategyRunner` now writes approved preflight data into every executed demo journal event.
- `StrategyValidationReportService` now reports:
  - `expected_preflight_net_pnl_usdt`
  - `actual_cash_flow_net_pnl_usdt`
  - `account_equity_delta_usdt`
  - `account_reconciliation_gap_usdt`
  - `expected_actual_gap_usdt`
  - `max_abs_account_reconciliation_gap_usdt`
  - `max_abs_expected_actual_gap_usdt`
  - `account_equity_sample_count`
  - `expected_actual_sample_count`
  - `executed_preflight_missing`
  - `positive_cash_flow_negative_equity_delta`

Conservative recommendations now warn when:

- executed events are missing approved preflight estimates
- account equity is negative while strategy cash-flow PnL is positive
- receipt, PnL tolerance, or residual inventory checks fail

## Verification

Targeted tests:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest \
  tests/unit/test_strategy_runtime.py::test_strategy_runner_executes_demo_mode_through_demo_executor \
  tests/unit/test_strategy_runtime.py::test_strategy_validation_report_summarizes_recent_receipt_pnl_and_residual_evidence \
  tests/unit/test_strategy_runtime.py::test_strategy_validation_report_reconciles_expected_cash_flow_and_account_equity \
  -q
```

Result:

- `3 passed in 0.41s`.

Lint and type checks:

```bash
UV_CACHE_DIR=../.uv-cache uv run ruff check \
  src/trading_assistant/strategies/runner.py \
  src/trading_assistant/strategies/validation_report.py \
  tests/unit/test_strategy_runtime.py

UV_CACHE_DIR=../.uv-cache uv run mypy \
  src/trading_assistant/strategies/runner.py \
  src/trading_assistant/strategies/validation_report.py
```

Result:

- `All checks passed!`
- `Success: no issues found in 2 source files`

Full verification after documentation sync:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q
UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=../.uv-cache uv run mypy src/
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validation-report --config ../configs/okx.demo.example.yaml --execution-mode demo --strategy all --limit 30 --json
find docs/plan -maxdepth 1 -type f -print
rg -n "(?i)(api[_-]?key|api[_-]?secret|passphrase|token)\s*[:=]\s*['\"][A-Za-z0-9_./+=-]{12,}" --glob '!*.lock' --glob '!docs/plan/2026-05-09-refactor/28-strategy-retrospective.state.json' .
```

Result:

- `292 passed in 7.89s`.
- `All checks passed!`.
- `Success: no issues found in 96 source files`.
- Latest 30-event validation report confirmed `positive_cash_flow_negative_equity_delta=0` and `executed_preflight_missing=16`.
- Refactor document directory scan returned no files directly under `docs/plan`.
- Hardcoded secret scan returned no matches.

## Decision

Do not use older demo journal entries as full expected-vs-actual promotion evidence because they lack persisted approved preflight estimates.

Future promotion evidence must include:

1. approved preflight expected PnL
2. actual order cash-flow PnL
3. account equity delta
4. account reconciliation gap
5. residual inventory value
6. exchange receipt completeness
7. explicit check that no positive strategy cash-flow hides a negative account equity delta
