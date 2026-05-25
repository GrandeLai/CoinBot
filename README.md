# CoinBot

CoinBot is a local-first, crypto-only quant trading and research monorepo extracted from QuantPilot. It focuses on safe crypto market data, OKX demo/live separation, arbitrage and directional strategy validation, PnL attribution, and agent-friendly CLI workflows.

It is not a turnkey profit machine. The default path is mock exchange, dry-run, and paper trading; every order-capable path is gated and observable before it can reach OKX Demo Trading or live trading.

## What Is Inside

| Path | Purpose |
| --- | --- |
| `backend` | Python 3.12 FastAPI service for crypto APIs, OKX trading surfaces, derivatives analytics, research, whale flow, token unlocks, and the `crypto-assistant` CLI. |
| `backend/src/trading_assistant` | Safe local trading assistant package: config, exchange interfaces, market data, arbitrage, strategy runtime, validation, reporting, and CLI handlers. |
| `common/python` | Shared Python config, crypto market data models, DuckDB storage, and OKX data fetcher utilities. |
| `quant-core` | Rust axum service for backtest, optimization, walk-forward validation, indicators, and Rhai strategy runtime. |
| `frontend` | React + Vite + Tailwind UI for the crypto assistant, OKX trading views, research, and quant workbench panels. |
| `configs` | Safe example configs for local mock/paper, 100 USDC paper validation, OKX Demo Trading, and OKX live separation. |
| `docs` | Design notes, refactor plans, phase reports, and migrated task/acceptance records. |

## Safety Model

The repository is crypto-only. Do not add stock, ETF, A-share, Hong Kong equity, Futu, or Longbridge surfaces.

Default trading behavior must remain:

```yaml
trading:
  live_trading: false
  dry_run: true
  require_confirm_before_order: true
```

Real orders require all configured gates to pass: live trading enabled, dry-run disabled, a non-mock exchange enabled, credentials loaded from environment variables, risk approval, and explicit agent/order permissions where applicable. Autonomous live trading is additionally blocked unless `agent_trading.enabled=true`, `agent_trading.allow_live_orders=true`, an allowlisted strategy/exchange is configured, `COINBOT_AGENT_OPERATOR_ID` is present, audit logging is enabled, caps are set, and `COINBOT_AGENT_LIVE_KILL_SWITCH` is not enabled.

OKX Demo Trading and OKX live trading use separate config and secret files:

| Mode | Config | Local secret file | Notes |
| --- | --- | --- | --- |
| Local paper/mock | `configs/config.example.yaml` | none required | Safe default for development and agent runs. |
| 100 USDC paper validation | `configs/100usdc.paper.example.yaml` | none required | Bounded local route for small-capital validation evidence. |
| OKX Demo Trading | `configs/okx.demo.example.yaml` | `.env.okx.demo` | May send tiny demo orders only after demo gates pass. |
| OKX live | `configs/okx.live.example.yaml` | `.env.okx.live` | Still blocked by live and agent gates by default. |

Never commit `.env`, `.env.okx.demo`, `.env.okx.live`, API keys, secrets, passphrases, tokens, or plaintext sensitive logs.

## Quick Start

Install and run the three app surfaces in separate terminals:

```bash
cd backend
uv run uvicorn coinbot_api.main:app --reload --host 127.0.0.1 --port 8001
```

```bash
cd quant-core
cargo run --bin coinbot-quant-server
```

```bash
cd frontend
npm install
npm run dev
```

Local URLs:

| Service | URL |
| --- | --- |
| Frontend | `http://127.0.0.1:5173` |
| Python API | `http://127.0.0.1:8001` |
| Rust quant-core | `http://127.0.0.1:8002` |

## First Safe CLI Run

Start with the mock/paper profile. These commands do not send real orders:

```bash
cd backend
uv run crypto-assistant --help
uv run crypto-assistant config validate --config ../configs/config.example.yaml --json
uv run crypto-assistant status --json
uv run crypto-assistant exchange ping --config ../configs/config.example.yaml --exchange mock --json
uv run crypto-assistant market ticker --config ../configs/config.example.yaml --exchange mock --symbol BTC/USDT --json
```

