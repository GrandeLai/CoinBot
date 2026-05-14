# Carry And Basis Scan Diagnostics

Date: 2026-05-11

## Scope

Implemented the next offline optimization step for the non-triangular strategies that are currently blocked from OKX Demo Trading by negative demo preflight.

The goal was not to force those strategies into demo execution. The goal was to make their scan and score output explainable:

- why a candidate was filtered
- what the current candidate net PnL is
- how far it is from the configured minimum
- whether depth is sufficient
- which cost component dominates

## Implementation

Changed files:

- `backend/src/trading_assistant/arbitrage/spot_perp_carry.py`
- `backend/src/trading_assistant/arbitrage/funding_carry_hedged.py`
- `backend/src/trading_assistant/arbitrage/futures_perp_basis.py`
- `backend/src/trading_assistant/arbitrage/scanner.py`
- `backend/src/trading_assistant/strategies/platform.py`
- `backend/tests/unit/test_strategy_platform.py`
- `backend/tests/integration/test_cli_core.py`

New behavior:

- `SpotPerpCarryScanner.diagnose(...)`
- `FundingCarryHedgedScanner.diagnose(...)`
- `FuturesPerpBasisScanner.diagnose(...)`
- `ArbitrageScanner.diagnose(...)`
- `StrategyScanReport.diagnostics`
- score-card reasons from scan diagnostics:
  - `scan_diagnostic:<reason>`
  - `scan_break_even_gap_usdt:<value>`
  - `scan_candidate_net_profit_usdt:<value>`

The diagnostics are read-only and run inside the existing scan path. They do not send orders.

## Local CLI Evidence

Commands:

- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy scan --config ../configs/config.example.yaml --strategy spot-perp-carry --symbol BTC/USDT --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy score --config ../configs/config.example.yaml --strategy spot-perp-carry --symbol BTC/USDT --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy scan --config ../configs/config.example.yaml --strategy funding-carry-hedged --symbol BTC/USDT --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy scan --config ../configs/config.example.yaml --strategy futures-perp-basis --symbol BTC/USDT --json`

Results:

- `spot-perp-carry` scan includes diagnostics:
  - `net_profit_usdt=0.3799120175964807038592281543`
  - `min_required_net_profit_usdt=0.15`
  - `break_even_gap_usdt=0`
  - `depth_sufficient=true`
- `funding-carry-hedged` scan includes diagnostics:
  - candidate count `2`
  - approved count `1`
  - best candidate `BTC/USDT`
  - rejected candidate `ETH/USDT` has `break_even_gap_usdt=0.2753846153846153846153846154`
- `futures-perp-basis` scan includes diagnostics:
  - `net_profit_usdt=0.3181094527363184079601990050`
  - `min_required_net_profit_usdt=0.15`
  - `break_even_gap_usdt=0`

Important interpretation:

- Local mock scan candidates are profitable because mock fixtures are designed to test the strategy engines.
- OKX demo execution remains blocked for non-triangular strategies when demo preflight is negative.
- The new diagnostics help tune offline scanners and thresholds without weakening OKX demo gates.

## Tests

- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_platform.py::test_strategy_scan_reports_break_even_diagnostics_when_carry_filtered tests/integration/test_cli_core.py::test_cli_strategy_list_run_and_review -q`
  - Result: `2 passed in 0.52s`
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/arbitrage/spot_perp_carry.py src/trading_assistant/arbitrage/funding_carry_hedged.py src/trading_assistant/arbitrage/futures_perp_basis.py src/trading_assistant/arbitrage/scanner.py src/trading_assistant/strategies/platform.py tests/unit/test_strategy_platform.py tests/integration/test_cli_core.py`
  - Result: `All checks passed!`
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/arbitrage/spot_perp_carry.py src/trading_assistant/arbitrage/funding_carry_hedged.py src/trading_assistant/arbitrage/futures_perp_basis.py src/trading_assistant/arbitrage/scanner.py src/trading_assistant/strategies/platform.py`
  - Result: `Success: no issues found in 5 source files`
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q`
  - Result: `289 passed in 7.55s`
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/`
  - Result: `All checks passed!`
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/`
  - Result: `Success: no issues found in 95 source files`
- `find docs/plan -maxdepth 1 -type f -print`
  - Result: no files directly under `docs/plan`
- Hardcoded secret scan
  - Result: no matches

## Safety

- No OKX API access.
- No OKX Demo Trading order.
- No live order.
- No change to demo preflight thresholds.
- No change to live gates.
- No guard or retrospective state mutation.

## Decision

This closes the first offline optimization gap for blocked carry/basis strategies. Before any new OKX demo attempt for these strategies, run:

`crypto-assistant strategy scan --config configs/config.example.yaml --strategy all --symbol BTC/USDT --json`

and inspect `diagnostics`. A strategy should not enter OKX demo execution unless local diagnostics and OKX demo preflight both show positive net PnL.
