# CoinBot Design

## 1. Scope

CoinBot is a crypto-only monorepo extracted from QuantPilot. It owns OKX trading, crypto market data, funding/open-interest/basis/ETF-flow analytics, crypto investment assistant cards, whale flow monitoring, token unlock calendars, crypto research summaries, and Rust quant-core computation.

QuantPilot keeps stock, ETF, A-share, Hong Kong equity, and non-crypto workbench surfaces.

## 2. Services

- `backend`: FastAPI service at `127.0.0.1:8001`.
- `backend/src/trading_assistant`: local CLI/service package for safe mock-first arbitrage workflows.
- `quant-core`: Rust axum service at `127.0.0.1:8002`.
- `frontend`: Vite app at `127.0.0.1:5173`.
- `common/python`: shared Python config, data models, DuckDB storage, and OKX fetcher.

## 3. Directory Contract

```text
backend/src/coinbot_api
backend/src/trading_assistant
common/python/coinbot_common
common/data-store/models
quant-core
frontend
docs
scripts
```

## 4. Public Interfaces

Python API:

- `GET /health`
- `GET /api/data/bars`
- `POST /api/data/fetch`
- `GET /api/data/universe`
- `GET /api/crypto/status`
- `GET /api/crypto/pairs`
- `GET /api/crypto/ticker`
- `GET /api/crypto/price/{symbol}`
- `GET /api/crypto/account`
- `GET /api/crypto/orders/*`
- `GET/POST /api/crypto/futures/*`
- `GET/POST /api/crypto/options/*`
- `POST /api/crypto-derivs/snapshot`
- `POST /api/crypto-derivs/funding-stats`
- `POST /api/crypto-derivs/etf-flow-stats`
- `GET /api/advisor/overview`
- `GET /api/advisor/crypto/opportunities`
- `GET /api/advisor/crypto/risks`
- `GET /api/crypto/research/latest`
- `POST /api/crypto/research/optimize`
- `GET /api/crypto/research/optimize/latest`
- `GET /api/crypto-whale/eth-inflow`
- `GET /api/crypto-whale/recent-transfers`
- `GET /api/token-unlocks/upcoming`

Rust API:

- `GET /healthz`
- `POST /api/backtest/run`
- `POST /api/walk-forward`
- `POST /api/optimize`
- `POST /api/indicators`

Local CLI:

- `crypto-assistant status`
- `crypto-assistant config validate`
- `crypto-assistant exchange list|ping`
- `crypto-assistant market ticker|orderbook`
- `crypto-assistant account balance`
- `crypto-assistant arbitrage scan|execute`
- `crypto-assistant agent live-readiness|execute-live|operation-catalog`
- `crypto-assistant autopilot run|status|report`
- `crypto-assistant strategy list|catalog|scan|discover-routes|opportunity-report|universe|regime-report|score|market-compare|portfolio-status|run|review|guard-status|retrospective|evolve|candidate-backtest|revival-window|validation-report|pnl-attribution|carry-basis-optimize|exit-optimize|position-report|validate-demo|validate-local|validate-demo-window|demo-window|demo-sampling|promotion-status`
- `crypto-assistant backtest run|walk-forward|bias-check`
- `crypto-assistant report generate`
- `crypto-assistant workflow run`

## 5. Configuration

All app-specific environment variables use the `COINBOT_` prefix. OKX credentials are:

- `COINBOT_OKX_API_KEY`
- `COINBOT_OKX_API_SECRET`
- `COINBOT_OKX_PASSPHRASE`
- `COINBOT_OKX_DEMO`

Trading safety defaults:

```yaml
trading:
  live_trading: false
  dry_run: true
  require_confirm_before_order: true
```

The local CLI defaults to mock exchange and paper/dry-run behavior. `crypto-assistant workflow run` connects mock market data, arbitrage scanning, backtesting, paper trading, sandbox readiness, live readiness gate checks, agent live-readiness gate checks, and reporting. Sandbox readiness checks execution quality, including spread persistence, depth-weighted fills, fee tiers, transfer/delay cost, and latency drift. Real trading must remain disabled unless `trading.live_trading=true`, `trading.dry_run=false`, credentials are loaded from environment variables, the exchange is non-mock and enabled, and risk checks pass.

