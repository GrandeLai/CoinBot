# Profit Expansion P0 Report

Date: 2026-05-16

## Scope

Implemented the first profit-expansion foundation from the open-source platform research:

- Dynamic universe and regime routing.
- Read-only triple-barrier position exit simulation.
- Read-only exit parameter optimization.

This phase does not add live order dispatch and does not enable autonomous live trading. All new commands report no-order evidence.

## Implemented

### Dynamic Universe And Regime Router

- Added `trading_assistant.strategies.universe.StrategyUniverseService`.
- Added `universe` config defaults for symbols, candle bar/limit, volume, depth, spread, trend, and range thresholds.
- Added CLI:
  - `crypto-assistant strategy universe --config configs/config.example.yaml --exchange mock --json`
  - `crypto-assistant strategy regime-report --config configs/config.example.yaml --exchange mock --symbol BTC/USDT --json`

The service reads ticker, orderbook, and completed candles, then returns:

- accepted/rejected symbols
- spread percentage
- bid/ask depth
- 24h quote volume estimate
- completed-candle return
- average close-to-close volatility
- regime: `trend`, `range`, `carry`, `illiquid`, or `avoid`
- reason codes such as `volume_below_minimum`

### Triple-Barrier Exit Optimizer

- Added `trading_assistant.strategies.position_executor.TripleBarrierPositionExecutor`.
- Added `ExitOptimizerService`.
- Added `exit_optimization` config defaults for take-profit, stop-loss, trailing-stop, and time-limit candidate grids.
- Added CLI:
  - `crypto-assistant strategy exit-optimize --config configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --exchange mock --json`
  - `crypto-assistant strategy position-report --config configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --exchange mock --json`

The optimizer simulates long-only directional exits over completed candles and ranks candidates by net PnL minus a drawdown penalty. It returns proposals only and does not edit configs.

## Safety

- `strategy universe` is read-only.
- `strategy regime-report` is read-only.
- `strategy exit-optimize` is read-only.
- `strategy position-report` is read-only.
- All new payloads include `orders_sent=false` and `live_orders_sent=false`.
- No live broker or `agent execute-live` path is called.
- Config examples preserve:

```yaml
trading:
  live_trading: false
  dry_run: true
  require_confirm_before_order: true
```

## Verification

Commands run:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_profit_expansion_p0.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py::test_cli_strategy_universe_regime_and_exit_commands -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_config.py -v
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy universe --config ../configs/config.example.yaml --exchange mock --json
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy exit-optimize --config ../configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --exchange mock --json
```

Results:

- `tests/unit/test_profit_expansion_p0.py`: 4 passed.
- `test_cli_strategy_universe_regime_and_exit_commands`: passed.
- `tests/unit/test_config.py`: 8 passed.
- `tests/integration/test_cli_core.py`: 21 passed.
- `ruff check src/ tests/`: passed.
- `mypy src/`: passed with no issues in 121 source files.
- Universe CLI smoke returned `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, and accepted `BTC/USDT` plus `ETH/USDT` on mock data.
- Exit optimizer CLI smoke returned `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, and ranked triple-barrier candidates for `trend-breakout`.
