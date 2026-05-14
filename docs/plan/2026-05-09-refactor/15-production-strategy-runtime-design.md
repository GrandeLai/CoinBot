# Production Strategy Runtime Design

Date: 2026-05-09

## Goal

Turn the existing four arbitrage scanners into a controlled long-running strategy runtime that can repeatedly scan, size, risk-check, execute in paper/mock by default, record every decision, review outcomes, and produce learning suggestions.

## Scope

The first production-grade increment covers:

- `cross-exchange`
- `triangular`
- `funding-rate`
- `spot-perp`

The runtime supports long-running operation through bounded or unbounded cycles, but tests and examples use bounded cycles. Default execution remains `paper`; OKX Demo Trading stays behind explicit configuration and existing broker gates. The runtime never enables live trading by default.

## Architecture

Add `backend/src/trading_assistant/strategies/` with five focused units:

- `registry.py`: declares the four strategy definitions and their scanner types.
- `models.py`: JSON-safe dataclasses for cycle results, order lifecycle plans, budget decisions, review reports, and learning suggestions.
- `policy.py`: position and order-lifecycle controls, including per-strategy capital caps, max open orders, order TTL, cancel/reprice instructions, and risk handoff.
- `journal.py`: append-only JSONL event storage for strategy runs, executions, skips, and review inputs.
- `runner.py`: orchestrates scan -> select -> risk -> budget -> lifecycle plan -> paper execution -> journaling.
- `review.py`: reads journal events, computes basic strategy statistics, and emits conservative parameter suggestions.
- `demo_validation.py`: runs manually gated OKX Demo Trading submit/cancel checks per strategy, with explicit demo-only account-mode switch support for swap validation.
- `demo_execution.py`: runs tiny OKX Demo Trading canary orders, waits for fills, cancels if needed, records account snapshots, and computes approximate PnL.

`TradingAssistantApp` exposes this through thin CLI handlers:

- `crypto-assistant strategy list --json`
- `crypto-assistant strategy run --strategy all --max-cycles 1 --interval-seconds 0 --execution-mode paper --json`
- `crypto-assistant strategy run --config configs/okx.demo.example.yaml --strategy all --max-cycles 1 --interval-seconds 0 --execution-mode demo --json`
- `crypto-assistant strategy review --json`
- `crypto-assistant strategy validate-demo --config configs/okx.demo.example.yaml --strategy all --allow-account-mode-switch --json`

## Safety Model

- Default execution mode is `paper`.
- Each opportunity must pass the existing `RiskManager`.
- Each strategy must pass runtime caps before execution.
- Live execution is not introduced by this design.
- OKX demo execution remains guarded by the existing demo gate; `strategy run --execution-mode demo` does not silently switch to demo order dispatch.
- OKX demo strategy execution requires an OKX demo config, uses tiny canary orders, applies demo max-order caps, records account snapshots and PnL evidence, and checks for no residual open orders/positions after manual validation runs.
- `strategy validate-demo` is the manually gated OKX Demo Trading path. It only runs with `okx_demo=true`, rejects live trading, cancels every submitted validation order, and allows account-mode switching only through explicit `--allow-account-mode-switch`.
- Order lifecycle plans always include cancel-after-TTL and rescan-before-reprice behavior so an external broker loop has deterministic instructions.

## Learning Model

The learning layer is intentionally advisory. It reads historical strategy events and suggests parameter changes such as:

- Increase `min_net_profit_pct` when a strategy has low win rate.
- Lower per-strategy capital when blocked or loss-like outcomes accumulate.
- Keep current settings when sample size is small or outcomes are healthy.

It does not rewrite code, change configuration files, or enable live trading.

## Acceptance

- All four strategies are listed by the registry.
- A bounded run over `all` strategies completes offline using mock/paper defaults.
- Each executed opportunity records risk, budget, lifecycle, and execution details.
- Review produces statistics and learning suggestions from recorded events.
- OKX Demo Trading validation command exists and all four strategies pass after the demo account moved to `acctLv=3`.
- OKX Demo Trading execution mode records PnL for all four strategies without sending live orders.
- CLI commands support `--help` and `--json`.
- Tests pass offline with no real exchange dependency.
