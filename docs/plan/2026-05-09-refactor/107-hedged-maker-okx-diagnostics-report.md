# Hedged Maker OKX Target Diagnostics Report

Date: 2026-05-21

## Goal

Fix the misleading OKX hedged-maker diagnostics path so preflight analysis reports real candidate-quality reasons instead of a disabled local mock hedge exchange.

## Implementation

- Updated `StrategyController._diagnose_definition` so OKX-targeted `hedged-maker` diagnostics call `HedgedMakerDemoCandidateService.candidate(..., target_exchange="okx")`.
- Kept non-OKX paper diagnostics on the existing generic hedged-maker scanner path.
- Passed the explicit `scan(..., exchange=...)` value into diagnostics so targeted scans and their diagnostic evidence use the same exchange.
- Added a regression test where `mock_alt` is disabled and `hedged_maker.hedge_exchange=mock_alt`, then verified `StrategyController.scan(strategy_name="hedged-maker")` still returns OKX candidate diagnostics.
- Added a regression test where the default enabled exchange is `mock`, `exchange="okx"` is passed explicitly, and diagnostics still use the OKX candidate path.
- Updated README, DESIGN, traceability, and final acceptance notes.

## Safety Boundaries

- The diagnostic path is read-only.
- It sends no maker orders, hedge orders, demo orders, or live orders.
- It does not write paper, demo, audit, journal, runtime guard, retrospective, or evolution state.
- The generic `strategy run --strategy hedged-maker --execution-mode demo` path remains unsupported.
- The explicit `hedged-maker-demo` manager still owns OKX Demo credential, operator, audit, execution-quality, risk, budget, provider demo-mode, and order-dispatch gates.

## OKX Demo Findings

Read-only `market-compare` after the fix produced an OKX hedged-maker opportunity payload and no longer reported `diagnostic_error:Exchange is disabled: mock_alt`.

The payload stayed observe-only because economics were too thin:

- `approved=false`
- `reasons=["edge_below_minimum"]`
- gross profit about `0.2003365666 USDT`
- fees about `0.1802003366 USDT`
- slippage about `0.0200400673 USDT`
- net profit about `0.0000961627 USDT`
- `orders_sent=false`
- `live_orders_sent=false`

Read-only bounded BTC carry/basis observer also produced no OKX demo preflight candidate:

- `evaluated_symbol_count=1`
- `target_demo_preflight_candidate_count=0`
- `total_card_count=3`
- `filtered_out_count=3` with `--min-quality-score 80`
- `funding-carry-hedged`: funding annualized below minimum and net profit below minimum
- `spot-perp-carry`: basis below minimum, funding annualized below minimum, and net profit below minimum
- `futures-perp-basis`: positive net profit about `0.007129 USDT`, but below the `0.075000 USDT` minimum and still about `0.067871 USDT` short of break-even buffer

## Verification

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_hedged_maker_demo.py::test_strategy_scan_uses_okx_hedged_maker_candidate_diagnostics -q
```

Result: failed before implementation with missing candidate diagnostic fields; passed after implementation.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_hedged_maker_demo.py::test_hedged_maker_demo_candidate_builds_okx_opportunity_payload tests/unit/test_hedged_maker_demo.py::test_strategy_scan_uses_okx_hedged_maker_candidate_diagnostics tests/unit/test_hedged_maker_demo.py::test_strategy_scan_honors_explicit_okx_exchange_for_hedged_maker_diagnostics -q
```

Result: `3 passed`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/platform.py tests/unit/test_hedged_maker_demo.py
```

Result: `All checks passed!`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/strategies/platform.py
```

Result: `Success: no issues found in 1 source file`.

```bash
git diff --check
```

Result: exit `0`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy market-compare --config ../configs/okx.demo.example.yaml --strategy hedged-maker --symbol BTC/USDT --target-exchange okx --json
```

Result: exit `0`; JSON reported `read_only=true`, `orders_sent=false`, `approved=false`, `demo_manager_compatible=true`, `reasons=["edge_below_minimum"]`, and no `diagnostic_error:Exchange is disabled: mock_alt`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy carry-basis-optimize --config ../configs/okx.demo.example.yaml --symbols BTC/USDT --target-exchange okx --min-quality-score 80 --max-symbols 1 --request-budget-seconds 90 --per-symbol-timeout-seconds 60 --json
```

Result: exit `0`; JSON reported `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, `evaluated_symbol_count=1`, `target_demo_preflight_candidate_count=0`, `total_card_count=3`, `filtered_out_count=3`, and `timeout_symbol_count=0`.

## Next Step

Keep `hedged-maker` in observation until OKX net edge remains above the configured minimum after fees and slippage. Continue using bounded carry/basis observer and hedged-maker candidate diagnostics before any OKX Demo manager attempt; do not lower preflight thresholds to force orders.
