# Range Grid Paper Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only/paper-only `range-grid` strategy that uses the new regime router to harvest range-bound volatility in mock/paper validation without enabling OKX Demo or live orders.

**Architecture:** Add a `RangeGridStrategyService` that reads ticker/orderbook/candles, requires `regime=range`, builds a bounded grid ladder, estimates round-trip grid PnL after fees/slippage, and returns a normal `ArbitrageOpportunity` so existing scan, score, paper runtime, risk, budget, journal, and validation paths can consume it. Keep demo support disabled in the registry.

**Tech Stack:** Python 3.12, Decimal, existing `ExchangeFactory`, `ArbitrageOpportunity`, `StrategyRegistry`, `StrategyRunner`, argparse CLI, pytest, ruff, mypy.

---

## File Structure

- Create `backend/src/trading_assistant/strategies/range_grid.py`
  - Owns grid ladder construction, diagnostics, and opportunity generation.
- Modify `backend/src/trading_assistant/config/schema.py`
  - Add `RangeGridConfig` with safe paper defaults.
- Modify `backend/src/trading_assistant/arbitrage/scanner.py`
  - Dispatch `range-grid` scans and diagnostics.
- Modify `backend/src/trading_assistant/strategies/registry.py`
  - Register `range-grid` as paper-only/demo-disabled.
- Modify `backend/src/trading_assistant/strategies/runner.py`
  - Route `range-grid` through the preferred single exchange.
- Modify `backend/src/trading_assistant/execution/engine.py`
  - Let dry-run execution resolve `range-grid` opportunities.
- Modify tests:
  - `backend/tests/unit/test_range_grid_strategy.py`
  - `backend/tests/unit/test_strategy_platform.py`
  - `backend/tests/integration/test_cli_core.py`
- Modify docs:
  - `README.md`
  - `docs/DESIGN.md`
  - `docs/plan/2026-05-09-refactor/02-acceptance-checklist.md`
  - `docs/plan/2026-05-09-refactor/03-traceability-matrix.md`
  - Add `docs/plan/2026-05-09-refactor/66-range-grid-paper-strategy-report.md`

## Task 1: Range Grid Unit Tests

- [ ] Write failing tests for a range regime producing one `range-grid` opportunity with:
  - `strategy_type == "range-grid"`
  - metadata `read_only=true`, `paper_only=true`, `grid_levels`
  - positive `net_profit`
  - buy/sell simulated legs
- [ ] Write failing diagnostic test for non-range regimes returning no opportunity and reason `regime_not_range`.
- [ ] Verify RED with:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_range_grid_strategy.py -v
```

## Task 2: Implement Range Grid Service

- [ ] Add `RangeGridConfig` to `config/schema.py`:
  - enabled, exchange, symbols, grid_levels, lookback_candles, total_quote_usdt, min_grid_spacing_pct, max_range_width_pct, fee_pct, slippage_pct.
- [ ] Implement `RangeGridStrategyService.scan(symbol, exchange)` and `diagnose(symbol, exchange)`.
- [ ] Use `StrategyUniverseService.symbol_report` as a gate; only emit opportunities for `regime=range`.
- [ ] Build grid bounds from completed candle high/low over lookback.
- [ ] Estimate net PnL as completed-grid cycles times level notional times spacing minus round-trip fees/slippage.
- [ ] Return a normal `ArbitrageOpportunity` with two simulated legs and no-order metadata.
- [ ] Verify GREEN with the unit tests.

## Task 3: Platform And Runtime Integration

- [ ] Register `range-grid` in `StrategyRegistry` with `category="grid"`, `demo_supported=False`, `live_supported=False`.
- [ ] Add scanner dispatch and diagnostics.
- [ ] Add `range-grid` to `ExecutionEngine.find_opportunity`.
- [ ] Route `range-grid` through `_preferred_single_exchange` in `StrategyRunner` and `StrategyController`.
- [ ] Add tests that strategy catalog includes `range-grid`, demo validation names exclude it, `strategy scan --strategy range-grid` returns an opportunity under range config, and `strategy run --strategy range-grid --execution-mode paper` journals an execution.

## Task 4: Docs And Traceability

- [ ] Document commands and paper-only caveat in README and DESIGN.
- [ ] Add acceptance checklist command:

```bash
crypto-assistant strategy scan --config configs/config.example.yaml --strategy range-grid --symbol BTC/USDT --json
crypto-assistant strategy run --config configs/config.example.yaml --strategy range-grid --execution-mode paper --json
```

- [ ] Add traceability row `R076 Range Grid Paper Strategy`.
- [ ] Add phase report with verification results.

## Task 5: Verification And Commit

- [ ] Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_range_grid_strategy.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_strategy_platform.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

- [ ] Run CLI smoke:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy scan --config ../configs/config.example.yaml --strategy range-grid --symbol BTC/USDT --json
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy run --config ../configs/config.example.yaml --strategy range-grid --max-cycles 1 --interval-seconds 0 --execution-mode paper --symbol BTC/USDT --json
```

- [ ] Commit:

```bash
git add README.md docs/DESIGN.md docs/plan/2026-05-09-refactor/02-acceptance-checklist.md docs/plan/2026-05-09-refactor/03-traceability-matrix.md docs/plan/2026-05-09-refactor/65-range-grid-paper-strategy-plan.md docs/plan/2026-05-09-refactor/66-range-grid-paper-strategy-report.md backend/src/trading_assistant/config/schema.py backend/src/trading_assistant/arbitrage/scanner.py backend/src/trading_assistant/strategies/range_grid.py backend/src/trading_assistant/strategies/registry.py backend/src/trading_assistant/strategies/runner.py backend/src/trading_assistant/strategies/platform.py backend/src/trading_assistant/execution/engine.py backend/tests/unit/test_range_grid_strategy.py backend/tests/unit/test_strategy_platform.py backend/tests/integration/test_cli_core.py configs/config.example.yaml configs/okx.demo.example.yaml
git commit -m "feat: add range grid paper strategy"
```