If a Codex or sandboxed local environment cannot write to the default uv cache, prefix commands with `UV_CACHE_DIR=.uv-cache`.

## 100 USDC Paper Validation

Use this when you want a small-capital, local-only validation pass before any OKX demo step:

```bash
cd backend
uv run crypto-assistant strategy validate-local \
  --config ../configs/100usdc.paper.example.yaml \
  --strategy all \
  --cycles 1 \
  --symbol BTC/USDT \
  --json
```

Then inspect realized paper PnL and attribution from the generated journal:

```bash
uv run crypto-assistant strategy validation-report \
  --config ../configs/100usdc.paper.example.yaml \
  --execution-mode paper \
  --strategy all \
  --limit 50 \
  --json

uv run crypto-assistant strategy pnl-attribution \
  --config ../configs/100usdc.paper.example.yaml \
  --execution-mode paper \
  --strategy all \
  --limit 50 \
  --json
```

Treat paper/mock results as system evidence, not market profit. They verify strategy selection, risk gates, journaling, PnL aggregation, drawdown tracking, and attribution plumbing.

## Strategy Workflow

The strategy platform separates read-only discovery, paper validation, OKX demo sampling, and promotion evidence.

### Read-Only Discovery

```bash
cd backend
uv run crypto-assistant strategy list --json
uv run crypto-assistant strategy catalog --config ../configs/config.example.yaml --json
uv run crypto-assistant strategy scan --config ../configs/config.example.yaml --strategy all --symbol BTC/USDT --json
uv run crypto-assistant strategy score --config ../configs/config.example.yaml --strategy all --json
uv run crypto-assistant strategy advisory-rank --config ../configs/config.example.yaml --strategy all --execution-mode paper --window 24h --json
uv run crypto-assistant strategy dex-lp-readiness --config ../configs/config.example.yaml --json
uv run crypto-assistant strategy portfolio-status --config ../configs/config.example.yaml --json
uv run crypto-assistant strategy opportunity-report --config ../configs/config.example.yaml --window 24h --json
uv run crypto-assistant strategy universe --config ../configs/config.example.yaml --exchange mock --json
uv run crypto-assistant strategy regime-report --config ../configs/config.example.yaml --exchange mock --symbol BTC/USDT --json
```

For triangular route expansion:

```bash
uv run crypto-assistant strategy discover-routes \
  --config ../configs/okx.demo.example.yaml \
  --exchange okx \
  --quote USDT \
  --json

uv run crypto-assistant strategy scan \
  --config ../configs/okx.demo.example.yaml \
  --strategy triangular-multi-route \
  --exchange okx \
  --route-mode discovered \
  --json
```

### Paper Runtime

```bash
uv run crypto-assistant strategy run \
  --config ../configs/config.example.yaml \
  --strategy all \
  --max-cycles 1 \
  --interval-seconds 0 \
  --execution-mode paper \
  --json

uv run crypto-assistant strategy guard-status \
  --config ../configs/config.example.yaml \
  --execution-mode paper \
  --json
```

## Autopilot Runtime

`crypto-assistant autopilot` is the detached paper/demo loop for running CoinBot without Codex automations. It can be launched by a shell, cron, launchd, systemd, or another process manager.

Paper mode never sends exchange orders:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run crypto-assistant autopilot run \
  --config ../configs/config.example.yaml \
  --mode paper \
  --strategy all \
  --cycles 0 \
  --interval-seconds 60 \
  --json
```

OKX Demo mode uses the existing demo-window gates and may send only tiny OKX Demo Trading orders:

```bash
UV_CACHE_DIR=.uv-cache uv run crypto-assistant autopilot run \
  --config ../configs/okx.demo.example.yaml \
  --mode demo \
  --strategy triangular-multi-route \
  --cycles 0 \
  --interval-seconds 300 \
  --demo-cycles-per-window 3 \
  --target-exchange okx \
  --json
