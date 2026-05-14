# Triangular Profitability Retrospective

Date: 2026-05-11

## Automation Status

The `okx-demo-target-watcher` heartbeat automation was deleted. No further 10-minute OKX demo target checks will run from that automation.

## Question

Why is `triangular-multi-route` not currently producing the desired OKX demo account profit?

## Evidence Reviewed

- Recent heartbeat checks repeatedly showed:
  - local validation: all five strategies skipped with `no_opportunity`
  - portfolio selection: no selected strategies
  - read-only OKX comparison: `target_no_opportunity`
  - open-risk: `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`
  - no new demo orders sent
- Current OKX demo equity checks fluctuated around `96k-97k USDT`, driven mostly by BTC, ETH, and OKB mark-to-market movement.
- Latest validation report command:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validation-report --config ../configs/okx.demo.example.yaml --execution-mode demo --strategy all --limit 80 --json
```

Result summary:

- scanned events: `80`
- executed: `23`
- skipped: `57`
- realized executed PnL: `13.258260 USDT`
- skipped preflight PnL: `-10.488476 USDT`
- `triangular-multi-route`: `executed=23`, `wins=23`, `realized_net_profit_usdt=13.258260`
- `triangular-multi-route` skipped reasons included `demo_preflight_not_profitable`, market-data failures, and runtime cooldown.
- execution quality passed: `true`
- receipt incomplete: `0`
- PnL out of tolerance: `0`
- residual inventory out of tolerance: `0`
- positive cash-flow PnL with negative account equity delta: `0`

Latest persisted expected-vs-actual triangular demo sample:

- approved preflight net PnL: `0.064467 USDT`
- actual order cash-flow PnL: `0.026190 USDT`
- expected-vs-actual gap: `-0.038277 USDT`
- receipts complete: `true`
- PnL reconciliation within tolerance: `true`
- residual inventory within tolerance: `true`

## Findings

1. `triangular-multi-route` is not unable to profit in all conditions. Historical OKX demo journal evidence shows profitable canary executions.
2. The current blocker is opportunity availability: recent OKX scans do not show a positive executable triangular edge, so the safe pipeline correctly refuses to place demo orders.
3. The strategy edge is tiny and fragile. Three taker legs must beat spread, fees, slippage, limit-buffer effects, lot-size rounding, and book movement between preflight and actual fills.
4. The latest persisted expected-vs-actual sample remained positive, but actual PnL was materially lower than preflight. This means preflight is useful as a gate, but not strong enough alone for size escalation.
5. Whole-account equity movement is not equivalent to strategy PnL. The demo account holds material BTC, ETH, and OKB, so market movement can dominate the small canary PnL.
6. Earlier high historical PnL samples should be treated cautiously because older executed events did not persist approved preflight estimates. They prove receipt/account reconciliation, but not full expected-vs-actual alignment.

## Root Cause

The main cause is market microstructure, not a single code bug:

- OKX triangular arbitrage on liquid pairs is highly efficient and rarely leaves persistent net-positive spreads.
- The configured canary is intentionally small and safe, so even profitable executions add only tiny account-level PnL.
- Current safety gates require positive local validation, positive demo preflight, clean runtime guard, clean open-risk, and portfolio selection. Recent runs failed at the opportunity/selection stage.
- Account-level target movement is dominated by existing BTC/ETH/OKB inventory price changes, which can swamp strategy cash-flow PnL.

## Decisions

- Do not force OKX demo orders when `no_opportunity` or `demo_preflight_not_profitable` appears.
- Do not lower `demo_min_preflight_net_pnl_usdt` below zero.
- Do not increase demo order size until new samples include persisted preflight, actual cash-flow PnL, account-equity delta, complete receipts, and clean residual inventory checks.
- Keep `triangular-multi-route` as the only current OKX demo execution candidate, but only when it passes the same local-first gates.

## Follow-Up

- Add stronger account-equity attribution that separates strategy cash-flow PnL from BTC/ETH/OKB inventory mark-to-market movement.
- Require more persisted expected-vs-actual samples before size changes.
- Consider adding a minimum positive preflight buffer above zero, because the latest persisted sample shrank from `0.064467 USDT` expected to `0.026190 USDT` actual.
- Continue read-only market comparison before demo execution so mock fixture opportunities are never confused with real OKX opportunities.