The detached autopilot runtime is exposed through `crypto-assistant autopilot run|status|report`. It wraps existing paper and OKX Demo Trading paths so an external process manager can run bounded or continuous paper/demo cycles without Codex. It persists state under `strategy_runtime.autopilot_state_path`, produces read-only status/report payloads, and stops immediately if any paper/demo payload reports `live_orders_sent=true`. It never calls `agent execute-live` or a live broker.

Autonomous agent live trading has an additional gate under `agent_trading`. Defaults are `agent_trading.enabled=false`, `agent_trading.allow_live_orders=false`, an empty strategy allowlist, an empty exchange allowlist, zero autonomous orders per day, and audit logging configured. Agent live readiness requires all generic live-trading gates plus an allowlisted strategy, non-mock allowed exchanges, environment credentials, a populated operator id, execution-quality approval, audit logging, daily/order-size caps, and `COINBOT_AGENT_LIVE_KILL_SWITCH` not enabled. `crypto-assistant agent live-readiness` and `crypto-assistant agent execute-live` accept either `--opportunity-id` or `--opportunity-file` so an external scanner can pass an OKX spot opportunity JSON into the guarded execution path. `crypto-assistant agent execute-live` is wired to the OKX spot broker adapter for already-approved OKX spot limit-order opportunities. Unsupported exchanges and perp legs remain blocked until their broker adapters and sandbox tests are added.

The OKX exchange adapter maps OKX ticker, orderbook, account balance, funding-rate, spot/perp quote, instrument metadata, swap ticker, and dated-futures basis payloads into the assistant's Decimal-based exchange interface. It is only instantiated when an enabled exchange uses `adapter: okx`; default config keeps OKX disabled.

The exchange interface also exposes completed OHLCV candles through `get_candles`. The OKX adapter reads `/api/v5/market/candles` or `/api/v5/market/history-candles` and filters unfinished rows before they reach strategies. The CLI exposes this as `crypto-assistant market candles --config configs/okx.demo.example.yaml --exchange okx --symbol BTC/USDT --bar 15m --limit 300 --json`, so read-only diagnostics can explicitly use the separated OKX demo/live config profiles.

The optional CCXT exchange adapter maps CCXT ticker, orderbook, balance, funding-rate, instrument metadata, spot/perp quote, and futures-basis payloads into the same Decimal interface for Binance/Bybit-style market-data reads. It is only instantiated when an enabled exchange uses `adapter: ccxt`; the default config keeps `binance` and `bybit` disabled. CCXT order dispatch is not implemented.

OKX simulated trading and live trading are separated into `configs/okx.demo.example.yaml` and `configs/okx.live.example.yaml`. The demo file reads `../.env.okx.demo`, uses `sandbox=true`, `okx_demo=true`, `live_trading=false`, `dry_run=false`, and `agent_trading.allow_demo_orders=true`; this means order dispatch is allowed only to OKX Demo Trading after the demo gate, credential gate, operator gate, risk gate, execution-quality gate, and provider demo-mode check pass. The live file reads `../.env.okx.live`, uses `sandbox=false`, `okx_demo=false`, `live_trading=true`, and `dry_run=false`, while keeping `agent_trading.allow_live_orders=false` by default. OKX demo validation uses `crypto-assistant exchange sandbox-check --config configs/okx.demo.example.yaml --exchange okx --symbol BTC/USDT --json`. The command performs non-order public checks by default, optional private account reads with `--include-private`, and always reports `live_orders_sent=false`.

Strategy-level OKX demo validation uses `crypto-assistant strategy validate-demo --config configs/okx.demo.example.yaml --strategy all --json`. It submits tiny OKX Demo Trading orders, cancels them, and confirms no open order remains. The optional `--allow-account-mode-switch` flag is limited to OKX Demo Trading and may switch the demo account from spot mode to futures mode for swap-based strategy validation after confirming no open orders or swap positions exist. If OKX requires the first account-mode setup in Web/App, the CLI reports the blocker and does not bypass it.

The operation validation hub is exposed through `crypto-assistant agent operation-catalog --json`. It is the middle-platform contract for demo/live parity: every registered live-capable operation must declare a demo config and demo command. The current catalog covers OKX sandbox checks and guarded OKX spot limit-order dispatch. Production use must validate the demo command first and keep demo credentials in `.env.okx.demo`, separate from `.env.okx.live`.