```

Status and reports are read-only:

```bash
uv run crypto-assistant autopilot status --config ../configs/config.example.yaml --json
uv run crypto-assistant autopilot report --config ../configs/config.example.yaml --mode paper --json
```

Autopilot does not call `agent execute-live` or any live broker. If a paper/demo payload ever reports `live_orders_sent=true`, autopilot stops and persists `stopped_reason=live_order_detected`.

### Rolling Evidence

```bash
uv run crypto-assistant strategy validation-report \
  --config ../configs/config.example.yaml \
  --execution-mode paper \
  --strategy all \
  --limit 50 \
  --json

uv run crypto-assistant strategy operator-brief \
  --config ../configs/config.example.yaml \
  --execution-mode paper \
  --strategy all \
  --limit 50 \
  --json

uv run crypto-assistant strategy pnl-attribution \
  --config ../configs/config.example.yaml \
  --execution-mode paper \
  --strategy all \
  --limit 50 \
  --json

uv run crypto-assistant strategy hedged-maker-report \
  --config ../configs/config.example.yaml \
  --limit 50 \
  --json

uv run crypto-assistant strategy diversification-report \
  --config ../configs/config.example.yaml \
  --strategy all \
  --execution-mode paper \
  --max-family-share-pct 60 \
  --min-queue-quality-score 80 \
  --json

uv run crypto-assistant strategy directional-sleeve-status \
  --config ../configs/config.example.yaml \
  --execution-mode paper \
  --limit 50 \
  --json
```

All rolling evidence commands are read-only and should report `orders_sent=false` and `live_orders_sent=false`.

| Command | Purpose |
| --- | --- |
| `validation-report` | Aggregate execution quality, PnL, drawdown, reason counts, residual inventory, and receipt/tolerance failures. |
| `advisory-rank` | Deterministic ranking from scorecards, rolling validation, opportunity density, and runtime guard state; it does not call external models or mutate configs. |
| `diversification-report` | Strategy-family concentration, validation PnL, advisory validation-budget caps, and a family-balanced `validation_queue` with deterministic quality scores. |
| `directional-sleeve-status` | Long-only directional promotion stages, size caps, guard cooldowns, and the permanent `directional_live_supported=false` boundary. |
| `operator-brief` | No-order checkpoint before another demo or promotion step. |
| `pnl-attribution` | Separates strategy cash-flow PnL from account-equity movement so unrelated inventory is not treated as strategy performance. |
| `hedged-maker-report` | Paper-only maker quote lifecycle, queue/partial-fill quality, adverse-selection samples, simulated hedge slippage, and active quote state. |

`diversification-report --min-queue-quality-score` filters only the queue while preserving family diagnostics. `hedged-maker-demo` remains a separate OKX Demo opportunity-file manager, not part of the generic `strategy run --strategy hedged-maker --execution-mode demo` path.

## Strategy Families

| Family | Strategies | Typical mode |
| --- | --- | --- |
| Cross-exchange arbitrage | `cross-exchange` | Mock/paper first; live adapter coverage is limited. |
| Triangular arbitrage | `triangular-multi-route` plus aliases `triangular` | Read-only discovery, paper, then OKX demo sampling when gates pass. |
| Carry and basis | `funding-carry-hedged`, `spot-perp-carry`, `futures-perp-basis` | Offline diagnostics and paper until economics beat fees, slippage, holding cost, and basis hedge cost. |
| Range grid | `range-grid` | Paper-only range-bound grid opportunity estimates; OKX Demo and live orders are not supported. |
| Smart DCA basket | `smart-dca-basket` plus alias `smart-dca` | Paper-only drawdown-tiered accumulation and basket weight-band diagnostics for BTC/ETH/SOL. |
| Hedged maker / XEMM | `hedged-maker` | Paper passive quote planner with taker hedge preview; an explicit OKX Demo manager exists for approved opportunity files, while live maker orders are not supported. |
| Directional spot | `trend-breakout`, `mean-reversion-spot`, `volatility-squeeze-breakout`, `momentum-rotation`, `orderbook-imbalance-scalp` | Paper first; selected strategies support tiny long-only OKX demo managed positions. Directional live trading is not supported. |
| DEX/CLMM LP | `dex-lp-readiness` | Deferred readiness gate for future DEX liquidity provision; no wallet, gateway, LP, demo, or live execution is implemented. |

Carry/basis tuning is read-only:

```bash
uv run crypto-assistant strategy carry-basis-optimize \
  --config ../configs/config.example.yaml \
  --symbol BTC/USDT \
  --json
