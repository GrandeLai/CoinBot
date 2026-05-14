# OKX Triangular Fill Reliability Report

Date: 2026-05-10

## Scope

- Improve the next OKX-only step after the latest demo run showed a triangular middle-leg non-fill.
- Keep the hard safety behavior: a leg that does not fully fill still aborts the sequence and unwinds filled legs.
- Do not add non-OKX broker dispatch and do not enable live trading.

## Code Changes

- Added `strategy_runtime.demo_limit_price_buffer_pct`.
  - Default safe config: `0.001`.
  - OKX demo profile: `0.003`.
- Updated OKX demo spot limit pricing to prefer `/api/v5/market/books` top-of-book:
  - buy limits use best ask plus the configured buffer.
  - sell limits use best bid minus the configured buffer.
  - falls back to last price when raw book data is unavailable.
- Updated triangular dynamic execution and preflight to share the same pricing path.
- Kept existing order-cap checks, PnL reconciliation, receipt checks, residual-inventory checks, and abort/unwind behavior.

## Validation

- Command:
  - `uv run pytest tests/unit/test_strategy_runtime.py tests/unit/test_config.py -q`
- Result:
  - `35 passed in 0.68s`.
- Command:
  - `uv run ruff check src/trading_assistant/strategies/demo_execution.py src/trading_assistant/config/schema.py tests/unit/test_strategy_runtime.py tests/unit/test_config.py`
- Result:
  - `All checks passed!`.
- Command:
  - `uv run mypy src/trading_assistant/strategies/demo_execution.py src/trading_assistant/config/schema.py`
- Result:
  - `Success: no issues found in 2 source files`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant config validate --config ../configs/okx.demo.example.yaml --json`
- Result:
  - exit 0; OKX demo config validated with redacted credentials and `strategy_runtime.demo_limit_price_buffer_pct=0.003`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`
- Result:
  - exit 0; `local_validation.status=Pass`, `executed=5`, `skipped=0`, `net_profit=4.967117651096646342373316272`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`
- Result:
  - exit 0; `demo_window_validation.status=Needs More Samples`, `executed=1`, `skipped=4`, `wins=1`, `losses=0`, `net_profit=1.601695`, `max_drawdown_usdt=0`.
  - `triangular-multi-route` was the only strategy allowed past the demo profitability preflight.
  - All three triangular spot legs filled; `pnl_validation.within_tolerance=true`, `exchange_receipts.complete=true`, `residual_inventory_within_tolerance=true`, and post-run `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy guard-status --config ../configs/okx.demo.example.yaml --execution-mode demo --json`
- Result:
  - exit 0; no active cooldown; `triangular-multi-route` recorded `last_reason=profitable_execution` and `last_net_profit=1.601695`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q`
- Result:
  - `275 passed in 9.00s`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/`
- Result:
  - `All checks passed!`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run mypy src/`
- Result:
  - `Success: no issues found in 93 source files`.

## Safety Result

- Live trading remains disabled.
- The OKX demo config still requires demo mode, demo credentials, local validation, profitability preflight, risk controls, and order caps.
- The higher OKX demo buffer may reduce false-positive preflight approvals because estimated buy prices become less optimistic and sell prices more conservative.
- This change improves fill probability for tiny demo limit orders, but does not force execution and does not bypass unfilled-leg unwind logic.

## Remaining Follow-Up

- Run another small OKX demo validation window before any size discussion to confirm this was not a one-off favorable book state.
- Keep size at the current demo stage until repeated clean windows show complete receipts, no residual open orders/positions, residual inventory below tolerance, no drawdown breaker, and positive realized PnL.
- Keep the non-OKX broker work deferred while the current focus is OKX-only strategy reliability.
