# Rolling Strategy Validation Report CLI

Date: 2026-05-11

## Scope

Implemented the next follow-up item from the OKX demo optimization loop:

- Add a read-only rolling validation report CLI.
- Summarize recent journal evidence without touching execution code.
- Keep live trading disabled and do not send OKX Demo Trading orders.
- Use the report to make future run/review/optimize cycles less manual.

## Implementation

New command:

`crypto-assistant strategy validation-report --config ... --execution-mode demo --strategy all --limit 50 --json`

Changed files:

- `backend/src/trading_assistant/strategies/validation_report.py`
- `backend/src/trading_assistant/application.py`
- `backend/src/trading_assistant/cli/main.py`
- `backend/tests/unit/test_strategy_runtime.py`
- `backend/tests/integration/test_cli_core.py`

The report aggregates:

- total scanned events
- executed / skipped / blocked
- wins / losses / win rate
- realized executed PnL
- skipped preflight PnL
- max drawdown
- receipt completeness failures
- PnL tolerance failures
- residual-inventory tolerance failures
- max residual inventory
- reason counts
- per-strategy breakdown
- conservative recommendations

## Current Journal Result

Command:

`UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validation-report --config ../configs/okx.demo.example.yaml --execution-mode demo --strategy all --limit 50 --json`

Result:

- Exit code: `0`
- Scanned events: `50`
- Executed: `19`
- Skipped: `31`
- Blocked: `0`
- Wins: `19`
- Losses: `0`
- Realized executed PnL: `12.904406 USDT`
- Skipped preflight PnL: `-5.689714 USDT`
- Max drawdown: `0`
- Receipt incomplete: `0`
- PnL out of tolerance: `0`
- Residual inventory out of tolerance: `0`
- Max residual inventory: `0.058822 USDT`
- Execution quality passed: `true`

Per-strategy summary:

| Strategy | Executed | Skipped | Realized PnL USDT | Skipped Preflight PnL USDT | Quality Passed |
| --- | ---: | ---: | ---: | ---: | --- |
| `triangular-multi-route` | 19 | 6 | `12.904406` | `0` | true |
| `cross-exchange` | 0 | 6 | `0` | `-0.775942` | true |
| `funding-carry-hedged` | 0 | 6 | `0` | `-1.551768` | true |
| `spot-perp-carry` | 0 | 6 | `0` | `-1.551770` | true |
| `futures-perp-basis` | 0 | 7 | `0` | `-1.810234` | true |

Recommendations:

- Keep `cross-exchange` blocked from demo execution until preflight net PnL turns positive.
- Keep `funding-carry-hedged` blocked from demo execution until preflight net PnL turns positive.
- Keep `futures-perp-basis` blocked from demo execution until preflight net PnL turns positive.
- Keep `spot-perp-carry` blocked from demo execution until preflight net PnL turns positive.

## Tests

- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_validation_report_summarizes_recent_receipt_pnl_and_residual_evidence tests/integration/test_cli_core.py::test_cli_strategy_list_run_and_review tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -q`
  - Result: `3 passed in 0.87s`
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/validation_report.py src/trading_assistant/application.py src/trading_assistant/cli/main.py tests/unit/test_strategy_runtime.py tests/integration/test_cli_core.py`
  - Result: `All checks passed!`
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/strategies/validation_report.py src/trading_assistant/application.py src/trading_assistant/cli/main.py`
  - Result: `Success: no issues found in 3 source files`
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q`
  - Result: `288 passed in 10.46s`
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/`
  - Result: `All checks passed!`
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/`
  - Result: `Success: no issues found in 95 source files`
- `find docs/plan -maxdepth 1 -type f -print`
  - Result: no files directly under `docs/plan`
- Hardcoded secret scan
  - Result: no matches

## Safety

- The new command is read-only.
- It reads the configured strategy journal and returns an aggregate report.
- It does not access OKX APIs.
- It does not send orders.
- It does not edit guard state, retrospective state, configs, or strategy parameters.
- It does not enable demo or live trading.

## Decision

This closes the reporting gap for future strategy loops. The next OKX demo run can start by checking:

`crypto-assistant strategy validation-report --config configs/okx.demo.example.yaml --execution-mode demo --strategy all --limit 50 --json`

The current evidence still supports only `triangular-multi-route` for demo execution. The other strategies should remain offline/paper optimization targets until their preflight net PnL turns positive.
