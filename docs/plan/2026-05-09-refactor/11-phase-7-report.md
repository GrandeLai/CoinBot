# Phase 7 Report: Backtesting

## Implemented

- Added `BacktestMetrics`.
- Added `calculate_backtest_metrics`.
- Added deterministic offline `BacktestEngine`.
- Implemented `backtest run`.

## Tests

- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache uv run --offline pytest tests/unit/test_risk_execution_backtest_report.py -q`
- Result: `8 passed in 0.16s`

## CLI Verification

- `crypto-assistant backtest run --config configs/config.example.yaml --json`: exit 0, returns trades, equity curve, total return, max drawdown, and win rate.

## Status

Done.
