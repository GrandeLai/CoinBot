# CoinBot

CoinBot is a local-first crypto-only quant trading and research monorepo extracted from QuantPilot.

It contains:

- `backend`: Python FastAPI service for OKX trading, market data, crypto derivatives analytics, advisor, whale flow, and token unlocks.
- `backend/src/trading_assistant`: safe local CLI/service package for mock exchange, market data, arbitrage scanning, dry-run execution, paper trading, backtesting, and reports.
- `common/python`: shared Python config, market data models, DuckDB storage, and OKX data fetcher.
- `quant-core`: Rust axum service for backtest, optimization, walk-forward validation, indicators, and Rhai strategy runtime.
- `frontend`: React + Vite + Tailwind UI that combines crypto assistant, OKX trading, crypto research, and quant workbench panels.
- `docs`: active architecture docs plus migrated historical task/acceptance records from QuantPilot.

## Quick Start

```bash
cd backend
uv run uvicorn coinbot_api.main:app --reload --host 127.0.0.1 --port 8001

cd ../quant-core
cargo run --bin coinbot-quant-server

cd ../frontend
npm install
npm run dev
```

The frontend runs on `http://127.0.0.1:5173`, Python API on `:8001`, and Rust quant-core on `:8002`.

## Crypto Assistant CLI

The CLI is exposed by the backend package:

```bash
cd backend
uv run crypto-assistant --help
uv run crypto-assistant status
uv run crypto-assistant config validate --config ../configs/config.example.yaml
uv run crypto-assistant exchange ping --config ../configs/config.example.yaml --exchange mock --json
uv run crypto-assistant exchange sandbox-check --config ../configs/okx.demo.example.yaml --exchange okx --symbol BTC/USDT --json
uv run crypto-assistant market ticker --config ../configs/config.example.yaml --exchange mock --symbol BTC/USDT --json
uv run crypto-assistant market orderbook --config ../configs/config.example.yaml --exchange mock --symbol BTC/USDT --json
uv run crypto-assistant market candles --config ../configs/okx.demo.example.yaml --exchange okx --symbol BTC/USDT --bar 15m --limit 120 --json
uv run crypto-assistant account balance --config ../configs/config.example.yaml --exchange mock --json
uv run crypto-assistant arbitrage scan --type cross-exchange --symbol BTC/USDT --json
uv run crypto-assistant arbitrage execute --opportunity-id test-opportunity --dry-run --json
uv run crypto-assistant agent live-readiness --config ../configs/config.example.yaml --opportunity-id test-opportunity --json
uv run crypto-assistant agent live-readiness --config ../configs/config.example.yaml --opportunity-file ../tmp/okx-opportunity.json --json
uv run crypto-assistant agent operation-catalog --json
uv run crypto-assistant strategy list --json
uv run crypto-assistant strategy catalog --config ../configs/config.example.yaml --json
uv run crypto-assistant strategy scan --config ../configs/config.example.yaml --strategy all --symbol BTC/USDT --json
uv run crypto-assistant strategy discover-routes --config ../configs/okx.demo.example.yaml --exchange okx --quote USDT --json
uv run crypto-assistant strategy scan --config ../configs/okx.demo.example.yaml --strategy triangular-multi-route --exchange okx --route-mode discovered --json
uv run crypto-assistant strategy opportunity-report --config ../configs/okx.demo.example.yaml --window 24h --json
uv run crypto-assistant strategy scan --config ../configs/config.example.yaml --strategy directional-all --symbol BTC/USDT --json
uv run crypto-assistant strategy score --config ../configs/config.example.yaml --strategy all --json
uv run crypto-assistant strategy score --config ../configs/config.example.yaml --strategy directional-all --json
uv run crypto-assistant strategy market-compare --config ../configs/okx.demo.example.yaml --strategy all --symbol BTC/USDT --target-exchange okx --json
uv run crypto-assistant strategy portfolio-status --config ../configs/config.example.yaml --json
uv run crypto-assistant strategy run --config ../configs/config.example.yaml --strategy all --max-cycles 1 --interval-seconds 0 --execution-mode paper --json
uv run crypto-assistant strategy run --config ../configs/config.example.yaml --strategy directional-all --max-cycles 1 --interval-seconds 0 --execution-mode paper --json
uv run crypto-assistant strategy run --config ../configs/okx.demo.example.yaml --strategy all --max-cycles 1 --interval-seconds 0 --execution-mode demo --json
uv run crypto-assistant strategy review --config ../configs/config.example.yaml --execution-mode demo --json
uv run crypto-assistant strategy guard-status --config ../configs/config.example.yaml --execution-mode paper --json
uv run crypto-assistant strategy retrospective --config ../configs/okx.demo.example.yaml --json
uv run crypto-assistant strategy evolve --config ../configs/config.example.yaml --strategy all --execution-mode paper --limit 50 --json
uv run crypto-assistant strategy candidate-backtest --config ../configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --limit 50 --json
uv run crypto-assistant strategy revival-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json
uv run crypto-assistant strategy validation-report --config ../configs/okx.demo.example.yaml --execution-mode demo --strategy all --limit 50 --json
uv run crypto-assistant strategy validate-demo --config ../configs/okx.demo.example.yaml --strategy all --symbol BTC/USDT --allow-account-mode-switch --json
uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --json
uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 10 --json
uv run crypto-assistant strategy demo-window --config ../configs/okx.demo.example.yaml --strategy triangular-multi-route --cycles 3 --symbol BTC/USDT --json
uv run crypto-assistant strategy promotion-status --config ../configs/okx.demo.example.yaml --strategy all --json
uv run crypto-assistant backtest run --config ../configs/config.example.yaml --json
uv run crypto-assistant report generate --type daily --json
uv run crypto-assistant workflow run --config ../configs/config.example.yaml --symbol BTC/USDT --json
```