```

To compare the same carry/basis candidates against a configured read-only target exchange before any demo preflight:

```bash
uv run crypto-assistant strategy carry-basis-optimize \
  --config ../configs/okx.demo.example.yaml \
  --symbol BTC/USDT \
  --target-exchange okx \
  --json
```

To sweep multiple symbols and rank the closest carry/basis unlock candidates before any demo-window attempt:

```bash
uv run crypto-assistant strategy carry-basis-optimize \
  --config ../configs/okx.demo.example.yaml \
  --symbols BTC/USDT,ETH/USDT,SOL/USDT \
  --target-exchange okx \
  --min-quality-score 80 \
  --max-symbols 6 \
  --request-budget-seconds 60 \
  --per-symbol-timeout-seconds 15 \
  --json
```

Start OKX sweeps with a small symbol set because each symbol reads spot/perp/funding/futures diagnostics from public endpoints. Use `--max-symbols`, `--request-budget-seconds`, and `--per-symbol-timeout-seconds` for bounded observer runs; sweep JSON includes per-symbol `observations` plus skipped, timeout, failed, and cache-hit counts. These controls are read-only and do not bypass demo preflight.

Dynamic universe and regime routing are read-only foundations for the next profit-expansion layer. `strategy universe` filters configured symbols by spread, 24h quote volume, depth, and completed-candle behavior; `strategy regime-report` classifies a symbol as `trend`, `range`, `carry`, `illiquid`, or `avoid` so future strategy selection can route range markets to grid/mean-reversion, trends to breakout/momentum, and carry regimes to basis/funding scans.

Range-grid validation uses the regime router and remains paper-only:

```bash
uv run crypto-assistant strategy scan \
  --config ../configs/config.example.yaml \
  --strategy range-grid \
  --symbol BTC/USDT \
  --exchange mock \
  --json

uv run crypto-assistant strategy run \
  --config ../configs/config.example.yaml \
  --strategy range-grid \
  --symbol BTC/USDT \
  --max-cycles 1 \
  --interval-seconds 0 \
  --execution-mode paper \
  --json
```

`range-grid` builds a bounded ladder from completed candles, estimates completed grid cycles after fee and slippage costs, and emits simulated buy/sell legs for the existing risk, budget, paper execution, journal, and scoring paths. It reports `paper_only=true`; it is deliberately excluded from OKX Demo and live execution until a separate stateful order manager is implemented and sandbox-tested.

Smart DCA basket validation looks for major-asset accumulation opportunities when a configured symbol has pulled back from its recent completed-candle high and is not overweight versus the target basket:

```bash
uv run crypto-assistant strategy scan \
  --config ../configs/config.example.yaml \
  --strategy smart-dca-basket \
  --symbol SOL/USDT \
  --exchange mock \
  --json

uv run crypto-assistant strategy run \
  --config ../configs/config.example.yaml \
  --strategy smart-dca-basket \
  --symbol SOL/USDT \
  --max-cycles 1 \
  --interval-seconds 0 \
  --execution-mode paper \
  --json
```

`smart-dca-basket` calculates recent drawdown, applies drawdown-tier size multipliers, checks quote balance and ask-side depth, compares current basket weight against `smart_dca.target_weights_pct`, and emits one simulated spot buy leg when the expected discount remains positive after fee and slippage assumptions. It is portfolio-management evidence, not guaranteed alpha: the reported net edge is an estimated discount/accumulation edge. The strategy is registered with `demo_supported=false` and `live_supported=false`.

Hedged-maker/XEMM validation plans a passive maker quote and an immediate hedge preview:

```bash
uv run crypto-assistant strategy scan \
  --config ../configs/config.example.yaml \
  --strategy hedged-maker \
  --symbol BTC/USDT \
  --exchange mock \
  --json

