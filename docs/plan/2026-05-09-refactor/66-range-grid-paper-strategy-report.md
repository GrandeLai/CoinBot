# Range Grid Paper Strategy Report

Date: 2026-05-16

## Summary

Implemented the P1 `range-grid` paper strategy from the open-source profit-logic research plan. The strategy is designed for range-bound crypto markets only: it uses the dynamic universe/regime router, builds a bounded grid from completed candle highs/lows, estimates completed round-trip grid-cycle PnL after fees and slippage, and emits a normal `ArbitrageOpportunity` for existing scan, score, risk, budget, paper execution, journal, retrospective, and evolution paths.

`range-grid` is intentionally not connected to OKX Demo Trading or live execution. It is registered with `demo_supported=false` and `live_supported=false`, and every emitted opportunity carries `read_only=true` and `paper_only=true`.

## Implemented

- Added `RangeGridConfig` with safe defaults under `range_grid`.
- Added `RangeGridStrategyService.scan()` and `diagnose()`.
- Added scanner, strategy registry, strategy platform, runner, execution-engine, and CLI scan integration for `range-grid`.
- Added paper-runtime coverage so `crypto-assistant strategy run --strategy range-grid --execution-mode paper` can simulate the grid legs through the existing dry-run execution engine.
- Updated `configs/config.example.yaml` and `configs/okx.demo.example.yaml` with explicit `range_grid` settings while keeping demo execution disabled for the strategy.
- Updated README, DESIGN, acceptance checklist, and traceability matrix.

## Safety

- No live trading gates were weakened.
- No OKX Demo grid orders were implemented.
- No credentials, secrets, passphrases, or tokens were added.
- Paper execution uses simulated buy/sell legs only.
- A future OKX Demo grid implementation must add a stateful order manager, cancellation/reprice handling, residual inventory controls, and sandbox validation before any exchange dispatch is allowed.

## Verification

Commands run from `backend` unless noted:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_range_grid_strategy.py -v
```

Result: `2 passed`.

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_strategy_platform.py -v
```

Result: `13 passed`.

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_config.py -v
```

Result: `8 passed`.

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_cli_core.py -v
```

Result: `22 passed`.

```bash
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
```

Result: `All checks passed!`

```bash
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

Result: `Success: no issues found in 122 source files`.

CLI smoke used `/private/tmp/coinbot-range-grid-smoke.yaml` so runtime journal, retrospective, and evolution outputs did not modify the repository:

```bash
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy scan --config /private/tmp/coinbot-range-grid-smoke.yaml --strategy range-grid --symbol BTC/USDT --exchange mock --json
```

Result: emitted one `range-grid-mock-btc-usdt` opportunity with `regime=range`, `paper_only=true`, and `net_profit=0.2945929674008451713867240444`.

```bash
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy run --config /private/tmp/coinbot-range-grid-smoke.yaml --strategy range-grid --max-cycles 1 --interval-seconds 0 --execution-mode paper --symbol BTC/USDT --json
```

Result: completed one paper cycle with `decision=executed`, `risk_approved=true`, `dry_run=true`, and `net_profit=0.2945929674008451713867240444`.

## Acceptance

- `range-grid` scans and diagnoses range-bound opportunities.
- Non-range regimes return no opportunity and explain `regime_not_range`.
- Strategy catalog includes `range-grid`.
- Demo validation names exclude `range-grid`.
- Paper runtime can execute the simulated opportunity through dry-run only.
- Docs and traceability are updated under the refactor directory.
