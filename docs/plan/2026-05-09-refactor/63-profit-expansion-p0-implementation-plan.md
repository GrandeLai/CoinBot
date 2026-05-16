# Profit Expansion P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build CoinBot's first profit-expansion foundation: dynamic market universe/regime routing plus a reusable triple-barrier position executor and exit optimizer, all paper/mock-first and live-disabled.

**Architecture:** Add two small strategy services. `StrategyUniverseService` reads exchange symbols, ticker spread/volume, orderbook depth, and candles to classify tradable symbols and market regimes without orders. `TripleBarrierPositionExecutor` and `ExitOptimizerService` provide deterministic exit lifecycle simulation and advisory parameter proposals for existing directional strategies, feeding CLI JSON and future strategy execution.

**Tech Stack:** Python 3.12, Pydantic v2 settings, Decimal calculations, existing `ExchangeFactory`, argparse CLI, pytest, ruff, mypy.

---

## File Structure

- Create `backend/src/trading_assistant/strategies/universe.py`
  - Owns symbol scoring, filters, candle-derived regime classification, and JSON-safe reports.
- Create `backend/src/trading_assistant/strategies/position_executor.py`
  - Owns triple-barrier position state simulation, exit event classification, and exit optimizer proposals.
- Modify `backend/src/trading_assistant/config/schema.py`
  - Add safe defaults for universe filters and triple-barrier optimizer candidate ranges.
- Modify `backend/src/trading_assistant/application.py`
  - Add facade methods `strategy_universe`, `strategy_regime_report`, `strategy_exit_optimize`, and `strategy_position_report`.
- Modify `backend/src/trading_assistant/cli/main.py`
  - Add CLI commands and handlers.
- Modify `README.md`, `docs/DESIGN.md`, `docs/plan/2026-05-09-refactor/02-acceptance-checklist.md`, and `03-traceability-matrix.md`
  - Keep public docs aligned.
- Add `backend/tests/unit/test_profit_expansion_p0.py`
  - Focused service tests.
- Modify `backend/tests/integration/test_cli_core.py`
  - CLI JSON and help coverage.
- Add `docs/plan/2026-05-09-refactor/64-profit-expansion-p0-report.md`
  - Phase report with verification evidence.

## Task 1: Dynamic Universe And Regime Service

**Files:**
- Create: `backend/src/trading_assistant/strategies/universe.py`
- Modify: `backend/src/trading_assistant/config/schema.py`
- Test: `backend/tests/unit/test_profit_expansion_p0.py`

- [ ] **Step 1: Write failing tests**

Add tests that create default settings with temp runtime paths, call `StrategyUniverseService(settings, ExchangeFactory(settings)).report(exchange="mock")`, and assert:

```python
assert report.read_only is True
assert report.orders_sent is False
assert report.live_orders_sent is False
assert report.exchange == "mock"
assert report.accepted_symbols
btc = next(row for row in report.symbols if row.symbol == "BTC/USDT")
assert btc.accepted is True
assert btc.regime in {"trend", "range", "carry", "avoid", "illiquid"}
assert btc.spread_pct >= Decimal("0")
```

