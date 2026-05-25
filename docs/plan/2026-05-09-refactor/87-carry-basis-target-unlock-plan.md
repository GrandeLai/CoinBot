# Carry/Basis Target Unlock Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add read-only target-exchange unlock diagnostics to carry/basis optimization so operators can see which blocked carry/basis strategies are closest to an OKX Demo preflight candidate.

**Architecture:** Keep scan, compare, and optimization responsibilities separate. `StrategyMarketComparisonService` remains the read-only target-market scanner; `CarryBasisOptimizationService` consumes its verdicts and adds card-level unlock fields without touching strategy runner, journal, broker, demo executor, or live gates.

**Tech Stack:** Python 3.12, Pydantic settings, dataclasses, Decimal arithmetic, argparse CLI, pytest.

---

### Task 1: Add Target Unlock Fields To Carry/Basis Cards

**Files:**
- Modify: `backend/src/trading_assistant/strategies/carry_basis_optimizer.py`
- Test: `backend/tests/unit/test_strategy_platform.py`

- [x] **Step 1: Write the failing unit test**

Add a test that calls:

```python
settings = load_settings(EXAMPLE_CONFIG)
_use_temp_runtime_paths(settings, tmp_path)
settings.exchanges["okx"].enabled = True
report = CarryBasisOptimizationService(
    settings,
    ExchangeFactory(settings),
    market_compare_factory_cls=TargetOKXFactory,
).report(symbol="BTC/USDT", target_exchange="okx")
spot = next(card for card in report.cards if card.strategy_name == "spot-perp-carry")
assert report.target_exchange == "okx"
assert spot.target_exchange == "okx"
assert spot.target_verdict == "demo_preflight_candidate"
assert spot.unlock_priority == "demo_candidate"
assert spot.target_best_net_profit_usdt > Decimal("0")
assert spot.target_delta_net_profit_usdt > Decimal("0")
```

- [x] **Step 2: Run the test to verify RED**

Run:

```bash
cd backend && uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_optimization_merges_target_market_unlock_diagnostics -v
```

Expected: fail because `market_compare_factory_cls`, `target_exchange`, `target_verdict`, and `unlock_priority` do not exist yet.

- [x] **Step 3: Implement the minimal code**

Add optional fields to `CarryBasisOptimizationCard`:

```python
target_exchange: str | None = None
target_verdict: str | None = None
target_reasons: list[str] = field(default_factory=list)
target_best_net_profit_usdt: Decimal = Decimal("0")
target_delta_net_profit_usdt: Decimal = Decimal("0")
unlock_priority: str = "local_only"
```

Add `target_exchange: str | None` to `CarryBasisOptimizationReport`. Let `CarryBasisOptimizationService.__init__` accept `market_compare_factory_cls: type[ExchangeFactory] = ExchangeFactory`. In `report()`, when `target_exchange` is provided, call `StrategyMarketComparisonService(self.settings, factory_cls=self.market_compare_factory_cls).compare(strategy_name="all", symbol=symbol, target_exchange=target_exchange)`, index the carry/basis comparisons by strategy name, and merge the matching verdict into each card.

- [x] **Step 4: Run the unit test to verify GREEN**

Run:

```bash
cd backend && uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_optimization_merges_target_market_unlock_diagnostics -v
```

Expected: pass.

### Task 2: Add CLI `--target-exchange` Support

**Files:**
- Modify: `backend/src/trading_assistant/application.py`
- Modify: `backend/src/trading_assistant/cli/main.py`
- Test: `backend/tests/integration/test_cli_core.py`

- [x] **Step 1: Write the failing integration assertion**

Extend `test_cli_strategy_carry_basis_optimize_is_read_only` to run:

```python
code, payload = _invoke(
    [
        "strategy",
        "carry-basis-optimize",
        "--config",
        str(config_path),
        "--symbol",
        "BTC/USDT",
        "--target-exchange",
        "mock",
        "--json",
    ],
    capsys,
)
assert code == 0
report = payload["strategy_carry_basis_optimization"]
assert report["target_exchange"] == "mock"
assert all("unlock_priority" in card for card in report["cards"])
```

- [x] **Step 2: Run the integration test to verify RED**

Run:

```bash
cd backend && uv run pytest tests/integration/test_cli_core.py::test_cli_strategy_carry_basis_optimize_is_read_only -v
```

Expected: fail because the CLI parser does not accept `--target-exchange`.

- [x] **Step 3: Implement the CLI path**

Add `--target-exchange` to the `carry-basis-optimize` parser, pass it through `Application.strategy_carry_basis_optimize(symbol, target_exchange)`, and include target counts in the human summary:

```python
f"target_candidates={summary['target_demo_preflight_candidate_count']}"
```

- [x] **Step 4: Run the integration test to verify GREEN**

Run:

```bash
cd backend && uv run pytest tests/integration/test_cli_core.py::test_cli_strategy_carry_basis_optimize_is_read_only -v
```

Expected: pass.

### Task 3: Update Refactor Docs And Verification Evidence

**Files:**
- Modify: `docs/DESIGN.md`
- Modify: `docs/plan/2026-05-09-refactor/03-traceability-matrix.md`
- Create: `docs/plan/2026-05-09-refactor/88-carry-basis-target-unlock-report.md`

- [x] **Step 1: Document behavior**

Document that `strategy carry-basis-optimize --target-exchange okx --json` is read-only, merges market-compare verdicts, and never sends demo/live orders.

- [x] **Step 2: Run targeted verification**

Run:

```bash
cd backend && uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_optimization_merges_target_market_unlock_diagnostics tests/integration/test_cli_core.py::test_cli_strategy_carry_basis_optimize_is_read_only -v
cd backend && uv run ruff check src/trading_assistant/strategies/carry_basis_optimizer.py src/trading_assistant/application.py src/trading_assistant/cli/main.py tests/unit/test_strategy_platform.py tests/integration/test_cli_core.py
```

Expected: tests pass and ruff reports no issues.
