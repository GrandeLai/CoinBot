# Final Acceptance Report: Crypto Assistant Refactor

## 1. Original Spec Coverage

The core loop is implemented and verified:

configuration loading -> mock exchange -> market ticker/orderbook -> arbitrage scan -> strategy runtime -> risk check -> position budget -> order lifecycle plan -> dry-run execution -> paper ledger -> strategy review -> sandbox readiness -> live readiness -> agent live-readiness -> operation validation catalog -> report generation -> CLI JSON output -> unit/integration/e2e tests.

The route is also available as one command:

`crypto-assistant workflow run --config configs/config.example.yaml --symbol BTC/USDT --json`

## 2. Implemented Features

- Project governance files: `AGENTS.md`, `CLAUDE.md`.
- Centralized refactor docs in `docs/plan/2026-05-09-refactor/`.
- `backend/src/trading_assistant` package.
- YAML config loader with `.env`, environment overrides, validation, and redaction.
- Safe defaults: live trading disabled, dry-run enabled, mock exchange enabled.
- Unified exceptions and CLI JSON error handling.
- Exchange interface and deterministic mock exchange.
- Market ticker and orderbook services.
- Account balance service.
- Arbitrage opportunity model.
- Cross-exchange, triangular, funding-rate, spot-perp, triangular-multi-route, spot-perp-carry, funding-carry-hedged, and futures-perp-basis scanners.
- Fee, slippage, depth, percentage, and risk-score calculations using `Decimal`.
- Risk manager with configured limits.
- Dry-run execution engine.
- Paper trading ledger.
- Deterministic backtest engine and metrics.
- Daily report generator and formatter.
- `crypto-assistant` CLI.
- One-command workflow route through mock market data, arbitrage scan, backtest, paper trading, sandbox readiness, live readiness gate, agent live-readiness gate, and report generation.
- Execution-quality enhancements for the套利主线: spread persistence, depth-weighted fills, maker/taker fee tiers, transfer/delay cost, latency drift cost, funding annualization, and holding cost.
- Controlled autonomous agent live-trading gate with explicit config, allowlisted strategies/exchanges, operator id, kill switch, audit log, risk approval, credential checks, and execution-quality checks.
- `--opportunity-file` support for Agent live-readiness and execute-live, allowing externally generated OKX spot opportunity JSON to enter the guarded path.
- OKX exchange adapter for ticker, orderbook, account balances, funding rates, spot/perp quotes, instrument metadata, and futures basis quotes.
- Optional CCXT market-data adapter for Binance/Bybit-style exchanges, covering ticker, orderbook, balances, funding rates, spot/perp quotes, instruments, and futures basis when available.
- Cross-exchange scanner now scans directed pairs across enabled exchanges while preserving the default mock `test-opportunity` path.
- OKX non-order sandbox validation command and safe example config.
- Separate OKX simulated-trading and live-trading config files with `okx_demo` mode checks.
- Separate OKX simulated-trading and live-trading local dotenv examples: `.env.okx.demo.example` and `.env.okx.live.example`.
- Config-specific `app.env_file` loading so OKX demo keys and OKX live keys can be kept in separate local files.
- OKX demo API validation report: `docs/plan/2026-05-09-refactor/14-okx-demo-api-validation-report.md`.
- OKX demo-order agent gate through `agent_trading.allow_demo_orders`, while live orders still require `agent_trading.allow_live_orders`.
- Operation validation hub and `crypto-assistant agent operation-catalog --json`, ensuring every registered live-capable operation has a demo config and demo command.
- OKX spot live broker adapter for already-approved spot limit-order opportunities after all agent gates pass.
- Production strategy runtime and strategy platform for `cross-exchange`, `triangular-multi-route`, `funding-carry-hedged`, `spot-perp-carry`, and `futures-perp-basis`, with compatibility aliases for `triangular`, `funding-rate`, and `spot-perp`.
- Strategy catalog, scan, score, and portfolio-status CLI commands.
- Strategy runtime position caps, per-strategy capital caps, max-open-order controls, order TTL, cancel/reprice lifecycle plans, JSONL journal, review statistics, and advisory learning suggestions.
- OKX strategy demo validation CLI with first-layer local mock/paper validation, tiny Demo Trading submit/cancel checks, and explicit demo-only account-mode switch support for derivative validation.
- OKX strategy demo execution CLI through `strategy run --execution-mode demo`, including tiny filled canary orders, account snapshots, approximate PnL, and post-run no-open-risk checks.
- Run/review/optimize/rerun loop for OKX Demo Trading strategy execution, with the optimized rerun limited to the only consistently positive demo path.
- Demo strategy optimization controls: preflight profitability gate before demo orders, cumulative stop-loss/drawdown breakers for longer sample loops, cash-flow PnL versus account-equity delta reconciliation, and execution-mode-specific review that counts only executed events as realized PnL.
- OKX exchange receipt reconciliation through `fills-history` for executed demo strategy orders.
- Stage-1 OKX demo position-size increase using `demo_order_size_multiplier=2` while live trading remains disabled.
- Stage-1 2x continuous OKX Demo Trading sample windows, including a latest 10-cycle pass with complete receipt checks, PnL reconciliation, residual-inventory checks, and no residual open orders or swap positions.
- Stateful strategy runtime guard that persists consecutive blocked runs, negative executions, market-data failures, and exchange rate-limit failures, applies cooldowns, and exposes `strategy guard-status --json`.
- Three-layer strategy validation middle layer: local paper validation, OKX Demo Trading validation windows, and advisory live-canary promotion status.
- OKX demo execution report: `docs/plan/2026-05-09-refactor/17-okx-demo-strategy-execution-report.md`.
- Three-layer trading system report: `docs/plan/2026-05-09-refactor/19-three-layer-trading-system-report.md`.
- OKX-first strategy platform design/plan/report: `docs/plan/2026-05-09-refactor/20-arbitrage-strategy-platform-design.md`, `21-arbitrage-strategy-platform-plan.md`, and `22-arbitrage-strategy-platform-report.md`.
- Expanded OKX demo strategy canary report: `docs/plan/2026-05-09-refactor/23-okx-demo-expanded-strategy-execution-report.md`.
- CCXT multi-CEX adapter report: `docs/plan/2026-05-09-refactor/24-ccxt-multi-cex-adapter-report.md`.
- OKX runtime guard hardening report: `docs/plan/2026-05-09-refactor/25-okx-runtime-guard-hardening-report.md`.
- OKX triangular fill reliability report: `docs/plan/2026-05-09-refactor/26-okx-triangular-fill-reliability-report.md`.
- OKX post-R052 demo validation report: `docs/plan/2026-05-09-refactor/27-okx-demo-post-r052-validation-report.md`.
- Strategy retrospective living document and implementation report: `docs/plan/2026-05-09-refactor/28-strategy-retrospective.md`, `28-strategy-retrospective.state.json`, and `29-strategy-retrospective-system-report.md`.
- Strategy optimization pressure report: `docs/plan/2026-05-09-refactor/30-strategy-optimization-pressure-report.md`.
- OKX demo spot order pricing now uses `/market/books` best bid/ask plus configurable `strategy_runtime.demo_limit_price_buffer_pct` for more realistic preflight and better tiny-limit fill reliability.
- Post-R052 OKX demo validation: a fresh 10-cycle window passed at the current 2x demo size with `executed=10`, `skipped=40`, `net_profit=15.863852`, and no open orders or positions.
- Strategy retrospective system: `strategy run`, `strategy validate-local`, and `strategy validate-demo-window` now include `retrospective_before`, `retrospective_after`, and `retrospective_path`; `strategy review` includes `retrospective_summary`; and `strategy retrospective --json` refreshes advisory issue memory from journal/guard evidence without orders or gate changes.
- Retrospective-driven optimization pressure: `strategy retrospective --json` now reports observed negative preflight PnL, break-even gap, strategy-specific action, config fields to review, and hard guardrails for repeated issues.
- Latest same-size targeted OKX demo validation: `triangular-multi-route` passed a 10-cycle window with `executed=10`, `wins=10`, `net_profit=2.629326`, `max_drawdown_usdt=0`, complete receipts, PnL/residual checks within tolerance, and no open orders or positions.
- Retrospective updates now only mark issues improved for observed strategy/execution-mode pairs, so a targeted triangular run does not hide unresolved preflight issues for non-selected strategies.
- Rolling validation report CLI: `strategy validation-report --json` summarizes recent journal evidence including realized executed PnL, skipped preflight PnL, approved preflight expected PnL, actual order cash-flow PnL, account-equity delta, reconciliation gaps, drawdown, receipt/PnL/residual validation quality, reason counts, and conservative per-strategy recommendations without accessing exchanges or sending orders.
- OKX demo preflight fill-price optimization: preflight now estimates expected fills from current top-of-book while still submitting marketable limit orders with protection prices; the latest post-optimization demo window executed one triangular canary with `net_profit=0.026190 USDT`, complete receipts, PnL/residual checks within tolerance, and no open orders or positions.
- Carry/basis scan diagnostics: `strategy scan --json` now reports candidate net PnL, minimum required PnL, break-even gap, depth sufficiency, and cost components for `spot-perp-carry`, `funding-carry-hedged`, and `futures-perp-basis`.
- Carry/basis quality gates: scanners now enforce configurable minimum funding annualized percentage, maximum basis hedge cost percentage, minimum spot-perp basis percentage, and minimum futures-perp basis percentage before opportunities can pass local scan.
- Unit, integration, and e2e tests.
- README, DESIGN, example config, and `.env.example` updates.

## 3. Unimplemented Features

- Real Binance/Bybit live broker adapters are not implemented.
- CCXT market-data adapter is implemented, but real Binance/Bybit sandbox network validation has not been run in this environment.
- OKX perp/swap live execution from `trading_assistant` is not implemented.
- Real OKX demo network validation has now been run for public market data, private account reads, spot demo order placement, swap demo order placement, demo order cancellation, and open-order absence after cancellation.
- Persistent report storage and historical trade database are not implemented.
- Full production-grade backtest data ingestion is not implemented.

## 4. Deferred / Blocked Items

- `R030` remains partially `Deferred`.
  - Reason: OKX market/account adapter, optional CCXT market-data adapter, OKX spot broker dispatch, OKX demo validation, and OKX demo strategy execution are implemented. Binance/Bybit live broker dispatch and real sandbox network acceptance still require credentials, connectivity, and exchange-specific order semantics.
  - Impact: current CLI supports the complete offline mock/dry-run core loop, autonomous agent live-readiness checks, opportunity-file handoff, OKX market/account mapping, fake-client-tested CCXT market-data mapping, OKX spot dispatch for already-approved OKX spot opportunities, and OKX Demo Trading canary strategy execution. Broader non-OKX live execution is not available.
  - Follow-up plan: install/validate `ccxt` in a controlled sandbox environment, run Binance/Bybit public/private read checks, then add live broker dispatch only after operation-catalog demo coverage exists.
- `R033` is `Done` for readiness, policy, and audit gating.
  - Reason: the requested Agent autonomous live-trading control surface now exists.
  - Impact: Agents can determine whether autonomous live trading is permitted and receive clear machine-readable blockers.
  - Follow-up plan: expand strategy-specific broker adapters after sandbox validation.
- `R034` is `Done`.
  - Reason: OKX spot broker dispatch is wired behind agent gates and covered by fake-provider tests.
  - Impact: `agent execute-live` can submit OKX spot limit orders only after the readiness gate passes and the opportunity legs are OKX spot legs.
  - Follow-up plan: keep OKX spot validation in `strategy validate-demo`; add swap/perp broker support only after OKX demo swap validation passes.
- `R035` is `Done`.
  - Reason: `agent live-readiness` and `agent execute-live` now accept opportunity JSON files.
  - Impact: a real scanner or another agent can pass an OKX spot opportunity into the guarded execution path without depending on the mock `test-opportunity`.
  - Follow-up plan: add a real OKX scanner that emits this file format directly.
- `R036` is `Done`.
  - Reason: `exchange sandbox-check` validates OKX adapter readiness without placing orders.
  - Impact: operators can test OKX public market paths and optional private account reads before enabling any Agent live execution.
  - Follow-up plan: keep real OKX network checks manually gated and never require them for offline CI.
- `R037` is `Done`.
  - Reason: OKX simulated-trading and live-trading profiles are split into two files and validated through config tests.
  - Impact: operators can validate/demo from `configs/okx.demo.example.yaml` and `.env.okx.demo` while keeping live settings isolated in `configs/okx.live.example.yaml` and `.env.okx.live`.
  - Follow-up plan: maintain separate deployment secrets and never reuse live credentials in demo validation.
- `R038` is `Done`.
  - Reason: the operation validation hub now lists current OKX live-capable operations and their matching demo validation commands.
  - Impact: `crypto-assistant agent operation-catalog --json` returns `missing_demo_validation=[]`, so automation can verify demo/live parity before considering a live operation covered.
  - Follow-up plan: every future live-capable broker operation must add a demo contract and test before being enabled.
