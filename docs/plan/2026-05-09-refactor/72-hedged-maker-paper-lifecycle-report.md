# Hedged Maker Paper Lifecycle Report

Date: 2026-05-16

## Summary

Implemented stateful paper lifecycle simulation for `hedged-maker`. Paper runs now persist open maker quotes, keep unchanged quotes inside the configured reprice threshold, cancel/replace expired quotes, simulate crossed maker fills, attribute the taker hedge, and separate realized paper PnL from expected scan edge.

This phase does not add OKX Demo or live maker order support. It keeps the strategy paper-only while improving evidence quality for future sandbox readiness work.

## Implemented

- Added `hedged_maker.paper_state_path` with safe default `logs/hedged-maker-paper-state.json`.
- Added `HedgedMakerPaperLifecycleService` with JSON state persistence.
- Added lifecycle statuses:
  - `quoted`
  - `active_quote_unchanged`
  - `replaced_after_ttl`
  - `requoted`
  - `filled_and_hedged`
  - `blocked_open_order_limit`
- Added Decimal fill and hedge attribution:
  - maker fill notional
  - hedge top-of-book notional
  - maker/taker fees
  - hedge slippage
  - realized net PnL
- Routed `StrategyRunner` hedged-maker paper execution through lifecycle simulation instead of treating maker and hedge legs as instant realized fills.
- Preserved expected scan edge in `execution.expected_net_profit` while cycle `net_profit` now reflects realized lifecycle PnL.
- Updated retrospective handling so pending hedged-maker paper quotes with zero realized PnL are not misclassified as execution losses.
- Updated README, DESIGN, acceptance checklist, traceability matrix, configs, unit tests, and CLI integration tests.

## Safety

- Lifecycle results report `paper_only=true`, `dry_run=true`, `simulation_only=true`, `orders_sent=false`, and `live_orders_sent=false`.
- State is paper-only JSON under `hedged_maker.paper_state_path`; it is not a live order store.
- `hedged-maker` remains registered with `demo_supported=false` and `live_supported=false`.
- OKX demo config keeps hedged-maker on mock/mock-alt and does not enable OKX demo maker orders.
- Pending quote PnL is not counted as realized profit.

## Verification

Commands run from `backend`:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_lifecycle.py tests/unit/test_hedged_maker_strategy.py tests/unit/test_config.py tests/unit/test_strategy_runtime.py tests/integration/test_cli_core.py -v
```

Result: `96 passed in 8.12s`.

```bash
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
```

Result: `All checks passed!`

```bash
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

Result: `Success: no issues found in 124 source files`.

CLI smoke:

```bash
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy run --config /private/tmp/coinbot-hedged-maker-lifecycle-smoke-3.yaml --strategy hedged-maker --max-cycles 2 --interval-seconds 0 --execution-mode paper --symbol BTC/USDT --json
```

Result: `completed=true`, `cycles_completed=2`, cycle 1 lifecycle `status=quoted`, cycle 2 lifecycle `status=active_quote_unchanged`, `orders_sent=false`, `live_orders_sent=false`, `expected_net_profit=0.5505461638204916983251574286`, realized `net_profit=0`, state path `/private/tmp/coinbot-hedged-maker-lifecycle-state-3.json`, and `retrospective_after.open_issue_count=0`.

## Acceptance

- Paper quote lifecycle state is persisted and visible in CLI JSON output.
- Repeated same-symbol paper runs reuse the active quote when reprice threshold is not crossed.
- Expired quotes are canceled and replaced.
- Crossed existing quotes simulate maker fill plus taker hedge and record realized PnL.
- Pending quotes are not treated as realized profits or losses.
- Demo/live maker quoting remains disabled.
