# Realistic Backtest And Walk-Forward Report

Date: 2026-05-16

## Summary

Implemented the next profit-expansion validation layer: read-only completed-candle backtest, expanding-window walk-forward validation, and deterministic bias diagnostics under `crypto-assistant backtest`.

This phase improves the system's ability to reject weak or under-observed strategy candidates before paper/demo promotion. It does not send orders, does not edit strategy parameters, and does not enable OKX Demo or live trading.

## Implemented

- Extended `BacktestConfig` with exchange, symbol, strategy, bar, candle limit, slippage, walk-forward window count, and minimum validation trades.
- Replaced the placeholder local backtest result with a completed-candle, fee/slippage-adjusted directional backtest wrapper while preserving existing `metrics`, `equity_curve`, and `mode` fields for workflow compatibility.
- Added `backtest walk-forward` with expanding train windows and forward validation windows.
- Added `backtest bias-check` diagnostics:
  - completed candles only
  - warmup window enforced
  - deterministic prefix replay
- Added CLI JSON coverage and unit tests.
- Updated README, DESIGN, acceptance checklist, and traceability matrix.

## Safety

- `backtest run` reports `read_only=true`, `orders_sent=false`, and `live_orders_sent=false`.
- `backtest walk-forward` reports `read_only=true`, `orders_sent=false`, and `live_orders_sent=false`.
- `backtest bias-check` reports `read_only=true`, `orders_sent=false`, and `live_orders_sent=false`.
- No live broker, demo executor, agent live execution, or order submission path is called.
- Default `min_window_trades=1` prevents no-trade forward windows from being treated as accepted validation evidence.

## Verification

Commands run from `backend`:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_realistic_backtest.py -v
```

Result: `3 passed`.

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_risk_execution_backtest_report.py -v
```

Result: `8 passed`.

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_workflow_route.py -v
```

Result: `1 passed`.

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_config.py -v
```

Result: `8 passed`.

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py -v
```

Result: `23 passed`.

```bash
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
```

Result: `All checks passed!`

```bash
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

Result: `Success: no issues found in 122 source files`.

CLI smoke:

```bash
UV_CACHE_DIR=.uv-cache uv run crypto-assistant backtest run --config ../configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --exchange mock --json
```

Result: `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, `trades=1`, `net_pnl_usdt=1.373188`, `total_return_pct=0.01`, and completed-candle fill model evidence.

```bash
UV_CACHE_DIR=.uv-cache uv run crypto-assistant backtest walk-forward --config ../configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --exchange mock --windows 2 --json
```

Result: `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, `window_count=2`, `accepted_windows=0`, `acceptance_rate_pct=0.00`, with both forward validation windows rejected by `validation_trades_below_minimum:0<1`.

```bash
UV_CACHE_DIR=.uv-cache uv run crypto-assistant backtest bias-check --config ../configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --exchange mock --json
```

Result: `passed=true`, `orders_sent=false`, `live_orders_sent=false`; checks `completed_candles_only`, `warmup_window_enforced`, and `prefix_replay_stable` all passed.

## Acceptance

- Backtest run is no-order and uses completed candles plus fee/slippage assumptions.
- Walk-forward validation produces explicit train/validation windows and conservative accepted/rejected evidence.
- Bias-check reports deterministic diagnostics without claiming future profitability.
- CLI commands support `--json`.
- Existing workflow backtest compatibility is preserved.
