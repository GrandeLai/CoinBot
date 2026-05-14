# Crypto Assistant Refactor Task Checklist

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development for implementation and verification-before-completion before status claims. Keep all refactor tracking documents in `docs/plan/2026-05-09-refactor/`.

**Goal:** Build a safe local-first crypto quantitative trading assistant loop: config loading -> mock exchange -> market data -> arbitrage scan -> risk check -> dry-run execution -> reporting -> CLI JSON output -> unit/integration/e2e tests, plus controlled agent live-readiness gates that never send real orders by default.

**Architecture:** Add a focused `trading_assistant` Python package under `backend/src` so it can coexist with the current FastAPI backend. Keep exchange access behind interfaces, put business logic in services, and expose a thin argparse CLI via the `crypto-assistant` console script.

**Tech Stack:** Python 3.12, Pydantic v2, PyYAML, python-dotenv, argparse, pytest, Decimal arithmetic.

---

## Phase 0: Project Inventory And Governance

- [x] Create `docs/plan/2026-05-09-refactor/`.
- [x] Copy original spec to `docs/plan/2026-05-09-refactor/00-refactor-spec.md`.
- [x] Update `AGENTS.md`.
- [x] Create `CLAUDE.md`.
- [x] Create task checklist, acceptance checklist, and traceability matrix in the refactor directory.
- [x] Write `04-phase-0-report.md`.

## Phase 1: Foundation Package

- [x] Add `backend/src/trading_assistant` package.
- [x] Add unified exception types.
- [x] Add config schema, YAML loader, env override support, `.env` support, and redacted dumps.
- [x] Add logging setup with redaction.
- [x] Add `configs/config.example.yaml` and update `.env.example`.
- [x] Add unit tests for config, validation, logging redaction, and exceptions.
- [x] Run Phase 1 tests and record results.
- [x] Write `05-phase-1-report.md`.

## Phase 2: CLI Foundation

- [x] Add thin CLI entrypoint and `crypto-assistant` console script.
- [x] Implement `status`.
- [x] Implement `config validate`.
- [x] Ensure help, clear errors, non-zero failures, and JSON mode.
- [x] Add CLI unit/integration tests.
- [x] Run Phase 2 tests and record results.
- [x] Write `06-phase-2-report.md`.

## Phase 3: Exchange Adapter Layer

- [x] Add exchange interface and shared exchange data models.
- [x] Add mock exchange with deterministic offline data.
- [x] Add exchange factory and placeholder real-exchange guard.
- [x] Implement `exchange list` and `exchange ping`.
- [x] Add unit/integration tests.
- [x] Run Phase 3 tests and record results.
- [x] Write `07-phase-3-report.md`.

## Phase 4: Market And Account Modules

- [x] Add market data service for ticker and orderbook.
- [x] Add account service for balances.
- [x] Implement CLI market/account commands.
- [x] Add unit/integration tests.
- [x] Run Phase 4 tests and record results.
- [x] Write `08-phase-4-report.md`.

## Phase 5: Arbitrage Scanning

- [x] Add arbitrage opportunity model.
- [x] Add fee, slippage, depth, and risk score calculations.
- [x] Add cross-exchange scanner.
- [x] Add triangular scanner.
- [x] Add funding-rate scanner.
- [x] Add spot-perp scanner.
- [x] Implement `arbitrage scan`.
- [x] Add unit/integration tests.
- [x] Run Phase 5 tests and record results.
- [x] Write `09-phase-5-report.md`.

## Phase 6: Risk And Execution

- [x] Add risk manager with configured limits.
- [x] Add order simulator.
- [x] Add dry-run execution engine.
- [x] Add paper trading ledger.
- [x] Implement `arbitrage execute`.
- [x] Add unit/integration tests.
- [x] Run Phase 6 tests and record results.
- [x] Write `10-phase-6-report.md`.

## Phase 7: Backtesting

- [x] Add backtest metrics.
- [x] Add deterministic mock backtest engine.
- [x] Implement `backtest run`.
- [x] Add unit/integration tests.
- [x] Run Phase 7 tests and record results.
- [x] Write `11-phase-7-report.md`.

## Phase 8: Reporting

- [x] Add report formatter.
- [x] Add daily report generator.
- [x] Implement `report generate`.
- [x] Add unit/integration tests.
- [x] Run Phase 8 tests and record results.
- [x] Write `12-phase-8-report.md`.

## Phase 9: Documentation And Final Acceptance