- `R039` is `Done`.
  - Reason: the production strategy runtime now runs the canonical strategy set in paper mode by default, while controlled OKX Demo Trading execution remains limited to demo-supported allowlisted canary paths.
  - Impact: strategies can run bounded or long-running paper cycles, apply capital/order controls, emit cancel/reprice lifecycle plans, record JSONL evidence, produce review-based learning suggestions, and record demo execution PnL where demo execution is explicitly supported.
  - Follow-up plan: use the existing demo execution path as the canary before future broker or strategy execution changes.
- `R040` is `Done`.
  - Reason: demo validation now runs first-layer local mock/paper validation before OKX Demo Trading submit/cancel checks. It covers `cross-exchange`, `triangular`, `funding-carry-hedged`, `spot-perp-carry`, and `futures-perp-basis`.
  - Impact: expanded carry/basis strategies can now perform tiny OKX Demo Trading canary submit/cancel validation without enabling live trading. The command still requires demo config, demo credentials, allowlist, provider demo mode, and derivative account-mode approval when needed.
  - Follow-up plan: keep this command manually gated and rerun it after any future OKX broker or strategy execution change.
- `R041` is `Done`.
  - Reason: demo execution supports tiny canary specs for spot, swap, and dated futures strategies, and runner-level demo execution also requires local validation and profitability preflight before orders. It now also reports residual non-USDT inventory and blocks demo-window validation if that value exceeds tolerance.
  - Impact: latest 10-cycle OKX Demo Trading window passed with `executed=10`, `skipped=40`, `net_profit=16.549322`, `win_rate_pct=100.00`, `max_drawdown_usdt=0`, all receipts complete, all PnL checks within tolerance, `max_residual_inventory_usdt=0.025127<0.10`, and post-run `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`.
  - Follow-up plan: add persisted equity curves and exchange-rate-limit circuit breakers before considering higher autonomy.
- `R042` is `Done`.
  - Reason: the deferred optimization controls are implemented and covered by unit tests.
  - Impact: `strategy run --execution-mode demo` now skips non-profitable demo preflight paths before order submission, records `pnl_validation`, and stops continuous small-sample loops when configured demo loss breakers trip. `strategy review --execution-mode demo` now reports demo-only realized PnL and does not count skipped/blocked estimates as actual profit.
  - Follow-up plan: run longer scheduled demo samples only after validating the preflight behavior with fresh OKX demo market data; do not increase order size from canary level until exchange-native realized PnL reconciliation is added.
- `R043` is `Done`.
  - Reason: executed OKX demo orders now fetch `fills-history` transaction details by `ordId`, summarize receipt completeness, fees, and exchange-reported fill PnL, and include that data in `pnl_validation.exchange_receipts`.
  - Impact: the latest real OKX Demo Trading 10-cycle window returned complete receipts for every executed triangular order, with all executed events reporting `exchange_receipts.complete=true`, no receipt errors, and no residual spot orders, swap orders, or positions.
  - Follow-up plan: keep canary size until a longer sample window proves receipt completeness and drawdown controls under varied market conditions; then stage a small demo size increase only in OKX demo.
- `R044` is `Done`.
  - Reason: demo order size is now configurable through `strategy_runtime.demo_order_size_multiplier`, and the OKX demo profile has been staged to 2x with a 20 USDT per-order cap.
  - Impact: the latest 2x OKX Demo Trading window skipped all negative-preflight strategies, executed only `triangular-multi-route`, returned `net_profit=16.549322` across 10 executions, `pnl_validation.within_tolerance=true`, `exchange_receipts.complete=true`, `residual_inventory_within_tolerance=true`, and no residual open orders or positions.
  - Follow-up plan: do not increase beyond 2x until repeated windows across different market conditions show complete receipts, residual inventory below tolerance, and no drawdown breaker triggers.
- `R045` is `Done`.
  - Reason: real OKX Demo Trading 2x sample windows were run before any further size increase.
  - Impact: the latest 10-cycle window completed with `demo_window_validation.status=Pass`, `demo_cumulative_net_pnl=16.549322`, `demo_max_drawdown_usdt=0`, `triangular-multi-route` executed 10 times, the other strategies were skipped by negative preflight, all executed PnL and residual-inventory checks were within tolerance, all OKX `fills-history` receipts were complete, and post-run checks returned `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`.
  - Follow-up plan: keep size at 2x until additional repeated sample windows prove the same receipt completeness and no-open-risk behavior across more market conditions.
- `R046` is `Done`.
  - Reason: long-running strategy execution needed cross-run state before more autonomous sampling.
  - Impact: `strategy run` now consults `StrategyRuntimeGuard` before each strategy cycle, persists consecutive blocked/negative execution state plus market-data/rate-limit failure state, cools down unsafe strategy/mode pairs, and exposes status through `strategy guard-status --json`.
  - Follow-up plan: continue adding OKX-specific circuit breakers only after they can be proven with fake-provider tests and local validation first.
- `R047` is `Done`.
  - Reason: three-layer validation is now explicit before further size or live-canary consideration.
  - Impact: `strategy validate-local` runs bounded paper validation, `strategy validate-demo-window` runs bounded OKX Demo Trading windows with receipt/no-open-risk/residual-inventory evidence, and `strategy promotion-status` reports local/demo/live-canary status without sending orders. Latest promotion status has `triangular-multi-route` local/demo Pass and live Fail because live-canary gates remain disabled by default.
  - Follow-up plan: use longer demo windows and market-regime-diverse samples before changing `validation_allow_live_canary` or raising demo size.
- `R048` is `Done`.
  - Reason: the OKX-first strategy platform adds catalog/controller/score/portfolio services plus `triangular-multi-route`, `funding-carry-hedged`, `spot-perp-carry`, and `futures-perp-basis`.
  - Impact: expanded strategies are available for scan, score, portfolio selection, paper validation, and demo-canary validation while live support remains disabled.
  - Follow-up plan: continue collecting OKX demo evidence before any size increase or live-canary discussion.
- `R049` is `Done`.
  - Reason: expanded OKX demo canary work now requires local validation first, supports spot/swap/futures submit-cancel validation, and stops/unwinds demo execution when a leg does not fully fill.
  - Impact: real OKX Demo Trading submit/cancel validation completed for all five demo-capable paths. Latest demo-window run returned `Pass`, `executed=10`, `skipped=40`, `net_profit=16.549322`, `pnl_validation.within_tolerance=true`, `exchange_receipts.complete=true`, `residual_inventory_within_tolerance=true`, and post-run `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`.
  - Follow-up plan: keep carry/basis strategies at canary size because the current market kept them skipped by `demo_preflight_not_profitable`.
- `R050` is `Done`.
  - Reason: the optional CCXT market-data adapter now maps Binance/Bybit-style spot, swap, and futures data into the shared exchange interface, and the cross-exchange scanner now uses enabled exchange pairs.
  - Impact: multi-CEX market data and cross-exchange scanning can be tested offline with fake CCXT clients; missing futures markets fail explicitly instead of producing fake basis opportunities.
  - Follow-up plan: install and validate `ccxt` in a controlled sandbox/read-only environment before enabling real Binance/Bybit configs; keep non-OKX broker dispatch deferred until demo/sandbox operation coverage exists.
- `R051` is `Done`.
  - Reason: longer OKX demo runs need to stop quickly when market data or exchange throttling becomes unhealthy.
  - Impact: `StrategyRuntimeGuard` now tracks consecutive market-data failures and rate-limit failures with configurable thresholds. `StrategyRunner` classifies exchange scan/preflight failures into guard-visible reasons, and `strategy guard-status --json` exposes the counters.
  - Follow-up plan: check guard status before the next OKX demo window; keep non-OKX broker dispatch deferred and do not increase demo size until repeated clean OKX windows pass.
- `R052` is `Done`.
  - Reason: the latest OKX-only demo follow-up showed a triangular middle-leg non-fill, so demo spot limit prices needed to use the current book instead of only last price.
  - Impact: OKX demo spot buys now price from best ask plus `demo_limit_price_buffer_pct`; spot sells price from best bid minus the same buffer. Preflight and execution share this path, and unfilled-leg abort/unwind behavior remains intact. The latest one-cycle OKX demo window filled all three triangular legs, recorded `net_profit=1.601695`, complete receipts, residual inventory within tolerance, and no post-run open orders or positions.
  - Follow-up plan: collect more small OKX demo windows across market states before any size increase; keep non-OKX broker dispatch deferred.
- `R053` is `Done`.
  - Reason: R052 needed fresh local-first OKX Demo Trading evidence beyond a single successful cycle.
  - Impact: guard status was clean, local validation passed, a 3-cycle OKX demo window returned `executed=3`, `skipped=12`, `net_profit=4.749252`, and a 10-cycle OKX demo window returned `status=Pass`, `executed=10`, `skipped=40`, `wins=10`, `losses=0`, `net_profit=15.863852`, `max_drawdown_usdt=0`, complete receipts, PnL within tolerance, residual inventory within tolerance, and no post-run open orders or positions.
  - Follow-up plan: continue current-size OKX demo sampling across more market regimes; do not increase size or enable live trading from this result alone.
- `R054` is `Done`.
  - Reason: repeated strategy execution and validation needed a durable memory so the next run can see unresolved issues before repeating the same mistake.
  - Impact: `strategy run`, `strategy validate-local`, and `strategy validate-demo-window` expose before/after retrospective summaries; `strategy retrospective --json` refreshes the living document and state file under the refactor directory; `strategy review --json` reports retrospective status. The system is non-blocking and never changes demo/live gates or sends orders.
  - Follow-up plan: use the current retrospective before each longer OKX demo window, then add owner/priority metadata only if the issue table grows beyond the current deterministic categories.
- `R055` is `Done`.
  - Reason: the current open retrospective issues were repeated negative OKX demo preflights; the system needed to convert them into actionable optimization pressure without weakening safety gates.
  - Impact: `strategy retrospective --json` now includes `optimization_pressure` with observed net PnL, break-even gap, strategy-specific action, config fields to review, and guardrails. The generated Markdown also includes a `Strategy Optimization Pressure` section.
  - Follow-up plan: improve carry/basis scanner entry conditions against the reported break-even gaps, then rerun local validation before any OKX demo window.
- `R056` is `Done`.
  - Reason: repeated retrospective pressure needed to affect strategy selection, not only narrative review.
  - Impact: strategies with repeated OKX demo `preflight_not_profitable` issues receive score penalties and can fall below the portfolio floor; current selection keeps only `triangular-multi-route`.
  - Follow-up plan: keep this conservative scoring enabled until carry/basis strategies show positive local and demo evidence.
- `R057` is `Done`.
  - Reason: demo validation should not burn cycles while the runtime guard is cooling down a strategy, and old transient failures should not reopen after later profitable evidence for the same strategy/mode.
  - Impact: demo-window validation now fast-fails when all targets are cooling down; retrospective cleanup handles later profitable execution without bypassing guard state.
  - Follow-up plan: keep checking guard status before longer OKX demo windows.
- `R058` is `Done`.
  - Reason: the previous optimization loop needed a larger same-size sample and a retrospective consistency fix for targeted runs.
  - Impact: `triangular-multi-route` passed a 10-cycle OKX demo window with `net_profit=2.629326` and no open risk; retrospective improvement is now scoped to observed strategy/execution-mode pairs.
  - Follow-up plan: do not increase size or enable live from this alone; keep collecting same-size samples across more market conditions.
- `R059` is `Done`.
  - Reason: future run/review/optimize cycles needed a machine-readable rolling report instead of manual JSONL parsing.
  - Impact: `strategy validation-report --json` now reports recent executed/skipped/blocked counts, realized PnL, skipped preflight PnL, drawdown, receipt/PnL/residual quality, reason counts, and conservative recommendations.
  - Follow-up plan: use this command before every OKX demo run and keep non-triangular strategies out of demo execution until their preflight net PnL turns positive.
- `R060` is `Done`.
  - Reason: blocked carry/basis strategies needed explainable offline economics before any further OKX demo attempt.
  - Impact: scan and score output now include candidate net PnL, minimum required PnL, break-even gap, depth and cost-component diagnostics for carry/basis strategies.
  - Follow-up plan: tune carry/basis thresholds and market filters offline from these diagnostics, then rerun local paper validation before any OKX demo window.
- `R061` is `Done`.
  - Reason: diagnostics alone showed candidate economics, but scanners needed explicit gates for weak funding, costly hedges, and too-small basis.
  - Impact: carry/basis scanners now reject candidates with `basis_below_minimum`, `funding_annualized_below_minimum`, `basis_hedge_cost_above_maximum`, or `futures_basis_below_minimum` before execution layers.
  - Follow-up plan: compare these local gates against real OKX market reads without orders before allowing carry/basis demo samples.
- `R062` is `Done`.
  - Reason: the system needed a formal read-only bridge between local mock validation and OKX demo preflight.
  - Impact: `strategy market-compare --json` compares mock baseline scans against a target exchange, returns per-strategy diagnostics and verdicts, and reports `orders_sent=false`.
  - Follow-up plan: run market-compare before every future OKX demo attempt and allow demo preflight only for strategies returning `demo_preflight_candidate`.
- `R063` is `Done`.
  - Reason: after the latest optimization, the system needed a bounded OKX Demo Trading validation run.
  - Impact: the latest 3-cycle demo window executed only `triangular-multi-route`, skipped non-profitable strategies through preflight, and ended with no open orders or positions.
  - Follow-up plan: collect at least 10 clean same-size demo executions before promotion or any size increase.