The strategy platform is exposed through `crypto-assistant strategy catalog|scan|discover-routes|opportunity-report|score|portfolio-status`. It registers OKX-first market-neutral strategies: `triangular-multi-route`, `spot-perp-carry`, `funding-carry-hedged`, `futures-perp-basis`, plus retained `cross-exchange`, and the paper-only `range-grid` and `hedged-maker` strategies. Legacy names `triangular`, `spot-perp`, and `funding-rate` remain compatibility aliases. Strategy controllers generate opportunities only; they do not place orders. Cross-exchange scanning now evaluates directed pairs across enabled exchanges while preserving the default mock/mock_alt path. `strategy discover-routes` reads spot instrument metadata, keeps configured triangular routes as priority routes, expands the route universe with default major assets and volume-ranked assets when bulk tickers are available, and reports accepted plus filtered routes with missing-symbol, depth, min-size, and tick-size reasons. `strategy scan --strategy triangular-multi-route --route-mode discovered` scans only accepted routes and still remains read-only. Scorecards combine net edge, depth/slippage/risk score, historical paper/demo samples, free-balance/sell-leg restrictions, and repeated OKX demo preflight pressure from the retrospective state. The portfolio service then applies maximum concurrency, score floors, and capital caps before runtime execution.

The strategy evolution layer is exposed through `crypto-assistant strategy evolve`. It is a simulation-only survival system over paper/demo journal evidence. Each strategy gets a status such as `active`, `watchlist`, `archived`, or `revive_candidate`; `strategy run`, `strategy validate-local`, and `strategy validate-demo-window` refresh this state after execution. Archive is soft state in `strategy_runtime.evolution_state_path`, not code deletion. Scorecards and portfolio selection read that state and block `strategy_archived_by_evolution`, while later profitable paper/demo samples can move an archived strategy to `revive_candidate`. Evolution summaries derive market-regime tags from completed candle features and then emit advisory parameter candidates; candidates are isolated simulation plans, not automatic config edits. `crypto-assistant strategy candidate-backtest` materializes those parameter candidates in temporary config copies, compares baseline versus candidate metrics, isolates runtime paths, and reports `orders_sent=false` plus `live_orders_sent=false`. The evolution report is written under `docs/plan/2026-05-09-refactor/45-strategy-evolution.md`. `crypto-assistant strategy revival-window` is the return path for archived strategies: it reads only current `revive_candidate` entries, runs local validation first, and attempts an OKX demo validation window only for those strategies after the OKX demo safety gate passes.

The strategy registry now separates `arbitrage`, `directional`, and `all` groups. `directional-all` runs OKX-first long-only spot strategies without mixing them into arbitrage review: `trend-breakout`, `mean-reversion-spot`, `volatility-squeeze-breakout`, `momentum-rotation`, and `orderbook-imbalance-scalp`. Directional signals contain action, confidence, expected edge, stop loss, take profit, time limit, and reason codes. The directional scanner wraps approved `buy` signals as opportunities so existing risk, budget, paper execution, journal, validation report, and retrospective services continue to apply. `orderbook-imbalance-scalp` is deliberately demo-disabled; the other directional strategies can run tiny OKX demo managed spot positions only after local validation passes. Demo directionals are long-only: first approved run opens a persisted managed spot position, later runs hold it or exit by take-profit, stop-loss, explicit `sell` reverse-signal, or time-limit trigger. A failed local buy gate can only reach demo execution when its context contains an explicit directional exit signal and the no-order preflight confirms a managed close; this path cannot open fresh inventory. Losing managed exits include `managed_exit_audit` evidence so the runtime guard can count the negative execution and apply cooldowns. Directional live trading is not supported.

Carry and basis scanners expose offline diagnostics through `strategy scan --json`. `spot-perp-carry`, `funding-carry-hedged`, and `futures-perp-basis` report candidate net PnL, configured minimum PnL, break-even gap, depth sufficiency, fee/slippage/holding/funding/basis components, and filtering reasons even when no opportunity is emitted. Strategy scorecards copy these into diagnostic reasons, letting agents optimize thresholds and market filters without sending OKX demo orders.