- [x] Update `README.md`.
- [x] Update `docs/DESIGN.md` summary.
- [x] Run unit, integration, and e2e tests.
- [x] Run CLI acceptance commands.
- [x] Check safety defaults and hardcoded secret patterns.
- [x] Add controlled agent live-readiness config, CLI, audit, kill switch, and tests.
- [x] Wire OKX spot broker dispatch behind agent live-trading gates with fake-provider unit tests.
- [x] Add OKX exchange adapter with fake-client tests.
- [x] Add `--opportunity-file` path for agent live-readiness and execute-live.
- [x] Add non-order OKX sandbox-check command and safe sandbox example config.
- [x] Split OKX simulated-trading and live-trading into separate config files.
- [x] Add separate local dotenv examples for OKX demo and live credentials.
- [x] Add operation validation hub and CLI catalog for demo/live operation parity.
- [x] Add production strategy runtime for all four arbitrage strategies.
- [x] Add strategy position caps, order TTL, cancel/reprice lifecycle plans, JSONL journal, review, and advisory learning.
- [x] Add `strategy list`, `strategy run`, and `strategy review` CLI commands.
- [x] Add demo strategy preflight gating, stop-loss/drawdown breakers, and PnL reconciliation.
- [x] Add OKX fills-history receipt reconciliation before considering larger demo position size.
- [x] Add stage-1 OKX demo size increase through `demo_order_size_multiplier=2` after receipt reconciliation.
- [x] Run a stage-1 2x continuous OKX demo sample window and record PnL, receipt, and no-open-risk evidence.
- [x] Add stateful strategy runtime guard for consecutive failures/losses with cooldown and CLI status output.
- [x] Add three-layer strategy validation commands: local paper validation, OKX demo validation window, and promotion status.
- [x] Add promotion thresholds under `strategy_runtime.validation_*` with live-canary promotion disabled by default.
- [x] Add unit/integration tests for validation service and CLI promotion gates.
- [x] Add OKX-first strategy platform: catalog, controller, scoring, and portfolio selection.
- [x] Add new scan/paper arbitrage strategies: `triangular-multi-route`, `spot-perp-carry`, `funding-carry-hedged`, and `futures-perp-basis`.
- [x] Add strategy platform CLI commands: `strategy catalog`, `strategy scan`, `strategy score`, and `strategy portfolio-status`.
- [x] Add unit/integration/e2e tests for the expanded strategy platform.
- [x] Write `20-arbitrage-strategy-platform-design.md`, `21-arbitrage-strategy-platform-plan.md`, and `22-arbitrage-strategy-platform-report.md`.
- [x] Expand OKX demo canary validation to `funding-carry-hedged`, `spot-perp-carry`, and `futures-perp-basis`.
- [x] Enforce first-layer local validation before `strategy validate-demo` and `strategy validate-demo-window`.
- [x] Add demo execution stop/unwind behavior for unfilled strategy legs.
- [x] Write `23-okx-demo-expanded-strategy-execution-report.md`.
- [x] Add OKX runtime guard hardening for market-data and rate-limit failures before longer demo runs.
- [x] Write `25-okx-runtime-guard-hardening-report.md`.
- [x] Improve OKX triangular demo fill reliability with orderbook-based spot marketable-limit pricing.
- [x] Write `26-okx-triangular-fill-reliability-report.md`.
- [x] Run post-R052 local-first OKX demo 3-cycle and 10-cycle validation windows without increasing position size.
- [x] Write `27-okx-demo-post-r052-validation-report.md`.
- [x] Add non-blocking strategy retrospective system with auto-updated Markdown/state memory.
- [x] Add `strategy retrospective --json` plus `retrospective_before/after/path` on strategy run and validation commands.
- [x] Write `28-strategy-retrospective.md` and `29-strategy-retrospective-system-report.md`.
- [x] Add retrospective-driven optimization pressure for repeated negative preflight issues.
- [x] Write `30-strategy-optimization-pressure-report.md`.
- [x] Apply retrospective demo preflight pressure to strategy scorecards and portfolio selection.
- [x] Write `32-retrospective-score-penalty-report.md`.
- [x] Run a new OKX demo optimization loop for the selected triangular strategy.
- [x] Add demo-window guard precheck to avoid burning validation cycles during runtime cooldown.
- [x] Improve retrospective cleanup for transient market-data failures after later profitable execution.
- [x] Write `33-demo-run-optimization-2026-05-11.md`.
- [x] Run a same-size 10-cycle OKX demo validation window for `triangular-multi-route`.
- [x] Scope retrospective improvements to actually observed strategy/execution-mode pairs.
- [x] Write `34-demo-10-cycle-validation-2026-05-11.md`.
- [x] Add read-only rolling strategy validation report CLI for recent journal evidence.
- [x] Write `35-rolling-validation-report-2026-05-11.md`.
- [x] Add scan diagnostics and break-even gap reporting for carry/basis strategies.
- [x] Write `36-carry-basis-scan-diagnostics-2026-05-11.md`.
- [x] Add configurable carry/basis quality gates for funding annualization, hedge cost, and basis thresholds.
- [x] Write `37-carry-basis-quality-gates-2026-05-11.md`.
- [x] Add read-only mock-vs-target strategy market comparison before OKX demo preflight.
- [x] Run OKX read-only market comparison and record current no-demo-candidate evidence.
- [x] Write `38-okx-read-only-market-compare-2026-05-11.md`.
- [x] Run a bounded OKX Demo Trading 3-cycle validation window after optimization.
- [x] Write `39-okx-demo-validation-2026-05-11.md`.
- [x] Audit expected-vs-actual OKX demo PnL alignment across preflight, order cash flow, account equity delta, residual inventory, and external reconciliation gaps.
- [x] Persist approved demo preflight estimates on future executed strategy journal events.
- [x] Extend `strategy validation-report` with expected/cash-flow/account-equity reconciliation fields and positive-cash-flow/negative-equity detection.
- [x] Write `40-pnl-reconciliation-audit-2026-05-11.md`.
- [x] Optimize OKX demo preflight to distinguish marketable limit protection price from expected top-of-book fill price.
- [x] Run one post-optimization OKX Demo Trading window and record the positive triangular canary result.
- [x] Write `41-demo-preflight-fill-price-optimization-2026-05-11.md`.
- [x] Add OKX spot directional strategy expansion with `trend-breakout`, `mean-reversion-spot`, `volatility-squeeze-breakout`, `momentum-rotation`, and `orderbook-imbalance-scalp`.
- [x] Add completed-candle market data support and `market candles` CLI.
- [x] Add Decimal-based directional indicators, no-lookahead backtest, signal/lifecycle models, and `directional-all` registry aggregate.
- [x] Wire directionals into scan, score, paper run, validation report, guard status, and retrospective-compatible journal flow.
- [x] Upgrade directional OKX demo execution from immediate round-trip canaries to persisted managed spot positions with open/hold/exit lifecycle handling.
- [x] Keep live unsupported and `orderbook-imbalance-scalp` demo-disabled.
- [x] Write `43-directional-strategy-expansion-design.md` and `44-directional-strategy-expansion-report.md`.
- [x] Add simulation-only strategy evolution service for promote/watchlist/probation/archive/revive-candidate decisions.
- [x] Add `strategy evolve --json` and refresh `evolution_after` on strategy run, local validation, and demo-window validation.
- [x] Block softly archived strategies from portfolio selection while allowing profitable paper/demo evidence to mark them as revival candidates.
- [x] Write `45-strategy-evolution.md`, `45-strategy-evolution.state.json`, and `46-strategy-evolution-system-report.md`.
- [x] Add advisory parameter mutation candidates to strategy evolution reports.
- [x] Add journal-derived market-regime tags to strategy evolution reports.
- [x] Add `strategy revival-window --json` to run local-first OKX demo validation only for current revival candidates.
- [x] Write `47-strategy-evolution-followups-report.md`.
- [x] Replace evolution market-regime tagging with completed-candle feature classification.
- [x] Add isolated `strategy candidate-backtest --json` for temporary-config parameter candidate comparison.
- [x] Write `48-candle-regime-candidate-backtest-report.md`.
- [x] Add `--config` support to read-only `exchange ping`, `market ticker`, `market orderbook`, `market candles`, and `account balance` diagnostics.
- [x] Write `49-readonly-market-config-diagnostics-report.md`.
- [x] Add read-only opportunity-density reporting for recent strategy journal evidence.
- [x] Add instrument-driven triangular route discovery and `--route-mode discovered` strategy scanning.
- [x] Upgrade triangular multi-route scanning metadata with multi-level orderbook fills, submitted limit prices, fee/slippage estimates, and min-size adjustment evidence.
- [x] Write `50-opportunity-density-route-discovery-report.md`.
- [x] Update traceability matrix and acceptance checklist.
- [x] Write `13-phase-9-report.md`.
- [x] Write `99-final-acceptance-report.md`.