- `R064` is `Done`.
  - Reason: the latest user audit found a known failure mode in other projects where strategy-level PnL was positive but whole-account movement was negative.
  - Impact: `strategy validation-report --json` now separates expected preflight PnL, actual order cash-flow PnL, account-equity delta, account reconciliation gap, expected-vs-actual gap, missing executed preflight estimates, and positive-cash-flow/negative-equity detections.
  - Follow-up plan: collect new OKX demo samples with persisted approved preflight estimates before using expected-vs-actual PnL alignment as promotion evidence.
- `R065` is `Done`.
  - Reason: OKX demo preflight incorrectly treated marketable-limit protection prices as expected fill prices, which made positive triangular opportunities look negative.
  - Impact: preflight JSON now separates `submitted_limit_price` from `expected_fill_price`; the post-optimization OKX demo window executed one positive triangular canary with clean receipt, PnL, residual, and open-risk evidence.
  - Follow-up plan: collect more same-size samples before any size increase and keep non-triangular strategies blocked until their top-of-book preflight net PnL turns positive.

No current item is marked `Blocked`.

## 5. Test Coverage

- Unit tests cover config loader/validation/redaction, exchange interface, mock exchange, OKX exchange adapter, optional CCXT market-data adapter, OKX sandbox validation, ticker, orderbook, account balance, opportunity model, arbitrage calculators/scanners, carry/basis scan diagnostics and quality gates, read-only strategy market comparison, fee/slippage/depth/risk scoring, risk manager, order simulator, paper trading, backtest metrics, report generation, agent live-trading gates, OKX broker dispatch conversion, strategy registry, strategy runtime policy, strategy runtime guard including market-data and rate-limit counters, strategy runner scan/preflight failure classification, strategy review learning, strategy retrospective classification/deduplication/escalation/manual-note preservation/path resolution, rolling strategy validation report aggregation, strategy validation service, strategy demo validation account-mode gating, account-mode-aware spot `tdMode`, expanded demo carry/basis canaries, unfilled-leg stop/unwind behavior, accumulated fill parsing, residual-inventory validation, demo execution PnL capture, and orderbook-based OKX demo spot limit pricing.
- Integration tests cover CLI config, mock exchange, market ticker, orderbook, account balance, OKX sandbox-check default blocker, arbitrage scan including enabled-pair cross-exchange scanning, dry-run execute, agent live-readiness, opportunity-file readiness/execution blockers, workflow, strategy list/run/review/retrospective/validation-report/market-compare and scan diagnostics, strategy validate-local, strategy promotion-status, strategy validate-demo blockers, strategy validate-demo-window safety blocker, and report generation.
- E2E tests cover the full mock dry-run CLI chain, workflow agent live-readiness blockers, and exit codes.

## 6. Test Commands And Results

- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q`
  - Latest full backend result after R065: `293 passed in 9.35s`
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py tests/unit/test_config.py tests/integration/test_cli_core.py tests/e2e/test_dry_run_flow.py -q`
  - R054 targeted result: `56 passed in 5.47s`
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/`
  - Latest lint result after R065: `All checks passed!`
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/`
  - Latest type-check result after R065: `Success: no issues found in 96 source files`
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_runner_executes_demo_mode_through_demo_executor tests/unit/test_strategy_runtime.py::test_strategy_validation_report_summarizes_recent_receipt_pnl_and_residual_evidence tests/unit/test_strategy_runtime.py::test_strategy_validation_report_reconciles_expected_cash_flow_and_account_equity -q`
  - R064 targeted result: `3 passed in 0.41s`
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_demo_preflight_uses_orderbook_expected_fill_price_not_limit_cap -q`
  - R065 focused result: `1 passed in 0.41s`
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_demo_execution_uses_spot_orderbook_for_marketable_limits tests/unit/test_strategy_runtime.py::test_strategy_runner_skips_unprofitable_demo_preflight_without_ordering -q`
  - R065 regression result: `2 passed in 0.34s`
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_platform.py::test_strategy_market_compare_is_read_only_and_explains_target_delta tests/integration/test_cli_core.py::test_cli_strategy_list_run_and_review tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -q`
  - R062 targeted result: `3 passed in 0.87s`
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_validation_report_summarizes_recent_receipt_pnl_and_residual_evidence tests/integration/test_cli_core.py::test_cli_strategy_list_run_and_review tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -q`
  - R059 targeted result: `3 passed in 0.87s`
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_platform.py::test_strategy_scan_reports_break_even_diagnostics_when_carry_filtered tests/integration/test_cli_core.py::test_cli_strategy_list_run_and_review -q`
  - R060 targeted result: `2 passed in 0.52s`
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_quality_gates_explain_basis_and_hedge_cost_filters tests/unit/test_strategy_platform.py::test_strategy_scan_reports_break_even_diagnostics_when_carry_filtered tests/unit/test_config.py::test_loads_safe_example_config tests/unit/test_config.py::test_loads_separate_okx_demo_and_live_configs -q`
  - R061 targeted result: `4 passed in 0.55s`
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_retrospective_does_not_improve_unobserved_strategy_issues tests/unit/test_strategy_runtime.py::test_strategy_retrospective_treats_transient_market_data_failure_as_improved_after_profit tests/unit/test_strategy_validation.py::test_validate_demo_window_fast_blocks_when_target_guard_is_cooling_down -q`
  - R058 targeted result: `3 passed in 0.48s`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy retrospective --help`
  - R054 CLI help result: exit 0.
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy retrospective --config ../configs/okx.demo.example.yaml --json`
  - R054 CLI JSON result: exit 0, `open_issue_count=4`, `repeated_issue_count=4`, `highest_severity=warning`, no orders sent.
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_retrospective_reports_optimization_pressure_for_repeated_preflight -q`
  - R055 targeted result: `1 passed`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy retrospective --config ../configs/okx.demo.example.yaml --json`
  - R055 CLI JSON result: exit 0, `optimization_pressure` contains 4 high-priority negative-preflight items with break-even gaps and guardrails.
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache uv run --project backend --offline pytest backend/tests/ -q`
  - R046 final result: `250 passed in 4.00s`
- `uv run pytest tests/unit/test_strategy_runtime.py tests/unit/test_strategy_validation.py tests/unit/test_config.py -q`
  - Latest targeted residual/demo validation result: `37 passed in 0.44s`
- `uv run pytest tests/ -q`
  - Latest full backend result: `274 passed in 9.29s`
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q`
  - Latest full backend result after R052: `275 passed in 9.00s`
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q`
  - Latest full backend result after R053: `275 passed in 7.62s`
- `uv run pytest tests/unit/test_ccxt_exchange_adapter.py tests/unit/test_exchange_market_account.py tests/integration/test_cli_core.py -q`
  - R050 targeted result: `19 passed in 0.57s`
- `uv run pytest tests/unit/test_strategy_runtime.py -q`
  - R051 targeted result: `27 passed in 0.72s`
- `uv run pytest tests/unit/test_strategy_runtime.py tests/unit/test_config.py -q`
  - R052 targeted result: `35 passed in 0.68s`
- `uv run ruff check src/ tests/`
  - Latest lint result: `All checks passed!`
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/`
  - Latest lint result after R052: `All checks passed!`
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/`
  - Latest lint result after R053: `All checks passed!`
- `uv run ruff check src/trading_assistant/strategies/demo_execution.py src/trading_assistant/config/schema.py tests/unit/test_strategy_runtime.py tests/unit/test_config.py`
  - R052 targeted lint result: `All checks passed!`
- `uv run ruff check src/trading_assistant/exchanges/ccxt.py src/trading_assistant/exchanges/factory.py src/trading_assistant/arbitrage/cross_exchange.py tests/unit/test_ccxt_exchange_adapter.py`
  - R050 targeted lint result: `All checks passed!`
- `uv run ruff check src/trading_assistant/strategies/guard.py src/trading_assistant/strategies/runner.py src/trading_assistant/config/schema.py tests/unit/test_strategy_runtime.py`
  - R051 targeted lint result: `All checks passed!`
- `uv run mypy src/`
  - Latest type-check result: `Success: no issues found in 93 source files`
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/`
  - Latest type-check result after R052: `Success: no issues found in 93 source files`
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/`
  - Latest type-check result after R053: `Success: no issues found in 93 source files`
- `uv run mypy src/trading_assistant/strategies/demo_execution.py src/trading_assistant/config/schema.py`
  - R052 targeted type-check result: `Success: no issues found in 2 source files`
- `uv run mypy src/trading_assistant/exchanges/ccxt.py src/trading_assistant/arbitrage/cross_exchange.py`
  - R050 targeted type-check result: `Success: no issues found in 2 source files`
- `uv run mypy src/trading_assistant/strategies/guard.py src/trading_assistant/strategies/runner.py src/trading_assistant/config/schema.py`
  - R051 targeted type-check result: `Success: no issues found in 3 source files`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`
  - R051 local precheck result: exit 0, `local_validation.status=Pass`, `executed=5`, `net_profit=4.967117651096646342373316272`.
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`
  - R051 OKX demo follow-up result: exit 0, `status=Needs More Samples`, `executed=1`, `skipped=4`, `net_profit=-0.032347`, no open spot orders, no open swap orders, no swap positions.
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy guard-status --config ../configs/okx.demo.example.yaml --execution-mode demo --json`
  - R051 OKX guard-status result: exit 0, no active cooldown; `triangular-multi-route` recorded one consecutive demo loss.
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant config validate --config ../configs/okx.demo.example.yaml --json`
  - R052 OKX demo config result: exit 0, credentials redacted, `strategy_runtime.demo_limit_price_buffer_pct=0.003`.
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`
  - R052 local precheck result: exit 0, `local_validation.status=Pass`, `executed=5`, `skipped=0`, `net_profit=4.967117651096646342373316272`.
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`
  - R052 OKX demo follow-up result: exit 0, `status=Needs More Samples`, `executed=1`, `skipped=4`, `wins=1`, `losses=0`, `net_profit=1.601695`, `max_drawdown_usdt=0`, complete receipts, residual inventory within tolerance, no open spot orders, no open swap orders, no swap positions.
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy guard-status --config ../configs/okx.demo.example.yaml --execution-mode demo --json`
  - R052 OKX guard-status result: exit 0, no active cooldown; `triangular-multi-route` recorded `last_reason=profitable_execution` and `last_net_profit=1.601695`.
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy guard-status --config ../configs/okx.demo.example.yaml --execution-mode demo --json`
  - R053 pre-run guard result: exit 0, no active cooldown before additional OKX demo windows.
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`
  - R053 local precheck result: exit 0, `local_validation.status=Pass`, `executed=5`, `skipped=0`, `net_profit=4.967117651096646342373316272`.
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 3 --symbol BTC/USDT --json`
  - R053 3-cycle OKX demo result: exit 0, `status=Needs More Samples`, `executed=3`, `skipped=12`, `wins=3`, `losses=0`, `net_profit=4.749252`, `max_drawdown_usdt=0`, and post-run no-open-risk checks passed.
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`
  - R053 second local precheck result: exit 0, `local_validation.status=Pass`, `executed=5`, `skipped=0`, `net_profit=4.967117651096646342373316272`.
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 10 --symbol BTC/USDT --json`
  - R053 10-cycle OKX demo result: exit 0, `status=Pass`, `executed=10`, `skipped=40`, `wins=10`, `losses=0`, `net_profit=15.863852`, `win_rate_pct=100.00`, `max_drawdown_usdt=0`, and post-run `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`.
- `tail -n 50 logs/okx-demo-strategy-events.jsonl | jq -s '{...}'`
  - R053 journal summary: latest 50 demo events had `executed=10`, `skipped=40`, `triangular-multi-route.net_profit=15.863852`, `receipt_incomplete=0`, `pnl_out_of_tolerance=0`, `residual_out_of_tolerance=0`, `max_residual_inventory_usdt=0.058822`.
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy review --config ../configs/okx.demo.example.yaml --execution-mode demo --json`
  - R053 review result: exit 0, `total_events=225`; `triangular-multi-route` has `executed=45`, `wins=44`, `losses=1`, `net_profit=71.827094`, `win_rate_pct=97.78`.
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy promotion-status --config ../configs/okx.demo.example.yaml --strategy all --json`
  - R053 promotion result: exit 0; `triangular-multi-route` local/demo `Pass`, live `Fail` because live-canary promotion, live trading, and agent live orders remain disabled. Other strategies remain demo `Needs More Samples` because current market data kept them preflight-skipped.
- `uv run pytest tests/ -q` from `backend/`
  - R047 final result after config/docs updates: `255 passed in 5.15s`
- `uv run pytest tests/unit/test_strategy_validation.py -q` from `backend/`
  - R047 targeted result: `4 passed in 0.58s`
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline pytest backend/tests/unit/test_strategy_runtime.py -q`
  - R044 targeted result: `17 passed in 0.34s`
