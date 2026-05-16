# Smart DCA Basket Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a paper-only Smart DCA / Basket Rebalancer strategy that identifies drawdown-tiered accumulation opportunities for major crypto assets while respecting liquidity, exposure, and portfolio-weight bands.

**Architecture:** Follow the existing `range-grid` and `hedged-maker` scanner pattern: a deterministic service reads mock/market data, account balances, candles, and orderbook depth, then emits normal `ArbitrageOpportunity` objects with `read_only=true` and `paper_only=true`. The strategy integrates through `ArbitrageScanner`, `StrategyRegistry`, `StrategyController`, `StrategyRunner`, and `ExecutionEngine`, but remains `demo_supported=false` and `live_supported=false`.

**Tech Stack:** Python 3.12, Pydantic v2 settings, Decimal calculations, argparse CLI, pytest, ruff, mypy.

---

## File Structure

- Create `backend/src/trading_assistant/strategies/smart_dca.py`
  - Owns drawdown-tier scoring, basket-weight diagnostics, liquidity checks, cost estimates, and opportunity conversion.
- Modify `backend/src/trading_assistant/config/schema.py`
  - Add `SmartDcaConfig` and attach it to `Settings`.
- Modify `backend/src/trading_assistant/arbitrage/scanner.py`
  - Dispatch `smart-dca-basket` and `smart-dca` to the service.
- Modify `backend/src/trading_assistant/strategies/registry.py`
  - Register `smart-dca-basket` with alias `smart-dca`, category `portfolio`, and demo/live disabled.
- Modify `backend/src/trading_assistant/strategies/platform.py`, `runner.py`, and `execution/engine.py`
  - Include the strategy in single-exchange scans and deterministic opportunity lookup.
- Modify `backend/src/trading_assistant/cli/main.py`
  - Add `smart-dca-basket` to `arbitrage scan --type` choices.
- Modify config examples and docs
  - Add safe defaults in `configs/config.example.yaml` and `configs/okx.demo.example.yaml`.
  - Update `README.md`, `docs/DESIGN.md`, acceptance checklist, and traceability matrix.
- Add tests:
  - `backend/tests/unit/test_smart_dca_strategy.py`
  - Update `backend/tests/unit/test_config.py`
  - Update `backend/tests/unit/test_strategy_platform.py`
  - Update `backend/tests/integration/test_cli_core.py`

## Task 1: RED Tests

- [ ] Add unit tests proving the service emits a BTC/USDT paper opportunity when drawdown, depth, target-weight gap, and cost filters pass.
- [ ] Add diagnostics tests proving the service explains filtered candidates when drawdown is below the minimum.
- [ ] Add config and registry tests proving defaults load, the strategy is enabled, and it is excluded from demo validation.
- [ ] Add CLI tests proving `strategy scan`, `strategy run --execution-mode paper`, and `arbitrage scan --type smart-dca-basket` return JSON.
- [ ] Run the focused test set and record the expected failures in the report.

## Task 2: Strategy Implementation

- [ ] Implement `SmartDcaEstimate` and `SmartDcaStrategyService`.
- [ ] Calculate completed-candle drawdown from recent high to current price.
- [ ] Apply configured drawdown tiers and multipliers to determine DCA order notional.
- [ ] Calculate basket current weights from balances plus current ticker prices.
- [ ] Add an underweight boost only when current weight is below target by the configured rebalance band; block overweight assets from new buys.
- [ ] Estimate fee, slippage, expected discount edge, and net paper edge using Decimal math.
- [ ] Emit a normal opportunity with one simulated spot buy leg, `paper_only=true`, `demo_supported=false`, `live_supported=false`, and complete diagnostics.

## Task 3: Integration, Docs, And Validation

- [ ] Wire scanner, registry, controller, runner, execution lookup, and CLI choices.
- [ ] Update config examples and docs with paper-only usage and safety caveats.
- [ ] Update acceptance and traceability rows under `docs/plan/2026-05-09-refactor/`.
- [ ] Run focused tests, broader affected tests, `ruff`, and `mypy`.
- [ ] Run CLI smoke commands for scan, paper run, and help.
- [ ] Write `docs/plan/2026-05-09-refactor/82-smart-dca-basket-report.md`.
- [ ] Commit as `feat: add smart dca basket strategy`.
