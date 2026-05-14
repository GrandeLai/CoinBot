# Candle Regime And Candidate Backtest Report

Date: 2026-05-12

## Scope

This report closes the remaining strategy-evolution optimization items:

- Replace mostly journal-hint market-regime tagging with completed-candle feature classification.
- Add an isolated candidate backtest runner that materializes parameter overrides in a temporary config copy and compares candidate metrics without touching checked-in configs.

## Implementation

- Added `StrategyMarketRegimeService` and `classify_candle_regime` in `backend/src/trading_assistant/strategies/market_regime.py`.
- `strategy evolve` now builds the evolution `market_regime` snapshot from completed OHLCV candles through the exchange interface before generating parameter candidates.
- Regime features include recent return, medium-window return, realized volatility, EMA slope, completed-candle count, ignored incomplete-candle count, per-symbol tags, and dominant tag counts.
- Added `StrategyCandidateBacktestService` in `backend/src/trading_assistant/strategies/candidate_backtest.py`.
- Added CLI command `crypto-assistant strategy candidate-backtest --json`.
- Candidate backtests deep-copy settings, apply symbolic parameter overrides, write a YAML config in a `tempfile.TemporaryDirectory`, isolate journal/runtime-guard/retrospective/evolution paths, compare baseline and candidate metrics, then discard the temporary directory.
- Directional candidates are evaluated through the no-lookahead directional backtest engine; arbitrage candidates use paper-mode strategy scoring with isolated runtime paths.
- The command reports `orders_sent=false`, `live_orders_sent=false`, and `checked_in_config_modified=false`.

## CLI Evidence

Command:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy evolve --config ../configs/config.example.yaml --strategy all --execution-mode paper --limit 50 --json
```

Result summary:

- Exit code: `0`
- `orders_sent=false`
- `live_orders_sent=false`
- `simulation_only=true`
- `market_regime.source=candles`
- `market_regime.exchange=mock`
- `market_regime.tag=trend_up`
- `market_regime.symbol_count=6`
- `market_regime.sample_count=720`
- `market_regime.tag_counts={"trend_up": 5, "trend_down": 1}`
- Parameter candidates generated for watchlist directional strategies.

Command:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy candidate-backtest --config ../configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --limit 50 --json
```

Result summary:

- Exit code: `0`
- `orders_sent=false`
- `live_orders_sent=false`
- `checked_in_config_modified=false`
- `candidate_count=1`
- Candidate: `trend-breakout-watchlist-candidate-v1`
- Temporary config materialized: `true`
- Temporary config persisted after run: `false`
- Baseline net PnL: `1.524057 USDT`
- Candidate net PnL: `1.524057 USDT`
- Delta net PnL: `0.000000 USDT`
- Demo probe advisory result: `accepted_for_demo_probe=true`

## Tests

Targeted validation already passed before this report:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_candle_market_regime_classifier_uses_completed_candles_only tests/unit/test_strategy_runtime.py::test_candidate_backtest_materializes_temp_config_without_mutating_settings tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -q
```

Result: `3 passed`.

```bash
UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/market_regime.py src/trading_assistant/strategies/candidate_backtest.py src/trading_assistant/strategies/evolution.py src/trading_assistant/application.py src/trading_assistant/cli/main.py tests/unit/test_strategy_runtime.py tests/integration/test_cli_core.py
```

Result: `All checks passed!`

```bash
UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/strategies/market_regime.py src/trading_assistant/strategies/candidate_backtest.py src/trading_assistant/strategies/evolution.py src/trading_assistant/application.py src/trading_assistant/cli/main.py
```

Result: `Success: no issues found in 5 source files`.

Full backend verification for this optimization batch:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q
```

Result: `312 passed in 17.94s`.

```bash
UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/
```

Result: `All checks passed!`.

```bash
UV_CACHE_DIR=../.uv-cache uv run mypy src/
```

Result: `Success: no issues found in 107 source files`.

Document and secret scans:

- `find docs/plan -maxdepth 1 -type f -print`: no output.
- `find backend/docs -maxdepth 5 -type f -print`: no output.
- Hardcoded key/secret/passphrase/token pattern scan: no matches.

## Safety

- No live trading was enabled.
- No OKX demo order was sent by these commands.
- Candidate backtests are local/paper/backtest only.
- Candidate overrides are advisory and do not edit checked-in config files.
- Runtime evidence paths are isolated during candidate comparison.
- Completed-candle filtering prevents unfinished candle leakage into regime classification.

## Follow-Up

- Run candidate backtests for all watchlist strategies after each meaningful paper/demo evidence update.
- Add historical real-market candle datasets for offline directional candidate comparison before considering larger OKX demo windows.
- Keep `strategy revival-window` local-first and demo-gated when a real `revive_candidate` appears.