- `uv run pytest tests/unit/test_strategy_runtime.py -q` from `backend/`
  - R047 targeted result: `19 passed in 0.37s`
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline pytest backend/tests/integration/test_cli_core.py -q`
  - R042 targeted result: `11 passed in 0.38s`
- `uv run pytest tests/integration/test_cli_core.py -q` from `backend/`
  - R047 targeted result: `12 passed in 0.66s`
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant strategy review --help`
  - exit 0; help includes `--execution-mode {paper,demo}` and `--json`.
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache uv run --project backend --offline ruff check backend/src backend/tests`
  - `All checks passed!`
- `uv run ruff check src/ tests/` from `backend/`
  - R047 final result: `All checks passed!`
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache uv run --offline mypy src/` from `backend/`
  - R046 final result: `Success: no issues found in 85 source files`
- `uv run mypy src/` from `backend/`
  - R049 final result: `Success: no issues found in 92 source files`
- Note: an initial `mypy backend/src` invocation from the repository root ignored `backend/pyproject.toml` and reported missing third-party stubs. The canonical backend-cwd command above passed.

## 7. CLI Acceptance Results

All required CLI commands were run successfully through the backend console script:

- `crypto-assistant --help`
- `crypto-assistant status`
- `crypto-assistant config validate --config configs/config.example.yaml`
- `crypto-assistant exchange list`
- `crypto-assistant exchange ping --exchange mock --json`
- `crypto-assistant exchange sandbox-check --config configs/okx.demo.example.yaml --exchange okx --symbol BTC/USDT --json`
- `crypto-assistant config validate --config configs/okx.demo.example.yaml`
- `crypto-assistant config validate --config configs/okx.live.example.yaml`
- `crypto-assistant market ticker --exchange mock --symbol BTC/USDT --json`
- `crypto-assistant market orderbook --exchange mock --symbol BTC/USDT --json`
- `crypto-assistant account balance --exchange mock --json`
- `crypto-assistant arbitrage scan --type cross-exchange --symbol BTC/USDT --json`
- `crypto-assistant arbitrage scan --type triangular --exchange mock --json`
- `crypto-assistant arbitrage scan --type funding-rate --json`
- `crypto-assistant arbitrage scan --type spot-perp --symbol BTC/USDT --json`
- `crypto-assistant arbitrage execute --opportunity-id test-opportunity --dry-run --json`
- `crypto-assistant agent live-readiness --config configs/config.example.yaml --opportunity-id test-opportunity --json`
- `crypto-assistant agent live-readiness --config configs/config.example.yaml --opportunity-file okx-opportunity.json --json`
- `crypto-assistant agent execute-live --config configs/config.example.yaml --opportunity-id test-opportunity --json`
- `crypto-assistant agent execute-live --config configs/config.example.yaml --opportunity-file okx-opportunity.json --json`
- `crypto-assistant agent operation-catalog --json`
- `crypto-assistant strategy list --json`
- `crypto-assistant strategy catalog --json`
- `crypto-assistant strategy scan --strategy all --symbol BTC/USDT --json`
- `crypto-assistant strategy score --strategy all --json`
- `crypto-assistant strategy portfolio-status --json`
- `crypto-assistant strategy run --config configs/config.example.yaml --strategy all --max-cycles 1 --interval-seconds 0 --execution-mode paper --json`
- `crypto-assistant strategy run --config configs/okx.demo.example.yaml --strategy all --max-cycles 1 --interval-seconds 0 --execution-mode demo --json`
- `crypto-assistant strategy review --config configs/config.example.yaml --json`
- `crypto-assistant strategy guard-status --config configs/config.example.yaml --execution-mode paper --json`
- `crypto-assistant strategy retrospective --config configs/okx.demo.example.yaml --json`
- `crypto-assistant strategy validation-report --config configs/okx.demo.example.yaml --execution-mode demo --strategy all --limit 50 --json`
- `crypto-assistant strategy validate-demo --config configs/okx.demo.example.yaml --strategy all --symbol BTC/USDT --allow-account-mode-switch --json`
- `crypto-assistant strategy validate-local --config configs/config.example.yaml --strategy all --cycles 1 --json`
- `crypto-assistant strategy validate-demo-window --config configs/okx.demo.example.yaml --strategy all --cycles 10 --json`
- `crypto-assistant strategy promotion-status --config configs/okx.demo.example.yaml --strategy all --json`
- `crypto-assistant backtest run --config configs/config.example.yaml --json`
- `crypto-assistant report generate --type daily --json`
- `crypto-assistant workflow run --config configs/config.example.yaml --symbol BTC/USDT --json`

In this uv workspace, the local invocation used `uv run --project backend --offline crypto-assistant ...` from the repository root.

Workflow acceptance result: exit 0, `completed=true`, `sandbox_readiness.ready=true`, `live_readiness.ready=false`, `agent_live_readiness.ready=false`, and no real orders sent.

Agent live-readiness acceptance result: exit 0, `agent_live_readiness.ready=false` under safe defaults. `agent execute-live` returns non-zero `SafetyError` under safe defaults and sends no real orders. Opportunity-file readiness/execution blockers are covered by integration tests. OKX exchange and dispatch behavior are covered by fake-client/fake-provider unit tests; OKX demo public/private read APIs were validated through `exchange sandbox-check`.

OKX sandbox-check acceptance result: unit tests validate successful fake-client public/private checks; CLI default config blocks because OKX remains disabled unless an operator explicitly uses `configs/okx.demo.example.yaml` or another OKX-enabled config. The command reports `live_orders_sent=false`.

OKX config split result: `configs/okx.demo.example.yaml` uses `sandbox=true`, `okx_demo=true`, `live_trading=false`, `dry_run=false`, `allow_demo_orders=true`, and `app.env_file=../.env.okx.demo`; `configs/okx.live.example.yaml` uses `sandbox=false`, `okx_demo=false`, `live_trading=true`, `dry_run=false`, `allow_live_orders=false`, and `app.env_file=../.env.okx.live`.

Operation catalog result: `crypto-assistant agent operation-catalog --json` returned `missing_demo_validation=[]` and listed demo/live command pairs for OKX sandbox checks and guarded OKX spot limit-order dispatch.

OKX demo API validation result: `crypto-assistant exchange sandbox-check --config configs/okx.demo.example.yaml --exchange okx --symbol BTC/USDT --json` returned exit 0 with public ping, ticker, orderbook, and spot/perp quote checks passing and `live_orders_sent=false`. The same command with `--include-private` returned exit 0 with private account read passing and `live_orders_sent=false`. A tiny OKX Demo Trading spot limit buy order (`BTC/USDT`, quantity `0.0001`, limit `79562.4`, required capital `7.9562 USDT`) was submitted through the guarded agent broker path, canceled immediately, and confirmed absent from open orders. `strategy validate-demo --allow-account-mode-switch` later returned `completed=true` after the demo account moved to `acctLv=3`; all four strategies submitted and canceled tiny OKX Demo Trading validation orders with `live_orders_sent=false`.

Earlier OKX demo strategy execution result: `crypto-assistant strategy run --config configs/okx.demo.example.yaml --strategy all --max-cycles 1 --interval-seconds 0 --execution-mode demo --json` returned exit 0 with `completed=true`. One tiny canary cycle produced `cross-exchange=-0.016063`, `triangular=0.376816`, `funding-rate=-0.016054`, `spot-perp=-0.032117`, total `0.312582 USDT`. Post-run check returned `provider_demo=true`, `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`, and `live_orders_sent=false`.

Earlier run/review/optimize/rerun result: a later all-strategy demo loop returned exit 0 and produced `cross-exchange=-0.016056`, `triangular=0.375936`, `funding-rate=-0.016047`, `spot-perp=-0.032103`, total `0.311730 USDT`. Review selected `triangular` as the only repeated demo path because the other three were cost-only round trips in that canary design. The optimized rerun `crypto-assistant strategy run --config configs/okx.demo.example.yaml --strategy triangular --max-cycles 1 --interval-seconds 0 --execution-mode demo --json` returned exit 0 with `net_pnl_usdt=0.375974`, `provider_demo=true`, and `live_orders_sent=false`.

Deferred optimization acceptance result: unit tests cover preflight skip-without-order behavior, demo stop-loss termination for multi-cycle runs, and `pnl_validation` reconciliation between order cash-flow net PnL and account-equity delta.

Earlier optimized OKX demo result: `crypto-assistant strategy run --config configs/okx.demo.example.yaml --strategy all --max-cycles 1 --interval-seconds 0 --execution-mode demo --json` skipped `cross-exchange`, `funding-rate`, and `spot-perp` through preflight without submitting orders, executed only `triangular`, and recorded `net_pnl_usdt=0.381294` with `pnl_validation.within_tolerance=true`. Post-run check returned `provider_demo=true`, `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`, and `live_orders_sent=false`.

Earlier OKX receipt reconciliation result: a later `strategy run --execution-mode demo` skipped `cross-exchange`, `funding-rate`, and `spot-perp` through preflight, executed only `triangular`, and recorded `net_pnl_usdt=0.383234`, `pnl_validation.within_tolerance=true`, and `pnl_validation.exchange_receipts.complete=true` with all 3 fills returned by OKX `fills-history`. Post-run check returned `provider_demo=true`, `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`, and `live_orders_sent=false`.

Earlier Stage-1 2x OKX demo result: after setting `configs/okx.demo.example.yaml` to `demo_order_size_multiplier=2` and `demo_max_order_value_usdt=20`, `strategy run --execution-mode demo` skipped `cross-exchange`, `funding-rate`, and `spot-perp` through preflight, executed only `triangular`, and recorded `net_pnl_usdt=0.750826`, `pnl_validation.within_tolerance=true`, and `exchange_receipts.complete=true`. Post-run check returned `provider_demo=true`, `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`, and `live_orders_sent=false`.

Stage-1 2x continuous sample result: `crypto-assistant strategy validate-demo-window --config configs/okx.demo.example.yaml --strategy all --cycles 10 --symbol BTC/USDT --json` returned exit 0 with `demo_window_validation.status=Pass`, `cycles_completed=10`, `executed=10`, `skipped=40`, `wins=10`, `losses=0`, `net_profit=16.549322`, `win_rate_pct=100.00`, and `max_drawdown_usdt=0`. The latest 50-event window had `triangular-multi-route:executed=10`; `cross-exchange`, `funding-carry-hedged`, `spot-perp-carry`, and `futures-perp-basis` were each skipped 10 times by `demo_preflight_not_profitable`. All triangular executions had `pnl_validation.within_tolerance=true`, `exchange_receipts.complete=true`, and `residual_inventory_within_tolerance=true`; the maximum residual inventory valuation was `0.025127 USDT` against a `0.10 USDT` tolerance. Post-run check returned `configured=true`, `demo=true`, `open_spot_orders=0`, `open_swap_orders=0`, and `swap_positions=0`.

Strategy runtime acceptance result: `crypto-assistant strategy list --json` now lists five canonical strategies. `crypto-assistant strategy catalog|scan|score|portfolio-status --json` returned exit 0 for the expanded strategy platform. `crypto-assistant strategy run --config configs/config.example.yaml --strategy all --max-cycles 1 --interval-seconds 0 --execution-mode paper --json` now completes one paper cycle across the expanded canonical set with no real orders. Historical OKX demo canary runs remain recorded above; current demo execution is restricted to demo-supported allowlisted paths and still performs preflight gating before OKX Demo Trading canary orders.

CCXT/cross-exchange acceptance result: `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant config validate --config ../configs/config.example.yaml --json`, `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant arbitrage scan --type cross-exchange --symbol BTC/USDT --json`, and `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy catalog --json` returned exit 0. The default cross-exchange scan still returns the mock `test-opportunity` path, while tests cover enabled fake CCXT exchange pairs without network or real API keys.

Stateful runtime guard acceptance result: targeted tests verified that consecutive demo losses persist to `strategy_runtime.runtime_guard_path`, trigger cooldown, and prevent the next run from calling the executor. R051 targeted tests also verified market-data and exchange rate-limit counters, cooldown after a simulated OKX `429` ticker failure, and counter reset after profitable execution. `crypto-assistant strategy guard-status --config configs/config.example.yaml --execution-mode paper --json` returned exit 0 and machine-readable entries with `cooldown_active` flags.

Previous OKX-only fill-failure follow-up result: after local validation passed with `executed=5` and `net_profit=4.967117651096646342373316272`, `strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json` returned exit 0. Demo status was `Needs More Samples` because the configured demo threshold is 10 executions and this was a one-cycle safety check. The run had `executed=1`, `skipped=4`, `net_profit=-0.032347`, and `max_drawdown_usdt=0.032347`; `triangular-multi-route` aborted/unwound after the ETH/BTC leg did not fill, `pnl_validation.within_tolerance=true`, `exchange_receipts.complete=true`, `residual_inventory_within_tolerance=true`, and post-run `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`. Follow-up `strategy guard-status --config ../configs/okx.demo.example.yaml --execution-mode demo --json` returned no active cooldown; `triangular-multi-route` had one consecutive demo loss. That result triggered the R052 orderbook-based pricing follow-up and still does not justify a size increase.

Latest OKX triangular fill-reliability result: after adding orderbook-based demo spot limit pricing and validating local first, `strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json` returned exit 0. Demo status remained `Needs More Samples` only because this was one demo execution against a 10-execution threshold. The run had `executed=1`, `skipped=4`, `wins=1`, `losses=0`, `net_profit=1.601695`, and `max_drawdown_usdt=0`; `triangular-multi-route` filled all three spot legs, `pnl_validation.within_tolerance=true`, `exchange_receipts.complete=true`, `residual_inventory_within_tolerance=true`, and post-run `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`. Follow-up `strategy guard-status --config ../configs/okx.demo.example.yaml --execution-mode demo --json` returned no active cooldown; `triangular-multi-route` recorded `last_reason=profitable_execution`.