Carry and basis scanners also enforce configurable quality gates under `arbitrage`: minimum funding annualized percentage, maximum basis hedge cost percentage, minimum spot-perp basis percentage, and minimum futures-perp basis percentage. The gates are part of scan diagnostics and keep weak carry/basis candidates in local/paper optimization until the economics are strong enough to justify an OKX demo preflight.

The carry/basis offline optimizer is exposed through `crypto-assistant strategy carry-basis-optimize`. It is read-only and reuses scan diagnostics for `funding-carry-hedged`, `spot-perp-carry`, and `futures-perp-basis` to summarize observed net PnL, required minimum PnL, break-even gap, fee/slippage/holding/basis-hedge costs, observed basis and funding percentages, suggested config fields, and conservative next actions. It reports `orders_sent=false`, `live_orders_sent=false`, and never edits configs; positive break-even gaps keep the strategy in local optimization rather than OKX demo execution.

The read-only market comparison layer is exposed through `crypto-assistant strategy market-compare`. It scans a mock baseline and a configured target exchange such as OKX, returns per-strategy opportunity counts, best net PnL, diagnostics, delta versus baseline, and a verdict for the next stage. It forces scan-only safety context, does not write the journal or retrospective, and reports `orders_sent=false`; it is intended to sit between local mock validation and any OKX demo preflight.

The opportunity-density layer is exposed through `crypto-assistant strategy opportunity-report`. It is read-only and journal-only: it aggregates scan count, opportunity count, demo preflight candidate count, pass rate, skipped reasons, average expected edge, realized PnL, expected-vs-actual gap, account-equity delta, route/symbol distribution, candidate observation pool, and demo size-stage readiness. This separates "did the system discover viable candidates?" from "did the last executed strategy make money?" and prevents paper/mock wins from being treated as OKX-tradable evidence.

The dynamic universe and regime layer is exposed through `crypto-assistant strategy universe` and `crypto-assistant strategy regime-report`. It is read-only and filters configured symbols by spread, 24h quote volume, orderbook depth, and completed-candle behavior, then classifies each accepted symbol as `trend`, `range`, or `carry`; rejected symbols are classified as `illiquid` or `avoid` with reason codes. It reports `orders_sent=false` and `live_orders_sent=false` and is intended to improve opportunity density and strategy routing before any paper/demo execution.

The range-grid paper strategy is exposed through `crypto-assistant strategy scan --strategy range-grid` and `crypto-assistant strategy run --strategy range-grid --execution-mode paper`. It uses the regime layer as an entry gate, accepts only `range` symbols, builds an evenly spaced ladder from completed-candle high/low bounds, estimates completed round-trip grid cycles after fees and slippage, and emits a normal `ArbitrageOpportunity` with `read_only=true`, `paper_only=true`, and simulated buy/sell legs. It is registered with `demo_supported=false` and `live_supported=false`; OKX Demo grid orders require a separate stateful order manager and sandbox validation before any exchange dispatch can be added.

The hedged-maker paper strategy is exposed through `crypto-assistant strategy scan --strategy hedged-maker` and `crypto-assistant strategy run --strategy hedged-maker --execution-mode paper`. It estimates passive maker quotes against an immediate taker hedge on a separate configured exchange, checks maker inventory and hedge depth, subtracts maker/taker fees plus hedge slippage, and emits simulated maker quote plus taker hedge legs. It reports `read_only=true` and `paper_only=true`, and is registered with `demo_supported=false` and `live_supported=false`; real maker orders require own-order tracking, stale quote cancel/refresh, adverse-selection controls, and sandbox parity tests before exchange dispatch can be added.

The backtest validation layer is exposed through `crypto-assistant backtest run|walk-forward|bias-check`. It is read-only, uses completed exchange candles, applies Decimal fee and slippage assumptions, and reuses the long-only directional backtest engine for strategy candidates. `backtest run` reports the fill model and a fee/slippage-adjusted result, `backtest walk-forward` runs expanding train windows plus forward validation windows, and `backtest bias-check` verifies completed-candle input, warmup enforcement, and deterministic prefix replay. These commands report `orders_sent=false` and `live_orders_sent=false`; they do not optimize checked-in config or enable paper/demo/live trading.

