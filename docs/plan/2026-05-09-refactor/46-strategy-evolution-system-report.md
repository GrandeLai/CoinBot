# Strategy Evolution System Report

Date: 2026-05-12

## Summary

Implemented a simulation-only strategy survival and evolution system. Every strategy execution and validation flow now refreshes an evolution state that ranks strategies, promotes stronger simulated performers, archives persistently unprofitable strategies, and marks archived strategies as revival candidates when later paper/demo evidence turns profitable again.

This system does not enable live trading, does not change live gates, and does not send orders by itself.

## Implemented

- Added `StrategyEvolutionService`.
- Added `crypto-assistant strategy evolve --json`.
- Added evolution config:
  - `strategy_runtime.evolution_enabled`
  - `strategy_runtime.evolution_state_path`
  - `strategy_runtime.evolution_report_path`
  - `strategy_runtime.evolution_min_net_profit_usdt`
  - `strategy_runtime.evolution_archive_score_penalty`
- Added soft archive state under `docs/plan/2026-05-09-refactor/45-strategy-evolution.state.json`.
- Added living evolution report under `docs/plan/2026-05-09-refactor/45-strategy-evolution.md`.
- `strategy run`, `strategy validate-local`, and `strategy validate-demo-window` now include `evolution_after` and `evolution_path`.
- Strategy score and portfolio selection now block strategies with `strategy_archived_by_evolution`.
- Archived strategies are not deleted; profitable later paper/demo samples can move them to `revive_candidate`.

## Current Simulation Result

Command:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy evolve --config ../configs/config.example.yaml --strategy all --execution-mode paper --limit 50 --json
```

Result:

- `orders_sent=false`
- `live_orders_sent=false`
- `simulation_only=true`
- Promoted by recent paper evidence:
  - `triangular-multi-route`
  - `spot-perp-carry`
  - `funding-carry-hedged`
  - `futures-perp-basis`
  - `cross-exchange`
- Archived strategies:
  - None
- Revival candidates:
  - None in the latest refresh; the archive/revival path is covered by tests and remains available when a previously archived strategy later becomes profitable in paper/demo evidence.
- Watchlist:
  - `trend-breakout`
  - `momentum-rotation`
  - `mean-reversion-spot`
  - `volatility-squeeze-breakout`
  - `orderbook-imbalance-scalp`

Portfolio status after the paper evolution refresh selects the strongest current simulated opportunities:

- `triangular-multi-route`
- `momentum-rotation`
- `trend-breakout`

## Validation

Commands run from `backend/`:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_evolution_archives_sustained_unprofitable_strategy tests/unit/test_strategy_runtime.py::test_strategy_evolution_marks_archived_strategy_as_revival_candidate_after_profit tests/unit/test_strategy_platform.py::test_strategy_score_and_portfolio_block_archived_strategy tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -q
```

Result:

```text
4 passed
```

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py tests/unit/test_strategy_platform.py tests/integration/test_cli_core.py -q
```

Result:

```text
68 passed
```

```bash
UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/evolution.py src/trading_assistant/strategies/platform.py src/trading_assistant/application.py src/trading_assistant/cli/main.py tests/unit/test_strategy_runtime.py tests/unit/test_strategy_platform.py tests/integration/test_cli_core.py
UV_CACHE_DIR=../.uv-cache uv run mypy src/
```

Result:

```text
All checks passed!
Success: no issues found in 104 source files
```

Full verification after R068:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q
UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=../.uv-cache uv run mypy src/
```

Result:

```text
307 passed in 18.67s
All checks passed!
Success: no issues found in 104 source files
```

Read-only OKX demo evidence check:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validation-report --config ../configs/okx.demo.example.yaml --execution-mode demo --strategy all --limit 50 --json
```

Result:

- Exit code: `0`
- Scanned demo journal events: `50`
- Executed demo events: `20`
- Skipped demo events: `30`
- Realized demo cash-flow PnL: `3.667118 USDT`
- `execution_quality_passed=true`
- `receipt_incomplete=0`
- `pnl_out_of_tolerance=0`
- `positive_cash_flow_negative_equity_delta=0`
- `triangular-multi-route`: `17` wins, `0` losses, `3.732983 USDT` realized demo cash-flow PnL.
- Carry/basis and cross-exchange paths remained skipped in demo evidence while preflight was negative.
- No new OKX demo orders were sent by this read-only validation report.

## Safety

- Live trading remains disabled.
- Evolution is advisory and simulation-only.
- Archive is soft state, not code deletion.
- Archived strategies require fresh profitable paper/demo evidence before reactivation.
- No API keys or secrets were added.

## Follow-Up

- Add strategy-parameter mutation proposals as separate simulated candidates, not automatic config edits.
- Add per-strategy market-regime tags so evolution can distinguish trend, range, and high-volatility windows.
- Add OKX demo revival windows for `revive_candidate` strategies only after local paper validation passes.
