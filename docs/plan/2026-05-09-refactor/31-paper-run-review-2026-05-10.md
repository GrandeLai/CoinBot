# Paper Strategy Run Review

Date: 2026-05-10

## Scope

Ran the current strategy set in local paper mode only.

No OKX Demo Trading orders were sent. No live trading path was enabled. This result is deterministic mock/paper evidence, not real realized profit.

## Commands

- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy retrospective --config ../configs/config.example.yaml --execution-mode paper --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy guard-status --config ../configs/config.example.yaml --execution-mode paper --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy portfolio-status --config ../configs/config.example.yaml --symbol BTC/USDT --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy run --config ../configs/config.example.yaml --strategy all --max-cycles 5 --interval-seconds 0 --execution-mode paper --symbol BTC/USDT --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy review --config ../configs/config.example.yaml --execution-mode paper --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy retrospective --config ../configs/config.example.yaml --execution-mode paper --json`

## Pre-Run State

- Paper runtime guard: no active cooldown.
- Paper guard last state for all five canonical strategies: `profitable_execution`.
- Portfolio selected:
  - `triangular-multi-route`
  - `cross-exchange`
  - `spot-perp-carry`
- Portfolio blocked by concurrency limit:
  - `funding-carry-hedged`
  - `futures-perp-basis`

## Local Validation

`strategy validate-local` result:

- Status: `Pass`
- Cycles: 1
- Total strategy events: 5
- Executed: 5
- Blocked: 0
- Skipped: 0
- Wins: 5
- Losses: 0
- Net profit: `4.967117651096646342373316272 USDT`
- Max drawdown: `0`

## Latest 5-Cycle Paper Run

`strategy run --execution-mode paper --max-cycles 5` result:

- Cycles: 5
- Strategy events: 25
- Executed: 25
- Blocked: 0
- Skipped: 0
- Wins: 25
- Losses: 0
- Total paper net profit: `24.835588255483 USDT`

Per-strategy latest 5-cycle net profit:

| Strategy | Events | Executed | Wins | Losses | Net Profit USDT |
| --- | --- | --- | --- | --- | --- |
| `triangular-multi-route` | 5 | 5 | 5 | 0 | `18.246020795841` |
| `spot-perp-carry` | 5 | 5 | 5 | 0 | `1.899560087982` |
| `funding-carry-hedged` | 5 | 5 | 5 | 0 | `1.675000000000` |
| `futures-perp-basis` | 5 | 5 | 5 | 0 | `1.590547263682` |
| `cross-exchange` | 5 | 5 | 5 | 0 | `1.424460107978` |

## Historical Paper Review Snapshot

`strategy review --execution-mode paper` result after this run:

- Total paper events: 400
- `triangular-multi-route`: executed `79`, net profit `280.9887202559488102379524043`, win rate `100.00%`.
- `cross-exchange`: executed `80`, net profit `22.14157768446310737852429197`, win rate `100.00%`.
- `spot-perp-carry`: executed `79`, net profit `29.23322535492901419716056766`, win rate `100.00%`.
- `funding-carry-hedged`: executed `79`, net profit `25.77500`, win rate `100.00%`.
- `futures-perp-basis`: executed `79`, net profit `24.47442786069651741293532316`, win rate `100.00%`.

Historical review still includes old compatibility-alias records:

- `triangular`: 1 blocked historical event.
- `funding-rate`: 1 blocked historical event.
- `spot-perp`: 1 executed historical event.

## Retrospective Findings

Paper mode did not add new open issues.

The active open issues remain from OKX demo mode:

- `cross-exchange`: `demo_preflight_not_profitable`, break-even gap `0.129325 USDT`.
- `funding-carry-hedged`: `demo_preflight_not_profitable`, break-even gap `0.258630 USDT`.
- `futures-perp-basis`: `demo_preflight_not_profitable`, break-even gap `0.258606 USDT`.
- `spot-perp-carry`: `demo_preflight_not_profitable`, break-even gap `0.258630 USDT`.

## Optimization Summary

- Keep `triangular-multi-route` as the primary OKX demo candidate because it dominates both paper score and prior demo evidence.
- Do not force the four negative-preflight strategies into OKX demo orders. Paper profitability is not enough when demo preflight is negative.
- For `spot-perp-carry`, require basis plus funding carry to exceed entry/exit fees, slippage, holding cost, and at least the `0.258630 USDT` observed demo break-even gap.
- For `funding-carry-hedged`, rank symbols by projected next-window funding and require projected funding to exceed hedge cost plus the `0.258630 USDT` break-even gap.
- For `futures-perp-basis`, require futures/perp basis to exceed fees, slippage, holding cost, and the `0.258606 USDT` break-even gap; flat or missing basis should remain wait-only.
- For `cross-exchange`, do not promote OKX-only demo execution until the scanner has real venue-pair spread evidence after transfer, latency, fee, slippage, and sell-leg checks.

## Next Recommended Run

1. Keep current paper run healthy checks.
2. Improve carry/basis entry filters using the retrospective break-even gaps.
3. Re-run `strategy validate-local --strategy all --cycles 1`.
4. Then run OKX demo only for allowlisted strategies whose demo preflight turns positive.

Do not increase demo size and do not enable live trading from this paper result alone.

## Implemented Optimization

After this review, repeated OKX demo `preflight_not_profitable` pressure was connected to strategy scoring and portfolio selection.

- `triangular-multi-route` remains selected.
- `cross-exchange`, `spot-perp-carry`, `funding-carry-hedged`, and `futures-perp-basis` now receive `repeated_demo_preflight_not_profitable` score reasons and are blocked below the portfolio score floor until the demo preflight issue improves.
- The penalty is controlled by `strategy_runtime.retrospective_demo_preflight_score_penalty`.
- This optimization sends no orders, lowers no thresholds, and enables no live trading.

Implementation report: `docs/plan/2026-05-09-refactor/32-retrospective-score-penalty-report.md`.