uv run crypto-assistant strategy run \
  --config ../configs/config.example.yaml \
  --strategy hedged-maker \
  --symbol BTC/USDT \
  --max-cycles 1 \
  --interval-seconds 0 \
  --execution-mode paper \
  --json

uv run crypto-assistant strategy hedged-maker-report \
  --config ../configs/config.example.yaml \
  --limit 50 \
  --json
```

`hedged-maker` estimates maker-buy/hedge-sell and maker-sell/hedge-buy candidates across configured exchanges, checks maker inventory and hedge depth, subtracts maker/taker fees plus hedge slippage, and persists paper maker quotes under `hedged_maker.paper_state_path`. Repeated paper runs use `strategy_runtime.order_ttl_seconds` and `strategy_runtime.reprice_threshold_pct` to keep, cancel, or replace quotes; crossed paper quotes simulate the taker hedge and record realized PnL separately from expected scan edge. The paper fill model also supports queue position, partial fills, stale quote cancellation, cancel latency, adverse selection detection, and expanded hedge slippage through the `hedged_maker.paper_*` settings. Strategy budget output includes active/projected paper quote order count and capital, so `open`, `partial_open`, and not-yet-effective `cancel_pending` quotes constrain future capacity while matching quotes are not double-counted as new orders. `hedged-maker-report` reads the journal and paper state without touching exchanges, then summarizes fill events, lifecycle counts, adverse-selection rate, simulated PnL, and active quote state.

The OKX Demo manager is a separate command for sandbox parity testing from an explicit opportunity file. It does not make the generic `strategy run --strategy hedged-maker --execution-mode demo` path available:

```bash
uv run crypto-assistant strategy hedged-maker-demo-candidate \
  --config ../configs/okx.demo.example.yaml \
  --symbol BTC/USDT \
  --target-exchange okx \
  --json

uv run crypto-assistant strategy hedged-maker-demo \
  --config ../configs/okx.demo.example.yaml \
  --opportunity-file hedged-maker-okx-opportunity.json \
  --json
```

`hedged-maker-demo-candidate` is read-only and returns an `opportunity_file_payload` plus compatibility reasons; local mock OKX configs deliberately report `target_exchange_adapter_is_mock` and must not be sent to the manager. OKX-targeted `strategy scan`/`market-compare` diagnostics for `hedged-maker` reuse the same single-exchange candidate payload path, so sandbox diagnostics are blocked by actual edge, spread, depth, and compatibility reasons instead of the generic paper scanner's secondary hedge exchange config. The opportunity file must describe a `strategy_type=hedged-maker` OKX opportunity with `maker_quote`, `hedge_preview`, and passing `execution_quality` metadata. The manager command requires OKX Demo credentials, `COINBOT_AGENT_OPERATOR_ID`, `agent_trading.allow_demo_orders=true`, the `hedged-maker` strategy allowlist, OKX exchange allowlist, risk approval, budget approval, provider demo-mode verification, and audit logging. It stores own-order state under `hedged_maker.demo_state_path`, submits maker quotes as OKX Demo `post_only` spot orders, cancels/replaces stale or repriced quotes, and sends the hedge only after observing a maker fill. Live maker orders are still unsupported.

DEX/CLMM liquidity provision is intentionally deferred. The readiness command is a no-order checklist for future testnet work:

```bash
uv run crypto-assistant strategy dex-lp-readiness \
  --config ../configs/config.example.yaml \
  --json
```

The command checks `dex_lp` config prerequisites such as DEX gateway configuration, testnet network selection, wallet policy acknowledgement, gas model, MEV protection, and testnet evidence. It never reads wallet secrets, connects to a DEX, mutates configs, or sends orders. Even when all testnet prerequisites are configured, it reports `execution_supported=false` and keeps live orders unsupported until a real DEX adapter, wallet policy, gas model, MEV controls, and testnet validation are implemented.

Directional exit tuning is also read-only:

```bash
uv run crypto-assistant strategy exit-optimize \
  --config ../configs/config.example.yaml \
  --strategy trend-breakout \
  --symbol BTC/USDT \
  --exchange mock \
  --json

uv run crypto-assistant strategy position-report \
  --config ../configs/config.example.yaml \
  --strategy trend-breakout \
  --symbol BTC/USDT \
  --exchange mock \
  --json