The default configuration is safe for local agent use: live trading is disabled, dry-run is enabled, autonomous agent live orders are disabled, and mock exchanges are enabled. `workflow run` connects the full route from mock market data through arbitrage scan, backtest, paper trading, sandbox readiness, live readiness, agent live-readiness, and report generation. Sandbox readiness now checks execution quality: spread persistence, depth-weighted fill completeness, fee model, transfer cost, and latency drift. Live and agent live-readiness are gate checks; they do not send real orders.

The strategy platform now registers OKX-first market-neutral arbitrage strategies: `triangular-multi-route`, `spot-perp-carry`, `funding-carry-hedged`, `futures-perp-basis`, plus the retained `cross-exchange` scanner. Legacy names `triangular`, `spot-perp`, and `funding-rate` remain compatibility aliases. `strategy catalog`, `strategy scan`, `strategy score`, and `strategy portfolio-status` expose metadata, opportunities, transparent scorecards, and bounded multi-strategy selection before anything reaches execution. `strategy discover-routes` expands triangular coverage from exchange spot instrument metadata, keeps configured routes as priority routes, filters missing/low-depth/min-size routes with reasons, and reports `orders_sent=false`. `strategy scan --strategy triangular-multi-route --route-mode discovered` uses those accepted routes for read-only scans. Scores combine net edge, risk score, depth/slippage, historical paper/demo samples, sell-leg/free-balance restrictions, and repeated OKX demo preflight pressure from the retrospective system.

`strategy evolve --json` maintains the strategy survival system. It is simulation-only: it reads paper/demo journal evidence, promotes stronger performers, softly archives strategies that have enough samples but remain unprofitable, and marks archived strategies as `revive_candidate` when later paper/demo evidence improves. It now derives market-regime tags from completed candle features before generating advisory parameter candidates, such as isolated threshold or drawdown changes to test in paper before any demo attempt. `strategy candidate-backtest --json` materializes each candidate in a temporary config copy, compares baseline versus candidate metrics, and destroys the temporary runtime paths after the run; it does not edit checked-in configs, write normal journals, send demo orders, or enable live trading. `strategy run`, `strategy validate-local`, and `strategy validate-demo-window` include `evolution_after` so each run updates the survival state. Archived strategies are blocked from portfolio selection by `strategy_archived_by_evolution`, but they are not deleted. `strategy revival-window --json` is the controlled return path: it selects only current `revive_candidate` strategies, requires local validation first, and only then attempts a bounded OKX demo validation window. It does not enable live trading.

