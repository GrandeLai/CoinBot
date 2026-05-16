# Hedged Maker Paper Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stateful paper lifecycle simulator for `hedged-maker` quotes so paper runs record open maker quotes, TTL cancel/refresh decisions, simulated fills, hedge attribution, and realized paper PnL separately from expected scan edge.

**Architecture:** Keep `hedged-maker` paper-only and add `HedgedMakerPaperLifecycleService` under `strategies/`. The service persists a small JSON state file configured under `hedged_maker.paper_state_path`, manages open paper maker orders, simulates fill/hedge decisions from current mock/orderbook snapshots, and returns a JSON-safe lifecycle payload consumed by `StrategyRunner` for paper runs.

**Tech Stack:** Python 3.12, Decimal, dataclasses, Pydantic v2 settings, existing exchange interface, existing strategy runner, pytest, ruff, mypy.

---

## Design Choices

- Scope is paper lifecycle only; no OKX Demo, live broker, websocket, or real order API is added.
- Open maker quotes persist in a JSON state file so repeated `strategy run --strategy hedged-maker` calls can observe existing paper quotes.
- A fresh paper run first evaluates existing open quotes:
  - cancel quotes older than `strategy_runtime.order_ttl_seconds`
  - fill a buy quote when quote price is at or above current maker ask
  - fill a sell quote when quote price is at or below current maker bid
  - immediately simulate the taker hedge on the hedge exchange top of book after a maker fill
- If no fill happens, the service keeps an existing same-symbol quote when its price is inside `strategy_runtime.reprice_threshold_pct`; otherwise it cancels/replaces it.
- Realized paper PnL is recorded only when a simulated maker fill and taker hedge happen. Pending/open quotes report realized PnL as `0`, while preserving expected edge as `expected_net_profit_usdt`.
- Runtime output includes `orders_sent=false`, `live_orders_sent=false`, `paper_only=true`, and `simulation_only=true`.

## Files

- Create `backend/src/trading_assistant/strategies/hedged_maker_lifecycle.py`
  - Paper state models, JSON persistence, TTL cancel/reprice, fill/hedge simulation, and lifecycle result serialization.
- Modify `backend/src/trading_assistant/config/schema.py`
  - Add `paper_state_path` to `HedgedMakerConfig`.
- Modify configs:
  - `configs/config.example.yaml`
  - `configs/okx.demo.example.yaml`
- Modify `backend/src/trading_assistant/strategies/runner.py`
  - Use the lifecycle service for `hedged-maker` paper execution instead of treating maker and hedge legs as instant fills.
- Add tests:
  - `backend/tests/unit/test_hedged_maker_lifecycle.py`
  - update `backend/tests/integration/test_cli_core.py`
  - update `backend/tests/unit/test_config.py`
- Update docs:
  - `README.md`
  - `docs/DESIGN.md`
  - `docs/plan/2026-05-09-refactor/02-acceptance-checklist.md`
  - `docs/plan/2026-05-09-refactor/03-traceability-matrix.md`
  - add `docs/plan/2026-05-09-refactor/72-hedged-maker-paper-lifecycle-report.md`

## Task 1: RED Lifecycle Tests

- [ ] Add `backend/tests/unit/test_hedged_maker_lifecycle.py`.
- [ ] Test first paper lifecycle call creates one open maker quote:
  - `status == "quoted"`
  - `paper_only is True`
  - `orders_sent is False`
  - `live_orders_sent is False`
  - `realized_net_profit_usdt == Decimal("0")`
  - state file contains one `open` quote.
- [ ] Test repeated same-symbol call inside reprice threshold keeps the existing quote instead of duplicating it:
  - `status == "active_quote_unchanged"`
  - state file still has one open quote.
- [ ] Test expired quote is canceled and replaced:
  - first call at `2026-05-16T00:00:00Z`
  - second call after `order_ttl_seconds + 1`
  - result includes a canceled order id and one new open quote.
