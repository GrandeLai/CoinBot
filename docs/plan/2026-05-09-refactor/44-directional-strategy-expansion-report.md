# OKX Spot Directional Strategy Expansion Report

Date: 2026-05-11

## Summary

Implemented the OKX spot directional strategy expansion. The system now has more than pure arbitrage: it can scan, score, paper-run, review, and validate long-only spot directional opportunities through the same strategy platform, risk manager, paper execution, journal, validation report, and retrospective layers.

Live trading remains disabled. Directional strategies are not wired to `agent execute-live`.

## Implemented

- Added `Candle` domain model and `Exchange.get_candles`.
- Added candle support to mock, OKX, and CCXT adapters.
- Added `crypto-assistant market candles`.
- Added `directional` package with models, indicators, strategies, scanner, and no-lookahead backtest.
- Added strategy registry categories and aggregates: `arbitrage`, `directional`, `all`, `directional-all`.
- Added five directional strategies:
  - `trend-breakout`
  - `mean-reversion-spot`
  - `volatility-squeeze-breakout`
  - `momentum-rotation`
  - `orderbook-imbalance-scalp`
- Added directional config and safe defaults.
- Added directionals to `strategy catalog`, `strategy scan`, `strategy score`, `strategy portfolio-status`, `strategy run`, `strategy validation-report`, `strategy guard-status`, and promotion flows.
- Added OKX demo allowlist entries for the first four directional strategies.
- Added persistent OKX demo directional position lifecycle state through `directional.position_state_path`.
- Upgraded directional demo execution from immediate buy/sell round-trip canaries to managed long-only spot positions:
  - first approved run opens a tiny managed spot long;
  - later runs hold when no exit trigger is met;
  - later runs exit when take-profit, stop-loss, or time-limit conditions are met;
  - validation reports no longer count managed open positions as realized losses.
- Kept `orderbook-imbalance-scalp` demo-disabled.
- Updated README, design docs, task checklist, acceptance checklist, and traceability matrix.

## Safety Result

- Default config still has `trading.live_trading=false`, `trading.dry_run=true`, and `trading.require_confirm_before_order=true`.
- OKX demo config still uses `sandbox=true`, `okx_demo=true`, `live_trading=false`, and separated `.env.okx.demo`.
- Directional strategy demo positions remain OKX-demo-only and require local validation first.
- Directional demo execution is long-only spot, does not use leverage, and does not touch swaps/futures/live paths.
- `orderbook-imbalance-scalp` is scan/backtest/paper only.
- No API key, secret, token, or passphrase was hardcoded.

## Test Results

Commands run from `backend/`:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_directional_strategies.py tests/unit/test_okx_candles.py tests/unit/test_strategy_platform.py tests/integration/test_cli_core.py -q
```

Result:

```text
29 passed
```

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q
```

Result:

```text
304 passed
```

```bash
UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/
```

Result:

```text
All checks passed!
```

```bash
UV_CACHE_DIR=../.uv-cache uv run mypy src/
```

Result:

```text
Success: no issues found in 103 source files
```

## OKX Demo Validation

Run date: 2026-05-12 Asia/Shanghai.

First-layer local validation:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy directional-all --cycles 1 --symbol BTC/USDT --json
```

Result:

- Status: `Pass`
- Total strategy events: `5`
- Executed: `2`
- Skipped: `3`
- Paper net profit estimate: `4.134961 USDT`
- Executed strategies: `trend-breakout`, `momentum-rotation`
- Skipped strategies: `mean-reversion-spot`, `volatility-squeeze-breakout`, `orderbook-imbalance-scalp`

The aggregate OKX demo command was correctly blocked:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy directional-all --cycles 1 --symbol BTC/USDT --json
```

Result:

- Exit code: non-zero safety block
- Reason: first-layer local validation did not execute every requested strategy.

Targeted OKX demo canaries were then run only for strategies that passed local validation:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy trend-breakout --cycles 1 --symbol BTC/USDT --json
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy momentum-rotation --cycles 1 --symbol BTC/USDT --json
```

Combined directional validation report:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validation-report --config ../configs/okx.demo.example.yaml --execution-mode demo --strategy directional-all --limit 20 --json
```

Result:

