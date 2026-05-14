# OKX Demo Expanded Strategy Execution Report

Date: 2026-05-10

## Scope

- Continue the previously Deferred carry/basis demo work.
- Keep live trading disabled.
- Allow OKX Demo Trading canary orders only after first-layer local mock/paper validation.
- Expand demo submit/cancel validation to:
  - `funding-carry-hedged`
  - `spot-perp-carry`
  - `futures-perp-basis`

## Code Changes

- `StrategyRegistry` now marks the three carry/basis strategies as demo-supported while keeping `live_supported=false`.
- `strategy validate-demo` and `strategy validate-demo-window` now run local mock/paper validation first and block OKX demo actions unless it passes.
- `StrategyDemoValidationService` can submit/cancel tiny spot, swap, and futures validation orders.
- `StrategyDemoExecutionService` can build tiny canary specs for spot-perp carry, hedged funding carry, and futures-perp basis.
- Demo execution now runs legs sequentially. If a leg does not fully fill, later legs are not submitted and already-filled legs are unwound with opposite canary orders.
- Triangular demo execution now sizes the `ETH/BTC` and `ETH/USDT` legs from actual filled inventory with conservative buffers, so a partial `fillSz` no longer forces the next leg to overuse available inventory.
- OKX order detail parsing now prefers `accFillSz` over the last-fill `fillSz`, which is required when OKX splits a filled order into multiple fills.
- PnL calculation now uses the triangular special-case formula only when the actual executed orders contain the complete triangular path; aborted/unwind sequences use actual order cash flow.
- PnL validation now reports `residual_inventory_usdt`, `residual_assets`, and `residual_inventory_within_tolerance`; demo-window validation fails if residual inventory exceeds the configured tolerance.
- `configs/okx.demo.example.yaml` allowlists the newly demo-supported strategies.
- `configs/okx.demo.example.yaml` now uses isolated OKX demo runtime guard/journal paths and sets demo-only PnL/residual-inventory tolerances to `0.10`.

## Local Validation

- Command:
  - `UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`
- Result:
  - Exit 0.
  - `local_validation.status=Pass`.
  - `executed=5`, `blocked=0`, `skipped=0`.
  - `win_rate_pct=100.00`.
  - Latest local net profit: `4.967117651096646342373316272`.

## OKX Demo Submit/Cancel Validation

- Command:
  - `UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy validate-demo --config ../configs/okx.demo.example.yaml --strategy all --symbol BTC/USDT --allow-account-mode-switch --json`
- Sandbox note:
  - The first run without elevated network access reached local validation but failed OKX API calls with DNS/network errors.
  - The command was rerun with approved network access.
- Result:
  - Exit 0.
  - `local_validation.status=Pass`.
  - `strategy_demo_validation.completed=true`.
  - `provider_demo=true`, `live_trading=false`, `dry_run=false`.
  - Account mode check: `before=3`, `after=3`; no switch was needed.
  - `cross-exchange`, `triangular`, `funding-carry-hedged`, `spot-perp-carry`, and `futures-perp-basis` all submitted and canceled tiny OKX Demo Trading orders.
  - Each validation item reported `live_orders_sent=false` and `open_after_cancel=false`.
  - `futures-perp-basis` validated a dated futures leg on `BTC-USDT-260529`.

## OKX Demo Runner Validation

- Command:
  - `UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy run --config ../configs/okx.demo.example.yaml --strategy all --symbol BTC/USDT --max-cycles 1 --interval-seconds 0 --execution-mode demo --json`
- Result:
  - Exit 0.
  - Every strategy ran its local validation gate first.
  - `cross-exchange`, `funding-carry-hedged`, `spot-perp-carry`, and `futures-perp-basis` were skipped by `demo_preflight_not_profitable`; no demo orders were sent for those paths.
  - `triangular-multi-route` submitted a triangular canary, the `ETH/BTC` middle leg did not fill, the executor stopped the remaining leg, and it unwound the filled BTC leg.
  - Final triangular execution status: `aborted_unwound`.
  - Final triangular net PnL: `-0.033506 USDT`.
  - `pnl_validation.within_tolerance=true`.
  - `exchange_receipts.complete=true`.
  - `demo_cumulative_net_pnl=-0.033506`.
  - `stopped_reason=null`.

## OKX Demo Window Validation

- Command:
  - `UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 10 --symbol BTC/USDT --json`
- Result:
  - Exit 0.
  - `local_validation.status=Pass`.
  - `demo_window_validation.status=Pass`.
  - Demo metrics: `cycles_completed=10`, `total=50`, `executed=10`, `skipped=40`, `wins=10`, `losses=0`, `net_profit=16.549322`, `win_rate_pct=100.00`, `max_drawdown_usdt=0`.
  - `triangular-multi-route` executed 10 times; `cross-exchange`, `funding-carry-hedged`, `spot-perp-carry`, and `futures-perp-basis` were each skipped 10 times by `demo_preflight_not_profitable`.
  - All executed triangular orders had `pnl_validation.within_tolerance=true`, `pnl_validation.exchange_receipts.complete=true`, and `pnl_validation.residual_inventory_within_tolerance=true`.
  - Latest parsed journal window: `max_residual_inventory_usdt=0.025127`, below the configured `demo_residual_inventory_tolerance_usdt=0.10`.
  - Post-run open risk: `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`, `demo=true`.

## Promotion Check

- Command:
  - `UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy promotion-status --config ../configs/okx.demo.example.yaml --strategy all --json`
- Result:
  - Exit 0.
  - `triangular-multi-route`: `local=Pass`, `demo=Pass`, `live=Fail`, `promotable_to_live_canary=false`.
  - Live remains blocked by `live_canary_promotion_disabled`, `live_trading_gate_not_enabled`, and `agent_live_orders_disabled`.

## Tests

- Command:
  - `uv run pytest tests/unit/test_strategy_runtime.py tests/unit/test_strategy_validation.py tests/unit/test_config.py -q`
- Result:
  - `37 passed in 0.44s`.
- Command:
  - `uv run pytest tests/ -q`
- Result:
  - `269 passed in 8.26s`.
- Command:
  - `uv run ruff check src/ tests/`
- Result:
  - `All checks passed!`.
- Command:
  - `uv run mypy src/`
- Result:
  - `Success: no issues found in 92 source files`.

## Safety Result

- Live trading remains disabled by default.
- Newly expanded demo strategies remain `live_supported=false`.
- OKX live config still has `agent_trading.allow_live_orders=false`.
- Demo validation and demo-window execution now require local validation first.
- Negative demo preflight estimates do not submit orders.
- Partial or unfilled demo sequences stop before later legs and unwind already-filled legs.
- Demo-window evidence now includes residual-inventory valuation and blocks promotion if residual inventory exceeds tolerance.
- No hardcoded API keys or plaintext secrets were added.

## Remaining Follow-Up

- Carry/basis paths have submit/cancel demo validation, but `strategy validate-demo-window` skipped them because the current preflight net PnL was negative.
- Keep `triangular-multi-route` at the current 2x OKX demo canary size until repeated windows across different market conditions keep receipts complete, drawdown at zero or acceptable, and residual inventory below tolerance.
- Live canary remains disabled and should stay disabled until an operator explicitly reviews longer demo evidence and changes the separate live safety gates.
