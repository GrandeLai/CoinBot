# OKX Demo Strategy Execution Report

Date: 2026-05-09

## Scope

Run all four production strategies through controlled OKX Demo Trading execution, not just submit/cancel validation. The run uses tiny marketable limit orders, waits for fills, cancels if needed, records account snapshots, computes approximate gross PnL, estimated taker fees, and net PnL, then verifies no open orders or swap positions remain.

## Command

`UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant strategy run --config configs/okx.demo.example.yaml --strategy all --max-cycles 1 --interval-seconds 0 --execution-mode demo --json`

## Result

- Exit code: 0.
- `completed=true`.
- `execution_mode=demo`.
- `provider_demo=true` for each execution.
- `account_mode=3`.
- `live_orders_sent=false` for each execution.
- All submitted orders filled; no order required TTL cancellation in this run.
- Journal path: `logs/strategy-events.jsonl`.

## Strategy PnL

| Strategy | Demo Orders | Net PnL USDT | Result |
| --- | ---: | ---: | --- |
| `cross-exchange` | 2 | `-0.016063` | Filled and closed |
| `triangular` | 3 | `0.376816` | Filled and closed |
| `funding-rate` | 2 | `-0.016054` | Filled and closed |
| `spot-perp` | 4 | `-0.032117` | Filled and closed |

Total net PnL for this one-cycle demo run: `0.312582 USDT`.

## Post-Run Open Risk Check

Command:

`UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline python -c "..."`

Result:

```json
{
  "provider_demo": true,
  "open_spot_orders": 0,
  "open_swap_orders": 0,
  "swap_positions": 0,
  "live_orders_sent": false
}
```

## Safety Notes

- This was OKX Demo Trading only.
- No live orders were sent.
- Real `.env.okx.demo` credentials were not printed.
- Spot orders used account-mode-aware `tdMode`; the account is currently `acctLv=3`, so spot demo orders used cross-margin mode.
- Swap notional estimates use the BTC-USDT-SWAP contract multiplier so strategy caps are not overstated by treating contract count as BTC quantity.
- The run is a controlled canary for execution and PnL capture, not proof that the strategies are profitable at production size.

## Status

Done. `strategy run --execution-mode demo` now executes controlled OKX Demo Trading canary orders for all four strategies, records PnL evidence, and leaves no open spot orders, swap orders, or swap positions after the run.

## Iteration: Run, Review, Optimize, Rerun

### First Iteration

Command:

`UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant strategy run --config configs/okx.demo.example.yaml --strategy all --max-cycles 1 --interval-seconds 0 --execution-mode demo --json`

Result:

| Strategy | Net PnL USDT | Review |
| --- | ---: | --- |
| `cross-exchange` | `-0.016056` | Loss from spread/fee canary round trip |
| `triangular` | `0.375936` | Positive route |
| `funding-rate` | `-0.016047` | Loss from spread/fee canary round trip |
| `spot-perp` | `-0.032103` | Loss from spot + swap round-trip costs |

Total first-iteration net PnL: `0.311730 USDT`.

Review output showed the last two all-strategy demo rounds had:

| Strategy | Runs | Net PnL USDT |
| --- | ---: | ---: |
| `cross-exchange` | 2 | `-0.032119` |
| `funding-rate` | 2 | `-0.032101` |
| `spot-perp` | 2 | `-0.064220` |
| `triangular` | 2 | `0.752752` |

Optimization decision: rerun only `triangular` because it was the only strategy with consistently positive demo execution PnL. The other three remain useful as execution canaries but should not be repeatedly run in demo mode while they are just fee-cost round trips.

### Optimized Rerun

Command:

`UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant strategy run --config configs/okx.demo.example.yaml --strategy triangular --max-cycles 1 --interval-seconds 0 --execution-mode demo --json`

Result:

- Exit code: 0.
- `completed=true`.
- `strategy=triangular`.
- `net_pnl_usdt=0.375974`.
- `provider_demo=true`.
- `live_orders_sent=false`.

Post-rerun open risk check:

```json
{
  "provider_demo": true,
  "open_spot_orders": 0,
  "open_swap_orders": 0,
  "swap_positions": 0,
  "live_orders_sent": false
}
```

Current demo execution aggregate:

| Strategy | Demo Runs | Net PnL USDT |
| --- | ---: | ---: |
| `cross-exchange` | 2 | `-0.032119` |
| `funding-rate` | 2 | `-0.032101` |
| `spot-perp` | 2 | `-0.064220` |
| `triangular` | 3 | `1.128726` |

Current total demo execution PnL: `1.000286 USDT`.

### Next Optimization Direction

- Keep `triangular` as the only active demo strategy for the next short loop.
- Continue using tiny canary size until exchange-native realized PnL reconciliation and rate-limit/circuit-breaker automation are added.
- Do not increase order size based on these few samples; the sample is too small and the run is still canary-grade.

## Deferred Optimization Items Implemented

After the run/review/optimize/rerun loop, the runtime now adds three controls before further repeated OKX Demo Trading runs:

- Demo preflight gate: `StrategyDemoExecutionService.preview()` estimates gross PnL, fees, and net PnL without submitting orders. `strategy run --execution-mode demo` skips a strategy when the preflight is below `strategy_runtime.demo_min_preflight_net_pnl_usdt`.
- Demo loss breakers: longer demo loops accumulate executed demo PnL and stop when `strategy_runtime.demo_stop_loss_usdt` or `strategy_runtime.demo_max_drawdown_usdt` is reached.
- PnL reconciliation: demo execution output includes `pnl_validation`, comparing order cash-flow net PnL with account-equity delta using current BTC/USDT, ETH/USDT, and USDT reference prices.

These controls mean the next `--strategy all --execution-mode demo` run will no longer repeatedly send orders for cost-only round trips unless their current no-order preflight turns positive.

## Verification After Optimization Controls

Command:

`UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant strategy run --config configs/okx.demo.example.yaml --strategy all --max-cycles 1 --interval-seconds 0 --execution-mode demo --json`

Result:

| Strategy | Decision | Net PnL / Preflight USDT | Notes |
| --- | --- | ---: | --- |
| `cross-exchange` | `skipped` | `-0.032105` | Preflight rejected; no demo order sent |
| `triangular` | `executed` | `0.381294` | Canary orders filled; `pnl_validation.within_tolerance=true` |
| `funding-rate` | `skipped` | `-0.032105` | Preflight rejected; no demo order sent |
| `spot-perp` | `skipped` | `-0.064210` | Preflight rejected; no demo order sent |

Post-run open risk check:

```json
{
  "provider_demo": true,
  "open_spot_orders": 0,
  "open_swap_orders": 0,
  "swap_positions": 0,
  "live_orders_sent": false
}
```

Demo-only review command:

`UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant strategy review --config configs/okx.demo.example.yaml --execution-mode demo --json`

Demo-only realized PnL after this run:

| Strategy | Demo Events | Executed | Skipped | Net PnL USDT | Win Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cross-exchange` | 4 | 2 | 1 | `-0.032119` | `0.00%` |
| `triangular` | 4 | 4 | 0 | `1.510020` | `100.00%` |
| `funding-rate` | 3 | 2 | 1 | `-0.032101` | `0.00%` |
| `spot-perp` | 3 | 2 | 1 | `-0.064220` | `0.00%` |

The review now filters to `execution_mode=demo` and counts only executed events as realized PnL, so skipped preflight estimates do not pollute profit statistics.

## Exchange Receipt Reconciliation Before Size Increase

The demo execution path now fetches OKX transaction details from `/api/v5/trade/fills-history` for every executed order and stores the summary in `pnl_validation.exchange_receipts`.

Latest canary command:

`UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant strategy run --config configs/okx.demo.example.yaml --strategy all --max-cycles 1 --interval-seconds 0 --execution-mode demo --json`

Result:

| Strategy | Decision | Net PnL / Preflight USDT | Receipt Status |
| --- | --- | ---: | --- |
| `cross-exchange` | `skipped` | `-0.032140` | No order sent |
| `triangular` | `executed` | `0.383234` | `complete=true`, `fill_count=3` |
| `funding-rate` | `skipped` | `-0.032140` | No order sent |
| `spot-perp` | `skipped` | `-0.064281` | No order sent |

Executed triangular receipt summary:

```json
{
  "source": "okx_fills_history",
  "complete": true,
  "orders_expected": 3,
  "orders_with_receipts": 3,
  "fill_count": 3,
  "fee_expense_usdt": "0.024496",
  "fill_pnl_usdt": "0.000000",
  "receipt_net_pnl_usdt": "-0.024496",
  "errors": []
}
```

For spot triangular fills, OKX `fillPnl` is `0` because the endpoint reports realised PnL for close-position derivatives trades. The actual spot strategy result is therefore still judged by account-equity delta plus fill receipt completeness/fees. This is enough to proceed to longer canary sampling, but not enough to enlarge position size yet.

Post-run open risk check:

```json
{
  "provider_demo": true,
  "open_spot_orders": 0,
  "open_swap_orders": 0,
  "swap_positions": 0,
  "live_orders_sent": false
}
```

Demo-only review after receipt reconciliation:

| Strategy | Demo Events | Executed | Skipped | Net PnL USDT | Win Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cross-exchange` | 5 | 2 | 2 | `-0.032119` | `0.00%` |
| `triangular` | 5 | 5 | 0 | `1.893254` | `100.00%` |
| `funding-rate` | 4 | 2 | 2 | `-0.032101` | `0.00%` |
| `spot-perp` | 4 | 2 | 2 | `-0.064220` | `0.00%` |

## Stage-1 Demo Size Increase

After receipt reconciliation passed, OKX demo config was staged from 1x to 2x:

```yaml
strategy_runtime:
  demo_max_order_value_usdt: "20"
  demo_order_size_multiplier: "2"
```

The shared safe config remains at `demo_order_size_multiplier: "1"`; only `configs/okx.demo.example.yaml` is staged to 2x.

