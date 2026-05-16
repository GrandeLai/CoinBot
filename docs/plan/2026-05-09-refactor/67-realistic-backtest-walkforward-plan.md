# Realistic Backtest And Walk-Forward Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the placeholder local backtest surface with read-only, candle-driven realistic backtest, walk-forward validation, and bias diagnostics for strategy candidates.

**Architecture:** Extend the existing `BacktestEngine` instead of introducing a parallel subsystem. The engine will reuse completed exchange candles, the existing long-only `DirectionalBacktestEngine`, Decimal fee/slippage math, and JSON-safe dataclasses. CLI commands remain no-order tools under `crypto-assistant backtest`, with `orders_sent=false` and `live_orders_sent=false`.

**Tech Stack:** Python 3.12, Pydantic v2 settings, Decimal, existing `ExchangeFactory`, argparse CLI, pytest, ruff, mypy.

---

## File Structure

- Modify `backend/src/trading_assistant/backtesting/engine.py`
  - Add realistic backtest payloads, walk-forward windows, and bias-check diagnostics.
- Modify `backend/src/trading_assistant/config/schema.py`
  - Add safe defaults for exchange, symbol, strategy, candle count, slippage, and walk-forward windows.
- Modify `backend/src/trading_assistant/application.py`
  - Add `backtest_walk_forward()` and `backtest_bias_check()` facade methods.
- Modify `backend/src/trading_assistant/cli/main.py`
  - Add `backtest run` options plus `backtest walk-forward` and `backtest bias-check`.
- Add `backend/tests/unit/test_realistic_backtest.py`
  - Focused service tests for no-order evidence and window diagnostics.
- Modify `backend/tests/unit/test_config.py`
  - Verify new backtest defaults load from example config.
- Modify `backend/tests/integration/test_cli_core.py`
  - Add CLI JSON coverage for the three backtest commands.
- Modify `README.md`, `docs/DESIGN.md`, `docs/plan/2026-05-09-refactor/02-acceptance-checklist.md`, and `03-traceability-matrix.md`.
- Add `docs/plan/2026-05-09-refactor/68-realistic-backtest-walkforward-report.md`.

## Task 1: Backtest Unit Tests

- [x] Add `backend/tests/unit/test_realistic_backtest.py`.
- [x] Test `BacktestEngine.run(strategy_name="trend-breakout", symbol="BTC/USDT", exchange="mock")` returns:
  - `read_only is True`
  - `orders_sent is False`
  - `live_orders_sent is False`
  - completed candle count greater than zero
  - a fill model containing fee, slippage, and completed-candle assumptions
  - a directional result for `trend-breakout`
- [x] Test `BacktestEngine.walk_forward(..., windows=2)` returns two windows with train and validation metrics and no-order evidence.
- [x] Test `BacktestEngine.bias_check(...)` returns `passed is True`, includes `completed_candles_only`, `warmup_window_enforced`, and `prefix_replay_stable` diagnostics, and sends no orders.
- [x] Verify RED:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_realistic_backtest.py -v
```

Expected: fail because the new methods/fields are not implemented.

## Task 2: Engine And Config Implementation

- [x] Extend `BacktestConfig` with:
  - `exchange: str = "mock"`
  - `symbol: str = "BTC/USDT"`
  - `strategy: str = "trend-breakout"`
  - `bar: str = "15m"`
  - `candles_limit: int = 120`
  - `slippage_pct: Decimal = Decimal("0.0005")`
  - `walk_forward_windows: int = 2`
  - `min_window_trades: int = 1`
- [x] Add validators for positive candle/window counts and non-negative money/fee/slippage thresholds.
- [x] Extend `BacktestResult` with no-order and realism fields while preserving existing `metrics`, `equity_curve`, and `mode` keys for current workflow tests.
- [x] Implement `BacktestEngine.run()`:
  - Load completed candles from the selected exchange.
  - Run `DirectionalBacktestEngine` for directional strategies.
  - Build an equity curve from initial capital plus net PnL.
  - Return fill assumptions: completed candles only, next-bar open entry, fee/slippage adjusted, no partial-fill venue dispatch.
- [x] Implement `BacktestEngine.walk_forward()`:
  - Split completed candles into expanding train and forward validation windows.
  - Run the same engine on both sides.
  - Mark each window accepted when validation trades meet `min_window_trades`.
- [x] Implement `BacktestEngine.bias_check()`:
  - Check completed-candle-only input.
  - Check warmup size is sufficient.
  - Replay strategy signals over prefixes twice and assert deterministic prefix replay.
  - Return diagnostic checks and reasons without claiming statistical certainty.
- [x] Verify GREEN:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_realistic_backtest.py -v
```

