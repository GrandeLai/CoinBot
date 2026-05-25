# Carry/Basis Multi-Symbol Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a read-only multi-symbol carry/basis sweep so operators can find which symbol/strategy pairs are closest to OKX Demo preflight eligibility before attempting simulated orders.

**Architecture:** Keep the existing single-symbol `carry-basis-optimize` behavior unchanged. Add a `sweep()` service method that calls the existing report path per symbol, ranks all cards by unlock priority and break-even gap, and exposes the sweep through the same CLI command via `--symbols`.

**Tech Stack:** Python 3.12, Decimal arithmetic, argparse CLI, pytest, ruff, mypy.

---

### Task 1: Service Sweep Shape

**Files:**
- Modify: `backend/tests/unit/test_strategy_platform.py`
- Modify: `backend/src/trading_assistant/strategies/carry_basis_optimizer.py`

- [x] **Step 1: Write the failing unit test**

Add a test that calls `CarryBasisOptimizationService.sweep(symbols=["BTC/USDT", "ETH/USDT"], target_exchange="okx")` with `TargetOKXFactory` and asserts:

- the sweep is read-only and sends no orders
- both symbols have per-symbol reports
- ranked cards include the symbol field
- ranked cards are ordered with `demo_candidate` before lower priorities
- summary includes `symbol_count`, `card_count`, and `target_demo_preflight_candidate_count`

- [x] **Step 2: Run the unit test and verify RED**

Run:

```bash
cd backend && uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_optimization_sweeps_multiple_symbols_and_ranks_unlocks -v
```

Expected: fail because `CarryBasisOptimizationService` has no `sweep()` method.

- [x] **Step 3: Implement minimal sweep support**

Add `CarryBasisOptimizationSweep` and `CarryBasisOptimizationService.sweep()`. Reuse `report()` for each symbol. Rank cards by:

1. `demo_candidate`
2. `paper_candidate`
3. `observe_only`
4. `local_only`

Then sort by `break_even_gap_usdt`, `target_delta_net_profit_usdt`, symbol, and strategy name.

- [x] **Step 4: Run the unit test and verify GREEN**

Run:

```bash
cd backend && uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_optimization_sweeps_multiple_symbols_and_ranks_unlocks -v
```

Expected: pass.

### Task 2: CLI Wiring

**Files:**
- Modify: `backend/tests/integration/test_cli_core.py`
- Modify: `backend/src/trading_assistant/application.py`
- Modify: `backend/src/trading_assistant/cli/main.py`

- [x] **Step 1: Write the failing CLI test**

Extend the CLI help test to assert `--symbols` appears for `strategy carry-basis-optimize`. Add an integration test that runs:

```bash
crypto-assistant strategy carry-basis-optimize --config <tmp-config> --symbols BTC/USDT,ETH/USDT --target-exchange mock --json
```

Assert the response has `mode=sweep`, `symbols=["BTC/USDT", "ETH/USDT"]`, `orders_sent=false`, `live_orders_sent=false`, per-symbol reports, ranked cards, and target candidate summary fields.

- [x] **Step 2: Run the CLI test and verify RED**

Run:

```bash
cd backend && uv run pytest tests/integration/test_cli_core.py::test_cli_strategy_carry_basis_optimize_is_read_only -v
```

Expected: fail because `--symbols` is not accepted.

- [x] **Step 3: Implement CLI and application support**

Add `--symbols` to the parser. If present, parse comma-separated symbols and call the new application sweep path; otherwise keep the existing single-symbol response unchanged.

- [x] **Step 4: Run the CLI test and verify GREEN**

Run:

```bash
cd backend && uv run pytest tests/integration/test_cli_core.py::test_cli_strategy_carry_basis_optimize_is_read_only -v
```

Expected: pass.

### Task 3: Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/DESIGN.md`
- Modify: `docs/plan/2026-05-09-refactor/03-traceability-matrix.md`
- Create: `docs/plan/2026-05-09-refactor/90-carry-basis-multi-symbol-sweep-report.md`
- Modify: `docs/plan/2026-05-09-refactor/99-final-acceptance-report.md`

- [x] **Step 1: Document the new CLI flag**

Add a README example showing:

```bash
uv run crypto-assistant strategy carry-basis-optimize \
  --config ../configs/okx.demo.example.yaml \
  --symbols BTC/USDT,ETH/USDT,SOL/USDT \
  --target-exchange okx \
  --json
```

- [x] **Step 2: Sync architecture and traceability docs**

Document that the sweep is read-only, reuses single-symbol diagnostics, and ranks candidates without sending demo or live orders.

- [x] **Step 3: Run focused verification**

Run:

```bash
cd backend && uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_optimization_sweeps_multiple_symbols_and_ranks_unlocks tests/unit/test_strategy_platform.py::test_carry_basis_optimization_merges_target_market_unlock_diagnostics tests/integration/test_cli_core.py::test_cli_strategy_carry_basis_optimize_is_read_only -v
cd backend && uv run ruff check src/trading_assistant/strategies/carry_basis_optimizer.py src/trading_assistant/application.py src/trading_assistant/cli/main.py tests/unit/test_strategy_platform.py tests/integration/test_cli_core.py
cd backend && uv run mypy src/trading_assistant/strategies/carry_basis_optimizer.py src/trading_assistant/application.py src/trading_assistant/cli/main.py
```

Expected: all pass.
