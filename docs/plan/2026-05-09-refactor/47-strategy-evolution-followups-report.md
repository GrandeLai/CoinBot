# Strategy Evolution Follow-Ups Report

Date: 2026-05-12

## Summary

Completed the deferred evolution-system follow-ups:

- Advisory parameter mutation candidates are now generated from evolution decisions.
- Recent journal evidence is tagged with market-regime metadata for future strategy comparison.
- `strategy revival-window --json` provides a local-first OKX demo return path for current `revive_candidate` strategies.

These changes do not enable live trading and do not automatically edit strategy parameters.

## Implemented

- `StrategyEvolutionService` now returns `market_regime` and `parameter_candidates`.
- Evolution state persists the latest market-regime summary and candidate list.
- Evolution Markdown report includes `Market Regime` and `Parameter Candidates` sections.
- Added `StrategyRevivalWindowService`.
- Added CLI command:

```bash
crypto-assistant strategy revival-window --config configs/okx.demo.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json
```

## Current Simulation Result

Command:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy evolve --config ../configs/config.example.yaml --strategy all --execution-mode paper --limit 50 --json
```

Result:

- `orders_sent=false`
- `live_orders_sent=false`
- `simulation_only=true`
- Market-regime source: `journal`
- Market-regime sample count: `50`
- Dominant tag: `unknown`
- Tag counts: `unknown=47`, `trend_up=3`
- Parameter candidates generated for watchlist strategies:
  - `momentum-rotation-watchlist-candidate-v1`
  - `trend-breakout-watchlist-candidate-v1`
  - `mean-reversion-spot-watchlist-candidate-v1`
  - `orderbook-imbalance-scalp-watchlist-candidate-v1`
  - `volatility-squeeze-breakout-watchlist-candidate-v1`

Revival-window no-candidate check:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy revival-window --config ../configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy revival-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json
```

Result:

- `candidates=[]`
- `reason=no_revival_candidates`
- `orders_sent=false`
- `live_orders_sent=false`
- The OKX demo config path also returned the same no-candidate/no-order result.

## Validation

Targeted tests:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_evolution_archives_sustained_unprofitable_strategy tests/unit/test_strategy_runtime.py::test_strategy_evolution_tags_market_regime_from_recent_journal tests/unit/test_strategy_runtime.py::test_strategy_revival_window_runs_only_revival_candidates_after_local_pass tests/unit/test_strategy_runtime.py::test_strategy_revival_window_skips_demo_when_local_validation_fails tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -q
```

Result:

```text
5 passed
```

Targeted static checks:

```bash
UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/evolution.py src/trading_assistant/strategies/revival.py src/trading_assistant/application.py src/trading_assistant/cli/main.py tests/unit/test_strategy_runtime.py tests/integration/test_cli_core.py
UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/strategies/evolution.py src/trading_assistant/strategies/revival.py src/trading_assistant/application.py src/trading_assistant/cli/main.py
```

Result:

```text
All checks passed!
Success: no issues found in 4 source files
```

Full backend verification:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q
UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=../.uv-cache uv run mypy src/
```

Result:

```text
310 passed in 16.97s
All checks passed!
Success: no issues found in 105 source files
```

Directory and safety scans:

- `find docs/plan -maxdepth 1 -type f -print`: no output.
- `find backend/docs -maxdepth 5 -type f -print`: no output.
- Hardcoded key/secret/passphrase/token pattern scan: no matches.
- Integration/e2e temp configs now override evolution report/state paths so tests do not overwrite `docs/plan/2026-05-09-refactor/45-strategy-evolution.state.json`.

## Safety

- Live trading remains disabled.
- Parameter candidates are advisory; no config file is modified automatically.
- `revival-window` runs no action when there are no current `revive_candidate` strategies.
- If candidates exist, `revival-window` requires OKX demo config, local validation first, and demo safety gates before any demo validation window can run.
- No API keys or secrets were added.

## Follow-Up

- Improve market-regime tagging by deriving tags from completed candle features rather than mostly journal hints.
- Add an isolated candidate backtest runner that materializes parameter overrides in a temporary config copy.
