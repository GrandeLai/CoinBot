# Open-Source Crypto Quant Profit Logic Research

Date: 2026-05-16

This report studies current open-source crypto quant/trading platforms and maps their profit logic into CoinBot-compatible feature candidates. It is a research and design input, not an investment guarantee. All proposed capabilities must keep CoinBot's existing defaults: mock/paper first, OKX Demo only after gates, live trading disabled by default, and no autonomous live dispatch unless a separate explicitly approved live gate is implemented and tested.

## Executive Summary

CoinBot already has a good first layer: arbitrage scanners, OKX demo validation, directional spot strategies, validation reports, PnL attribution, operator brief, and detached autopilot. The next profit-oriented expansion should not be "more signals" first. The open-source platforms show that durable crypto bot edge usually comes from combining:

1. Better opportunity selection: dynamic universe, regime filters, pair filters, and route quality.
2. Better exits and order lifecycle: triple-barrier exits, trailing protection, refresh/cancel logic, and execution state machines.
3. More realistic validation: orderbook-aware backtests, walk-forward optimization, bias checks, and paper/demo evidence.
4. New bounded strategy families: grid/range trading, market making, cross-exchange market making, and smart DCA.
5. Agent discipline: LLMs may help rank, explain, and research, but deterministic services must own risk, sizing, order state, and execution.

Recommended implementation order:

1. Dynamic universe + regime router.
2. Triple-barrier position executor and exit optimizer.
3. Realistic backtest/walk-forward validator.
4. Range-grid paper strategy.
5. Hedged maker / XEMM simulator.
6. ML/LLM advisory ranker after deterministic evidence exists.

## Sources Reviewed

Primary source links:

- Hummingbot Strategy V2 architecture, controllers, executors, arbitrage, XEMM, grid, PMM, and dashboard controller docs:
  - https://hummingbot.org/strategies/v2-strategies/
  - https://hummingbot.org/strategies/v2-strategies/controllers/
  - https://hummingbot.org/strategies/v2-strategies/executors/
  - https://hummingbot.org/strategies/v2-strategies/executors/arbitrage-executor/
  - https://hummingbot.org/strategies/v2-strategies/executors/xemm-executor/
  - https://hummingbot.org/strategies/v2-strategies/executors/gridexecutor/
  - https://hummingbot.org/strategies/v1-strategies/pure-market-making/
  - https://hummingbot.org/dashboard/config/
- Hummingbot Condor / Trading Agents:
  - https://condor.hummingbot.org/trading-agents/overview
  - https://condor.hummingbot.org/api-reference/architecture
  - https://condor.hummingbot.org/executors/position-executor
- Freqtrade docs:
  - https://docs.freqtrade.io/en/2026.3/configuration/
  - https://docs.freqtrade.io/en/2026.3/hyperopt/
  - https://docs.freqtrade.io/en/2026.1/plugins/
  - https://docs.freqtrade.io/en/2026.3/freqai-running/
  - https://docs.freqtrade.io/en/stable/lookahead-analysis/
  - https://docs.freqtrade.io/en/stable/stoploss/
- Jesse docs:
  - https://docs.jesse.trade/
- NautilusTrader docs:
  - https://nautilustrader.io/docs/latest/concepts/overview/
  - https://nautilustrader.io/docs/latest/concepts/backtesting/
  - https://nautilustrader.io/docs/latest/concepts/execution/
  - https://nautilustrader.io/docs/latest/concepts/live/
- OctoBot:
  - https://github.com/drakkar-software/octobot
- Superalgos:
  - https://superalgos.org/suite-systematic-trading.shtml
  - https://superalgos.org/faqs-crypto-trading-bots-open-source-crypto-trading-bots-strategies.shtml
- TradingAgents:
  - https://github.com/tauricresearch/tradingagents
  - https://arxiv.org/abs/2412.20138
- CCXT:
  - https://github.com/ccxt/ccxt/wiki/manual

## Platform Patterns And Profit Logic

### Hummingbot

Core profit logic:

- Pure market making: place passive bid/ask quotes around mid price, refresh stale quotes, and capture spread when both sides fill over time.
- Cross-exchange market making: quote on a less liquid maker venue, then hedge fills on a more liquid taker venue.
- Arbitrage executor: buy and sell equivalent assets across venues/markets when post-cost profitability exceeds threshold.
- Grid executor: create multiple price levels in a range and harvest oscillations with per-level take profits.
- Position executor: enter a directional position and close by take profit, stop loss, trailing stop, or time limit.
- LP executor: deploy and rebalance concentrated liquidity positions on CLMM DEXs.

Design lessons for CoinBot:

- Separate long-running strategy/controllers from finite execution workflows.
- Make execution workflows stateful and self-contained: created, active, closing, closed/failed.
- Keep order management out of signal generation.
- Add maker-quote refresh, cancellation, and profitability recheck before any quote remains live.
- Add performance reports at controller/executor level, not only strategy level.

CoinBot fit:

- High fit: triple-barrier executor, grid executor, XEMM simulator, maker quote planner.
- Medium fit: CLMM LP, because CoinBot has no DEX gateway yet.
- Safety note: market making can lose money through inventory drift and adverse selection; it must start in paper/demo with strict inventory and stale-quote controls.

### Freqtrade

Core profit logic:

- Indicator-based entry/exit strategies across many pairs.
- Minimal ROI tables, stoploss, trailing stop, custom stoploss, position adjustment, max open trades, and stake sizing.
- Hyperopt searches entry, exit, ROI, stoploss, trailing, trade count, and protection parameters.
- Protections lock pairs or the whole bot after stoploss streaks, drawdown, low-profit pairs, or cooldown windows.
- Pairlists filter the trading universe by volume, delisting risk, age, precision, price, spread, range stability, volatility, shuffle, and remote lists.
- FreqAI adds periodic retraining, model expiration, prediction persistence, and historical/live prediction reuse.
- Lookahead analysis detects biased strategies that accidentally inspect future data.

Design lessons for CoinBot:

- Add explicit pair/universe filters before strategy scoring.
- Optimize exits and protections separately from entries.
- Persist optimization results as proposals, not automatic config edits.
- Add bias checks for strategy candidates.
- Treat ML as a ranking/veto layer until it has forward evidence.

CoinBot fit:

- High fit: dynamic universe filters, protection matrix, walk-forward hyperopt for exit parameters, lookahead-style checks.
- Medium fit: FreqAI-like retraining; useful after deterministic feature store and validation are stronger.

### NautilusTrader

Core profit logic:

- It is less a strategy catalog and more an execution/backtest realism engine.
- Uses the same strategy/execution components across backtest, sandbox, and live contexts.
- Backtesting supports L1/L2/L3 order book data, trade ticks, bars, execution sequencing, latency models, fill models, and immutable historical data.
- Execution has a RiskEngine on submit/modify paths and live reconciliation against venue state.

Design lessons for CoinBot:

- Improve validation realism before adding fragile high-frequency features.
- A strategy should be tested against the same order lifecycle semantics it will use in paper/demo.
- Add orderbook depth simulation, latency, partial fills, duplicate-fill protection, and reconciliation evidence.

CoinBot fit:

- High fit: realistic backtest engine for existing arbitrage/directional strategies.
- High fit: event journal as a single source of truth for fills, positions, and PnL.
- Medium fit: full event-driven rewrite; unnecessary before targeted execution simulation.

### Jesse

Core profit logic:

- Multi-timeframe, multi-symbol directional strategies with no lookahead bias.
- Smart order support for market, limit, and stop orders.
- Built-in risk helpers, metrics, debug, optimize, leveraged and short-selling support, partial fills, alerts, and generated charts.

Design lessons for CoinBot:

- CoinBot should improve multi-timeframe strategy inputs and per-trade debug evidence.
- Partial fills and multi-order entries/exits matter even in paper/demo.
- Leverage/shorting should remain deferred unless risk/execution coverage is much stronger.

CoinBot fit:

- High fit: multi-timeframe directional signals and debug traces.
- Medium fit: partial fill simulation.
- Low immediate fit: leverage and shorting.

### OctoBot

Core profit logic:

- Built-in grid, DCA, crypto baskets, TradingView automation, technical indicators, AI connectors, and paper/live progression.
- Grid extracts value from volatility by maintaining many buy/sell levels.
- DCA reduces average entry cost during local drops and is optimized/backtested.
- AI/TradingView features automate external signals but still route through bot execution.

