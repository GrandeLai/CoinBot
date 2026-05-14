# Strategy Retrospective

Last updated: 2026-05-14T10:04:47.905029+00:00

This document is auto-updated after strategy execution and validation. It is advisory and never enables live trading.

## Current Open Issues

| ID | Strategy | Mode | Category | Severity | Occurrences | Last Seen | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ri-d3399ff1a4d3 | cross-exchange | demo | preflight_not_profitable | warning | 16 | 2026-05-12T06:13:18.089786+00:00 | Do not force demo orders; wait for a profitable preflight or improve scanner pricing. |
| ri-a5df76fbd5d2 | funding-carry-hedged | demo | preflight_not_profitable | warning | 16 | 2026-05-12T06:13:18.089786+00:00 | Do not force demo orders; wait for a profitable preflight or improve scanner pricing. |
| ri-ca56d8efd289 | futures-perp-basis | demo | preflight_not_profitable | warning | 16 | 2026-05-12T06:13:18.089786+00:00 | Do not force demo orders; wait for a profitable preflight or improve scanner pricing. |
| ri-a01c63a277fe | spot-perp-carry | demo | preflight_not_profitable | warning | 16 | 2026-05-12T06:13:18.089786+00:00 | Do not force demo orders; wait for a profitable preflight or improve scanner pricing. |
| ri-b173009977c9 | all | paper | insufficient_samples | warning | 15 | 2026-05-11T15:03:47.005508+00:00 | Collect more local/demo samples before promotion or size decisions. |
| ri-db0c0799a25f | triangular-multi-route | demo | insufficient_samples | warning | 3 | 2026-05-14T10:04:47.905029+00:00 | Collect more local/demo samples before promotion or size decisions. |
| ri-1c817c39b0d9 | trend-breakout | demo | execution_loss | warning | 2 | 2026-05-12T06:13:18.089786+00:00 | Keep size unchanged and inspect fees, slippage, fills, and route assumptions before rerunning. |
| ri-7833b202c763 | momentum-rotation | demo | execution_loss | warning | 1 | 2026-05-12T06:13:18.089786+00:00 | Keep size unchanged and inspect fees, slippage, fills, and route assumptions before rerunning. |
| ri-a5d9ba2247ed | all | demo | insufficient_samples | info | 1 | 2026-05-11T12:13:44.813640+00:00 | Collect more local/demo samples before promotion or size decisions. |

## Repeated Issues

| ID | Strategy | Mode | Category | Severity | Occurrences | Last Seen | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ri-d3399ff1a4d3 | cross-exchange | demo | preflight_not_profitable | warning | 16 | 2026-05-12T06:13:18.089786+00:00 | Do not force demo orders; wait for a profitable preflight or improve scanner pricing. |
| ri-a5df76fbd5d2 | funding-carry-hedged | demo | preflight_not_profitable | warning | 16 | 2026-05-12T06:13:18.089786+00:00 | Do not force demo orders; wait for a profitable preflight or improve scanner pricing. |
| ri-ca56d8efd289 | futures-perp-basis | demo | preflight_not_profitable | warning | 16 | 2026-05-12T06:13:18.089786+00:00 | Do not force demo orders; wait for a profitable preflight or improve scanner pricing. |
| ri-a01c63a277fe | spot-perp-carry | demo | preflight_not_profitable | warning | 16 | 2026-05-12T06:13:18.089786+00:00 | Do not force demo orders; wait for a profitable preflight or improve scanner pricing. |
| ri-b173009977c9 | all | paper | insufficient_samples | warning | 15 | 2026-05-11T15:03:47.005508+00:00 | Collect more local/demo samples before promotion or size decisions. |
| ri-db0c0799a25f | triangular-multi-route | demo | insufficient_samples | warning | 3 | 2026-05-14T10:04:47.905029+00:00 | Collect more local/demo samples before promotion or size decisions. |
| ri-1c817c39b0d9 | trend-breakout | demo | execution_loss | warning | 2 | 2026-05-12T06:13:18.089786+00:00 | Keep size unchanged and inspect fees, slippage, fills, and route assumptions before rerunning. |

## Improved Issues

