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
- `crypto-assistant strategy list|catalog|scan|discover-routes|opportunity-report|score|market-compare|portfolio-status|run|review|guard-status|retrospective|evolve|candidate-backtest|revival-window|validation-report|validate-demo|validate-local|validate-demo-window|promotion-status`
- `crypto-assistant backtest run`
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

Autonomous agent live trading has an additional gate under `agent_trading`. Defaults are `agent_trading.enabled=false`, `agent_trading.allow_live_orders=false`, an empty strategy allowlist, an empty exchange allowlist, zero autonomous orders per day, and audit logging configured. Agent live readiness requires all generic live-trading gates plus an allowlisted strategy, non-mock allowed exchanges, environment credentials, a populated operator id, execution-quality approval, audit logging, daily/order-size caps, and `COINBOT_AGENT_LIVE_KILL_SWITCH` not enabled. `crypto-assistant agent live-readiness` and `crypto-assistant agent execute-live` accept either `--opportunity-id` or `--opportunity-file` so an external scanner can pass an OKX spot opportunity JSON into the guarded execution path. `crypto-assistant agent execute-live` is wired to the OKX spot broker adapter for already-approved OKX spot limit-order opportunities. Unsupported exchanges and perp legs remain blocked until their broker adapters and sandbox tests are added.

The OKX exchange adapter maps OKX ticker, orderbook, account balance, funding-rate, spot/perp quote, instrument metadata, swap ticker, and dated-futures basis payloads into the assistant's Decimal-based exchange interface. It is only instantiated when an enabled exchange uses `adapter: okx`; default config keeps OKX disabled.

The exchange interface also exposes completed OHLCV candles through `get_candles`. The OKX adapter reads `/api/v5/market/candles` or `/api/v5/market/history-candles` and filters unfinished rows before they reach strategies. The CLI exposes this as `crypto-assistant market candles --config configs/okx.demo.example.yaml --exchange okx --symbol BTC/USDT --bar 15m --limit 300 --json`, so read-only diagnostics can explicitly use the separated OKX demo/live config profiles.

The optional CCXT exchange adapter maps CCXT ticker, orderbook, balance, funding-rate, instrument metadata, spot/perp quote, and futures-basis payloads into the same Decimal interface for Binance/Bybit-style market-data reads. It is only instantiated when an enabled exchange uses `adapter: ccxt`; the default config keeps `binance` and `bybit` disabled. CCXT order dispatch is not implemented.

OKX simulated trading and live trading are separated into `configs/okx.demo.example.yaml` and `configs/okx.live.example.yaml`. The demo file reads `../.env.okx.demo`, uses `sandbox=true`, `okx_demo=true`, `live_trading=false`, `dry_run=false`, and `agent_trading.allow_demo_orders=true`; this means order dispatch is allowed only to OKX Demo Trading after the demo gate, credential gate, operator gate, risk gate, execution-quality gate, and provider demo-mode check pass. The live file reads `../.env.okx.live`, uses `sandbox=false`, `okx_demo=false`, `live_trading=true`, and `dry_run=false`, while keeping `agent_trading.allow_live_orders=false` by default. OKX demo validation uses `crypto-assistant exchange sandbox-check --config configs/okx.demo.example.yaml --exchange okx --symbol BTC/USDT --json`. The command performs non-order public checks by default, optional private account reads with `--include-private`, and always reports `live_orders_sent=false`.

Strategy-level OKX demo validation uses `crypto-assistant strategy validate-demo --config configs/okx.demo.example.yaml --strategy all --json`. It submits tiny OKX Demo Trading orders, cancels them, and confirms no open order remains. The optional `--allow-account-mode-switch` flag is limited to OKX Demo Trading and may switch the demo account from spot mode to futures mode for swap-based strategy validation after confirming no open orders or swap positions exist. If OKX requires the first account-mode setup in Web/App, the CLI reports the blocker and does not bypass it.

The operation validation hub is exposed through `crypto-assistant agent operation-catalog --json`. It is the middle-platform contract for demo/live parity: every registered live-capable operation must declare a demo config and demo command. The current catalog covers OKX sandbox checks and guarded OKX spot limit-order dispatch. Production use must validate the demo command first and keep demo credentials in `.env.okx.demo`, separate from `.env.okx.live`.

