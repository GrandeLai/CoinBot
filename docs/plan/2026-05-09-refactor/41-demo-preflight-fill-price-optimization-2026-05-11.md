# Demo Preflight Fill Price Optimization

Date: 2026-05-11

## Goal

Optimize strategy/demo parameters without weakening safety gates, lowering the positive-PnL preflight threshold, or increasing demo order size.

The observed issue was that OKX demo preflight treated a marketable limit order's submitted protection price as the expected fill price. For a buy order, the protection price is intentionally above best ask; for a sell order, it is below best bid. Using those protection prices as expected fills made preflight too conservative and could block otherwise positive tiny triangular canaries.

## Change

- Demo execution still submits marketable limit orders with `strategy_runtime.demo_limit_price_buffer_pct`.
- Demo preflight now estimates PnL from current top-of-book expected fill prices when orderbook data is available.
- Preflight JSON now shows both:
  - `submitted_limit_price`
  - `expected_fill_price`
  - `submitted_limit_notional_usdt`
  - `estimated_notional_usdt`
- Fees, positive preflight gate, local validation, risk checks, demo caps, receipt checks, residual-inventory checks, and no-open-risk checks remain unchanged.

## Safety

- No live-trading gate changed.
- No demo size cap changed.
- `demo_min_preflight_net_pnl_usdt` remains `0`.
- Negative preflight strategies still skip execution.
- The optimization only separates "limit protection price" from "expected fill price"; it does not force orders.

## Verification Before Demo

Targeted unit tests:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest \
  tests/unit/test_strategy_runtime.py::test_strategy_demo_preflight_uses_orderbook_expected_fill_price_not_limit_cap \
  tests/unit/test_strategy_runtime.py::test_strategy_demo_execution_uses_spot_orderbook_for_marketable_limits \
  tests/unit/test_strategy_runtime.py::test_strategy_runner_skips_unprofitable_demo_preflight_without_ordering \
  -q
```

Result:

- New focused test: `1 passed in 0.41s`.
- Existing focused tests: `2 passed in 0.34s`.

Full verification after docs sync:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q
UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=../.uv-cache uv run mypy src/
find docs/plan -maxdepth 1 -type f -print
rg -n "(?i)(api[_-]?key|api[_-]?secret|passphrase|token)\s*[:=]\s*['\"][A-Za-z0-9_./+=-]{12,}" --glob '!*.lock' --glob '!docs/plan/2026-05-09-refactor/28-strategy-retrospective.state.json' .
```

Result:

- `293 passed in 27.88s`.
- `All checks passed!`.
- `Success: no issues found in 96 source files`.
- Refactor document directory scan returned no files directly under `docs/plan`.
- Hardcoded secret scan returned no matches.

Read-only OKX demo preview after the change:

- `cross-exchange`: `net_pnl_usdt=-0.032226`, skipped.
- `triangular`: `net_pnl_usdt=0.067597`, approved for demo-window gate.
- `funding-carry-hedged`: `net_pnl_usdt=-0.065231`, skipped.
- `spot-perp-carry`: `net_pnl_usdt=-0.065131`, skipped.
- `futures-perp-basis`: `net_pnl_usdt=-0.065324`, skipped.

## Demo Execution Result

Command:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window \
  --config ../configs/okx.demo.example.yaml \
  --strategy all \
  --cycles 1 \
  --symbol BTC/USDT \
  --json
```

Result:

- Local validation: `Pass`.
- Demo status: `Needs More Samples`.
- Reason: `minimum_samples_not_met:1<10`.
- Executed: `1`.
- Skipped: `4`.
- Wins: `1`.
- Losses: `0`.
- Demo net profit: `0.026190 USDT`.
- Post-run open spot orders: `0`.
- Post-run open swap orders: `0`.
- Post-run swap positions: `0`.

Executed strategy:

- `triangular-multi-route`.
- Approved preflight net PnL: `0.064467 USDT`.
- Actual order cash-flow PnL: `0.026190 USDT`.
- Expected-vs-actual gap: `-0.038277 USDT`.
- PnL reconciliation within tolerance: `true`.
- Exchange receipts complete: `true`.
- Residual inventory within tolerance: `true`.
- No live orders sent.

Skipped strategies:

- `cross-exchange`: `demo_preflight_not_profitable`.
- `funding-carry-hedged`: `demo_preflight_not_profitable`.
- `spot-perp-carry`: `demo_preflight_not_profitable`.
- `futures-perp-basis`: `demo_preflight_not_profitable`.

## Account Equity Note

After the demo canary, the account marked-to-market estimate was:

- `97245.58046108809 USDT`.

This includes `USDT`, `BTC`, `ETH`, and `OKB` valued from current OKX prices. It decreased versus the prior snapshot because the account holds material BTC/ETH/OKB inventory and market prices moved. The strategy canary itself recorded positive order cash-flow PnL, so whole-account equity movement must not be attributed only to the strategy.

## Follow-Up

- Continue using local validation and read-only preview before demo orders.
- Keep non-triangular strategies skipped until their top-of-book preflight net PnL turns positive.
- Collect more new samples with persisted approved preflight estimates before any size increase.
- Consider adding an account-equity report that includes OKB in the standard PnL validation reference set, while keeping strategy cash-flow PnL separate from whole-account market movement.
