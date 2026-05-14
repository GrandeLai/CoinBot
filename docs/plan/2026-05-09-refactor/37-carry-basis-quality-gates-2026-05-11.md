# Carry And Basis Quality Gates

Date: 2026-05-11

## Scope

Implemented the next offline optimization step for non-triangular carry and basis strategies.

The previous diagnostics made filtered candidates explainable. This change adds configurable quality gates so carry/basis strategies can be made stricter before any OKX Demo Trading attempt:

- minimum funding annualized percentage
- maximum basis hedge cost percentage
- minimum spot-perp basis percentage
- minimum futures-perp basis percentage

No OKX API calls or orders were used for this step.

## Implementation

Changed files:

- `backend/src/trading_assistant/config/schema.py`
- `backend/src/trading_assistant/arbitrage/spot_perp_carry.py`
- `backend/src/trading_assistant/arbitrage/funding_carry_hedged.py`
- `backend/src/trading_assistant/arbitrage/futures_perp_basis.py`
- `configs/config.example.yaml`
- `configs/okx.demo.example.yaml`
- `configs/okx.live.example.yaml`
- `backend/tests/unit/test_config.py`
- `backend/tests/unit/test_strategy_platform.py`

New config fields:

- `arbitrage.funding_min_annualized_pct`
- `arbitrage.funding_max_basis_hedge_cost_pct`
- `arbitrage.spot_perp_min_basis_pct`
- `arbitrage.futures_basis_min_basis_pct`

New filter reasons:

- `basis_below_minimum`
- `funding_annualized_below_minimum`
- `basis_hedge_cost_above_maximum`
- `futures_basis_below_minimum`

Diagnostics now include the configured thresholds next to observed candidate values, so agents can compare actual market state against the current policy.

## Local CLI Evidence

Commands:

- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy scan --config ../configs/config.example.yaml --strategy spot-perp-carry --symbol BTC/USDT --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy scan --config ../configs/config.example.yaml --strategy funding-carry-hedged --symbol BTC/USDT --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy scan --config ../configs/config.example.yaml --strategy futures-perp-basis --symbol BTC/USDT --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`

Results:

- `spot-perp-carry` diagnostics:
  - `basis_pct=0.4399120175964807038592281544`
  - `min_basis_pct=0.05`
  - `min_funding_annualized_pct=20`
  - `net_profit_usdt=0.3799120175964807038592281543`
  - `break_even_gap_usdt=0`
- `funding-carry-hedged` diagnostics:
  - `candidate_count=2`
  - `approved_count=1`
  - BTC candidate passed with `basis_hedge_cost_pct=0.02500` under max `0.30`
  - ETH candidate was rejected by `basis_hedge_cost_above_maximum` and `net_profit_below_minimum`
- `futures-perp-basis` diagnostics:
  - `futures_perp_basis_pct=0.3781094527363184079601990050`
  - `min_futures_basis_pct=0.05`
  - `min_funding_annualized_pct=20`
  - `net_profit_usdt=0.3181094527363184079601990050`
  - `break_even_gap_usdt=0`
- Local validation:
  - status `Pass`
  - executed `5`
  - skipped `0`
  - blocked `0`
  - wins `5`
  - net profit `4.967117651096646342373316272`

## Tests

- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_quality_gates_explain_basis_and_hedge_cost_filters tests/unit/test_strategy_platform.py::test_strategy_scan_reports_break_even_diagnostics_when_carry_filtered tests/unit/test_config.py::test_loads_safe_example_config tests/unit/test_config.py::test_loads_separate_okx_demo_and_live_configs -q`
  - Result: `4 passed in 0.55s`
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/config/schema.py src/trading_assistant/arbitrage/spot_perp_carry.py src/trading_assistant/arbitrage/funding_carry_hedged.py src/trading_assistant/arbitrage/futures_perp_basis.py tests/unit/test_config.py tests/unit/test_strategy_platform.py`
  - Result: `All checks passed!`
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/config/schema.py src/trading_assistant/arbitrage/spot_perp_carry.py src/trading_assistant/arbitrage/funding_carry_hedged.py src/trading_assistant/arbitrage/futures_perp_basis.py`
  - Result: `Success: no issues found in 4 source files`
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q`
  - Result: `290 passed in 7.70s`
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/`
  - Result: `All checks passed!`
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/`
  - Result: `Success: no issues found in 95 source files`
- `find docs/plan -maxdepth 1 -type f -print`
  - Result: no files directly under `docs/plan`
- Hardcoded secret scan
  - Result: no matches

## Safety

- No OKX network access.
- No OKX Demo Trading orders.
- No live orders.
- No demo preflight threshold reduction.
- No live gate changes.
- No guard state editing.

## Decision

The carry/basis strategies are now stricter and more explainable in local/paper mode. This still does not make them eligible for OKX Demo Trading while their OKX demo preflight remains negative. The next step is to use these diagnostics with real OKX market reads, still without orders, to compare live market candidate economics against local mock assumptions.