The production strategy runtime is exposed through `crypto-assistant strategy list|run|review|guard-status`. It runs scan -> select -> risk -> position budget -> order lifecycle plan -> paper execution -> journal. Runtime controls live under `strategy_runtime` and include per-position capital caps, per-strategy capital caps, max open orders, order TTL, reprice threshold, demo max order value, demo order-size multiplier, optional per-strategy demo size overrides, demo limit-price marketability buffer, demo wait/poll settings, demo preflight thresholds, adaptive expected-vs-actual preflight buffering, demo stop-loss/drawdown breakers, PnL reconciliation tolerance, residual-inventory tolerance, a stateful runtime guard, and an append-only JSONL journal. The runtime guard persists consecutive blocked runs, negative executions, market-data failures, and exchange rate-limit failures to `strategy_runtime.runtime_guard_path`; when `max_consecutive_execution_failures`, `max_consecutive_losses`, `max_consecutive_market_data_failures`, or `max_consecutive_rate_limit_failures` is reached, future cycles for that strategy/mode are skipped until `failure_cooldown_seconds` expires. `strategy guard-status --json` exposes that state for Codex/Claude agents and operators. With `configs/okx.demo.example.yaml` and `--execution-mode demo`, the runtime bypasses live trading entirely, allows only demo-supported allowlisted execution paths, runs a no-order profitability preflight before any OKX Demo Trading order, prices spot demo limit submissions from orderbook best ask/bid plus `demo_limit_price_buffer_pct`, estimates preflight PnL from top-of-book expected fill prices, reports both submitted protection price and expected fill price, raises the effective preflight threshold when recent journal samples show expected PnL exceeding actual cash-flow PnL, sends tiny canary orders only when the effective preflight threshold passes, waits for fills, cancels if needed, records account snapshots, writes order cash-flow PnL plus account-equity delta reconciliation, reports non-USDT residual inventory, fetches OKX `fills-history` rows for exchange receipt completeness/fee checks, and stops longer loops when demo loss breakers trip. Per-strategy demo sizing overrides can set an order-size multiplier or lower effective max order value for a named strategy, and each preflight/execution reports the effective `sizing_policy`; global runtime, directional, and autonomous-agent caps still constrain the final order cap. Managed directional exits are treated as risk-reducing closes: take-profit, stop-loss, reverse-signal, and time-limit exits may proceed even when expected PnL is negative, but only after the preview reason is `directional_exit_*`; entry attempts still require the normal local and preflight gates. The adaptive buffer is read-only, capped, skipped for directional lifecycle previews, and recorded in `execution.preflight.adaptive_preflight_buffer`; it does not edit strategy parameters or enable live trading. Review is advisory: it can filter by `--execution-mode`, counts only executed events as realized PnL, and emits conservative learning suggestions without editing code, changing configs, or enabling live trading.

The strategy validation middle layer is exposed through `crypto-assistant strategy validate-local`, `crypto-assistant strategy validate-demo-window`, `crypto-assistant strategy demo-window`, `crypto-assistant strategy demo-sampling`, and `crypto-assistant strategy promotion-status`. Local validation runs bounded paper cycles. Demo-window validation runs bounded OKX Demo Trading cycles and requires demo evidence such as provider demo mode, no live orders, PnL reconciliation, residual inventory within tolerance, fill receipts, and no residual open orders or swap positions. If every requested strategy is already in runtime guard cooldown, demo-window validation fails fast before runner execution so it does not burn empty validation cycles or make avoidable post-run network calls. The `strategy demo-window` orchestration command wraps that execution path with no-order prechecks first: OKX sandbox health, runtime guard status, read-only market comparison, and rolling validation quality. The `strategy demo-sampling` scheduler repeats that orchestration for a bounded number of same-size windows, records the fixed demo size stage including per-strategy overrides, sleeps only after successful order-attempt windows, and stops immediately on precheck blocks, no-order windows, or any live-order signal. `strategy operator-brief` is the no-order operator snapshot that combines safety switches, size stage, runtime guard state, rolling validation evidence, and conservative recommendations before another demo or promotion step. If the local network or OKX market read fails, orchestration blocks before the strategy runner so the failure is reported as a health-gate issue rather than polluting strategy market-data failure counters. Promotion status reads paper/demo journal statistics plus runtime guard state and reports local, demo, and live-canary status. Live-canary promotion remains disabled by default through `strategy_runtime.validation_allow_live_canary=false` and still requires the generic trading and autonomous agent live gates.