The platform also includes OKX-first long-only spot directional strategies for times when pure arbitrage is scarce: `trend-breakout`, `mean-reversion-spot`, `volatility-squeeze-breakout`, `momentum-rotation`, and `orderbook-imbalance-scalp`. Use `strategy scan --strategy directional-all` and `strategy run --strategy directional-all --execution-mode paper` to keep them separated from arbitrage during validation. Directional strategies use completed candles only, Decimal-based EMA/RSI/ATR/Bollinger/Donchian indicators, fee/slippage-adjusted no-lookahead backtests, and the same risk/journal/retrospective pipeline. The first four strategies can run tiny OKX Demo Trading managed spot positions after local validation: the first approved run opens a long-only spot position, later runs hold until take-profit, stop-loss, or time-limit exit conditions apply, and position state is persisted under `directional.position_state_path`. `orderbook-imbalance-scalp` remains scan/backtest/paper only. Directional live trading is not supported.

Carry and basis scans include diagnostics even when no candidate passes filters. `strategy scan --json` reports candidate net PnL, configured minimum net PnL, break-even gap, depth sufficiency, and cost components such as fees, slippage, holding cost, funding carry, and basis profit. Scorecards surface these as `scan_diagnostic:*` and `scan_break_even_gap_usdt:*` reasons, so blocked strategies can be tuned offline before any OKX demo attempt.

Carry and basis strategy entry is additionally controlled by `arbitrage.funding_min_annualized_pct`, `arbitrage.funding_max_basis_hedge_cost_pct`, `arbitrage.spot_perp_min_basis_pct`, and `arbitrage.futures_basis_min_basis_pct`. These gates make weak funding, expensive hedge, or insufficient basis candidates fail locally with explicit reasons before they can reach OKX demo preflight.

`strategy market-compare --json` is the read-only bridge between local mock validation and OKX demo execution. It scans the same strategy set against a mock baseline and a configured target exchange, reports opportunity counts, best net PnL, diagnostics, and a verdict such as `observe_only`, `paper_only`, or `demo_preflight_candidate`. It forces scan-only safety context, does not write the journal or retrospective, and always reports `orders_sent=false`.

`strategy opportunity-report --json` is the read-only opportunity-density view. It answers whether recent runs are finding candidates rather than only whether executed PnL was positive: scan count, opportunity count, demo preflight candidate count, pass rate, skipped reasons, average expected edge, realized PnL, expected-vs-actual gap, account-equity delta, route/symbol distribution, candidate observation pool, and demo size-stage readiness. It reads only the strategy journal and does not write journal/retrospective state or send orders.

The strategy runtime keeps live trading disabled while running scan -> select -> risk -> position budget -> order lifecycle plan -> paper execution -> journal. A stateful runtime guard persists consecutive blocked runs, negative executions, market-data failures, and exchange rate-limit failures to `strategy_runtime.runtime_guard_path`; once `max_consecutive_execution_failures`, `max_consecutive_losses`, `max_consecutive_market_data_failures`, or `max_consecutive_rate_limit_failures` is reached, the strategy enters a cooldown and `strategy guard-status --json` exposes the machine-readable state. With `configs/okx.demo.example.yaml` and `--execution-mode demo`, demo orders are limited to allowlisted demo-capable execution paths, must pass first-layer local mock/paper validation, then run a no-order profitability preflight before tiny OKX Demo Trading canary orders are sent. Demo order size is controlled by `strategy_runtime.demo_order_size_multiplier` and capped by `demo_max_order_value_usdt`; demo spot limit submission prices prefer OKX orderbook best ask/bid when available and apply `demo_limit_price_buffer_pct` as a marketable-limit protection cap. Preflight PnL uses current top-of-book expected fill prices and reports both `submitted_limit_price` and `expected_fill_price`, so the protection cap is not mistaken for the expected cost. The shared safe config stays at 1x with a 0.1% limit-price buffer, while the OKX demo profile is staged at 2x with a 0.3% buffer after receipt reconciliation. Demo execution waits briefly for fills, cancels if needed, records account snapshots, computes order cash-flow PnL, reconciles it against account-equity delta within `demo_pnl_reconciliation_tolerance_usdt`, tracks non-USDT residual inventory within `demo_residual_inventory_tolerance_usdt`, fetches OKX `/api/v5/trade/fills-history` rows to verify exchange receipt completeness and fees, and stops longer loops if `demo_stop_loss_usdt` or `demo_max_drawdown_usdt` trips. `strategy review --execution-mode demo` reads only demo events, counts only executed events as realized PnL, and emits conservative learning suggestions such as raising profit thresholds or reducing position caps. The learning layer is advisory only; it does not rewrite code, edit config files, or enable live trading.