The strategy platform is exposed through `crypto-assistant strategy catalog|scan|discover-routes|opportunity-report|score|portfolio-status`. It registers OKX-first market-neutral strategies: `triangular-multi-route`, `spot-perp-carry`, `funding-carry-hedged`, `futures-perp-basis`, plus retained `cross-exchange`. Legacy names `triangular`, `spot-perp`, and `funding-rate` remain compatibility aliases. Strategy controllers generate opportunities only; they do not place orders. Cross-exchange scanning now evaluates directed pairs across enabled exchanges while preserving the default mock/mock_alt path. `strategy discover-routes` reads spot instrument metadata, keeps configured triangular routes as priority routes, expands the route universe with default major assets and volume-ranked assets when bulk tickers are available, and reports accepted plus filtered routes with missing-symbol, depth, min-size, and tick-size reasons. `strategy scan --strategy triangular-multi-route --route-mode discovered` scans only accepted routes and still remains read-only. Scorecards combine net edge, depth/slippage/risk score, historical paper/demo samples, free-balance/sell-leg restrictions, and repeated OKX demo preflight pressure from the retrospective state. The portfolio service then applies maximum concurrency, score floors, and capital caps before runtime execution.

The strategy evolution layer is exposed through `crypto-assistant strategy evolve`. It is a simulation-only survival system over paper/demo journal evidence. Each strategy gets a status such as `active`, `watchlist`, `archived`, or `revive_candidate`; `strategy run`, `strategy validate-local`, and `strategy validate-demo-window` refresh this state after execution. Archive is soft state in `strategy_runtime.evolution_state_path`, not code deletion. Scorecards and portfolio selection read that state and block `strategy_archived_by_evolution`, while later profitable paper/demo samples can move an archived strategy to `revive_candidate`. Evolution summaries derive market-regime tags from completed candle features and then emit advisory parameter candidates; candidates are isolated simulation plans, not automatic config edits. `crypto-assistant strategy candidate-backtest` materializes those parameter candidates in temporary config copies, compares baseline versus candidate metrics, isolates runtime paths, and reports `orders_sent=false` plus `live_orders_sent=false`. The evolution report is written under `docs/plan/2026-05-09-refactor/45-strategy-evolution.md`. `crypto-assistant strategy revival-window` is the return path for archived strategies: it reads only current `revive_candidate` entries, runs local validation first, and attempts an OKX demo validation window only for those strategies after the OKX demo safety gate passes.

The strategy registry now separates `arbitrage`, `directional`, and `all` groups. `directional-all` runs OKX-first long-only spot strategies without mixing them into arbitrage review: `trend-breakout`, `mean-reversion-spot`, `volatility-squeeze-breakout`, `momentum-rotation`, and `orderbook-imbalance-scalp`. Directional signals contain action, confidence, expected edge, stop loss, take profit, time limit, and reason codes. The directional scanner wraps approved `buy` signals as opportunities so existing risk, budget, paper execution, journal, validation report, and retrospective services continue to apply. `orderbook-imbalance-scalp` is deliberately demo-disabled; the other directional strategies can run tiny OKX demo managed spot positions only after local validation passes. Demo directionals are long-only: first approved run opens a persisted managed spot position, later runs hold it or exit by take-profit, stop-loss, or time-limit trigger. Directional live trading is not supported.

Carry and basis scanners expose offline diagnostics through `strategy scan --json`. `spot-perp-carry`, `funding-carry-hedged`, and `futures-perp-basis` report candidate net PnL, configured minimum PnL, break-even gap, depth sufficiency, fee/slippage/holding/funding/basis components, and filtering reasons even when no opportunity is emitted. Strategy scorecards copy these into diagnostic reasons, letting agents optimize thresholds and market filters without sending OKX demo orders.

Carry and basis scanners also enforce configurable quality gates under `arbitrage`: minimum funding annualized percentage, maximum basis hedge cost percentage, minimum spot-perp basis percentage, and minimum futures-perp basis percentage. The gates are part of scan diagnostics and keep weak carry/basis candidates in local/paper optimization until the economics are strong enough to justify an OKX demo preflight.

The read-only market comparison layer is exposed through `crypto-assistant strategy market-compare`. It scans a mock baseline and a configured target exchange such as OKX, returns per-strategy opportunity counts, best net PnL, diagnostics, delta versus baseline, and a verdict for the next stage. It forces scan-only safety context, does not write the journal or retrospective, and reports `orders_sent=false`; it is intended to sit between local mock validation and any OKX demo preflight.

The opportunity-density layer is exposed through `crypto-assistant strategy opportunity-report`. It is read-only and journal-only: it aggregates scan count, opportunity count, demo preflight candidate count, pass rate, skipped reasons, average expected edge, realized PnL, expected-vs-actual gap, account-equity delta, route/symbol distribution, candidate observation pool, and demo size-stage readiness. This separates "did the system discover viable candidates?" from "did the last executed strategy make money?" and prevents paper/mock wins from being treated as OKX-tradable evidence.