- [ ] Test crossed existing quote simulates maker fill and taker hedge:
  - seed an open buy quote with price above current maker ask
  - result `status == "filled_and_hedged"`
  - hedge side is `sell`
  - realized net PnL is present and state marks the order `filled`.
- [ ] Verify RED:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_lifecycle.py -v
```

Expected: fail because `trading_assistant.strategies.hedged_maker_lifecycle` does not exist.

## Task 2: Lifecycle Service

- [ ] Implement `HedgedMakerPaperLifecycleService`.
- [ ] Implement JSON state shape:
  - top-level `orders` list
  - each order has id, opportunity id, symbol, maker/hedge exchanges, maker/hedge sides, price, quantity, expected net PnL, status, created/updated timestamps, optional filled/hedged timestamps, and optional realized net PnL.
- [ ] Implement deterministic order id from strategy, symbol, side, timestamp, and state sequence.
- [ ] Implement fill math with Decimal:
  - maker buy fill notional = maker fill price * quantity
  - maker sell fill notional = maker fill price * quantity
  - hedge sell uses hedge bid; hedge buy uses hedge ask
  - fees = maker notional * maker fee + hedge notional * taker fee
  - slippage = hedge notional * hedge slippage
  - net PnL = sell notional - buy notional - fees - slippage
- [ ] Verify GREEN with lifecycle unit tests.

## Task 3: Runner Integration

- [ ] Add `paper_state_path` defaults to schema and example configs.
- [ ] In `StrategyRunner._run_one`, route `definition.name == "hedged-maker"` and `mode == "paper"` through the lifecycle service after risk/budget approval.
- [ ] Return `decision="executed"` for quoted/unchanged/replaced/filled lifecycle results; return realized lifecycle PnL as the cycle `net_profit`.
- [ ] Preserve expected scan edge inside execution payload as `expected_net_profit`.
- [ ] Update CLI integration test to assert `strategy run --strategy hedged-maker` includes `execution.hedged_maker_lifecycle.status` and writes the configured state file.
- [ ] Update config tests for `paper_state_path`.

## Task 4: Docs And Traceability

- [ ] Document the stateful paper lifecycle and state path in README.
- [ ] Update DESIGN hedged-maker paragraph to mention stateful paper quotes, TTL cancel/refresh, simulated fills, and realized-vs-expected PnL separation.
- [ ] Add acceptance checklist entries for lifecycle state output.
- [ ] Add traceability row `R079 Hedged Maker Paper Lifecycle`.
- [ ] Add phase report with verification results.

## Task 5: Verification And Commit

- [ ] Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_lifecycle.py tests/unit/test_hedged_maker_strategy.py tests/unit/test_config.py tests/integration/test_cli_core.py -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

- [ ] Run CLI smoke with temp runtime paths:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy run --config /private/tmp/coinbot-hedged-maker-lifecycle-smoke.yaml --strategy hedged-maker --max-cycles 2 --interval-seconds 0 --execution-mode paper --symbol BTC/USDT --json
```

- [ ] Commit:

```bash
git add README.md docs/DESIGN.md docs/plan/2026-05-09-refactor/02-acceptance-checklist.md docs/plan/2026-05-09-refactor/03-traceability-matrix.md docs/plan/2026-05-09-refactor/71-hedged-maker-paper-lifecycle-plan.md docs/plan/2026-05-09-refactor/72-hedged-maker-paper-lifecycle-report.md backend/src/trading_assistant/config/schema.py backend/src/trading_assistant/strategies/hedged_maker_lifecycle.py backend/src/trading_assistant/strategies/runner.py backend/tests/unit/test_hedged_maker_lifecycle.py backend/tests/unit/test_hedged_maker_strategy.py backend/tests/unit/test_config.py backend/tests/integration/test_cli_core.py configs/config.example.yaml configs/okx.demo.example.yaml
git commit -m "feat: add hedged maker paper lifecycle"
```
