# Hedged Maker Paper Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a paper-only hedged maker / XEMM simulator that plans passive maker quotes and immediate taker hedges before any demo/live order support exists.

**Architecture:** Add `HedgedMakerStrategyService` under `strategies/` and dispatch it through the existing `ArbitrageScanner`, strategy registry, platform controller, runner, and dry-run execution engine. The service will estimate both maker-buy/hedge-sell and maker-sell/hedge-buy quote candidates, subtract maker/taker fees and hedge slippage, check maker inventory and hedge depth, and emit a normal `ArbitrageOpportunity` with `read_only=true` and `paper_only=true`.

**Tech Stack:** Python 3.12, Decimal, Pydantic v2 settings, existing exchange interface, `ArbitrageOpportunity`, argparse CLI, pytest, ruff, mypy.

---

## File Structure

- Create `backend/src/trading_assistant/strategies/hedged_maker.py`
  - Owns quote planning, hedge preview, diagnostics, and opportunity construction.
- Modify `backend/src/trading_assistant/config/schema.py`
  - Add `HedgedMakerConfig`.
- Modify `backend/src/trading_assistant/arbitrage/scanner.py`
  - Dispatch `hedged-maker` scans and diagnostics.
- Modify `backend/src/trading_assistant/strategies/registry.py`
  - Register `hedged-maker` as paper-only/demo-disabled/live-disabled.
- Modify `backend/src/trading_assistant/strategies/platform.py` and `runner.py`
  - Route `hedged-maker` through the strategy controller/runtime.
- Modify `backend/src/trading_assistant/execution/engine.py`
  - Let dry-run execution resolve `hedged-maker` opportunity IDs.
- Modify `backend/src/trading_assistant/cli/main.py`
  - Add `hedged-maker` to `arbitrage scan --type`.
- Modify configs:
  - `configs/config.example.yaml`
  - `configs/okx.demo.example.yaml`
- Add tests:
  - `backend/tests/unit/test_hedged_maker_strategy.py`
  - update `backend/tests/unit/test_strategy_platform.py`
  - update `backend/tests/unit/test_config.py`
  - update `backend/tests/integration/test_cli_core.py`
- Update docs:
  - `README.md`
  - `docs/DESIGN.md`
  - `docs/plan/2026-05-09-refactor/02-acceptance-checklist.md`
  - `docs/plan/2026-05-09-refactor/03-traceability-matrix.md`
  - add `docs/plan/2026-05-09-refactor/70-hedged-maker-paper-simulator-report.md`

## Task 1: Unit Tests

- [x] Add `backend/tests/unit/test_hedged_maker_strategy.py`.
- [x] Test default mock/mocked-alt BTC scan emits one `hedged-maker` paper opportunity:
  - `strategy_type == "hedged-maker"`
  - metadata `read_only=true`, `paper_only=true`, `maker_order_type="limit_post_only"`
  - metadata includes `maker_quote` and `hedge_preview`
  - legs include one maker quote and one taker hedge
  - net profit is positive after maker/taker fees and hedge slippage
- [x] Test diagnostics reject weak edge when `settings.hedged_maker.min_edge_pct` is set above the observed edge.
- [x] Verify RED:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_strategy.py -v
```

Expected: fail because `trading_assistant.strategies.hedged_maker` does not exist.

## Task 2: Config And Service

- [x] Add `HedgedMakerConfig`:
  - enabled, maker_exchange, hedge_exchange, symbols, quote_notional_usdt, quote_spread_pct, min_edge_pct, maker_fee_pct, taker_fee_pct, hedge_slippage_pct, min_hedge_depth_usdt.
- [x] Implement `HedgedMakerStrategyService.scan(symbol, maker_exchange=None, hedge_exchange=None)` and `diagnose(...)`.
- [x] Quote candidates:
  - maker buy: buy passively below maker mid, then hedge by selling on hedge exchange bid.
  - maker sell: sell passively above maker mid, then hedge by buying on hedge exchange ask.
- [x] Check maker USDT/base inventory and hedge orderbook depth.
- [x] Return the best approved candidate as an `ArbitrageOpportunity`.
- [x] Verify GREEN with unit tests.

## Task 3: Platform, Runtime, CLI

- [x] Add scanner dispatch and diagnostics for `hedged-maker`.
- [x] Register strategy with `demo_supported=false` and `live_supported=false`.
- [x] Add `hedged-maker` to runtime/platform symbol-scan paths.
- [x] Add `hedged-maker` to execution-engine opportunity lookup.
- [x] Add `hedged-maker` to `arbitrage scan --type` choices.
- [x] Update tests:
  - catalog includes `hedged-maker`
  - demo validation names exclude it
  - strategy scan/run paper path works
- [x] Run targeted tests:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_strategy.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_strategy_platform.py::test_strategy_catalog_registers_new_strategies_and_compatibility_aliases -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py::test_cli_strategy_hedged_maker_scans_and_runs_in_paper -v
```

## Task 4: Docs And Traceability

- [x] Document `hedged-maker` paper-only caveat and commands in README.
- [x] Update DESIGN with XEMM paper simulator behavior.
- [x] Add acceptance checklist commands:
  - `crypto-assistant strategy scan --config configs/config.example.yaml --strategy hedged-maker --symbol BTC/USDT --json`
  - `crypto-assistant strategy run --config configs/config.example.yaml --strategy hedged-maker --execution-mode paper --symbol BTC/USDT --json`
- [x] Add traceability row `R078 Hedged Maker Paper Simulator`.
- [x] Add phase report with verification results.

## Task 5: Verification And Commit

- [x] Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_strategy.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_strategy_platform.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_config.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

- [x] Run CLI smoke:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy scan --config ../configs/config.example.yaml --strategy hedged-maker --symbol BTC/USDT --json
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy run --config ../configs/config.example.yaml --strategy hedged-maker --max-cycles 1 --interval-seconds 0 --execution-mode paper --symbol BTC/USDT --json
```

- [x] Commit:

```bash
git add README.md docs/DESIGN.md docs/plan/2026-05-09-refactor/02-acceptance-checklist.md docs/plan/2026-05-09-refactor/03-traceability-matrix.md docs/plan/2026-05-09-refactor/69-hedged-maker-paper-simulator-plan.md docs/plan/2026-05-09-refactor/70-hedged-maker-paper-simulator-report.md backend/src/trading_assistant/config/schema.py backend/src/trading_assistant/arbitrage/scanner.py backend/src/trading_assistant/strategies/hedged_maker.py backend/src/trading_assistant/strategies/registry.py backend/src/trading_assistant/strategies/platform.py backend/src/trading_assistant/strategies/runner.py backend/src/trading_assistant/execution/engine.py backend/src/trading_assistant/cli/main.py backend/tests/unit/test_hedged_maker_strategy.py backend/tests/unit/test_strategy_platform.py backend/tests/unit/test_config.py backend/tests/integration/test_cli_core.py configs/config.example.yaml configs/okx.demo.example.yaml
git commit -m "feat: add hedged maker paper simulator"
```