The three-layer promotion flow is now explicit. `strategy validate-local` runs a bounded local paper validation, `strategy validate-demo-window` runs a bounded OKX Demo Trading validation window with receipt/no-open-risk/residual-inventory evidence, and `strategy promotion-status` summarizes local, demo, and live-canary readiness from the strategy journal and runtime guard. Demo-window validation now fails fast when every requested strategy is already in runtime guard cooldown, avoiding empty demo cycles and unnecessary post-run network calls. `strategy demo-window --json` is the safer operator entrypoint for repeated OKX demo sampling: it runs no-order OKX sandbox health checks, guard status, `market-compare`, and `validation-report` before delegating to `validate-demo-window`. Network or OKX health failures block before the strategy runner, so they are reported as orchestration health failures rather than counted as strategy market-data failures. Thresholds live under `strategy_runtime.validation_*`; `validation_allow_live_canary` defaults to `false`, so a passing local/demo result still cannot promote itself to live trading without an operator changing the live safety gates.

The strategy retrospective system gives each run a memory. `strategy run`, `strategy validate-local`, and `strategy validate-demo-window` return `retrospective_before`, `retrospective_after`, and `retrospective_path` in JSON output. `strategy retrospective --json` refreshes the advisory issue summary from the strategy journal and runtime guard without placing orders or changing gates. The auto-updated document lives at `docs/plan/2026-05-09-refactor/28-strategy-retrospective.md`, keeps a marker-protected manual notes section, and tracks repeated problems such as non-profitable preflight, incomplete receipts, PnL reconciliation drift, residual inventory, open risk, and runtime guard cooldowns. During refresh, transient market-data, rate-limit, and preflight failures are treated as improved when a later profitable execution exists for the same strategy and mode; targeted runs only improve issues for observed strategy/mode pairs, so unrelated blocked strategies stay visible. The same JSON also includes `optimization_pressure`, which turns repeated issues into strategy-specific actions, break-even gaps, config fields to review, and guardrails such as never forcing demo orders when preflight remains negative.

`strategy validation-report --json` is the read-only rolling evidence view for future optimization loops. It summarizes the latest matching strategy journal events by strategy, including executed/skipped/blocked counts, realized executed PnL, skipped preflight PnL, approved preflight expected PnL, actual order cash-flow PnL, account-equity delta, account reconciliation gap, expected-vs-actual gap, win rate, drawdown, receipt completeness failures, PnL tolerance failures, residual-inventory failures, max residual inventory, reason counts, missing executed preflight estimates, positive-cash-flow/negative-equity detections, and conservative recommendations. It does not access OKX, send orders, edit guard state, or change strategy settings. Older executed demo entries without persisted preflight estimates should not be used as complete expected-vs-actual promotion evidence.

Autonomous agent live trading requires all safety controls to pass at the same time: `trading.live_trading=true`, `trading.dry_run=false`, `trading.require_confirm_before_order=false`, `agent_trading.enabled=true`, `agent_trading.allow_live_orders=true`, a non-mock exchange in `agent_trading.allowed_exchanges`, an allowlisted strategy, environment-sourced credentials, a populated `COINBOT_AGENT_OPERATOR_ID`, risk approval, execution-quality approval, audit logging, and `COINBOT_AGENT_LIVE_KILL_SWITCH` not enabled. `agent live-readiness` and `agent execute-live` accept either `--opportunity-id` or `--opportunity-file`; the file path lets an external scanner hand an OKX spot opportunity to the guarded execution path. `agent execute-live` is wired to the OKX spot broker adapter for already-approved OKX spot limit-order opportunities. Unsupported exchanges or perp legs remain blocked.

