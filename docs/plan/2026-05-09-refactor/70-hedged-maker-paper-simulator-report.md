# Hedged Maker Paper Simulator Report

Date: 2026-05-16

## Summary

Implemented a paper-only hedged maker / XEMM simulator that evaluates passive maker quotes against an immediate taker hedge on a second exchange. The strategy estimates maker-buy/hedge-sell and maker-sell/hedge-buy candidates, subtracts maker/taker fees and hedge slippage, checks maker inventory and hedge depth, and emits normal strategy opportunities with explicit `read_only=true` and `paper_only=true` metadata.

This phase expands profit-discovery coverage without enabling demo or live order support for maker quoting. It does not send exchange orders, does not reuse OKX demo order paths, and does not relax existing risk gates.

## Implemented

- Added `HedgedMakerConfig` with conservative mock/mock-alt defaults, Decimal economics, inventory/depth thresholds, and validation.
- Added `HedgedMakerStrategyService` with quote planning, hedge preview, diagnostics, and opportunity construction.
- Routed `hedged-maker` through the arbitrage scanner, strategy registry, platform controller, strategy runner, dry-run execution lookup, and CLI choices.
- Registered the strategy as market-making, paper-only, demo-disabled, and live-disabled.
- Added unit and integration coverage for opportunity emission, weak-edge diagnostics, config loading, catalog visibility, and paper strategy run flow.
- Updated README, DESIGN, acceptance checklist, and traceability matrix.

## Safety

- Opportunities include `read_only=true`, `paper_only=true`, `demo_supported=false`, and `live_supported=false`.
- Strategy registry excludes `hedged-maker` from demo validation names.
- Paper runtime uses dry-run execution and records simulated orders only.
- OKX demo config keeps hedged-maker on `mock`/`mock_alt`; no OKX demo maker order dispatch is introduced.
- Real maker quoting remains deferred until own-order tracking, cancel/refresh control, fill reconciliation, and sandbox parity tests exist.

## Verification

Commands run from `backend`:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_strategy.py tests/unit/test_strategy_platform.py tests/unit/test_config.py tests/integration/test_cli_core.py -v
```

Result: `47 passed in 9.07s`.

```bash
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
```

Result: `All checks passed!`

```bash
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

Result: `Success: no issues found in 123 source files`.

CLI smoke:

```bash
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy scan --config ../configs/config.example.yaml --strategy hedged-maker --symbol BTC/USDT --json
```

Result: emitted one `hedged-maker` opportunity for `BTC/USDT`, `opportunity_id=hedged-maker-mock-mock_alt-btc-usdt`, `paper_only=true`, `maker_order_type=limit_post_only`, `hedge_order_type=taker_market_preview`, and `net_profit=0.5505461638204916983251574286`.

```bash
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy run --config /private/tmp/coinbot-hedged-maker-smoke.yaml --strategy hedged-maker --max-cycles 1 --interval-seconds 0 --execution-mode paper --symbol BTC/USDT --json
```

Result: `completed=true`, `cycles_completed=1`, `decision=executed`, `execution.status=simulated`, `execution.dry_run=true`, `selected_opportunity_id=hedged-maker-mock-mock_alt-btc-usdt`, and runtime journal/guard/retrospective/evolution artifacts were written under `/private/tmp`.

## Acceptance

- Hedged-maker opportunity discovery uses fees, hedge slippage, maker inventory, and hedge depth before approval.
- Strategy scan and paper run are available through existing CLI/runtime surfaces.
- Demo and live support remain disabled in registry and metadata.
- Documentation and traceability records describe the paper-only caveat and next safety prerequisites.