- Demo events scanned: `2`
- Executed: `2`
- Skipped/blocked: `0`
- Realized demo PnL: `-0.065865 USDT`
- Account equity delta: `-0.065864 USDT`
- Account reconciliation gap: `0.000001 USDT`
- Receipt incomplete: `0`
- PnL out of tolerance: `0`
- Residual inventory out of tolerance: `0`
- Max residual inventory: `0.016364 USDT`
- Post-run open spot orders: `0`
- Post-run open swap orders: `0`
- Post-run swap positions: `0`

Interpretation: this historical first demo validation confirmed order plumbing and receipt reconciliation, but the PnL was negative because that release used immediate buy/sell round-trip canaries. That round-trip result must not be interpreted as directional alpha evidence.

## Managed Position Lifecycle Follow-Up

Implemented on 2026-05-12:

- `StrategyDemoExecutionService.execute(..., context=...)` now supports directional lifecycle context from the local validation gate.
- `StrategyRunner` passes local validation context into demo preflight and execution when the executor supports it.
- `DirectionalPositionStore` persists managed demo spot positions under `directional.position_state_path`.
- Directional demo preflight now returns:
  - `directional_entry_gate_passed` when no managed position exists;
  - `directional_position_hold` when an open position has not hit an exit trigger;
  - `directional_exit_take_profit`, `directional_exit_stop_loss`, or `directional_exit_time_limit` when an exit is due.
- Validation reporting treats `managed_directional_open_position` as an open lifecycle state, not a realized loss sample.

Targeted lifecycle tests:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_directional_demo_execution_opens_position_without_immediate_exit tests/unit/test_strategy_runtime.py::test_directional_demo_execution_closes_position_on_take_profit tests/unit/test_strategy_runtime.py::test_directional_demo_preview_holds_existing_position_before_exit -q
```

Result:

```text
3 passed
```

Relevant regression suite:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py tests/unit/test_directional_strategies.py tests/integration/test_cli_core.py -q
```

Result:

```text
63 passed
```

Full verification after the managed lifecycle follow-up:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q
UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=../.uv-cache uv run mypy src/
```

Result:

```text
304 passed
All checks passed!
Success: no issues found in 103 source files
```

OKX Demo Trading lifecycle smoke test:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy trend-breakout --cycles 1 --symbol BTC/USDT --json
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy run --config ../configs/okx.demo.example.yaml --strategy trend-breakout --symbol BTC/USDT --max-cycles 1 --interval-seconds 0 --execution-mode demo --json
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy run --config ../configs/okx.demo.example.yaml --strategy trend-breakout --symbol BTC/USDT --max-cycles 1 --interval-seconds 0 --execution-mode demo --json
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validation-report --config ../configs/okx.demo.example.yaml --execution-mode demo --strategy trend-breakout --limit 5 --json
```

Result:

- Local validation passed with `executed=1`, selected `directional-trend-breakout-btc-usdt`, and paper net profit estimate `1.174961 USDT`.
- First OKX demo lifecycle run sent one long-only spot buy order for `0.0002 BTC`, filled at `81661.3107000000000001`, and persisted `trend-breakout|BTC/USDT` as `state=open`.
- The managed open position notional is `16.332262 USDT`, below the configured `250 USDT` directional position cap.
- Second OKX demo lifecycle run returned `directional_position_hold`, sent no additional orders, and did not duplicate the position.
- Validation report now reads the managed open-position evidence successfully and reports `execution_quality_passed=true`; the remaining `trend-breakout` loss in the latest window is the earlier historical round-trip canary, not the new managed open position.

## CLI Acceptance

Verified by tests:

- `crypto-assistant market candles --exchange mock --symbol BTC/USDT --bar 15m --limit 80 --json`
- `crypto-assistant strategy catalog --json`
- `crypto-assistant strategy scan --strategy directional-all --symbol BTC/USDT --json`
- `crypto-assistant strategy score --strategy directional-all --json`
- `crypto-assistant strategy run --strategy directional-all --execution-mode paper --json`

## Deferred / Follow-Up

- Reverse-signal managed exits are still a follow-up; current managed exits use take-profit, stop-loss, and time-limit triggers.
- Live support is intentionally not implemented.
- `orderbook-imbalance-scalp` remains demo-disabled until the slower directional set produces enough stable validation evidence.