2x demo command:

`UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant strategy run --config configs/okx.demo.example.yaml --strategy all --max-cycles 1 --interval-seconds 0 --execution-mode demo --json`

2x result:

| Strategy | Decision | Net PnL / Preflight USDT | Notes |
| --- | --- | ---: | --- |
| `cross-exchange` | `skipped` | `-0.064276` | 2x preflight rejected; no order sent |
| `triangular` | `executed` | `0.750826` | 2x canary orders filled |
| `funding-rate` | `skipped` | `-0.064275` | 2x preflight rejected; no order sent |
| `spot-perp` | `skipped` | `-0.128551` | 2x preflight rejected; no order sent |

2x triangular validation:

- `pnl_validation.within_tolerance=true`
- `equity_delta_usdt=0.767511`
- `difference_usdt=0.016684`
- `exchange_receipts.complete=true`
- `orders_expected=3`
- `orders_with_receipts=3`
- `fill_count=3`
- `fee_expense_usdt=0.048956`

2x post-run open risk check:

```json
{
  "provider_demo": true,
  "open_spot_orders": 0,
  "open_swap_orders": 0,
  "swap_positions": 0,
  "live_orders_sent": false
}
```

Demo-only review after 2x run:

| Strategy | Demo Events | Executed | Skipped | Net PnL USDT | Win Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cross-exchange` | 6 | 2 | 3 | `-0.032119` | `0.00%` |
| `triangular` | 6 | 6 | 0 | `2.644080` | `100.00%` |
| `funding-rate` | 5 | 2 | 3 | `-0.032101` | `0.00%` |
| `spot-perp` | 5 | 2 | 3 | `-0.064220` | `0.00%` |

## Stage-1 2x Continuous Sample Window

Before increasing size beyond 2x, a continuous 3-cycle sample window was run against OKX Demo Trading.

Command:

`UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant strategy run --config configs/okx.demo.example.yaml --strategy all --max-cycles 3 --interval-seconds 0 --execution-mode demo --json`

Result:

- Exit code: 0 after network approval.
- `completed=true`.
- `cycles_completed=3`.
- `demo_cumulative_net_pnl=2.235405`.
- `demo_max_drawdown_usdt=0`.
- `live_orders_sent=false` for all executed demo orders.

Latest 12-event window:

| Strategy | Decision Count | Executed PnL USDT | Notes |
| --- | ---: | ---: | --- |
| `cross-exchange` | skipped 3 | n/a | Negative 2x demo preflight; no order sent |
| `triangular` | executed 3 | `2.235405` | All 9 spot legs filled |
| `funding-rate` | skipped 3 | n/a | Negative 2x demo preflight; no order sent |
| `spot-perp` | skipped 3 | n/a | Negative 2x demo preflight; no order sent |

Executed triangular validation:

- All `pnl_validation.within_tolerance=true`.
- All `exchange_receipts.complete=true`.
- Each executed cycle returned 3 fills from OKX `fills-history`.
- No missing order suffixes were reported.

Post-window open risk check:

```json
{
  "configured": true,
  "demo": true,
  "open_spot_orders": 0,
  "open_swap_orders": 0,
  "swap_positions": 0
}
```

Demo-only review after the 2x continuous window:

| Strategy | Demo Events | Executed | Skipped | Net PnL USDT | Win Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cross-exchange` | 9 | 2 | 6 | `-0.032119` | `0.00%` |
| `triangular` | 9 | 9 | 0 | `4.879485` | `100.00%` |
| `funding-rate` | 8 | 2 | 6 | `-0.032101` | `0.00%` |
| `spot-perp` | 8 | 2 | 6 | `-0.064220` | `0.00%` |

Decision: keep size at 2x for now. The 3-cycle sample passed, but it is still a short sample and only one strategy is currently profitable after live market preflight. The next safe step is more 2x sampling with the same receipt/no-open-risk checks before any additional multiplier increase.

## Stateful Runtime Guard Added Before Further Sampling

After the first 2x continuous window, the next highest-priority safety gap was state across independent runs. The runtime now persists consecutive blocked runs and negative executions per strategy/execution mode in:

`strategy_runtime.runtime_guard_path`

Guard controls:

```yaml
strategy_runtime:
  runtime_guard_enabled: true
  runtime_guard_path: logs/strategy-runtime-guard.json
  max_consecutive_execution_failures: 3
  max_consecutive_losses: 3
  failure_cooldown_seconds: 300
```

Behavior:

- Profitable executions reset consecutive failure/loss counters.
- Negative executions increment both consecutive failures and losses.
- Blocked cycles increment consecutive failures.
- Skipped no-opportunity or negative-preflight cycles do not place orders and do not count as realized losses.
- When a threshold is reached, the strategy/mode pair enters cooldown and future cycles are skipped before executor calls.

CLI status command:

`UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant strategy guard-status --config configs/config.example.yaml --execution-mode paper --json`

This command gives the Agent a cheap pre-run check before deciding whether to continue sampling, pause a strategy, or wait for cooldown expiry.