Design lessons for CoinBot:

- Grid and DCA are expected user-facing profit modes in crypto bots.
- External signals should enter through a signed/validated signal ingestion path, not direct order dispatch.
- UI/mobile is not CoinBot's immediate priority; CLI JSON and reports matter more.

CoinBot fit:

- High fit: range-grid paper strategy.
- Medium fit: smart DCA for BTC/ETH/SOL accumulation with strict exposure caps.
- Medium fit: external signal ingestion as read-only/paper first.

### Superalgos

Core profit logic:

- Strategy protocol with Trigger, Open, Manage, and Close stages.
- Users define conditions and formulas, then backtest, paper-trade, forward-test, and finally live trade.
- Strong emphasis on visual simulation, datasets, slippage/fee assumptions, and overfitting warnings.

Design lessons for CoinBot:

- CoinBot strategies should expose explicit stages instead of opaque "signal -> order".
- Every strategy should show trigger/open/manage/close evidence in JSON.
- Forward testing with tiny capital/demo should remain a separate evidence layer.

CoinBot fit:

- High fit: standard strategy lifecycle schema for all strategy families.
- Medium fit: visual charts; current repo can defer unless frontend becomes priority.

### TradingAgents And Condor

Core profit logic:

- TradingAgents uses specialized LLM roles for technical, sentiment, news, fundamental, bull/bear research, trader, and risk management.
- Condor separates LLM reasoning from deterministic Hummingbot executors. The agent runs on ticks and uses executors as its hands; risk limits remain deterministic.

Design lessons for CoinBot:

- LLMs should not directly place orders. They should produce explainable recommendations, strategy rankings, and post-trade analysis.
- File-backed state, tick journals, and session continuity are important for autonomous systems.
- Every agent action should be tagged by strategy/operator/session for auditability.

CoinBot fit:

- High fit: LLM/agent advisory layer over existing `operator-brief`, `validation-report`, and `autopilot`.
- Low fit: direct LLM-driven order placement.

### CCXT

Core value:

- Unified exchange API across many crypto venues.
- Useful for market-data breadth and cross-exchange opportunity discovery.

Design lessons for CoinBot:

- Use CCXT mainly for read-only data first.
- Direct exchange adapters remain better for high-reliability order execution.
- Any CCXT trading adapter must go behind the existing exchange interface, credential gates, and demo/paper validation.

CoinBot fit:

- High fit: expand read-only market universe to Binance/Bybit/Gate-style venues for signal density.
- Medium fit: paper-trading simulation from CCXT market data.
- Low immediate fit: CCXT live order dispatch.

## CoinBot Current Capability Map

Already present:

- Arbitrage: cross-exchange, triangular multi-route, funding carry, spot-perp carry, futures-perp basis.
- Directional: trend breakout, mean reversion spot, volatility squeeze breakout, momentum rotation, orderbook imbalance scalp.
- Execution safety: dry-run/paper defaults, OKX demo separation, agent live gates, runtime guard, demo preflight, PnL reconciliation, residual inventory checks.
- Evidence: strategy journal, validation report, PnL attribution, operator brief, retrospective, evolution, opportunity density.
- Autonomy: detached `crypto-assistant autopilot run|status|report` for paper/demo loops.

Important gaps:

- No maker-style quote placement model.
- No range-grid strategy.
- No dynamic universe/pair filtering comparable to Freqtrade pairlists.
- Backtest engine is still a deterministic placeholder and does not simulate real fills.
- Directional exits are strategy-local; there is no reusable triple-barrier executor.
- No walk-forward/hyperopt layer for exits, protections, and regime filters.
- No ML/LLM advisory ranker integrated into strategy selection.
- DEX/CLMM/LP profit sources are out of scope for current exchange adapters.

## Recommended Feature Candidates

### 1. Dynamic Universe And Regime Router

Goal: increase opportunity density while avoiding bad markets.

Profit logic:

- More tradable symbols/routes increase the chance of finding real edges.
- Filters prevent wasting cycles on high-spread, low-liquidity, newly listed, delisting-risk, or unstable symbols.
- Regime routing sends range markets to grid/mean-reversion, trending markets to breakout/momentum, and high-funding regimes to carry/basis.

New components:

- `market_universe` service that scores symbols by volume, spread, depth, volatility, range stability, listing age when available, and excluded symbols.
- `regime_router` service that maps each symbol to `range`, `trend`, `carry`, `illiquid`, or `avoid`.
- CLI:
  - `crypto-assistant strategy universe --config ... --exchange okx --json`
  - `crypto-assistant strategy regime-report --config ... --symbol BTC/USDT --json`

Safety:

- Read-only first.
- No orders.
- Feed outputs into existing strategy scorecards only after tests.

Priority: P0.

### 2. Triple-Barrier Position Executor And Exit Optimizer

Goal: improve realized PnL by standardizing exits.

Profit logic:

- Entries are only half the system; exits determine whether small edge survives fees.
- Use take-profit, stop-loss, trailing stop, and time-limit barriers.
- Optimize barrier parameters per strategy/regime using paper/backtest evidence.

New components:

- `strategies/position_executor.py` with deterministic state transitions.
- `strategies/exit_optimizer.py` producing parameter proposals for TP/SL/trailing/time limit.
- Add lifecycle evidence to directional demo/paper events.

CLI:

- `crypto-assistant strategy exit-optimize --strategy trend-breakout --symbol BTC/USDT --json`
- `crypto-assistant strategy position-report --execution-mode paper --json`

Safety:

- No live support.
- Demo closes only existing managed demo positions.
- Parameter proposals are advisory until explicitly staged in config.

Priority: P0.

### 3. Realistic Backtest And Walk-Forward Validation

Goal: prevent fake profitability.

Profit logic:

- Strategies that survive fees, slippage, latency, partial fills, and out-of-sample windows are more likely to remain profitable in paper/demo.

New components:

- Replace placeholder `BacktestEngine` with candle/orderbook-driven simulation.
- Add split windows: train/optimize -> validate -> forward/paper evidence.
- Add lookahead and recursive indicator checks for directional candidates.
- Store backtest events in the same schema family as strategy journal events.

CLI:

- `crypto-assistant backtest run --strategy all --symbol BTC/USDT --timerange ... --json`
- `crypto-assistant backtest walk-forward --strategy directional-all --json`
- `crypto-assistant backtest bias-check --strategy trend-breakout --json`

Safety:

- No orders.
- Any optimized candidate goes through paper validation before demo.

Priority: P0.

### 4. Range Grid Strategy

Goal: add a volatility-harvesting strategy for range-bound markets.

Profit logic:

- Place a ladder of buy/sell levels within a range.
- Profit comes from buying lower levels and selling higher levels repeatedly.
- The edge depends on fees, spread, volatility, and not getting trapped in a one-way trend.

New components:

- `strategies/grid.py` or `arbitrage/range_grid.py` scanner/controller.
- Grid level state store: inactive, open placed, open filled, close placed, complete.
- Regime gate: only enable when range stability and volatility filters pass.
- Capital allocator: total grid quote amount, per-level amount, max inventory, activation bounds.

CLI:

- `crypto-assistant strategy scan --strategy range-grid --symbol BTC/USDT --json`
- `crypto-assistant strategy run --strategy range-grid --execution-mode paper --json`

Safety:

- Paper only first.
- Demo deferred until at least N paper samples and drawdown below threshold.
- Auto-stop on trend breakout, inventory cap, or fee-adjusted expectancy below zero.

Priority: P1.

### 5. Hedged Maker / XEMM Simulator

Goal: evolve from taker-only arbitrage scans to maker spread capture.

Profit logic:

- Quote passively on one market at a price that is profitable versus a hedge market.
- When maker quote fills, immediately hedge on the more liquid venue.
- Captures maker spread/rebate while reducing directional exposure.

New components:

- `strategies/hedged_maker.py` quote planner.
- Maker quote refresh/cancel logic.
- Hedge preview against taker orderbook.
- Inventory skew and stale quote guard.
- Paper fill simulator first.

CLI:

- `crypto-assistant strategy scan --strategy hedged-maker --symbol BTC/USDT --json`
- `crypto-assistant strategy run --strategy hedged-maker --execution-mode paper --json`

Safety:

- Paper only until there is an implemented non-mock second venue and demo/live parity tests.
- Requires own-order tracking before any real maker order.
- Quote cancels if hedge profitability disappears.