Add a second test that raises `settings.universe.min_24h_volume_usdt` above mock volume and asserts BTC is rejected with `volume_below_minimum`.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_profit_expansion_p0.py::test_strategy_universe_accepts_liquid_mock_symbols -v
```

Expected: fail because `trading_assistant.strategies.universe` does not exist.

- [ ] **Step 3: Implement minimal config and service**

Add `UniverseConfig` to `config/schema.py`:

```python
class UniverseConfig(BaseModel):
    """Read-only market universe and regime filter controls."""

    enabled: bool = True
    symbols: list[str] = Field(default_factory=lambda: ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT", "ADA/USDT"])
    bar: str = "15m"
    candles_limit: int = 80
    min_24h_volume_usdt: Decimal = Decimal("100000")
    min_depth_usdt: Decimal = Decimal("1000")
    max_spread_pct: Decimal = Decimal("0.10")
    trend_return_threshold_pct: Decimal = Decimal("1.00")
    range_volatility_max_pct: Decimal = Decimal("1.25")
```

Add to `Settings`:

```python
universe: UniverseConfig = Field(default_factory=UniverseConfig)
```

Implement `StrategyUniverseService` with dataclasses:

```python
@dataclass(frozen=True)
class UniverseSymbolReport:
    symbol: str
    accepted: bool
    regime: str
    reasons: list[str]
    spread_pct: Decimal
    bid_depth_usdt: Decimal
    ask_depth_usdt: Decimal
    volume_24h_usdt: Decimal
    return_pct: Decimal
    volatility_pct: Decimal
```

Service logic:

- `symbols = settings.universe.symbols or exchange.list_symbols()`
- For each symbol, read ticker, orderbook, and candles.
- `mid = (bid + ask) / 2`
- `spread_pct = (ask - bid) / mid * 100`
- `volume_24h_usdt = ticker.volume * ticker.last`
- `depth = min(orderbook.depth_notional("bid"), orderbook.depth_notional("ask"))`
- `return_pct = (last_close - first_close) / first_close * 100`
- `volatility_pct = average absolute close-to-close return`
- Reject with reason codes: `spread_above_maximum`, `volume_below_minimum`, `depth_below_minimum`, `market_data_error:*`
- Regime:
  - `illiquid` if any liquidity rejection.
  - `trend` if absolute return is at least `trend_return_threshold_pct`.
  - `range` if volatility is at most `range_volatility_max_pct`.
  - `carry` if accepted but neither trend nor range.
  - `avoid` if rejected for market data.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_profit_expansion_p0.py -v
```

Expected: pass Task 1 tests.

## Task 2: Triple-Barrier Position Executor And Exit Optimizer

**Files:**
- Create: `backend/src/trading_assistant/strategies/position_executor.py`
- Modify: `backend/src/trading_assistant/config/schema.py`
- Test: `backend/tests/unit/test_profit_expansion_p0.py`

- [ ] **Step 1: Write failing tests**

Add tests:

```python
def test_triple_barrier_executor_exits_on_take_profit() -> None:
    candles = _position_candles(["100", "101", "102.5", "102.2"])
    executor = TripleBarrierPositionExecutor()
    result = executor.simulate_long(
        strategy_name="trend-breakout",
        symbol="BTC/USDT",
        entry_price=Decimal("100"),
        quantity=Decimal("1"),
        candles=candles,
        take_profit_pct=Decimal("2"),
        stop_loss_pct=Decimal("1"),
        trailing_stop_pct=Decimal("0.5"),
        time_limit_bars=10,
        fee_pct=Decimal("0.001"),
    )
    assert result.exit_reason == "take_profit"
    assert result.orders_sent is False
    assert result.live_orders_sent is False
    assert result.net_pnl_usdt > Decimal("0")
```

Add an optimizer test that asserts `ExitOptimizerService(...).optimize("trend-breakout", "BTC/USDT")` returns read-only proposals sorted by score and includes `take_profit_pct`, `stop_loss_pct`, `trailing_stop_pct`, and `time_limit_bars`.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_profit_expansion_p0.py::test_triple_barrier_executor_exits_on_take_profit -v
```

Expected: fail because `trading_assistant.strategies.position_executor` does not exist.

- [ ] **Step 3: Implement minimal executor and optimizer**

Add `PositionExitResult`, `ExitParameterCandidate`, `ExitOptimizationReport`, `TripleBarrierPositionExecutor`, and `ExitOptimizerService`.

Executor behavior:

- Long-only simulation.
- Check each completed candle after entry.
- Exit priority: stop loss, take profit, trailing stop, time limit.
- Fees: `(entry_notional + exit_notional) * fee_pct`.
- Return `orders_sent=False`, `live_orders_sent=False`, `read_only=True`.

Optimizer behavior:

- Use exchange candles for the symbol.
- Build candidate grid from config defaults.
- For each candidate, simulate from first completed candle close.
- Score = net PnL minus drawdown penalty.
- Return top candidates with reason codes.
- Do not mutate config and do not place orders.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_profit_expansion_p0.py -v
```

Expected: pass all unit tests in the new file.

## Task 3: Application And CLI Wiring

**Files:**
- Modify: `backend/src/trading_assistant/application.py`
- Modify: `backend/src/trading_assistant/cli/main.py`
- Test: `backend/tests/integration/test_cli_core.py`

- [ ] **Step 1: Write failing CLI tests**

Add to `test_cli_strategy_help_includes_all_json_commands` or equivalent help test:

```python
with pytest.raises(SystemExit) as universe_help_exit:
    main(["strategy", "universe", "--help"])
assert universe_help_exit.value.code == 0
assert "--exchange" in capsys.readouterr().out
```

Add CLI behavior test:

```python
code, payload = _invoke(["strategy", "universe", "--config", str(config_path), "--exchange", "mock"], capsys)
assert code == 0
assert payload["strategy_universe"]["read_only"] is True
assert payload["strategy_universe"]["accepted_symbols"]

code, payload = _invoke(["strategy", "regime-report", "--config", str(config_path), "--exchange", "mock", "--symbol", "BTC/USDT"], capsys)
assert code == 0
assert payload["strategy_regime_report"]["symbol"] == "BTC/USDT"

code, payload = _invoke(["strategy", "exit-optimize", "--config", str(config_path), "--strategy", "trend-breakout", "--symbol", "BTC/USDT"], capsys)
assert code == 0
assert payload["strategy_exit_optimization"]["read_only"] is True
assert payload["strategy_exit_optimization"]["candidates"]

code, payload = _invoke(["strategy", "position-report", "--config", str(config_path), "--strategy", "trend-breakout", "--symbol", "BTC/USDT"], capsys)
assert code == 0
assert payload["strategy_position_report"]["read_only"] is True
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py::test_cli_strategy_universe_regime_and_exit_commands -v
```

Expected: fail with invalid choice or missing handler.

- [ ] **Step 3: Implement application facade and CLI parser/handlers**

Application methods:

```python
def strategy_universe(self, exchange: str) -> dict[str, Any]:
    return {"strategy_universe": StrategyUniverseService(self.settings, self.exchanges).report(exchange=exchange).to_dict()}

def strategy_regime_report(self, exchange: str, symbol: str) -> dict[str, Any]:
    return {"strategy_regime_report": StrategyUniverseService(self.settings, self.exchanges).symbol_report(exchange=exchange, symbol=symbol).to_dict()}

def strategy_exit_optimize(self, strategy_name: str, symbol: str, exchange: str) -> dict[str, Any]:
    return {"strategy_exit_optimization": ExitOptimizerService(self.settings, self.exchanges).optimize(strategy_name, symbol, exchange=exchange).to_dict()}

def strategy_position_report(self, strategy_name: str, symbol: str, exchange: str) -> dict[str, Any]:
    return {"strategy_position_report": ExitOptimizerService(self.settings, self.exchanges).position_report(strategy_name, symbol, exchange=exchange).to_dict()}
```

CLI commands:

- `strategy universe --config ... --exchange mock --json`
- `strategy regime-report --config ... --exchange mock --symbol BTC/USDT --json`
- `strategy exit-optimize --config ... --strategy trend-breakout --symbol BTC/USDT --exchange mock --json`
- `strategy position-report --config ... --strategy trend-breakout --symbol BTC/USDT --exchange mock --json`

- [ ] **Step 4: Run integration tests to verify GREEN**

Run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py::test_cli_strategy_universe_regime_and_exit_commands -v
```

Expected: pass.

## Task 4: Documentation And Traceability

**Files:**
- Modify: `README.md`
- Modify: `docs/DESIGN.md`
- Modify: `docs/plan/2026-05-09-refactor/02-acceptance-checklist.md`
- Modify: `docs/plan/2026-05-09-refactor/03-traceability-matrix.md`
- Create: `docs/plan/2026-05-09-refactor/64-profit-expansion-p0-report.md`

- [ ] **Step 1: Update docs**

Document:

- Dynamic universe/regime commands.
- Exit optimization/position report commands.
- Read-only/no-order safety.
- Traceability rows:
  - `R074 Dynamic Universe And Regime Router`
  - `R075 Triple-Barrier Position Executor And Exit Optimizer`

- [ ] **Step 2: Run docs sanity checks**

Run:

```bash
rg -n "strategy universe|regime-report|exit-optimize|position-report" README.md docs/DESIGN.md docs/plan/2026-05-09-refactor/02-acceptance-checklist.md docs/plan/2026-05-09-refactor/03-traceability-matrix.md
```

Expected: all four commands appear in docs and traceability.

## Task 5: Final Verification And Commit

**Files:**
- All changed files.

- [ ] **Step 1: Run targeted tests**

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_profit_expansion_p0.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py::test_cli_strategy_universe_regime_and_exit_commands -v
```

- [ ] **Step 2: Run broad Python quality gates**

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

- [ ] **Step 3: Run CLI smoke**

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy universe --config ../configs/config.example.yaml --exchange mock --json
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy exit-optimize --config ../configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --exchange mock --json
```

Expected: both exit 0, both report `read_only=true`, `orders_sent=false`, and `live_orders_sent=false`.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/DESIGN.md docs/plan/2026-05-09-refactor/02-acceptance-checklist.md docs/plan/2026-05-09-refactor/03-traceability-matrix.md docs/plan/2026-05-09-refactor/63-profit-expansion-p0-implementation-plan.md docs/plan/2026-05-09-refactor/64-profit-expansion-p0-report.md backend/src/trading_assistant/config/schema.py backend/src/trading_assistant/application.py backend/src/trading_assistant/cli/main.py backend/src/trading_assistant/strategies/universe.py backend/src/trading_assistant/strategies/position_executor.py backend/tests/unit/test_profit_expansion_p0.py backend/tests/integration/test_cli_core.py
git commit -m "feat: add profit expansion p0 foundations"
```