```

`exit-optimize` simulates long-only triple-barrier exits across take-profit, stop-loss, trailing-stop, and time-limit candidates. It returns parameter proposals only; it does not edit configs or send orders.

### Backtest Validation

Backtest commands are read-only and use completed candles, fee/slippage-adjusted directional simulation, and no live order dispatch:

```bash
uv run crypto-assistant backtest run \
  --config ../configs/config.example.yaml \
  --strategy trend-breakout \
  --symbol BTC/USDT \
  --exchange mock \
  --json

uv run crypto-assistant backtest walk-forward \
  --config ../configs/config.example.yaml \
  --strategy trend-breakout \
  --symbol BTC/USDT \
  --exchange mock \
  --windows 2 \
  --json

uv run crypto-assistant backtest bias-check \
  --config ../configs/config.example.yaml \
  --strategy trend-breakout \
  --symbol BTC/USDT \
  --exchange mock \
  --json
```

`backtest run` reports the fill model assumptions, including completed candles, next-bar entry, fee, and slippage. `walk-forward` splits candles into expanding train windows and forward validation windows. `bias-check` is a deterministic diagnostic for obvious local backtest hazards such as incomplete candles, missing warmup, or unstable prefix replay; it is not proof of future profitability.

Strategy evolution is simulation-only. It reads journal evidence, softly archives weak strategies, creates revive candidates, and generates isolated parameter candidates without editing checked-in configs or enabling trading:

```bash
uv run crypto-assistant strategy evolve \
  --config ../configs/config.example.yaml \
  --strategy all \
  --execution-mode paper \
  --limit 50 \
  --json

uv run crypto-assistant strategy candidate-backtest \
  --config ../configs/config.example.yaml \
  --strategy trend-breakout \
  --symbol BTC/USDT \
  --limit 50 \
  --json
```

## OKX Demo Trading Path

Prepare demo credentials locally:

```bash
cp .env.okx.demo.example .env.okx.demo
```

Edit `.env.okx.demo` with OKX Demo Trading credentials. Keep demo and live credentials separate.

Run no-order checks first:

```bash
cd backend
uv run crypto-assistant exchange sandbox-check \
  --config ../configs/okx.demo.example.yaml \
  --exchange okx \
  --symbol BTC/USDT \
  --json

uv run crypto-assistant strategy market-compare \
  --config ../configs/okx.demo.example.yaml \
  --strategy all \
  --symbol BTC/USDT \
  --target-exchange okx \
  --json

uv run crypto-assistant strategy operator-brief \
  --config ../configs/okx.demo.example.yaml \
  --execution-mode demo \
  --strategy all \
  --limit 50 \
  --json
```

Only after the no-order checks pass, use bounded OKX Demo Trading windows. These commands may send tiny OKX Demo Trading orders, never live orders:

```bash
uv run crypto-assistant strategy demo-window \
  --config ../configs/okx.demo.example.yaml \
  --strategy triangular-multi-route \
  --cycles 3 \
  --symbol BTC/USDT \
  --json

uv run crypto-assistant strategy demo-sampling \
  --config ../configs/okx.demo.example.yaml \
  --strategy triangular-multi-route \
  --windows 3 \
  --cycles-per-window 3 \
  --interval-seconds 0 \
  --symbol BTC/USDT \
  --json
```

For hedged-maker sandbox parity, use the explicit opportunity-file manager instead of the generic demo runtime:

```bash
uv run crypto-assistant strategy hedged-maker-demo-candidate \
  --config ../configs/okx.demo.example.yaml \
  --symbol BTC/USDT \
  --target-exchange okx \
  --json

uv run crypto-assistant strategy hedged-maker-demo \
  --config ../configs/okx.demo.example.yaml \
  --opportunity-file hedged-maker-okx-opportunity.json \
  --json
```

Promotion remains evidence-only unless an operator explicitly changes the live gates:

```bash
uv run crypto-assistant strategy promotion-status \
  --config ../configs/okx.demo.example.yaml \
  --strategy all \
  --json
