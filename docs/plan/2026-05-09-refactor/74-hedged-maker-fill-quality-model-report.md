# Hedged Maker Fill Quality Model Report

Date: 2026-05-16

## Summary

Implemented a deterministic paper fill-quality model for `hedged-maker` so paper lifecycle evidence now reflects queue position, partial fills, stale quote cancellation, cancel latency, adverse selection, and expanded taker hedge slippage.

The feature remains paper-only. It does not enable OKX demo orders or live orders, and it preserves the existing safe defaults:

```yaml
trading:
  live_trading: false
  dry_run: true
  require_confirm_before_order: true
```

## Implementation

- Added `hedged_maker.paper_queue_ahead_pct` and `paper_min_fill_pct` to derive a deterministic paper fill ratio.
- Added partial fill handling with `partial_open`, `filled_quantity`, and `remaining_quantity`.
- Added stale quote cancellation through `paper_stale_quote_seconds`.
- Added simulated cancel latency through `paper_cancel_latency_seconds` and `cancel_pending`.
- Kept cancel-pending maker quotes fillable before cancel effective time, while preventing repeated cancel requests from extending the effective time.
- Added adverse selection detection from current maker mid-price and `paper_adverse_selection_buffer_pct`.
- Added `paper_adverse_hedge_slippage_multiplier` to expand simulated taker hedge slippage when adverse selection is detected.
- Exposed `fill_quality`, `adverse_selection`, `hedge_slippage_multiplier`, and `effective_hedge_slippage_pct` in simulated hedge payloads.
- Updated example configs, README, DESIGN, acceptance checklist, and traceability matrix.

## Safety

- No live-capable dispatch path was added.
- All execution payloads continue to report `paper_only=true`, `dry_run=true`, `simulation_only=true`, `orders_sent=false`, and `live_orders_sent=false`.
- OKX demo and live configs keep hedged-maker pointed at mock exchanges for this paper lifecycle work.
- The model uses `Decimal` for price, quantity, fee, slippage, and PnL calculations.

## Verification

Red phase:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_lifecycle.py tests/unit/test_config.py::test_loads_safe_example_config -v
```

Result: failed as expected before implementation because the new config fields and lifecycle behavior were missing.

Focused verification:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_lifecycle.py tests/unit/test_config.py -v
```

Result: `16 passed in 0.41s`.

Broader verification:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_lifecycle.py tests/unit/test_config.py tests/integration/test_cli_core.py -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

Final result:

- `40 passed in 6.08s`
- `All checks passed!`
- `Success: no issues found in 124 source files`

CLI smoke:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy run --config /private/tmp/coinbot-hedged-maker-fill-quality-smoke.yaml --strategy hedged-maker --max-cycles 2 --interval-seconds 0 --execution-mode paper --symbol BTC/USDT --json
```

Result:

- Completed 2 paper cycles for `hedged-maker`.
- Cycle 1 status: `replaced_after_ttl`.
- Cycle 2 status: `active_quote_unchanged`.
- `orders_sent=false`.
- `live_orders_sent=false`.
- Journal path: `/private/tmp/coinbot-hedged-maker-fill-quality-events.jsonl`.

## Follow-up

Next ordered item: create the hedged-maker paper evaluation report that summarizes queue/partial-fill/adverse-selection evidence across paper samples and prepares the lifecycle metrics for capital/order budget integration.