| ID | Strategy | Mode | Category | Severity | Occurrences | Last Seen | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ri-d004b4da0097 | triangular-multi-route | demo | pnl_out_of_tolerance | critical | 10 | 2026-05-10T10:53:10.928405+00:00 | Investigate account-equity delta versus order cash-flow before trusting the PnL sample. |
| ri-a95fd3d3a6f5 | triangular-multi-route | demo | runtime_guard_cooldown | critical | 3 | 2026-05-14T09:55:41.427383+00:00 | Respect the runtime guard cooldown and inspect the last failure reason. |
| ri-8f034a701f5e | triangular-multi-route | demo | market_data_failure | warning | 3 | 2026-05-11T03:25:07.444702+00:00 | Wait for healthy market data or reduce polling before rerunning. |
| ri-0abce69d13ce | all | demo | insufficient_samples | warning | 2 | 2026-05-11T12:04:32.783830+00:00 | Collect more local/demo samples before promotion or size decisions. |
| ri-5aadbdab9f8d | triangular-multi-route | demo | preflight_not_profitable | warning | 2 | 2026-05-11T12:04:32.783830+00:00 | Do not force demo orders; wait for a profitable preflight or improve scanner pricing. |
| ri-514b732af535 | triangular-multi-route | demo | validation_failed | warning | 2 | 2026-05-14T09:55:41.427383+00:00 | Review this issue before the next strategy execution. |
| ri-1faf866c5ef1 | triangular-multi-route | demo | execution_loss | warning | 1 | 2026-05-10T10:53:10.928405+00:00 | Keep size unchanged and inspect fees, slippage, fills, and route assumptions before rerunning. |
| ri-34b8ad27898a | triangular-multi-route | demo | leg_not_filled_abort | warning | 1 | 2026-05-10T10:53:10.928405+00:00 | Review leg marketability, orderbook depth, and unwind evidence before another demo window. |
| ri-61ed4e3198d2 | all | demo | insufficient_samples | info | 1 | 2026-05-11T06:25:58.061207+00:00 | Collect more local/demo samples before promotion or size decisions. |
| ri-a8496b6550da | momentum-rotation | demo | insufficient_samples | info | 1 | 2026-05-11T16:30:31.612263+00:00 | Collect more local/demo samples before promotion or size decisions. |
| ri-7e286d7b673e | trend-breakout | demo | insufficient_samples | info | 1 | 2026-05-11T16:29:46.281047+00:00 | Collect more local/demo samples before promotion or size decisions. |
| ri-3c96bd614313 | triangular-multi-route | demo | insufficient_samples | info | 1 | 2026-05-11T03:17:47.635054+00:00 | Collect more local/demo samples before promotion or size decisions. |

## Next Run Checklist

- [ ] Run local validation before any OKX Demo Trading window.
- [ ] Check strategy guard status before repeated demo execution.
- [ ] Keep live trading and live-canary gates disabled unless a separate approval explicitly changes them.
- [ ] Do not force strategies that are currently skipped by demo_preflight_not_profitable.
- [ ] Collect enough samples to satisfy validation_min_* thresholds before promotion decisions.

## Test Evolution Pressure

- Add or keep tests proving negative preflight skips before any demo order is submitted.

## Strategy Optimization Pressure

| Strategy | Category | Priority | Occurrences | Break-even Gap USDT | Action | Guardrails |
| --- | --- | --- | --- | --- | --- | --- |
| cross-exchange | preflight_not_profitable | high | 16 | 0.032448 | Keep OKX demo orders blocked until scanner emits a venue-pair spread that remains positive after fees, transfer cost, latency drift, and sell-leg availability checks. | do_not_lower_demo_min_preflight_net_pnl_below_zero, do_not_force_demo_orders_when_preflight_is_negative, rerun_strategy_validate_local_before_okx_demo, do_not_increase_demo_size_until_repeated_clean_passes |
| funding-carry-hedged | preflight_not_profitable | high | 16 | 0.065108 | Rank funding symbols and require projected next-window funding to exceed hedge cost, fees, slippage, and the observed break-even gap before demo execution. | do_not_lower_demo_min_preflight_net_pnl_below_zero, do_not_force_demo_orders_when_preflight_is_negative, rerun_strategy_validate_local_before_okx_demo, do_not_increase_demo_size_until_repeated_clean_passes |
| futures-perp-basis | preflight_not_profitable | high | 16 | 0.064914 | Require dated-futures/perp basis to exceed fees, slippage, holding cost, and the observed break-even gap; treat flat or unavailable futures basis as wait. | do_not_lower_demo_min_preflight_net_pnl_below_zero, do_not_force_demo_orders_when_preflight_is_negative, rerun_strategy_validate_local_before_okx_demo, do_not_increase_demo_size_until_repeated_clean_passes |
| spot-perp-carry | preflight_not_profitable | high | 16 | 0.065011 | Require positive spot/perp basis plus projected funding carry to exceed entry/exit fees, slippage, holding cost, and the observed break-even gap before demo execution. | do_not_lower_demo_min_preflight_net_pnl_below_zero, do_not_force_demo_orders_when_preflight_is_negative, rerun_strategy_validate_local_before_okx_demo, do_not_increase_demo_size_until_repeated_clean_passes |