Post-R052 OKX validation result: after a clean guard check and fresh local validation, a 3-cycle OKX demo window returned `executed=3`, `skipped=12`, `wins=3`, `losses=0`, `net_profit=4.749252`, and no post-run open risk. A subsequent 10-cycle OKX demo window returned `demo_window_validation.status=Pass`, `executed=10`, `skipped=40`, `wins=10`, `losses=0`, `net_profit=15.863852`, `win_rate_pct=100.00`, `max_drawdown_usdt=0`, `open_spot_orders=0`, `open_swap_orders=0`, and `swap_positions=0`. The latest 50 demo journal events had `receipt_incomplete=0`, `pnl_out_of_tolerance=0`, `residual_out_of_tolerance=0`, and `max_residual_inventory_usdt=0.058822`. `strategy promotion-status` shows `triangular-multi-route` local/demo `Pass` and live `Fail`; live remains blocked by design.

Strategy retrospective acceptance result: `crypto-assistant strategy retrospective --config ../configs/okx.demo.example.yaml --json` returned exit 0, refreshed `docs/plan/2026-05-09-refactor/28-strategy-retrospective.md`, and reported `open_issue_count=4`, `repeated_issue_count=4`, `highest_severity=warning`. The current open issues are all `demo_preflight_not_profitable` for strategies skipped by current OKX demo preflight. The same payload now includes 4 `optimization_pressure` items with break-even gaps: `cross-exchange=0.129325`, `funding-carry-hedged=0.258630`, `futures-perp-basis=0.258606`, and `spot-perp-carry=0.258630` USDT. No orders were sent and no safety gates changed. Integration tests also verify `strategy run --execution-mode paper --json` returns `retrospective_before`, `retrospective_after`, and `retrospective_path`, and `strategy review --json` returns `retrospective_summary`.

Latest targeted OKX demo validation result: after guard, portfolio, and local validation checks, `strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy triangular-multi-route --cycles 10 --symbol BTC/USDT --json` returned exit 0 with `demo_window_validation.status=Pass`, `cycles_completed=10`, `executed=10`, `skipped=0`, `wins=10`, `losses=0`, `net_profit=2.629326`, `win_rate_pct=100.00`, `max_drawdown_usdt=0`, complete receipts, PnL and residual inventory within tolerance, and post-run `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`. Historical demo review then reported `triangular-multi-route` `executed=58`, `wins=57`, `losses=1`, `net_profit=75.206223`, `win_rate_pct=98.28`. Live promotion remains Fail by design.

Rolling validation report acceptance result: `strategy validation-report --config ../configs/okx.demo.example.yaml --execution-mode demo --strategy all --limit 50 --json` returned exit 0 and read only the local strategy journal. The latest 50 demo events had `executed=19`, `skipped=31`, `wins=19`, `losses=0`, `realized_net_profit_usdt=12.904406`, `skipped_preflight_net_pnl_usdt=-5.689714`, `max_drawdown_usdt=0`, `receipt_incomplete=0`, `pnl_out_of_tolerance=0`, `residual_inventory_out_of_tolerance=0`, and `max_residual_inventory_usdt=0.058822`. Recommendations keep all non-triangular strategies blocked from demo execution until preflight net PnL turns positive.

Carry/basis diagnostics acceptance result: `strategy scan --config ../configs/config.example.yaml --strategy spot-perp-carry --symbol BTC/USDT --json` returned diagnostics with `net_profit_usdt=0.3799120175964807038592281543`, `min_required_net_profit_usdt=0.15`, `break_even_gap_usdt=0`, and `depth_sufficient=true`. `funding-carry-hedged` diagnostics showed `candidate_count=2`, `approved_count=1`, and the rejected `ETH/USDT` candidate had `break_even_gap_usdt=0.2753846153846153846153846154`. `futures-perp-basis` diagnostics showed `net_profit_usdt=0.3181094527363184079601990050`, `min_required_net_profit_usdt=0.15`, and `break_even_gap_usdt=0`. These commands are scan-only and sent no orders.

Carry/basis quality gates acceptance result: local `strategy scan` output now shows `spot-perp-carry` `basis_pct=0.4399120175964807038592281544` against `min_basis_pct=0.05`, `funding-carry-hedged` BTC `basis_hedge_cost_pct=0.02500` against max `0.30`, and the ETH candidate rejected by `basis_hedge_cost_above_maximum` plus `net_profit_below_minimum`. `futures-perp-basis` shows `futures_perp_basis_pct=0.3781094527363184079601990050` against `min_futures_basis_pct=0.05`. `strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json` returned Pass with `executed=5`, `skipped=0`, `blocked=0`, `wins=5`, and `net_profit=4.967117651096646342373316272`.

Three-layer validation acceptance result: `strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json` returned exit 0 with `local_validation.status=Pass`, `executed=5`, and `net_profit=4.967117651096646342373316272`. `strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 10 --symbol BTC/USDT --json` returned exit 0 after approved OKX demo network access with `demo_window_validation.status=Pass`, `executed=10`, `skipped=40`, `wins=10`, `losses=0`, `net_profit=16.549322`, `win_rate_pct=100.00`, `max_drawdown_usdt=0`, `pnl_validation.within_tolerance=true`, `exchange_receipts.complete=true`, `residual_inventory_within_tolerance=true`, `max_residual_inventory_usdt=0.025127`, and post-run `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`. The safe default config still blocks demo-window order execution when OKX demo is not enabled. `strategy promotion-status --config ../configs/okx.demo.example.yaml --strategy all --json` returned exit 0; `triangular-multi-route` has local/demo Pass and live Fail because live-canary gates remain disabled.

## 8. Risk Acceptance

- Risk manager is independent from execution.
- Oversized order checks are tested.
- Net profit, min profit, slippage, blacklist, exposure, and exchange availability checks are implemented.
- Execution refuses to continue when risk checks fail.
- Live execution path is guarded and not enabled by default.
- `workflow run` reports sandbox readiness as ready under mock dry-run settings and live plus agent live-readiness as not ready under safe defaults.
- Sandbox readiness now depends on execution-quality approval for opportunities that provide quality metadata.
- Agent live-readiness requires explicit autonomous-trading config, allowlisted strategy/exchange, non-mock exchange, environment credentials, operator id, daily/order-size caps, audit logging, risk approval, execution-quality approval, and kill switch not enabled.
- Strategy runtime defaults to paper mode, applies existing risk checks plus strategy capital/order controls, and records cancel/reprice lifecycle plans without enabling live trading.

## 9. Safety Check

- Default live trading: disabled.
- Default dry-run: enabled.
- Default autonomous agent live trading: disabled.
- Default mock exchange: enabled.
- Real trading requires `trading.live_trading=true`, `trading.dry_run=false`, enabled non-mock exchange, credentials from environment variables, and risk approval.
- Autonomous agent live trading additionally requires `agent_trading.enabled=true`, `agent_trading.allow_live_orders=true`, `trading.require_confirm_before_order=false`, allowlisted strategy/exchange, operator id, audit logging, execution-quality approval, daily/order caps, and kill switch off.
- OKX Demo Trading orders require `agent_trading.enabled=true`, `agent_trading.allow_demo_orders=true`, `trading.live_trading=false`, `trading.dry_run=false`, `trading.require_confirm_before_order=false`, `sandbox=true`, `okx_demo=true`, OKX demo credentials, operator id, audit logging, execution-quality approval, risk approval, and provider demo-mode match.
- OKX Demo Trading account-mode switching is allowed only through explicit `--allow-account-mode-switch`, only in provider demo mode, and only when no open orders or swap positions are present. OKX code `51070` is treated as a blocker requiring Web/App operator action.
- OKX Demo Trading strategy execution is allowed only through explicit `--execution-mode demo` with an OKX demo config; it uses tiny canary orders, account snapshots, PnL capture, and post-run open-order/position checks.
- OKX Demo Trading repeated strategy execution first requires a positive no-order preflight signal and is bounded by demo stop-loss/drawdown breakers.
- OKX Demo Trading spot limit prices use current orderbook best bid/ask plus a configured buffer; this improves fill probability without bypassing preflight, order caps, receipt reconciliation, residual-inventory checks, or abort/unwind logic.
- Strategy runtime additionally persists cross-run consecutive failure/loss/market-data/rate-limit counters and skips strategies in cooldown before any executor call.
- Strategy retrospective is read/write documentation and state only; it records repeated problems but does not place orders, change strategy parameters, disable guards, enable demo/live gates, or bypass local-first validation.
- Optimization pressure is advisory only; it does not lower preflight thresholds and explicitly says not to force demo orders when preflight is negative.
- Strategy review can be filtered to demo or paper mode; skipped and blocked estimates are not counted as realized profit.
- Executed OKX demo orders must have complete exchange receipts before any demo position-size escalation decision.
- Current OKX demo profile is stage-1 only: `demo_order_size_multiplier=2`, still demo-only and capped at 20 USDT per order.
- Further position-size increases are intentionally held after the latest 10-cycle 2x window; more market-regime-diverse samples are required before raising the multiplier again.
- Post-R052 10-cycle OKX Demo Trading validation passed at the current 2x stage, but this is still not enough to enable live trading or increase size.
- The latest targeted 10-cycle OKX Demo Trading validation also passed for `triangular-multi-route`, but it remains same-size evidence only and does not justify live trading or size increase by itself.
- The rolling validation report is read-only and does not access OKX APIs, place orders, edit guard state, edit retrospective state, or change configs.
- Carry/basis scan diagnostics are read-only and do not bypass OKX demo preflight or portfolio scoring.
- Carry/basis quality gates make local scanning stricter and do not lower OKX demo preflight thresholds.
- Three-layer promotion is advisory by default: `strategy_runtime.validation_allow_live_canary=false`, and local/demo pass results do not enable live trading.
- OKX spot broker dispatch additionally requires all opportunity legs to use `exchange=okx`, `market=spot`, valid side, positive limit price, and a configured OKX provider.
- CLI/report/config redaction avoids plaintext credential output.
- `.env.example` exists and contains no real secrets.
- `.env.okx.demo.example` and `.env.okx.live.example` exist and contain no real secrets.
- `.gitignore` ignores `.env`, `.env.okx.demo`, and `.env.okx.live`.

## 10. Documentation Directory Compliance

All refactor planning, task, traceability, acceptance, phase report, and final report documents are under:

`docs/plan/2026-05-09-refactor/`

`find docs/plan -maxdepth 1 -type f -print` returned no files.

Project-level exceptions are only:

- `AGENTS.md`
- `CLAUDE.md`

User-facing project docs updated outside the refactor directory:

- `README.md`
- `docs/DESIGN.md`

## 11. Hardcoded Secret Check

Command:

`rg -n -S "(api[_-]?key|api[_-]?secret|passphrase|token)\\s*[:=]\\s*['\\\"][A-Za-z0-9_\\-]{12,}" backend configs docs README.md AGENTS.md CLAUDE.md .env.example .env.okx.demo.example .env.okx.live.example`

Result: no hardcoded secret values found.

Live-switch scan:

`rg -n "allow_live_orders: true|validation_allow_live_canary: true|live_trading: true" backend configs README.md docs/DESIGN.md docs/plan/2026-05-09-refactor/99-final-acceptance-report.md AGENTS.md CLAUDE.md`

Result: aside from the scan command text in this report, `live_trading: true` appears only in `configs/okx.live.example.yaml` and unit-test fixtures; no default `allow_live_orders: true` or `validation_allow_live_canary: true` was found.

## 12. Mock / Dry-Run / Paper Trading Support

- Mock exchange is implemented.
- Dry-run execution is implemented and tested.
- Paper trading ledger is implemented and tested.
- Production strategy runtime paper execution is implemented and tested.
- Production strategy runtime OKX demo execution is implemented, tested with fake providers, and manually validated against OKX Demo Trading.

## 12.1 OKX-First Strategy Platform Addendum

Date: 2026-05-10

Implemented:

- Added `StrategyCatalog`, `StrategyController`, `StrategyScoreService`, and `StrategyPortfolioService`.
- Added canonical strategies `triangular-multi-route`, `spot-perp-carry`, `funding-carry-hedged`, and `futures-perp-basis`.
- Preserved compatibility aliases: `triangular`, `spot-perp`, and `funding-rate`.
- Extended mock exchange with SOL, swap, and dated futures fixtures.
- Extended OKX adapter interface with instrument metadata and futures basis quote methods.
- Added CLI commands:
  - `crypto-assistant strategy catalog --json`
  - `crypto-assistant strategy scan --strategy all --symbol BTC/USDT --json`
  - `crypto-assistant strategy score --strategy all --json`
  - `crypto-assistant strategy portfolio-status --json`

Validation:

- `UV_CACHE_DIR=.uv-cache uv run pytest tests/ -q` from `backend/`: `274 passed in 9.29s`.
- `UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/` from `backend/`: `All checks passed!`.
- `UV_CACHE_DIR=.uv-cache uv run mypy src/` from `backend/`: `Success: no issues found in 93 source files`.
- New CLI commands returned exit 0 for JSON output and exit 0 for `--help`.