The OKX exchange adapter is available when the `okx` exchange is explicitly enabled. It maps OKX ticker, orderbook, account balance, funding-rate, and spot/perp quote payloads into the assistant's Decimal-based domain models. Tests use fake OKX clients and do not hit the real OKX network.

The optional CCXT exchange adapter is available for configs such as `binance` and `bybit` when those exchanges are explicitly enabled and the local environment has `ccxt` installed. It is market-data only: ticker, orderbook, balances, funding rates, instruments, spot/perp quotes, and futures basis reads are mapped into the shared Decimal models, but no CCXT order placement is implemented. The cross-exchange scanner now scans directed pairs across enabled exchanges; the safe default still uses only `mock` and `mock_alt`, while fake-client tests cover CCXT-backed Binance/Bybit-style pairs offline.

OKX simulated trading and live trading use separate files:

- `configs/okx.demo.example.yaml` reads `../.env.okx.demo`, keeps `sandbox=true`, `okx_demo=true`, `live_trading=false`, `dry_run=false`, and `agent_trading.allow_demo_orders=true`. This profile may send orders only to OKX Demo Trading after the agent demo gate, risk gate, credential gate, operator gate, and broker mode check pass.
- `configs/okx.live.example.yaml` reads `../.env.okx.live`, keeps `sandbox=false`, `okx_demo=false`, `live_trading=true`, and `dry_run=false`, but still leaves `agent_trading.allow_live_orders=false` so an operator must explicitly enable final live order permission.

Create local secret files from `.env.okx.demo.example` and `.env.okx.live.example`; never commit the real `.env.okx.demo` or `.env.okx.live` files. OKX Demo Trading API requests use the same REST domain as production but must include `x-simulated-trading: 1`, which the OKX provider enables when `COINBOT_OKX_DEMO=true`. The implementation follows the OKX API v5 documentation at `https://www.okx.com/docs-v5/zh/`.

For OKX demo validation, start from `configs/okx.demo.example.yaml`. The `exchange sandbox-check` command performs non-order checks and reports `live_orders_sent=false`; add `--include-private` only when OKX demo credentials are present. `strategy validate-demo` first runs local mock/paper validation and then performs tiny OKX Demo Trading submit/cancel checks for demo-supported allowlisted paths: `cross-exchange`, `triangular`, `funding-carry-hedged`, `spot-perp-carry`, and `futures-perp-basis`. Add `--allow-account-mode-switch` only when the operator accepts switching the OKX demo account from spot mode to futures mode so swap/futures validation can run; the command still verifies `okx_demo=true`, refuses live trading, and blocks when open orders or derivative positions exist. OKX may require the first account-mode setup to be completed in the Web/App UI. `agent operation-catalog --json` exposes the operation validation hub: every registered live-capable operation must also publish a demo config and demo command before it is accepted as covered.

## Environment

Use `COINBOT_` variables:

```bash
COINBOT_TRADING_LIVE_TRADING=false
COINBOT_TRADING_DRY_RUN=true
COINBOT_AGENT_TRADING_ENABLED=false
COINBOT_AGENT_ALLOW_DEMO_ORDERS=false
COINBOT_AGENT_ALLOW_LIVE_ORDERS=false
COINBOT_AGENT_OPERATOR_ID=
COINBOT_AGENT_LIVE_KILL_SWITCH=false
COINBOT_OKX_API_KEY=
COINBOT_OKX_API_SECRET=
COINBOT_OKX_PASSPHRASE=
COINBOT_OKX_DEMO=true
```

Without OKX credentials, public market and analytics endpoints still work where the upstream APIs allow unauthenticated access.

Never commit `.env`, `.env.okx.demo`, or `.env.okx.live`. Use `.env.example`, `.env.okx.demo.example`, and `.env.okx.live.example` for local setup shape only.

## Refactor Artifacts

The 2026-05-09 crypto trading assistant refactor is tracked under:

```text
docs/plan/2026-05-09-refactor/
```

The core acceptance loop is: config loading -> mock exchange -> ticker/orderbook -> arbitrage scan with execution-quality costs -> risk check -> dry-run execution -> paper trading -> sandbox readiness -> live readiness gate -> agent live-readiness gate -> report generation -> CLI JSON -> unit/integration/e2e tests.