The production strategy runtime is exposed through `crypto-assistant strategy list|run|review|guard-status`. It runs scan -> select -> risk -> position budget -> order lifecycle plan -> paper execution -> journal. Runtime controls live under `strategy_runtime` and include per-position capital caps, per-strategy capital caps, max open orders, order TTL, reprice threshold, demo max order value, demo order-size multiplier, demo limit-price marketability buffer, demo wait/poll settings, demo preflight thresholds, demo stop-loss/drawdown breakers, PnL reconciliation tolerance, residual-inventory tolerance, a stateful runtime guard, and an append-only JSONL journal. The runtime guard persists consecutive blocked runs, negative executions, market-data failures, and exchange rate-limit failures to `strategy_runtime.runtime_guard_path`; when `max_consecutive_execution_failures`, `max_consecutive_losses`, `max_consecutive_market_data_failures`, or `max_consecutive_rate_limit_failures` is reached, future cycles for that strategy/mode are skipped until `failure_cooldown_seconds` expires. `strategy guard-status --json` exposes that state for Codex/Claude agents and operators. With `configs/okx.demo.example.yaml` and `--execution-mode demo`, the runtime bypasses live trading entirely, allows only demo-supported allowlisted execution paths, runs a no-order profitability preflight before any OKX Demo Trading order, prices spot demo limit submissions from orderbook best ask/bid plus `demo_limit_price_buffer_pct`, estimates preflight PnL from top-of-book expected fill prices, reports both submitted protection price and expected fill price, sends tiny canary orders only when the preflight passes, waits for fills, cancels if needed, records account snapshots, writes order cash-flow PnL plus account-equity delta reconciliation, reports non-USDT residual inventory, fetches OKX `fills-history` rows for exchange receipt completeness/fee checks, and stops longer loops when demo loss breakers trip. Review is advisory: it can filter by `--execution-mode`, counts only executed events as realized PnL, and emits conservative learning suggestions without editing code, changing configs, or enabling live trading.

The strategy validation middle layer is exposed through `crypto-assistant strategy validate-local`, `crypto-assistant strategy validate-demo-window`, and `crypto-assistant strategy promotion-status`. Local validation runs bounded paper cycles. Demo-window validation runs bounded OKX Demo Trading cycles and requires demo evidence such as provider demo mode, no live orders, PnL reconciliation, residual inventory within tolerance, fill receipts, and no residual open orders or swap positions. If every requested strategy is already in runtime guard cooldown, demo-window validation fails fast before runner execution so it does not burn empty validation cycles or make avoidable post-run network calls. Promotion status reads paper/demo journal statistics plus runtime guard state and reports local, demo, and live-canary status. Live-canary promotion remains disabled by default through `strategy_runtime.validation_allow_live_canary=false` and still requires the generic trading and autonomous agent live gates.

The strategy retrospective layer is exposed through `crypto-assistant strategy retrospective`. It is deterministic and advisory: it reads the strategy journal plus runtime guard state, deduplicates issues by strategy/mode/category/reason, escalates repeated issues for operator attention, and rewrites `docs/plan/2026-05-09-refactor/28-strategy-retrospective.md` plus its state file under the same refactor directory. `strategy run`, `strategy validate-local`, and `strategy validate-demo-window` include `retrospective_before`, `retrospective_after`, and `retrospective_path` in JSON output, while `strategy review` includes a retrospective summary. Retrospective summaries also include `optimization_pressure`, converting repeated issues into observed net PnL, break-even gap, strategy-specific action, config fields to review, and hard guardrails. Repeated high-priority OKX demo `preflight_not_profitable` pressure is consumed by strategy scoring through `strategy_runtime.retrospective_demo_preflight_score_penalty`, so affected strategies can fall below the portfolio score floor until the issue improves. During journal refresh, older transient market-data, rate-limit, and preflight failures are treated as improved when a later profitable execution exists for the same strategy and mode; targeted updates only clear issues for observed strategy/mode pairs, so skipped strategies are not falsely marked improved. The retrospective system does not send orders, change strategy parameters, enable demo/live gates, or block OKX demo sampling by itself.

The rolling validation report is exposed through `crypto-assistant strategy validation-report`. It is read-only and summarizes recent strategy journal evidence by strategy: executed/skipped/blocked counts, realized executed PnL, skipped preflight PnL, approved preflight expected PnL, actual order cash-flow PnL, account-equity delta, account reconciliation gap, expected-vs-actual gap, win rate, drawdown, receipt completeness, PnL tolerance, residual inventory, missing executed preflight estimates, positive-cash-flow/negative-equity detections, reason counts, and conservative recommendations. It is intended to replace manual journal parsing before the next run/review/optimize cycle and does not access exchange APIs or mutate runtime state. Older executed demo entries without persisted preflight estimates are excluded from complete expected-vs-actual promotion evidence.

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