Safety:

- New platform commands are scan/score/selection only and do not submit orders.
- New carry/basis strategies are scan/paper-first.
- OKX Demo Trading execution remains allowlisted and demo-capable only for supported canary paths.
- Live trading remains disabled by default and live-canary promotion remains disabled by `strategy_runtime.validation_allow_live_canary=false`.

## 12.2 Strategy Retrospective Addendum

Date: 2026-05-10

Implemented:

- Added `StrategyRetrospectiveService` for deterministic issue classification, deduplication, repeated-issue escalation, Markdown rendering, and JSON state persistence.
- Added `crypto-assistant strategy retrospective --config ... --json`.
- Added retrospective before/after/path payloads to `strategy run`, `strategy validate-local`, and `strategy validate-demo-window`.
- Added `retrospective_summary` to `strategy review --json`.
- Added config fields under `strategy_runtime.retrospective_*`.
- Added generated artifacts in the refactor directory:
  - `28-strategy-retrospective.md`
  - `28-strategy-retrospective.state.json`
  - `29-strategy-retrospective-system-report.md`

Validation:

- Targeted retrospective tests returned `5 passed in 0.45s`.
- Targeted retrospective ruff check returned `All checks passed!`.
- `crypto-assistant strategy retrospective --config ../configs/okx.demo.example.yaml --json` returned exit 0 and updated the retrospective document/state under `docs/plan/2026-05-09-refactor/`.

Safety:

- The retrospective system reads local evidence and writes only the configured retrospective document/state.
- It does not send orders, access OKX directly, change config, enable live trading, or weaken demo/live safety gates.

## 12.3 Retrospective-Driven Optimization Pressure Addendum

Date: 2026-05-10

Implemented:

- Added `optimization_pressure` to retrospective JSON summaries.
- Added `Strategy Optimization Pressure` to `28-strategy-retrospective.md`.
- Added `30-strategy-optimization-pressure-report.md`.
- Added unit and integration assertions for the new field.

Current output:

- 4 high-priority items, all from repeated `demo_preflight_not_profitable`.
- Break-even gaps:
  - `cross-exchange`: `0.129325 USDT`
  - `funding-carry-hedged`: `0.258630 USDT`
  - `futures-perp-basis`: `0.258606 USDT`
  - `spot-perp-carry`: `0.258630 USDT`

Safety:

- The output gives optimization direction only.
- It does not lower `demo_min_preflight_net_pnl_usdt`.
- It does not force OKX demo orders.
- It preserves local-first validation and live-disabled defaults.

## 12.4 Retrospective-Aware Portfolio Scoring Addendum

Date: 2026-05-10

Implemented:

- Added `strategy_runtime.retrospective_demo_preflight_score_penalty`, defaulting to `30`.
- Added the setting to safe, OKX demo, and OKX live example configs.
- Added `execution_mode` to retrospective `optimization_pressure` items.
- Updated strategy scorecards to consume repeated high-priority demo `preflight_not_profitable` pressure.
- Added score reasons `repeated_demo_preflight_not_profitable` and `demo_break_even_gap_usdt:*`.
- Updated portfolio selection so affected strategies can fall below `portfolio_min_score`.
- Added `32-retrospective-score-penalty-report.md`.

Current acceptance result:

- `crypto-assistant strategy portfolio-status --config ../configs/config.example.yaml --symbol BTC/USDT --json` returned exit 0.
- Current selected strategy: `triangular-multi-route`.
- `cross-exchange`, `spot-perp-carry`, `funding-carry-hedged`, and `futures-perp-basis` are blocked below the score floor because their repeated OKX demo preflight issues remain open.

Validation:

- Targeted unit/config/retrospective plus CLI portfolio-pressure tests returned `14 passed`.
- Targeted ruff check returned `All checks passed!`.
- Targeted mypy check returned `Success: no issues found in 3 source files`.
- Full backend test suite returned `284 passed in 8.41s`.
- Full backend ruff check returned `All checks passed!`.
- Full backend mypy returned `Success: no issues found in 94 source files`.

Safety:

- This change is score/selection only.
- It sends no orders and does not enable demo or live trading.
- It does not lower preflight thresholds.
- It makes the next run more conservative until the repeated demo preflight issues improve.
- Refactor document scan returned no files directly under `docs/plan`.
- Hardcoded secret scan returned no matches.
- Live-switch scan found only the known OKX live example, OKX demo dry-run-off config, report command text, and unit-test fixtures.

## 12.6 Targeted 10-Cycle OKX Demo Validation Addendum

Date: 2026-05-11

Implemented:

- Ran a same-size 10-cycle OKX Demo Trading validation window for the currently selected strategy `triangular-multi-route`.
- Kept the four strategies with repeated negative demo preflight pressure out of execution.
- Updated retrospective consistency so targeted runs only improve issues for observed strategy/execution-mode pairs.
- Added `34-demo-10-cycle-validation-2026-05-11.md`.

Run results:

- Pre-run guard: `triangular-multi-route` `cooldown_active=false`.
- Portfolio selection: only `triangular-multi-route`.
- Local validation: Pass, `executed=1`, `net_profit=3.6492041591681663667266546`, `win_rate_pct=100.00`, `max_drawdown_usdt=0`.
- OKX demo validation: Pass, `cycles_completed=10`, `executed=10`, `skipped=0`, `wins=10`, `losses=0`, `net_profit=2.629326`, `win_rate_pct=100.00`, `max_drawdown_usdt=0`.
- Per-cycle net PnL: `0.268557`, `0.250414`, `0.271760`, `0.266617`, `0.267841`, `0.252238`, `0.265390`, `0.264729`, `0.253457`, `0.268323`.
- All cycles had complete OKX fills-history receipts, PnL reconciliation within tolerance, residual inventory within tolerance, and post-run `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`.
- Historical demo review after the run: `triangular-multi-route` `executed=58`, `wins=57`, `losses=1`, `net_profit=75.206223`, `win_rate_pct=98.28`.
- Promotion status: local Pass, demo Pass, live Fail because live-canary, live trading, and agent live-order gates remain disabled.

Validation:

- Targeted R058 tests returned `3 passed in 0.48s`.
- Full backend test suite returned `287 passed in 9.37s`.
- Full backend ruff check returned `All checks passed!`.
- Full backend mypy returned `Success: no issues found in 94 source files`.
- Refactor document scan returned no files directly under `docs/plan`.
- Hardcoded secret scan returned no matches.

Safety:

- No live trading was enabled.
- No demo size increase was made.
- OKX Demo Trading orders were sent only after local validation and guard checks.
- Non-selected strategies remain visible in retrospective/portfolio pressure instead of being falsely marked improved.

## 12.7 Rolling Validation Report Addendum

Date: 2026-05-11

Implemented:

- Added `StrategyValidationReportService`.
- Added `crypto-assistant strategy validation-report --config ... --execution-mode demo --strategy all --limit 50 --json`.
- Added unit coverage for receipt/PnL/residual aggregation.
- Added integration coverage for CLI output and `--help`.
- Added `35-rolling-validation-report-2026-05-11.md`.

Current report:

- Exit code: `0`.
- Scanned events: `50`.
- Executed: `19`.
- Skipped: `31`.
- Wins: `19`.
- Losses: `0`.
- Realized executed PnL: `12.904406 USDT`.
- Skipped preflight PnL: `-5.689714 USDT`.
- Max drawdown: `0`.
- Receipt incomplete: `0`.
- PnL out of tolerance: `0`.
- Residual inventory out of tolerance: `0`.
- Max residual inventory: `0.058822 USDT`.
- Recommendations: keep `cross-exchange`, `funding-carry-hedged`, `futures-perp-basis`, and `spot-perp-carry` out of demo execution until preflight net PnL turns positive.

Validation:

- Targeted rolling-report tests returned `3 passed in 0.87s`.
- Targeted ruff check returned `All checks passed!`.
- Targeted mypy returned `Success: no issues found in 3 source files`.

Safety:

- Read-only local journal analysis.
- No exchange access.
- No order dispatch.
- No guard/config/retrospective mutation.

## 12.8 Carry/Basis Scan Diagnostics Addendum

Date: 2026-05-11

Implemented:

- Added `diagnose()` methods for `spot-perp-carry`, `funding-carry-hedged`, and `futures-perp-basis`.
- Added `ArbitrageScanner.diagnose(...)`.
- Added `StrategyScanReport.diagnostics`.
- Added score-card reasons from diagnostics:
  - `scan_diagnostic:<reason>`
  - `scan_break_even_gap_usdt:<value>`
  - `scan_candidate_net_profit_usdt:<value>`
- Added `36-carry-basis-scan-diagnostics-2026-05-11.md`.

Validation:

- Targeted scan-diagnostics tests returned `2 passed in 0.52s`.
- Targeted ruff check returned `All checks passed!`.
- Targeted mypy returned `Success: no issues found in 5 source files`.

Safety:

- Scan and score only.
- No OKX API access in the validation commands run for this change.
- No order dispatch.
- No demo/live gate changes.
- No preflight threshold changes.

## 12.9 Carry/Basis Quality Gates Addendum

Date: 2026-05-11

Implemented:

- Added `arbitrage.funding_min_annualized_pct`.
- Added `arbitrage.funding_max_basis_hedge_cost_pct`.
- Added `arbitrage.spot_perp_min_basis_pct`.
- Added `arbitrage.futures_basis_min_basis_pct`.
- Added filter reasons:
  - `basis_below_minimum`
  - `funding_annualized_below_minimum`
  - `basis_hedge_cost_above_maximum`
  - `futures_basis_below_minimum`
- Added `37-carry-basis-quality-gates-2026-05-11.md`.

Validation:

- Targeted quality-gate/config tests returned `4 passed in 0.55s`.
- Targeted ruff check returned `All checks passed!`.
- Targeted mypy returned `Success: no issues found in 4 source files`.
- Local validation returned Pass with `executed=5`, `skipped=0`, `blocked=0`, `wins=5`, and `net_profit=4.967117651096646342373316272`.

Safety:

- No OKX network access.
- No order dispatch.
- No demo/live gate changes.
- No threshold reduction.

## 12.10 OKX Read-Only Market Compare Addendum

Date: 2026-05-11

Implemented:

- Added `StrategyMarketComparisonService`.
- Added `crypto-assistant strategy market-compare`.
- Added mock-baseline versus target-exchange snapshots with per-strategy best net PnL, diagnostics, delta, and verdict.
- Added structured `scan_error:*` diagnostics so unavailable target market data conservatively returns `observe_only` instead of promoting demo preflight.
- Added `38-okx-read-only-market-compare-2026-05-11.md`.

Current OKX read-only result:

- Command: `crypto-assistant strategy market-compare --config configs/okx.demo.example.yaml --strategy all --symbol BTC/USDT --target-exchange okx --json`.
- Exit code: `0`.
- `read_only=true`.
- `orders_sent=false`.
- Demo-preflight candidates: `0`.
- `cross-exchange`: `observe_only`, no OKX cross-venue target pair.
- `triangular-multi-route`: `observe_only`, no current OKX route opportunity at configured thresholds.
- `funding-carry-hedged`: `observe_only`, blocked by `funding_annualized_below_minimum` and `net_profit_below_minimum`.
- `spot-perp-carry`: `observe_only`, blocked by `basis_below_minimum`, `funding_annualized_below_minimum`, and `net_profit_below_minimum`.
- `futures-perp-basis`: `observe_only`, blocked by `funding_annualized_below_minimum` and `net_profit_below_minimum`.

Validation:

- Targeted market-compare/CLI tests returned `3 passed in 0.87s`.
- Restricted-network smoke check returned exit code `0` with `diagnostic:scan_error:ConnectError` and `observe_only`.
- Targeted ruff check returned `All checks passed!`.
- Targeted mypy returned `Success: no issues found in 3 source files`.

Safety:

- Read-only scan context only.
- No journal writes.
- No retrospective updates.
- No order dispatch.
- No demo/live gate changes.
- Current evidence says to keep non-triangular strategies out of OKX demo orders until read-only market compare produces `demo_preflight_candidate`.

## 12.11 OKX Demo Validation After Optimization Addendum

Date: 2026-05-11

Run sequence:

- Local paper validation: Pass, `executed=5`, `wins=5`, `net_profit=4.967117651096646342373316272`.
- OKX read-only market compare: `read_only=true`, `orders_sent=false`, no broad `demo_preflight_candidate`.
- OKX demo validation window: `strategy validate-demo-window --config configs/okx.demo.example.yaml --strategy all --cycles 3 --symbol BTC/USDT --json`.

Demo window result:

- Status: `Needs More Samples`.
- Reason: `minimum_samples_not_met:3<10`.
- Cycles completed: `3`.
- Total strategy events: `15`.
- Executed: `3`.
- Skipped: `12`.
- Blocked: `0`.
- Wins: `3`.
- Losses: `0`.
- Net profit: `0.327664 USDT`.
- Win rate: `100.00`.
- Max drawdown: `0`.
- Post-run open risk: `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`.

Review after run:

- Latest 30 demo events: `executed=16`, `wins=16`, `realized_net_profit_usdt=3.706793`, `receipt_incomplete=0`, `pnl_out_of_tolerance=0`, `residual_inventory_out_of_tolerance=0`, `max_residual_inventory_usdt=0.058291`.
- Historical demo review: `triangular-multi-route` has `executed=61`, `wins=60`, `losses=1`, `net_profit=75.533887`, `win_rate_pct=98.36`.

Safety:

- Live trading remained disabled.
- Non-triangular strategies were skipped by `demo_preflight_not_profitable`.
- No demo/live gate was weakened.
- No size increase is justified from this run because the demo validation threshold still requires `10` executions.

## 12.12 PnL Reconciliation Audit Addendum

Date: 2026-05-11

Implemented:

- Audited the current OKX demo journal for the failure mode where strategy/order cash-flow PnL is positive while account equity is negative.
- Updated `StrategyRunner` so future executed OKX demo events preserve the approved preflight estimate in the journal.
- Updated `StrategyValidationReportService` to report approved preflight expected PnL, actual order cash-flow PnL, account-equity delta, account reconciliation gap, expected-vs-actual gap, missing preflight counts, and positive-cash-flow/negative-equity detections.
- Added `40-pnl-reconciliation-audit-2026-05-11.md`.

Audit result:

- Latest 20 executed OKX demo events had `sum_event_net_profit=10.063914`, `sum_cash_flow=10.063914`, `sum_equity_delta=11.872038`, `sum_account_reconciliation_gap=1.808116`, `max_abs_account_gap=0.091073`, complete receipts, PnL within tolerance, and residual inventory within tolerance.
- Latest 30-event validation report had `executed=16`, `actual_cash_flow_net_pnl_usdt=3.706793`, `account_equity_delta_usdt=5.150647`, `account_reconciliation_gap_usdt=1.443854`, `max_abs_account_reconciliation_gap_usdt=0.090500`, and `positive_cash_flow_negative_equity_delta=0`.
- `executed_preflight_missing=16` in that historical 30-event window, so older executed entries cannot be used as complete expected-vs-actual promotion evidence.

Validation:

- Targeted PnL reconciliation tests returned `3 passed in 0.41s`.
- Targeted ruff check returned `All checks passed!`.
- Targeted mypy returned `Success: no issues found in 2 source files`.
- Full backend test suite returned `292 passed in 7.89s`.
- Full backend ruff check returned `All checks passed!`.
- Full backend mypy returned `Success: no issues found in 96 source files`.
- Refactor document scan returned no files directly under `docs/plan`.
- Hardcoded secret scan returned no matches.

Safety:

- No orders were sent for this audit.
- The report command is read-only and did not access OKX.
- Live trading remained disabled.
- Future size or promotion decisions must use new samples that include approved preflight, cash-flow PnL, account-equity delta, residual inventory, and receipt evidence together.

## 12.13 Demo Preflight Fill-Price Optimization Addendum

Date: 2026-05-11

Implemented:

- Updated OKX demo preflight so expected PnL uses current top-of-book expected fill prices instead of marketable-limit protection prices.
- Kept submitted demo limit orders marketable by retaining `demo_limit_price_buffer_pct` as a protection cap.
- Added `submitted_limit_price`, `expected_fill_price`, `submitted_limit_notional_usdt`, and `estimated_notional_usdt` to preflight JSON.
- Added `41-demo-preflight-fill-price-optimization-2026-05-11.md`.

Post-optimization read-only preview:

- `triangular`: `net_pnl_usdt=0.067597`, approved.
- `cross-exchange`: `net_pnl_usdt=-0.032226`, skipped.
- `funding-carry-hedged`: `net_pnl_usdt=-0.065231`, skipped.
- `spot-perp-carry`: `net_pnl_usdt=-0.065131`, skipped.
- `futures-perp-basis`: `net_pnl_usdt=-0.065324`, skipped.

OKX Demo Trading result:

- Command: `crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`.
- Local validation: `Pass`.
- Demo status: `Needs More Samples` because `1<10`.
- Executed: `1`.
- Skipped: `4`.
- Executed strategy: `triangular-multi-route`.
- Approved preflight net PnL: `0.064467 USDT`.
- Actual order cash-flow PnL: `0.026190 USDT`.
- Expected-vs-actual gap: `-0.038277 USDT`.
- PnL reconciliation within tolerance: `true`.
- Exchange receipts complete: `true`.
- Residual inventory within tolerance: `true`.
- Post-run `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`.

Safety:

- Live trading remained disabled.
- No gate threshold was lowered.
- No demo size cap was increased.
- Non-triangular strategies remained skipped while their preflight PnL was negative.
- Whole-account marked-to-market equity after the run was about `97245.58046108809 USDT`; this movement includes BTC/ETH/OKB market-price drift and is tracked separately from strategy order cash-flow PnL.

## 12.5 OKX Demo Optimization Loop Addendum

Date: 2026-05-11

Implemented:

- Ran a fresh local-first optimization loop using the selected strategy `triangular-multi-route`.
- Added a demo-window guard precheck so `strategy validate-demo-window` fast-fails before runner execution when every requested strategy is already in runtime guard cooldown.
- Updated retrospective journal refresh so older transient market-data, rate-limit, and preflight failures are treated as improved when a later profitable execution exists for the same strategy and execution mode.
- Added `33-demo-run-optimization-2026-05-11.md`.

Run results:

- Local validation before demo: Pass, `executed=5`, `net_profit=4.967117651096646342373316272`.
- Current portfolio still selects only `triangular-multi-route`; the four non-selected strategies remain blocked by repeated OKX demo negative preflight pressure.
- First OKX demo attempt found the target strategy in runtime guard cooldown caused by an earlier network market-data failure; no orders were sent during that blocked window.
- After the guard cooldown naturally expired, `triangular-multi-route` ran 3 OKX Demo Trading cycles.
- Demo rerun result: `executed=3`, `wins=3`, `losses=0`, `net_profit=0.749803`, `win_rate_pct=100.00`, `max_drawdown_usdt=0`.
- Per-cycle net PnL: `0.246403`, `0.246880`, `0.256520`.
- All three cycles had PnL reconciliation within tolerance, complete OKX fills-history receipts, residual inventory within tolerance, and post-run `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`.
- Review after rerun reports historical demo `triangular-multi-route` stats: `executed=48`, `wins=47`, `losses=1`, `net_profit=72.576897`, `win_rate_pct=97.92`.
- Promotion status: local Pass, demo Pass, live Fail because live-canary, live trading, and agent live-order gates remain disabled.

Validation:

- Targeted guard/retrospective tests returned `2 passed`.
- Expanded targeted validation tests returned `8 passed`.
- Targeted ruff check returned `All checks passed!`.
- Targeted mypy returned `Success: no issues found in 2 source files`.
- Full backend test suite returned `286 passed in 9.95s`.
- Full backend ruff check returned `All checks passed!`.
- Full backend mypy returned `Success: no issues found in 94 source files`.

Safety:

- Live trading remained disabled.
- OKX Demo Trading orders were sent only after local validation passed and runtime guard cooldown naturally expired.
- No guard state was manually edited or bypassed.
- No demo size increase was made.
- The next evidence gap is sample count: run a 10-cycle triangular demo window before considering any size change.
- Refactor document scan returned no files directly under `docs/plan`.
- Hardcoded secret scan returned no matches.
- Live-switch scan found only the known OKX live example, OKX demo dry-run-off config, report command text, and unit-test fixtures.

## 12.6 Directional Demo Position Lifecycle Addendum

Date: 2026-05-12

Implemented:

- Replaced directional demo immediate round-trip behavior with a persisted managed long-only spot position lifecycle.
- Added `directional.position_state_path` in safe and OKX demo configs.
- Added `DirectionalPositionStore` for open/hold/closed position state.
- Passed local-validation context from `StrategyRunner` into demo preflight and execution so demo execution knows the selected directional symbol.
- Added directional preflight outcomes for entry, hold, and exit.
- Added take-profit, stop-loss, and time-limit exits for managed directional demo positions.
- Updated validation reporting so managed open directional positions are not counted as realized losses.

Validation:

- Targeted lifecycle tests returned `3 passed`.
- Relevant regression suite returned `63 passed`.
- Targeted ruff check returned `All checks passed!`.
- Full backend test suite returned `304 passed`.
- Full backend ruff check returned `All checks passed!`.
- Full backend mypy returned `Success: no issues found in 103 source files`.
- OKX Demo Trading lifecycle smoke test opened one managed `trend-breakout` BTC/USDT spot position (`0.0002 BTC`, filled at `81661.3107000000000001`, notional `16.332262 USDT`) after local validation passed, then a second run correctly returned `directional_position_hold` with no duplicate order.
- `strategy validation-report --config ../configs/okx.demo.example.yaml --execution-mode demo --strategy trend-breakout --limit 5 --json` returned exit 0 after the managed-position fix and reported `execution_quality_passed=true`.

Safety:

- Live trading remains disabled.
- Directional demo execution remains OKX-demo-only, long-only spot, and allowlist gated.
- No demo size cap was increased.
- No guard, risk, or profitability threshold was weakened.
- Reverse-signal exits remain a follow-up; implemented exits are take-profit, stop-loss, and time limit.

## 12.7 Strategy Evolution System Addendum

Date: 2026-05-12

Implemented:

- Added a simulation-only `StrategyEvolutionService` that classifies strategies as `champion`, `active`, `watchlist`, `probation`, `archived`, or `revive_candidate`.
- Added `crypto-assistant strategy evolve --json`.
- Added `evolution_after` and `evolution_path` to `strategy run`, `strategy validate-local`, and `strategy validate-demo-window`.
- Added soft archive state in `docs/plan/2026-05-09-refactor/45-strategy-evolution.state.json` and a living report in `docs/plan/2026-05-09-refactor/45-strategy-evolution.md`.
- Wired evolution state into strategy scoring and portfolio selection so archived strategies are blocked by `strategy_archived_by_evolution` until profitable simulated evidence marks them as revival candidates.
- Updated README, design notes, traceability, task tracking, and acceptance checklist.

Current simulation result:

- Command: `crypto-assistant strategy evolve --config configs/config.example.yaml --strategy all --execution-mode paper --limit 50 --json`.
- `orders_sent=false`, `live_orders_sent=false`, `simulation_only=true`.
- Promoted from recent paper evidence: `triangular-multi-route`, `spot-perp-carry`, `funding-carry-hedged`, `futures-perp-basis`, and `cross-exchange`.
- Latest archived strategies: none.
- Latest revival candidates: none; archive/revival behavior is covered by unit tests and remains available when a previously archived strategy later becomes profitable in paper/demo evidence.
- Watchlist due to insufficient or missing simulated samples: `trend-breakout`, `momentum-rotation`, `mean-reversion-spot`, `volatility-squeeze-breakout`, and `orderbook-imbalance-scalp`.
- Portfolio status after evolution selected `triangular-multi-route`, `momentum-rotation`, and `trend-breakout`; archived strategies would be blocked before selection.

Validation:

- Targeted evolution tests returned `4 passed`.
- Strategy runtime/platform/CLI regression subset returned `68 passed`.
- Targeted ruff check returned `All checks passed!`.
- Targeted mypy returned `Success: no issues found in 104 source files`.
- Full backend verification after R068 returned `307 passed in 18.67s`, `ruff` clean, and `mypy` clean.
- Read-only OKX demo validation report scanned `50` demo journal events with `20` executed, `30` skipped, `3.667118 USDT` realized demo cash-flow PnL, `execution_quality_passed=true`, `receipt_incomplete=0`, `pnl_out_of_tolerance=0`, and `positive_cash_flow_negative_equity_delta=0`.
- Document directory scan returned no files directly under `docs/plan` and no stray refactor docs under `backend/docs`.
- Hardcoded key/secret/passphrase/token pattern scan returned no matches outside ignored local env/log/cache paths.

Safety:

- No live trading was enabled.
- The evolution command is advisory and simulation-only.
- Archive is state, not code deletion.
- No strategy parameter is changed automatically.
- No OKX demo order was sent by the evolution command itself.

## 12.8 Strategy Evolution Follow-Ups Addendum

Date: 2026-05-12

Implemented:

- Added advisory parameter mutation candidates to `strategy evolve --json`.
- Added recent journal-derived `market_regime` tags to evolution state and report output. This was superseded in 12.9 by completed-candle-derived regime tagging.
- Added `crypto-assistant strategy revival-window --json`.
- Added `StrategyRevivalWindowService`, which selects only current `revive_candidate` strategies, runs local validation first, and only then attempts a bounded OKX demo validation window after demo safety gates pass.
- Added `docs/plan/2026-05-09-refactor/47-strategy-evolution-followups-report.md`.

Current simulation result:

- Command: `crypto-assistant strategy evolve --config configs/config.example.yaml --strategy all --execution-mode paper --limit 50 --json`.
- `orders_sent=false`, `live_orders_sent=false`, `simulation_only=true`.
- Market-regime source: `journal`.
- Market-regime sample count: `50`.
- Dominant tag: `unknown`; counts were `unknown=47`, `trend_up=3`.
- Parameter candidates generated for watchlist strategies: `momentum-rotation`, `trend-breakout`, `mean-reversion-spot`, `orderbook-imbalance-scalp`, and `volatility-squeeze-breakout`.
- Command: `crypto-assistant strategy revival-window --config configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`.
- Current revival candidates: none, so `orders_sent=false`, `live_orders_sent=false`, and no OKX demo validation was attempted.
- The same no-candidate check against `configs/okx.demo.example.yaml` also returned `orders_sent=false` and `live_orders_sent=false`.