```

`strategy validate-demo --allow-account-mode-switch` is reserved for OKX Demo Trading swap/futures validation. It may switch only the demo account from spot mode to futures mode after provider demo-mode verification and open-risk checks. It must never target live trading.

## CLI Command Map

| Area | Commands |
| --- | --- |
| Config/status | `status`, `config validate` |
| Exchange/market/account | `exchange list`, `exchange ping`, `exchange sandbox-check`, `market ticker`, `market orderbook`, `market candles`, `account balance` |
| Arbitrage | `arbitrage scan`, `arbitrage execute` |
| Strategy discovery | `strategy list`, `strategy catalog`, `strategy scan`, `strategy discover-routes`, `strategy opportunity-report`, `strategy universe`, `strategy regime-report`, `strategy score`, `strategy advisory-rank`, `strategy dex-lp-readiness`, `strategy market-compare`, `strategy portfolio-status` |
| Strategy runtime | `strategy run`, `strategy review`, `strategy guard-status`, `strategy retrospective`, `strategy evolve`, `strategy candidate-backtest`, `strategy revival-window` |
| Detached autopilot | `autopilot run`, `autopilot status`, `autopilot report` |
| Validation/evidence | `strategy validate-local`, `strategy validate-demo`, `strategy validate-demo-window`, `strategy demo-window`, `strategy demo-sampling`, `strategy promotion-status`, `strategy validation-report`, `strategy operator-brief`, `strategy diversification-report`, `strategy directional-sleeve-status`, `strategy pnl-attribution`, `strategy hedged-maker-report`, `strategy hedged-maker-demo-candidate`, `strategy hedged-maker-demo`, `strategy carry-basis-optimize`, `strategy exit-optimize`, `strategy position-report` |
| Agent live gate | `agent live-readiness`, `agent execute-live`, `agent operation-catalog` |
| Backtest/report/workflow | `backtest run`, `backtest walk-forward`, `backtest bias-check`, `report generate`, `workflow run` |

Every machine-readable CLI command should support `--json`, and every CLI command should support `--help`.

## Environment

Use `COINBOT_` variables only:

```bash
COINBOT_TRADING_LIVE_TRADING=false
COINBOT_TRADING_DRY_RUN=true
COINBOT_REQUIRE_CONFIRM_BEFORE_ORDER=true
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

Without OKX credentials, mock exchange, paper validation, local scans, and many public market/analytics endpoints still work. Private OKX account reads and OKX Demo Trading require local credentials.

## Repository Hygiene

Keep local runtime artifacts out of git:

- Secret files: `.env`, `.env.*`, `.env.okx.demo`, and `.env.okx.live`; only the checked-in `*.example` templates are safe.
- Runtime evidence: `logs/`, `backend/logs/`, JSONL journals, local state files, generated opportunity payloads, and temporary SQLite/DuckDB databases.
- Tool output: Python caches, uv cache, Node build output, Rust `target/`, coverage reports, and editor metadata.

Do commit the lock files (`uv.lock`, `frontend/package-lock.json`, `Cargo.lock`) and the curated refactor state JSON files under `docs/plan/2026-05-09-refactor/`.

## Verification

Run the relevant checks after changes:

```bash
cd backend
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest tests/ -v
```

```bash
cd quant-core
cargo test
```

```bash
cd frontend
npm install
npm run build
```

For CLI smoke checks:

```bash
cd backend
uv run crypto-assistant --help
uv run crypto-assistant strategy --help
uv run crypto-assistant config validate --config ../configs/config.example.yaml --json
uv run crypto-assistant strategy catalog --config ../configs/config.example.yaml --json
```

## Documentation

Start with:

- `docs/DESIGN.md` for current architecture and public interfaces.
- `docs/plan/2026-05-09-refactor/00-refactor-spec.md` for the crypto trading assistant refactor goals.
- `docs/plan/2026-05-09-refactor/` for active phase reports, traceability, acceptance notes, and final reports.

Keep refactor planning and acceptance artifacts under `docs/plan/2026-05-09-refactor/`. Historical migrated task records live under `docs/tasks/**` and `docs/acceptance/**`.