Priority: P1.

### 6. Smart DCA / Basket Rebalancer

Goal: provide lower-frequency accumulation/rebalancing mode for major crypto assets.

Profit logic:

- DCA buys more during local drops, reducing average entry cost.
- Basket rebalancing harvests relative moves by trimming overweight assets and adding underweight assets.
- This is more portfolio-management than pure alpha.

New components:

- `strategies/smart_dca.py`
- BTC/ETH/SOL allowlist by default.
- Drawdown-tiered buys, cooldowns, max exposure, rebalance bands.

Safety:

- Paper first.
- No leverage.
- No meme/illiquid assets by default.

Priority: P2.

### 7. ML/LLM Advisory Ranker

Goal: use AI/ML to prioritize strategies without delegating execution.

Profit logic:

- ML ranks probability of next-period favorable movement or strategy success.
- LLM explains context, summarizes evidence, detects regime/news conflicts, and proposes watchlist changes.
- Deterministic gates decide whether orders are allowed.

New components:

- `features` service for candles, orderbook features, funding, basis, volatility, route density, journal-derived performance.
- `strategy_ranker` that consumes deterministic features and optionally model predictions.
- `agent_advisor` that reads operator brief, validation report, and ranker output, returning a no-order recommendation.

Safety:

- Advisory only.
- Model age/expiry required.
- Predictions and final outcomes logged.
- No LLM direct order tool.

Priority: P2.

### 8. CLMM/DEX Liquidity Provision

Goal: explore DEX fee income and LP rebalancing.

Profit logic:

- Earn LP fees inside a chosen price range.
- Rebalance when out of range.
- Major risk is impermanent loss, gas/RPC failures, MEV, and wallet security.

CoinBot fit:

- Deferred. CoinBot currently has CEX/OKX-oriented adapters and safety gates.
- Revisit only after a DEX gateway, wallet policy, gas model, and testnet validation exist.

Priority: Deferred.

## Recommended Architecture Direction

Do not turn CoinBot into a monolithic "profit bot". Add an evidence-driven strategy pipeline:

```text
Market data
  -> Universe filters
  -> Regime router
  -> Strategy scanners/controllers
  -> Strategy scorecards
  -> Deterministic executor planner
  -> Paper/demo execution
  -> Journal + validation + attribution
  -> Optimizer/advisor proposals
  -> Operator approval / config staging
```

The main architectural pattern to borrow from Hummingbot is `controller -> executor`, but implement it in CoinBot's lighter CLI/service style:

- Controller: decides whether a strategy has an opportunity.
- Executor: owns a finite order/position lifecycle.
- Guard: can deny or cool down.
- Journal: records every state transition.
- Optimizer/advisor: proposes, never silently mutates live behavior.

## Traceability Additions

Suggested future requirements:

- R074 Dynamic Universe And Regime Router.
- R075 Triple-Barrier Position Executor And Exit Optimizer.
- R076 Realistic Backtest And Walk-Forward Validation.
- R077 Range Grid Strategy.
- R078 Hedged Maker / XEMM Paper Simulator.
- R079 Smart DCA / Basket Rebalancer.
- R080 ML/LLM Advisory Ranker.

## Acceptance Criteria For Any Profit Feature

Every new profit feature must include:

- `--help` and `--json` CLI coverage.
- Unit tests for calculations and edge cases.
- Integration test for CLI JSON.
- Decimal-based money, price, and yield calculations.
- No real orders by default.
- Paper first, OKX Demo second only when applicable.
- Journal records with expected PnL, realized PnL, fees, slippage, drawdown, and reason codes.
- Validation report integration.
- Runtime guard integration.
- Traceability matrix and acceptance checklist updates.
- Explicit `Deferred` status for live trading if broker adapters or parity tests are missing.

## Immediate Recommendation

Build the next milestone around `Dynamic Universe + Regime Router + Triple-Barrier Executor`.

Reason:

- It improves the profitability of all existing strategies rather than adding one isolated bot mode.
- It is safer than starting with market making or grid because it is read-only/paper-first.
- It uses CoinBot's current strengths: strategy registry, scorecards, journal, validation report, operator brief, and autopilot.
- It creates the foundation needed for grid, XEMM, DCA, and ML ranking.
