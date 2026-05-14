# OKX Demo 10-Cycle Triangular Validation

Date: 2026-05-11

## Scope

Continued the next validation step from the previous optimization loop:

- Keep position size unchanged.
- Run only the currently selected strategy: `triangular-multi-route`.
- Do not run the four strategies still blocked by repeated OKX demo negative preflight pressure.
- Keep live trading disabled.

The raw 10-cycle JSON output was captured at `/private/tmp/coinbot-okx-demo-triangular-10.json`.

## Pre-Run Checks

Commands:

- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy guard-status --config ../configs/okx.demo.example.yaml --strategy triangular-multi-route --execution-mode demo --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy portfolio-status --config ../configs/config.example.yaml --symbol BTC/USDT --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy triangular-multi-route --cycles 1 --symbol BTC/USDT --json`

Results:

- Demo guard for `triangular-multi-route`: `cooldown_active=false`.
- Portfolio selected only `triangular-multi-route`.
- Local validation: Pass, `executed=1`, `net_profit=3.6492041591681663667266546`, `win_rate_pct=100.00`, `max_drawdown_usdt=0`.

## OKX Demo 10-Cycle Result

Command:

`UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy triangular-multi-route --cycles 10 --symbol BTC/USDT --json`

Result:

- Validation status: `Pass`
- Cycles completed: `10`
- Total events: `10`
- Executed: `10`
- Blocked: `0`
- Skipped: `0`
- Wins: `10`
- Losses: `0`
- Net profit: `2.629326 USDT`
- Win rate: `100.00%`
- Max drawdown: `0`
- Stopped reason: `null`
- Post-run provider demo mode: `true`
- Post-run open spot orders: `0`
- Post-run open swap orders: `0`
- Post-run swap positions: `0`

Per-cycle evidence:

| Cycle | Net PnL USDT | Orders | Receipts Complete | PnL Within Tolerance | Residual Within Tolerance | Residual USDT | Fill Count |
| --- | ---: | ---: | --- | --- | --- | ---: | ---: |
| 1 | `0.268557` | 3 | true | true | true | `0.058227` | 3 |
| 2 | `0.250414` | 3 | true | true | true | `0.058210` | 3 |
| 3 | `0.271760` | 3 | true | true | true | `0.058218` | 3 |
| 4 | `0.266617` | 3 | true | true | true | `0.058204` | 3 |
| 5 | `0.267841` | 3 | true | true | true | `0.058188` | 3 |
| 6 | `0.252238` | 3 | true | true | true | `0.058182` | 3 |
| 7 | `0.265390` | 3 | true | true | true | `0.058206` | 5 |
| 8 | `0.264729` | 3 | true | true | true | `0.058243` | 3 |
| 9 | `0.253457` | 3 | true | true | true | `0.058242` | 4 |
| 10 | `0.268323` | 3 | true | true | true | `0.058239` | 3 |

## Review And Promotion State

Commands:

- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy review --config ../configs/okx.demo.example.yaml --execution-mode demo --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy guard-status --config ../configs/okx.demo.example.yaml --execution-mode demo --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy retrospective --config ../configs/okx.demo.example.yaml --execution-mode demo --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy promotion-status --config ../configs/okx.demo.example.yaml --strategy triangular-multi-route --json`

Results:

- Historical demo review after this run:
  - `triangular-multi-route`: `executed=58`, `wins=57`, `losses=1`, `net_profit=75.206223`, `win_rate_pct=98.28`.
  - Other four strategies remain `executed=0` and should stay wait-only until their preflight pressure clears.
- Runtime guard:
  - `triangular-multi-route`: `cooldown_active=false`, `last_reason=profitable_execution`, `last_net_profit=0.268323`.
- Promotion status:
  - Local: Pass.
  - Demo: Pass.
  - Live: Fail, as expected, because `validation_allow_live_canary=false`, live trading is disabled, and agent live orders are disabled.

## Optimization Implemented

The 10-cycle run exposed a retrospective consistency issue:

- The single command's `retrospective_after` can only observe the strategy that just ran.
- A targeted triangular run should not mark unrelated `spot-perp-carry`, `funding-carry-hedged`, `futures-perp-basis`, or `cross-exchange` demo issues as improved.

Implemented fix:

- Retrospective updates now track observed `strategy_name + execution_mode` pairs.
- An open issue is marked improved only when its own strategy/mode was observed and the issue was absent.
- This keeps the four non-selected strategies' repeated negative preflight pressure open and visible.

Changed files:

- `backend/src/trading_assistant/strategies/retrospective.py`
- `backend/tests/unit/test_strategy_runtime.py`

## Tests

- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_retrospective_does_not_improve_unobserved_strategy_issues tests/unit/test_strategy_runtime.py::test_strategy_retrospective_treats_transient_market_data_failure_as_improved_after_profit tests/unit/test_strategy_validation.py::test_validate_demo_window_fast_blocks_when_target_guard_is_cooling_down -q`
  - Result: `3 passed in 0.48s`.
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/retrospective.py tests/unit/test_strategy_runtime.py`
  - Result: `All checks passed!`.
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/strategies/retrospective.py`
  - Result: `Success: no issues found in 1 source file`.
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q`
  - Result: `287 passed in 9.37s`.
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/`
  - Result: `All checks passed!`.
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/`
  - Result: `Success: no issues found in 94 source files`.
- `find docs/plan -maxdepth 1 -type f -print`
  - Result: no files directly under `docs/plan`.
- Hardcoded secret scan
  - Result: no matches.

## Decision

- `triangular-multi-route` passed the 10-cycle OKX demo validation at the current size.
- Do not increase size yet without another explicit operator decision.
- The next reasonable step is either:
  - run another 10-cycle triangular window at the same size to check repeatability, or
  - improve one blocked carry/basis strategy's preflight model offline before demo execution.
- Keep live trading disabled.