Validation:

- Targeted follow-up tests returned `5 passed`.
- Targeted ruff check returned `All checks passed!`.
- Targeted mypy returned `Success: no issues found in 4 source files`.
- Full backend verification after R069 returned `310 passed in 16.97s`, `ruff` clean, and `mypy` clean across `105` source files.
- Document directory scan returned no files directly under `docs/plan` and no stray refactor docs under `backend/docs`.
- Hardcoded key/secret/passphrase/token pattern scan returned no matches outside ignored local env/log/cache paths.
- Integration/e2e tests now use temporary evolution report/state paths, so test runs do not overwrite the living strategy evolution state in the refactor directory.

Safety:

- Live trading remains disabled.
- Parameter candidates are advisory only and do not modify config automatically.
- `revival-window` does nothing when there are no `revive_candidate` strategies.
- If candidates exist, `revival-window` is local-first and OKX-demo-gated.
- No OKX demo orders were sent during the no-candidate check.

## 12.9 Candle Regime And Candidate Backtest Addendum

Date: 2026-05-12

Implemented:

- Added completed-candle market-regime classification in `backend/src/trading_assistant/strategies/market_regime.py`.
- Updated `strategy evolve` so `market_regime` is derived from completed OHLCV candle features instead of mostly journal hints.
- Added isolated candidate backtesting in `backend/src/trading_assistant/strategies/candidate_backtest.py`.
- Added `crypto-assistant strategy candidate-backtest --json`.
- Candidate backtests materialize parameter overrides into temporary YAML config copies, isolate journal/guard/retrospective/evolution paths, compare baseline/candidate metrics, and discard temporary files after the run.
- Added `docs/plan/2026-05-09-refactor/48-candle-regime-candidate-backtest-report.md`.

Current simulation result:

- Command: `crypto-assistant strategy evolve --config configs/config.example.yaml --strategy all --execution-mode paper --limit 50 --json`.
- `orders_sent=false`, `live_orders_sent=false`, `simulation_only=true`.
- `market_regime.source=candles`, `exchange=mock`, `tag=trend_up`, `symbol_count=6`, `sample_count=720`.
- Regime counts: `trend_up=5`, `trend_down=1`.
- Command: `crypto-assistant strategy candidate-backtest --config configs/config.example.yaml --strategy trend-breakout --symbol BTC/USDT --limit 50 --json`.
- `orders_sent=false`, `live_orders_sent=false`, `checked_in_config_modified=false`, `candidate_count=1`.
- Candidate `trend-breakout-watchlist-candidate-v1` materialized a temporary config, did not persist it, and compared baseline/candidate net PnL at `1.524057 USDT` with `delta=0.000000 USDT`.

Validation:

- Targeted candle-regime/candidate-backtest/CLI tests returned `3 passed`.
- Targeted ruff check returned `All checks passed!`.
- Targeted mypy returned `Success: no issues found in 5 source files`.
- Full backend verification returned `312 passed in 17.94s`, `ruff` clean, and `mypy` clean across `107` source files.
- Document directory scans returned no files directly under `docs/plan` and no stray refactor docs under `backend/docs`.
- Hardcoded key/secret/passphrase/token pattern scan returned no matches outside ignored local env/log/cache paths.

Safety:

- No live trading was enabled.
- No OKX demo orders were sent.
- Candidate parameter changes remain advisory and isolated.
- Checked-in config files were not mutated by candidate backtests.
- Completed-candle filtering ignores unfinished candles for regime classification.

## 12.10 Read-Only Market Config Diagnostics Addendum

Date: 2026-05-12

Implemented:

- Added `--config` support to read-only diagnostics commands:
  - `exchange list`
  - `exchange ping`
  - `market ticker`
  - `market orderbook`
  - `market candles`
  - `account balance`
- Added `docs/plan/2026-05-09-refactor/49-readonly-market-config-diagnostics-report.md`.
- Updated README and design notes with OKX demo config examples for read-only K-line diagnostics.

Current scan result:

- OKX read-only sweep across `BTC/USDT`, `ETH/USDT`, `SOL/USDT`, `XRP/USDT`, `DOGE/USDT`, and `ADA/USDT` found no `demo_preflight_candidate`.
- All strategies remained `observe_only`.
- No OKX demo order was sent.
- Candidate backtest remains advisory only; `momentum-rotation` and `trend-breakout` look useful in mock backtests but did not pass current OKX read-only/demo gates.

Validation:

- `market candles --config ../configs/okx.demo.example.yaml --exchange okx --symbol BTC/USDT --bar 15m --limit 5 --json` returned completed OKX candles.
- Targeted integration test returned `1 passed`.
- Targeted ruff check returned `All checks passed!`.
- Targeted mypy returned `Success: no issues found in 1 source file`.
- Full backend verification returned `312 passed in 15.71s`, `ruff` clean, and `mypy` clean across `107` source files.
- Document directory scans returned no files directly under `docs/plan` and no stray refactor docs under `backend/docs`.
- Hardcoded key/secret/passphrase/token pattern scan returned no matches outside ignored local env/log/cache paths.

Safety:

- The added CLI options are read-only diagnostics.
- Live trading remains disabled.
- No demo/live gate was weakened.
- OKX demo/live config separation is preserved.

## 12.11 Opportunity Density And Route Discovery Addendum

Date: 2026-05-13

Implemented:

- Added `crypto-assistant strategy opportunity-report --config ... --window 24h --json`.
- Added `crypto-assistant strategy discover-routes --config ... --exchange okx --quote USDT --json`.
- Added `crypto-assistant strategy scan --strategy triangular-multi-route --exchange okx --route-mode discovered --json`.
- Added instrument-driven triangular route discovery that keeps configured routes as priority routes, expands from spot instruments and bulk OKX spot tickers when available, and reports accepted plus filtered route candidates.
- Upgraded `triangular-multi-route` opportunity metadata with multi-level orderbook expected fill prices, submitted limit prices, depth-consumed percentages, fee/slippage estimates, and min-size adjustment evidence.
- Added opportunity-density aggregation from the strategy journal: scan count, opportunity count, demo preflight candidate count, pass rate, skipped reasons, average expected edge, average realized PnL, expected-vs-actual gap, account-equity delta, route/symbol distribution, observation-pool gaps, and demo size-stage readiness.
- Added `docs/plan/2026-05-09-refactor/50-opportunity-density-route-discovery-report.md`.

Validation:

- Targeted tests passed:
  - `test_new_okx_first_arbitrage_scanners_return_paper_opportunities`
  - `test_triangular_route_discovery_expands_and_explains_mock_routes`
  - `test_opportunity_density_report_aggregates_expected_actual_and_break_even_gaps`
  - `test_cli_strategy_list_run_and_review`
  - `test_cli_strategy_retrospective_empty_history`
- `crypto-assistant strategy discover-routes --config ../configs/config.example.yaml --exchange mock --quote USDT --json` returned accepted mock triangular routes and filtered-route reasons with `orders_sent=false`.
- `crypto-assistant strategy scan --config ../configs/config.example.yaml --strategy triangular-multi-route --exchange mock --route-mode discovered --json` returned discovered-route triangular opportunities with multi-level fill metadata.
- `crypto-assistant strategy opportunity-report --config ../configs/config.example.yaml --window 24h --json` returned read-only journal opportunity-density metrics with `orders_sent=false`.
- Full backend verification returned `314 passed`, `ruff` clean, and `mypy` clean.
- Document directory scan returned no files directly under `docs/plan`.
- Hardcoded key/secret/passphrase/token scan returned no matches outside ignored local env/log/cache paths.
- `ruff check src/ tests/` passed.
- `mypy src/` passed across `109` source files.

Safety:

- The new commands are read-only unless a separate existing `strategy run`/validation command is invoked.
- No OKX demo order was sent by this addendum.
- No live/demo gate was weakened.
- Demo size-stage readiness now explicitly blocks size increase when recent demo sample quality is insufficient, including historical `executed_preflight_missing`.

## 13. Follow-Up Optimizations

- Install and validate `ccxt` in controlled Binance/Bybit sandbox or read-only environments before enabling those configs.
- Keep rerunning `strategy validate-demo --allow-account-mode-switch` after any future OKX broker or strategy execution change.
- Keep rerunning `strategy run --execution-mode demo` after any future strategy execution change and compare PnL, account-equity delta, and `fills-history` receipt completeness against the journal.
- Keep running more 2x OKX demo sample windows before any further size increase; require complete receipts, no open orders/positions, residual inventory below tolerance, no drawdown breaker, and stable positive realized PnL.
- Use `strategy promotion-status` as the operator/Agent checkpoint before any live-canary discussion; keep `validation_allow_live_canary=false` until longer demo windows pass.
- Add swap/perp broker support only after hedge semantics and sandbox tests are implemented.
- Add persisted paper ledger storage.
- Add richer backtest data ingestion and strategy configuration.
- Add structured report export files under a configured output directory.
- Check `strategy guard-status --config configs/okx.demo.example.yaml --execution-mode demo --json` before each longer OKX demo window and keep cooldowns intact when rate-limit or market-data counters trip.
- Watch the next several OKX triangular demo windows specifically for middle-leg fill reliability under orderbook-based pricing before any size increase.
- Read `docs/plan/2026-05-09-refactor/28-strategy-retrospective.md` before each strategy execution or optimization session and resolve repeated open issues before increasing demo size.
- Use `optimization_pressure` break-even gaps to tune carry/basis entry filters; do not lower demo preflight below zero or force negative-preflight strategies into OKX demo.
- Keep retrospective-aware scoring enabled so repeated negative OKX demo preflight can block affected strategies below the portfolio score floor until evidence improves.
- Keep the demo-window guard precheck intact so cooldown windows do not burn validation cycles or make avoidable post-run network checks.
- Run another `triangular-multi-route` OKX demo window at the same size across a different market condition before any size increase.
- Keep using `strategy validation-report` before every future OKX demo size or promotion decision, and require new samples with persisted approved preflight estimates before claiming expected-vs-actual PnL alignment.
- Use read-only `market candles --config configs/okx.demo.example.yaml` plus `strategy market-compare` to diagnose OKX directional candidates before any demo order attempt.
- Persist spread samples and funding observations from real market data once real exchange adapters are added.
- Wire strategy-specific OKX demo brokers for the four strategies after real-market scanner validation; do not enable demo strategy execution by label alone.
- Keep `spot-perp-carry`, `funding-carry-hedged`, and `futures-perp-basis` at tiny OKX demo canary size until real-market preflight turns profitable and longer local/demo samples prove clean receipts, residual inventory below tolerance, and acceptable drawdown.
- Run `strategy market-compare --config configs/okx.demo.example.yaml --strategy all --target-exchange okx --json` before every future OKX demo execution attempt and only consider demo orders for strategies that return `demo_preflight_candidate`.
- Run `strategy opportunity-report --config configs/okx.demo.example.yaml --window 24h --json` before any size-stage discussion to confirm candidate density, expected-vs-actual quality, and size readiness.
- Run `strategy discover-routes --config configs/okx.demo.example.yaml --exchange okx --quote USDT --json` before triangular scans so filtered-route reasons can guide OKX universe expansion without forcing orders.
- Use `strategy evolve --execution-mode paper` and later `--execution-mode demo` before each strategy pool change; archived strategies should return only through profitable simulated evidence, not manual preference.
- When a real `revive_candidate` appears, run `strategy revival-window` with `configs/okx.demo.example.yaml` only after confirming local validation and runtime guard state are clean.

## 14. Delivery Decision

Meets the current deliverable standard for the offline safe refactor core, OKX Demo Trading validation of supported canary paths, controlled OKX Demo Trading execution/PnL canary cycles including run/review/optimize/rerun loops, orderbook-based OKX triangular demo fill-reliability hardening, the three-layer local/demo/live-canary validation gate, the OKX-first strategy platform with expanded pure-arbitrage scan/paper coverage, OKX spot directional strategies with persisted managed demo position lifecycle, the read-only mock-vs-OKX market comparison gate before demo preflight, read-only opportunity-density reporting, instrument-driven triangular route discovery, discovered-route triangular scans with multi-level fill evidence, read-only market/account diagnostics with explicit separated config loading, the non-blocking strategy retrospective memory, retrospective-driven optimization pressure, retrospective-aware strategy scoring, the simulation-only strategy evolution system for promotion/archive/revival decisions, advisory parameter candidates, completed-candle-derived market-regime tags, isolated temporary-config candidate backtests, local-first revival windows for revive candidates, guard-hygienic demo validation that avoids empty cooldown windows, the latest same-size 10-cycle targeted triangular OKX demo validation, the PnL reconciliation audit separating expected preflight, order cash-flow, and account-equity evidence, and the demo preflight fill-price optimization that produced a new positive triangular OKX demo canary without weakening gates. Broader real exchange/live trading work remains explicitly deferred and documented.