Expected: pass.

## Task 3: CLI And Application Wiring

- [x] Add optional args to `backtest run`:
  - `--config`
  - `--strategy`
  - `--symbol`
  - `--exchange`
  - `--bar`
  - `--limit`
- [x] Add `backtest walk-forward` with the same args plus `--windows`.
- [x] Add `backtest bias-check` with the same args.
- [x] Add application facade methods for walk-forward and bias-check.
- [x] Add CLI integration tests:

```python
code, payload = _invoke(["backtest", "run", "--config", str(EXAMPLE_CONFIG), "--strategy", "trend-breakout", "--symbol", "BTC/USDT", "--exchange", "mock"], capsys)
assert code == 0
assert payload["backtest"]["read_only"] is True
assert payload["backtest"]["orders_sent"] is False

code, payload = _invoke(["backtest", "walk-forward", "--config", str(EXAMPLE_CONFIG), "--strategy", "trend-breakout", "--symbol", "BTC/USDT", "--exchange", "mock", "--windows", "2"], capsys)
assert code == 0
assert payload["backtest_walk_forward"]["read_only"] is True
assert len(payload["backtest_walk_forward"]["windows"]) == 2

code, payload = _invoke(["backtest", "bias-check", "--config", str(EXAMPLE_CONFIG), "--strategy", "trend-breakout", "--symbol", "BTC/USDT", "--exchange", "mock"], capsys)
assert code == 0
assert payload["backtest_bias_check"]["orders_sent"] is False
assert payload["backtest_bias_check"]["passed"] is True
```

- [x] Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py::test_cli_backtest_realistic_walk_forward_and_bias_check -v
```

Expected: pass.

## Task 4: Docs, Traceability, And Report

- [x] Update README with backtest command examples and caveats.
- [x] Update DESIGN with the backtest validation layer.
- [x] Add acceptance checklist entries for:
  - `crypto-assistant backtest run --config configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --exchange mock --json`
  - `crypto-assistant backtest walk-forward --config configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --exchange mock --windows 2 --json`
  - `crypto-assistant backtest bias-check --config configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --exchange mock --json`
- [x] Add traceability row `R077 Realistic Backtest And Walk-Forward`.
- [x] Add phase report with actual verification results.

## Task 5: Verification And Commit

- [x] Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_realistic_backtest.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_risk_execution_backtest_report.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_workflow_route.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_config.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

- [x] Run CLI smoke:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run crypto-assistant backtest run --config ../configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --exchange mock --json
UV_CACHE_DIR=.uv-cache uv run crypto-assistant backtest walk-forward --config ../configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --exchange mock --windows 2 --json
UV_CACHE_DIR=.uv-cache uv run crypto-assistant backtest bias-check --config ../configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --exchange mock --json
```

- [x] Commit:

```bash
git add backend/src/trading_assistant/backtesting/engine.py backend/src/trading_assistant/config/schema.py backend/src/trading_assistant/application.py backend/src/trading_assistant/cli/main.py backend/tests/unit/test_realistic_backtest.py backend/tests/unit/test_config.py backend/tests/integration/test_cli_core.py README.md docs/DESIGN.md docs/plan/2026-05-09-refactor/02-acceptance-checklist.md docs/plan/2026-05-09-refactor/03-traceability-matrix.md docs/plan/2026-05-09-refactor/67-realistic-backtest-walkforward-plan.md docs/plan/2026-05-09-refactor/68-realistic-backtest-walkforward-report.md configs/config.example.yaml configs/okx.demo.example.yaml
git commit -m "feat: add realistic backtest validation"
```