## Recent Run Summary

| Time | Operation | Issues | Modes | Summary |
| --- | --- | --- | --- | --- |
| 2026-05-14T10:04:47.905029+00:00 | strategy_validate_demo_window | 1 | demo,paper | {"cycles_completed": 3, "executed": 3, "execution_mode": "demo", "net_profit": "0.667779", "operation": "strategy_validate_demo_window", "run_completed": true, "skipped": 0, "validation_status": "Needs More Samples"} |
| 2026-05-14T09:55:41.427383+00:00 | strategy_validate_demo_window | 2 | demo,paper | {"cycles_completed": 0, "executed": 0, "execution_mode": "demo", "net_profit": "0", "operation": "strategy_validate_demo_window", "run_completed": false, "skipped": 0, "validation_status": "Fail"} |
| 2026-05-14T04:01:32.243576+00:00 | strategy_validate_demo_window | 1 | demo,paper | {"cycles_completed": 3, "executed": 3, "execution_mode": "demo", "net_profit": "0.600680", "operation": "strategy_validate_demo_window", "run_completed": true, "skipped": 0, "validation_status": "Needs More Samples"} |
| 2026-05-13T08:35:23.958281+00:00 | strategy_run | 0 | demo | {"cycles_completed": 1, "executed": null, "execution_mode": "demo", "net_profit": "0.111501", "operation": "strategy_run", "run_completed": true, "skipped": null, "validation_status": null} |
| 2026-05-12T06:13:18.096421+00:00 | strategy_validate_local | 0 | paper | {"cycles_completed": 1, "executed": 1, "execution_mode": "paper", "net_profit": "3.6492041591681663667266546", "operation": "strategy_validate_local", "run_completed": true, "skipped": 0, "validation_status": "Pass"} |
| 2026-05-12T06:13:18.089786+00:00 | strategy_retrospective | 27 | demo | {"execution_mode": "demo", "journal_events": 50} |
| 2026-05-11T16:51:18.910123+00:00 | strategy_run | 0 | demo | {"cycles_completed": 1, "executed": null, "execution_mode": "demo", "net_profit": "0", "operation": "strategy_run", "run_completed": true, "skipped": null, "validation_status": null} |
| 2026-05-11T16:51:00.804468+00:00 | strategy_run | 1 | demo | {"cycles_completed": 1, "executed": null, "execution_mode": "demo", "net_profit": "0.000000", "operation": "strategy_run", "run_completed": true, "skipped": null, "validation_status": null} |
| 2026-05-11T16:50:23.405953+00:00 | strategy_validate_local | 0 | paper | {"cycles_completed": 1, "executed": 1, "execution_mode": "paper", "net_profit": "1.174961", "operation": "strategy_validate_local", "run_completed": true, "skipped": 0, "validation_status": "Pass"} |
| 2026-05-11T16:30:31.612263+00:00 | strategy_validate_demo_window | 2 | demo,paper | {"cycles_completed": 1, "executed": 1, "execution_mode": "demo", "net_profit": "-0.032849", "operation": "strategy_validate_demo_window", "run_completed": true, "skipped": 0, "validation_status": "Needs More Samples"} |

## Manual Notes

<!-- RETROSPECTIVE_MANUAL_NOTES_START -->
### 2026-05-11 Triangular Profitability Review

- The `okx-demo-target-watcher` heartbeat automation was stopped after repeated no-op checks.
- Current diagnosis: `triangular-multi-route` is not structurally broken, but current OKX top-of-book data has not produced a fresh executable edge. Recent local validation repeatedly returned `no_opportunity`, portfolio selection returned no selected strategies, and read-only market comparison returned `target_no_opportunity` for OKX.
- Historical demo evidence: the OKX demo journal shows `triangular-multi-route` executed profitably in prior windows, but older events without persisted approved preflight estimates should not be used as full expected-vs-actual promotion evidence.
- Latest persisted expected-vs-actual sample: approved preflight `0.064467 USDT`, actual cash-flow PnL `0.026190 USDT`, expected-vs-actual gap `-0.038277 USDT`, receipts complete, PnL reconciliation within tolerance, residual inventory within tolerance.
- Whole-account equity movement must not be attributed to the strategy alone because the demo account holds material BTC, ETH, and OKB inventory. Recent marked-to-market equity changes were mostly inventory price movement, while no new triangular orders were sent.
- Action: keep triangular in observe/local-first mode until OKX scan produces a positive top-of-book edge; do not force orders, do not lower preflight below zero, and collect more new samples with persisted preflight before any size increase.
<!-- RETROSPECTIVE_MANUAL_NOTES_END -->
