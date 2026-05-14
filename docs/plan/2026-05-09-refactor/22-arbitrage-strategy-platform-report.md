# OKX-First Arbitrage Strategy Platform Report

Date: 2026-05-10

## Implemented

- Added configurable multi-route triangular scanning.
- Added spot-perp carry, hedged funding carry, and futures-perp basis scanners.
- Extended mock exchange fixtures with SOL, swap, and dated futures data.
- Extended OKX exchange interface with instrument metadata and futures basis quote methods.
- Added strategy catalog, scan controller, score service, and portfolio service.
- Enabled local-first OKX Demo Trading canary support for `funding-carry-hedged`, `spot-perp-carry`, and `futures-perp-basis`.
- Added OKX demo residual-inventory tracking so demo-window validation can fail if non-USDT dust exceeds `strategy_runtime.demo_residual_inventory_tolerance_usdt`.
- Added CLI commands:
  - `crypto-assistant strategy catalog --json`
  - `crypto-assistant strategy scan --strategy all --symbol BTC/USDT --json`
  - `crypto-assistant strategy score --strategy all --json`
  - `crypto-assistant strategy portfolio-status --json`
- Migrated legacy strategy names to compatibility aliases:
  - `triangular` -> `triangular-multi-route`
  - `funding-rate` -> `funding-carry-hedged`
  - `spot-perp` -> `spot-perp-carry`

## Validation

- Targeted test command:
  - `UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_arbitrage_calculators.py tests/unit/test_strategy_platform.py tests/unit/test_strategy_runtime.py tests/unit/test_exchange_market_account.py tests/unit/test_okx_exchange_adapter.py tests/integration/test_cli_core.py tests/e2e/test_dry_run_flow.py -q`
- Result:
  - `51 passed in 6.36s`
- Follow-up targeted test command after allowlist/policy updates:
  - `UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_strategy_runtime.py tests/unit/test_strategy_platform.py tests/integration/test_cli_core.py tests/e2e/test_dry_run_flow.py -q`
- Result:
  - `38 passed in 7.23s`
- Full backend test command:
  - `UV_CACHE_DIR=.uv-cache uv run pytest tests/ -q`
- Result:
  - `269 passed in 8.26s`
- Expanded demo-canary targeted test command:
  - `uv run pytest tests/unit/test_strategy_runtime.py tests/unit/test_strategy_platform.py tests/integration/test_cli_core.py -q`
- Result:
  - `39 passed in 0.70s`
- Lint command:
  - `UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/`
- Result:
  - `All checks passed!`
- Type-check command:
  - `UV_CACHE_DIR=.uv-cache uv run mypy src/`
- Result:
  - `Success: no issues found in 92 source files`
- Latest OKX demo-window command:
  - `UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 10 --symbol BTC/USDT --json`
- Result:
  - Exit 0; `demo_window_validation.status=Pass`, `executed=10`, `skipped=40`, `net_profit=16.549322`, `win_rate_pct=100.00`, `max_drawdown_usdt=0`, all executed receipts complete, all PnL and residual-inventory checks within tolerance, and post-run `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`.

## CLI Acceptance

- `UV_CACHE_DIR=.uv-cache uv run crypto-assistant config validate --config ../configs/config.example.yaml --json`
  - Exit 0; safe config shows `live_trading=false`, `dry_run=true`, and `require_confirm_before_order=true`.
- `UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy catalog --json`
  - Exit 0; lists 5 canonical strategies and 3 compatibility aliases.
- `UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy scan --strategy all --symbol BTC/USDT --json`
  - Exit 0; returns mock opportunities for cross-exchange, multi-route triangular, funding carry, spot-perp carry, and futures-perp basis.
- `UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy score --strategy all --json`
  - Exit 0; returns scorecards for all 5 strategies.
- `UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy portfolio-status --json`
  - Exit 0; selected `triangular-multi-route`, `cross-exchange`, and `spot-perp-carry` under default max-concurrency 3.
- `UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy catalog --help`
- `UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy scan --help`
- `UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy score --help`
- `UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy portfolio-status --help`
  - All returned exit 0 with argparse help output.

## Safety Result

- Safe default config remains `live_trading=false`, `dry_run=true`, and `require_confirm_before_order=true`.
- OKX demo config remains separate from OKX live config and uses `.env.okx.demo`.
- OKX live config keeps `agent_trading.allow_live_orders=false`.
- New strategy platform commands do not submit orders.
- New strategies are still local/paper-first. OKX demo execution is now available only after local validation, allowlist checks, demo-mode verification, and small canary order caps.
- OKX demo validation now records non-USDT residual inventory; the latest 10-cycle window had `max_residual_inventory_usdt=0.025127`, below the configured `0.10` tolerance.

## Deferred

- Multi-CEX real cross-exchange demo/live promotion remains Deferred until additional real exchange adapters and sandbox tests exist.
- Further position-size escalation for `spot-perp-carry`, `funding-carry-hedged`, and `futures-perp-basis` remains Deferred until their own profitable OKX demo preflight windows appear; current markets kept these paths skipped by `demo_preflight_not_profitable`.
- Live-canary remains Disabled by default and requires separate operator approval plus validation evidence.
