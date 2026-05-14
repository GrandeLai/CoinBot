# OKX Runtime Guard Hardening Report

Date: 2026-05-10

## Scope

- Continue unresolved OKX-focused follow-up work without adding non-OKX broker dispatch.
- Harden long-running OKX demo strategy execution before any additional size increase.
- Keep live trading disabled and keep all new verification offline by default.

## Code Changes

- Added runtime guard counters:
  - `max_consecutive_market_data_failures`
  - `max_consecutive_rate_limit_failures`
- Extended `StrategyRuntimeGuard` state with:
  - `consecutive_market_data_failures`
  - `consecutive_rate_limit_failures`
- Updated `strategy guard-status --json` output to expose the new thresholds and counters.
- Updated `StrategyRunner` to classify exchange scan and OKX demo preflight market-data failures as guard-visible reasons:
  - `market_data_error:*`
  - `exchange_rate_limit:*`
- Updated safe configs:
  - `configs/config.example.yaml`
  - `configs/okx.demo.example.yaml`

## Validation

- Command:
  - `uv run pytest tests/unit/test_strategy_runtime.py -q`
- Result:
  - `27 passed in 0.72s`.
- Command:
  - `uv run ruff check src/trading_assistant/strategies/guard.py src/trading_assistant/strategies/runner.py src/trading_assistant/config/schema.py tests/unit/test_strategy_runtime.py`
- Result:
  - `All checks passed!`.
- Command:
  - `uv run mypy src/trading_assistant/strategies/guard.py src/trading_assistant/strategies/runner.py src/trading_assistant/config/schema.py`
- Result:
  - `Success: no issues found in 3 source files`.
- Command:
  - `uv run pytest tests/ -q`
- Result:
  - `274 passed in 9.29s`.
- Command:
  - `uv run ruff check src/ tests/`
- Result:
  - `All checks passed!`.
- Command:
  - `uv run mypy src/`
- Result:
  - `Success: no issues found in 93 source files`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant config validate --config ../configs/config.example.yaml --json`
- Result:
  - exit 0; default config reports `max_consecutive_market_data_failures=3` and `max_consecutive_rate_limit_failures=2`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant config validate --config ../configs/okx.demo.example.yaml --json`
- Result:
  - exit 0; OKX demo credentials were redacted and live orders remained disabled.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`
- Result:
  - exit 0; `local_validation.status=Pass`, `executed=5`, `net_profit=4.967117651096646342373316272`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`
- Result:
  - exit 0 after OKX Demo Trading network access. `local_validation.status=Pass`; demo status was `Needs More Samples` because `1<10` sample threshold; `executed=1`, `skipped=4`, `net_profit=-0.032347`, `max_drawdown_usdt=0.032347`.
  - The only executed path was `triangular-multi-route`; its second leg did not fill, so the runtime aborted and unwound the filled BTC leg. `pnl_validation.within_tolerance=true`, `exchange_receipts.complete=true`, `residual_inventory_within_tolerance=true`, and post-run `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy guard-status --config ../configs/okx.demo.example.yaml --execution-mode demo --json`
- Result:
  - exit 0; no cooldown was active. `triangular-multi-route` recorded `consecutive_failures=1`, `consecutive_losses=1`, and market-data/rate-limit counters stayed at `0`.

## Safety Result

- No live-trading setting was enabled.
- No new broker dispatch path was added.
- OKX demo orders remain gated by existing local validation, demo config, provider demo-mode verification, risk controls, and order caps.
- The new guard behavior reduces long-running OKX demo risk by cooling down repeated bad market-data or rate-limit states before more requests are sent.
- Latest OKX Demo Trading result was a small controlled loss caused by an unfilled triangular middle leg; the unwind and no-open-risk checks passed, so no size increase is justified.

## Remaining Follow-Up

- Run the next OKX demo window only after local validation and guard status are clean.
- Keep non-OKX broker work deferred.
- Keep additional OKX demo size increases blocked until repeated windows show complete receipts, no residual open orders/positions, residual inventory below tolerance, no drawdown breaker, and stable realized PnL.
