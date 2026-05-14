# Opportunity Density And Route Discovery Report

Date: 2026-05-13

## Scope

This addendum implements the OKX opportunity-density and triangular route-discovery optimization. The goal is to improve real candidate discovery before any demo size increase, not to force OKX demo or live orders.

## Implemented

- Added `OpportunityDensityService`.
- Added `TriangularRouteDiscoveryService`.
- Added CLI commands:
  - `crypto-assistant strategy opportunity-report --config ... --window 24h --json`
  - `crypto-assistant strategy discover-routes --config ... --exchange okx --quote USDT --json`
  - `crypto-assistant strategy scan --strategy triangular-multi-route --exchange okx --route-mode discovered --json`
- Extended `strategy scan` with `--exchange` and `--route-mode configured|discovered`.
- Extended OKX public adapter with bulk spot ticker access through `/api/v5/market/tickers`.
- Upgraded `triangular-multi-route` metadata to record:
  - multi-level orderbook expected fill price
  - submitted limit price
  - depth consumed
  - fee estimate
  - slippage estimate
  - min-size adjustment
  - route-level preflight quality summary

## Read-Only OKX Check

Command:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy discover-routes --config ../configs/okx.demo.example.yaml --exchange okx --quote USDT --route-limit 20 --json
```

Result:

- Exit code: `0`.
- Orders sent: `false`.
- Accepted OKX routes observed:
  - `USDT -> BTC -> ETH -> USDT`
  - `USDT -> BTC -> SOL -> USDT`
  - `USDT -> USDC -> ETH -> USDT`
  - `USDT -> USDC -> ADA -> USDT`
  - `USDT -> USDC -> ONDO -> USDT`
- Filtered routes reported reasons such as `missing_symbol:*` and `route_depth_below_minimum`.
- No OKX demo order or live order was submitted.

## Local Verification

Commands:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_arbitrage_calculators.py::test_new_okx_first_arbitrage_scanners_return_paper_opportunities tests/unit/test_strategy_platform.py::test_triangular_route_discovery_expands_and_explains_mock_routes tests/unit/test_strategy_platform.py::test_opportunity_density_report_aggregates_expected_actual_and_break_even_gaps tests/integration/test_cli_core.py::test_cli_strategy_list_run_and_review tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -q
UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=../.uv-cache uv run mypy src/
```

Results:

- Targeted tests: `5 passed`.
- Full backend tests: `314 passed`.
- Ruff: `All checks passed!`.
- Mypy: `Success: no issues found in 109 source files`.
- Refactor document directory scan: no files directly under `docs/plan`.
- Hardcoded key/secret/passphrase/token scan: no matches outside ignored local env/log/cache paths.

## Safety Notes

- `strategy opportunity-report` reads only the strategy journal.
- `strategy discover-routes` reads only exchange public market/instrument data.
- `strategy scan --route-mode discovered` performs scan-only market reads and does not place orders.
- Live trading remains disabled by default.
- Demo order gates remain unchanged.
- The report explicitly marks size-stage readiness as blocked when recent demo evidence lacks enough clean samples or preflight snapshots.

## Follow-Up

- Run `strategy opportunity-report` before every future demo size-stage decision.
- Run OKX `discover-routes` before triangular scans to keep the route universe current.
- Add a compact filtered-route output option if the full OKX universe becomes too noisy for routine operator review.
- Only consider demo execution when local validation, read-only market evidence, runtime guard, preflight, risk, and open-risk checks all pass.