The strategy retrospective layer is exposed through `crypto-assistant strategy retrospective`. It is deterministic and advisory: it reads the strategy journal plus runtime guard state, deduplicates issues by strategy/mode/category/reason, escalates repeated issues for operator attention, and rewrites `docs/plan/2026-05-09-refactor/28-strategy-retrospective.md` plus its state file under the same refactor directory. `strategy run`, `strategy validate-local`, and `strategy validate-demo-window` include `retrospective_before`, `retrospective_after`, and `retrospective_path` in JSON output, while `strategy review` includes a retrospective summary. Retrospective summaries also include `optimization_pressure`, converting repeated issues into observed net PnL, break-even gap, strategy-specific action, config fields to review, and hard guardrails. Repeated high-priority OKX demo `preflight_not_profitable` pressure is consumed by strategy scoring through `strategy_runtime.retrospective_demo_preflight_score_penalty`, so affected strategies can fall below the portfolio score floor until the issue improves. During journal refresh, older transient market-data, rate-limit, and preflight failures are treated as improved when a later profitable execution exists for the same strategy and mode; targeted updates only clear issues for observed strategy/mode pairs, so skipped strategies are not falsely marked improved. The retrospective system does not send orders, change strategy parameters, enable demo/live gates, or block OKX demo sampling by itself.

The rolling validation report is exposed through `crypto-assistant strategy validation-report`. It is read-only and summarizes recent strategy journal evidence by strategy: executed/skipped/blocked counts, realized executed PnL, skipped preflight PnL, approved preflight expected PnL, actual order cash-flow PnL, account-equity delta, account reconciliation gap, expected-vs-actual gap, win rate, drawdown, receipt completeness, PnL tolerance, residual inventory, missing executed preflight estimates, positive-cash-flow/negative-equity detections, reason counts, and conservative recommendations. It is intended to replace manual journal parsing before the next run/review/optimize cycle and does not access exchange APIs or mutate runtime state. Older executed demo entries without persisted preflight estimates are excluded from complete expected-vs-actual promotion evidence.

The operator brief is exposed through `crypto-assistant strategy operator-brief`. It is read-only and reports `orders_sent=false` plus `live_orders_sent=false`. It reads only config, runtime guard state, and the strategy journal, then returns safety switches, the current demo size stage, guard entries, rolling validation evidence, and recommendations such as collecting more demo samples, waiting for cooldown, or keeping live canary disabled.

The PnL attribution ledger is exposed through `crypto-assistant strategy pnl-attribution`. It is a read-only per-event view over the same strategy journal and reports `orders_sent=false` plus `live_orders_sent=false`. Each row separates preflight expected PnL, strategy order cash-flow PnL, account-equity delta, attribution gap, residual inventory, tolerance flags, and a classification such as account-equity matched, account-equity diverged, positive cash-flow with negative equity delta, or strategy cash-flow only. It is intended for demo accounts that may contain unrelated inventory, so strategy cash-flow is not confused with whole-account mark-to-market movement.

The triple-barrier exit optimizer is exposed through `crypto-assistant strategy exit-optimize` and `crypto-assistant strategy position-report`. It simulates long-only directional exits over completed candles using take-profit, stop-loss, trailing-stop, and time-limit barriers. It returns ranked parameter proposals and a best position simulation with `read_only=true`, `orders_sent=false`, and `live_orders_sent=false`; proposals do not mutate configs and must still pass paper/demo validation before any trading path can use them.

## 6. Market Universe

The first-class universe is crypto-only:

- `BTC-USDT`
- `ETH-USDT`
- `SOL-USDT`
- `XRP-USDT`
- `DOGE-USDT`
- `ADA-USDT`

Aliases such as `BTCUSDT`, `BTC/USDT`, and `BTC-USD` resolve to canonical OKX symbols.

## 7. Verification

```bash
cd backend && uv run pytest tests/ -v
cd backend && uv run ruff check src/ tests/
cd backend && uv run mypy src/
cd quant-core && cargo test
cd frontend && npm install && npm run build
```

Refactor traceability, phase reports, and final acceptance for the 2026-05-09 assistant refactor live under `docs/plan/2026-05-09-refactor/`.
