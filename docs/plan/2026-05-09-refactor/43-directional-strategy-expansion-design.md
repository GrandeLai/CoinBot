# OKX Spot Directional Strategy Expansion Design

Date: 2026-05-11

## Objective

The prior strategy set was dominated by pure arbitrage. In current OKX demo observations, only triangular arbitrage produced frequent enough positive opportunities. This design adds a controlled directional layer so the assistant can still produce explainable, testable spot opportunities when market-neutral arbitrage spreads are unavailable.

This does not promise profit. The acceptance target is more strategy coverage, no-lookahead local validation, transparent scoring, bounded OKX demo canaries, and no live-trading path.

## Scope

Included:

- OKX/mainstream spot symbols: `BTC/USDT`, `ETH/USDT`, `SOL/USDT`, `XRP/USDT`, `DOGE/USDT`, `ADA/USDT`.
- `market candles` CLI backed by exchange adapters.
- Lightweight indicators: EMA, RSI, ATR, Bollinger bands, Donchian channel, return, volatility, volume z-score.
- Directional signal model with `buy`, `sell`, and `hold`.
- Position lifecycle model: `planned`, `open_submitted`, `open`, `exit_submitted`, `closed`, `aborted`.
- Five directional strategies:
  - `trend-breakout`
  - `mean-reversion-spot`
  - `volatility-squeeze-breakout`
  - `momentum-rotation`
  - `orderbook-imbalance-scalp`
- `directional-all` aggregate in the strategy registry.
- Local/paper execution through the existing risk, budget, lifecycle, journal, review, and retrospective pipeline.
- OKX demo managed spot-position eligibility for the first four strategies only; `orderbook-imbalance-scalp` remains scan/backtest/paper only.
- Persistent demo position state for open/hold/exit lifecycle across CLI invocations.

Excluded:

- Live trading for directional strategies.
- Leverage, swaps, futures, grid, market making, and short selling.
- Automatic parameter mutation.

## Architecture

### Exchange Layer

`trading_assistant.exchanges.base.Exchange` now exposes:

```text
get_candles(symbol, bar="15m", limit=100, history=False)
```

Adapters:

- `MockExchange`: deterministic multi-symbol completed candle fixtures.
- `OKXExchange`: maps OKX `/api/v5/market/candles` and `/api/v5/market/history-candles` rows into `Candle`, filtering unfinished rows by `confirm`.
- `CCXTExchange`: maps `fetch_ohlcv` into `Candle` when supported.

### Directional Package

New package:

```text
backend/src/trading_assistant/directional/
```

Files:

- `models.py`: `DirectionalSignal`, `DirectionalPositionLifecycle`, `DirectionalBacktestResult`.
- `indicators.py`: Decimal-based indicators.
- `strategies.py`: signal generators.
- `backtest.py`: no-lookahead long-only backtest.
- `scanner.py`: converts approved `buy` signals into `ArbitrageOpportunity` objects so existing risk/execution services can remain unchanged.
- `position_store.py`: persists OKX demo managed spot positions, including entry price, quantity, stop-loss, take-profit, time limit, and close evidence.

### Strategy Registry

The registry now supports categories:

- `arbitrage`
- `directional`

Aggregates:

- `all`: all enabled strategies.
- `arbitrage-all`
- `directional-all`

The CLI continues to use the existing `strategy` command family.

### Safety

Directional strategies are long-only spot strategies. Demo execution:

- require OKX demo config;
- require local validation first;
- require risk and runtime guard approval;
- opens only one managed spot long per strategy/symbol;
- holds the position across invocations until take-profit, stop-loss, time-limit, or future reverse-signal exit conditions apply;
- persists state to `directional.position_state_path`;
- do not support live trading;
- do not route through `agent execute-live`;
- keep `orderbook-imbalance-scalp` demo-disabled.

Default live trading remains disabled.

## Risk Controls

Config defaults:

```yaml
directional:
  max_position_value_usdt: "250"
  total_max_exposure_usdt: "750"
  single_trade_risk_equity_pct: "0.20"
  daily_loss_pct: "0.50"
  min_profit_factor: "1.10"
  max_backtest_drawdown_pct: "5"
```

Actual paper order notional is still constrained by the existing `strategy_runtime` and `risk` caps. The default safe config therefore keeps paper/demo sizing inside the stricter currently configured caps.

## Validation Model

Each strategy scan requires:

- current `buy` signal;
- completed-candle-only data;
- backtest net PnL above threshold;
- profit factor >= configured minimum;
- max drawdown <= configured maximum;
- positive expected net profit after fee and slippage estimates.

The backtest enters only after signals derived from already completed prior candles, so the current candle is not used to decide its own entry.

## CLI Surface

New/extended commands:

```bash
crypto-assistant market candles --exchange okx --symbol BTC/USDT --bar 15m --limit 300 --json
crypto-assistant strategy catalog --json
crypto-assistant strategy scan --strategy directional-all --symbol BTC/USDT --json
crypto-assistant strategy score --strategy directional-all --json
crypto-assistant strategy run --strategy directional-all --execution-mode paper --json
crypto-assistant strategy run --strategy directional-all --execution-mode demo --json
crypto-assistant strategy validation-report --strategy directional-all --execution-mode demo --json
```

## Deferred Items

- Reverse-signal exits for managed directional demo positions are still a follow-up; the implemented first lifecycle exits by take-profit, stop-loss, and time limit.
- `orderbook-imbalance-scalp` is intentionally not demo-enabled until the slower directional strategies build enough validation evidence.
