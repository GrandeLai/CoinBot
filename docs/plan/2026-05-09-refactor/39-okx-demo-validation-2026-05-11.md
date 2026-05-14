# OKX Demo Validation Run Report

Date: 2026-05-11

## Goal

Run a bounded OKX Demo Trading validation window after the latest optimization work, while preserving the three-layer safety flow:

```text
local paper validation -> OKX read-only market compare -> OKX demo preflight -> tiny demo canary execution -> review
```

## Pre-Checks

Local validation command:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-local \
  --config ../configs/config.example.yaml \
  --strategy all \
  --cycles 1 \
  --symbol BTC/USDT \
  --json
```

Result:

- Status: `Pass`.
- Total strategy events: `5`.
- Executed: `5`.
- Blocked: `0`.
- Skipped: `0`.
- Wins: `5`.
- Losses: `0`.
- Net profit: `4.967117651096646342373316272 USDT`.

OKX demo guard status:

- Runtime guard enabled.
- No active cooldown for any strategy.
- `triangular-multi-route` last reason: `profitable_execution`.
- Non-triangular strategies last reason: `demo_preflight_not_profitable`.

OKX read-only market compare:

- `read_only=true`.
- `orders_sent=false`.
- Demo-preflight candidates: `0`.
- All target strategies returned `observe_only` under current OKX market snapshot.

Decision:

- Proceed with a small bounded demo window only because the user requested simulation validation.
- Do not force non-profitable strategies; rely on runtime preflight to skip them.

## Demo Window Command

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window \
  --config ../configs/okx.demo.example.yaml \
  --strategy all \
  --cycles 3 \
  --symbol BTC/USDT \
  --json
```

## Demo Window Result

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
- Win rate: `100.00%`.
- Max drawdown: `0`.

Executed strategy:

- `triangular-multi-route`: executed 3 tiny OKX Demo Trading canaries.

Skipped strategies:

- `cross-exchange`: skipped by `demo_preflight_not_profitable`.
- `funding-carry-hedged`: skipped by `demo_preflight_not_profitable`.
- `spot-perp-carry`: skipped by `demo_preflight_not_profitable`.
- `futures-perp-basis`: skipped by `demo_preflight_not_profitable`.

Post-run open-risk check:

- `checked=true`.
- `configured=true`.
- `demo=true`.
- `open_spot_orders=0`.
- `open_swap_orders=0`.
- `swap_positions=0`.

## Rolling Review After Run

Command:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validation-report \
  --config ../configs/okx.demo.example.yaml \
  --execution-mode demo \
  --strategy all \
  --limit 30 \
  --json
```

Latest 30 demo events:

- Scanned events: `30`.
- Executed: `16`.
- Skipped: `14`.
- Blocked: `0`.
- Wins: `16`.
- Losses: `0`.
- Realized net profit: `3.706793 USDT`.
- Skipped preflight PnL: `-2.721266 USDT`.
- Max drawdown: `0`.
- Receipt incomplete: `0`.
- PnL out of tolerance: `0`.
- Residual inventory out of tolerance: `0`.
- Max residual inventory: `0.058291 USDT`.
- Execution quality passed: `true`.

Historical demo review:

- Total demo events: `259`.
- `triangular-multi-route`: `executed=61`, `wins=60`, `losses=1`, `net_profit=75.533887 USDT`, `win_rate_pct=98.36`.
- `cross-exchange`, `funding-carry-hedged`, `spot-perp-carry`, and `futures-perp-basis` remain skipped-only in demo review.

## Retrospective Update

Open issues after this run:

- `open_issue_count=5`.
- `repeated_issue_count=4`.
- `highest_severity=warning`.

Issues:

- `cross-exchange`: repeated `demo_preflight_not_profitable`, occurrences increased to `13`.
- `funding-carry-hedged`: repeated `demo_preflight_not_profitable`, occurrences increased to `13`.
- `spot-perp-carry`: repeated `demo_preflight_not_profitable`, occurrences increased to `13`.
- `futures-perp-basis`: repeated `demo_preflight_not_profitable`, occurrences increased to `13`.
- `all`: `minimum_samples_not_met:3<10`; collect more demo samples before promotion or size decisions.

## Decision

The demo run is healthy but not promotion-complete:

- Triangular remains the only strategy with current positive OKX demo execution evidence.
- Non-triangular strategies should remain blocked from demo execution until read-only market compare and runtime preflight turn positive.
- Do not increase size yet because this window has only `3` executed samples and validation requires `10`.
- Next reasonable step is another same-size `triangular-multi-route` or selected-strategy demo window, not broader size increase.

## Safety

- Live trading remained disabled.
- The run used OKX Demo Trading only.
- Runtime preflight blocked negative strategies before order dispatch.
- No open spot orders remained.
- No open swap orders remained.
- No swap positions remained.
- No demo/live gates were weakened.
