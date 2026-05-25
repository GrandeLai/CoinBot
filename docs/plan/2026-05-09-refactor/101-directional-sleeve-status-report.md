# Directional Sleeve Status Report

Date: 2026-05-20

## Goal

Expose a conservative promotion view for long-only directional strategies so they can contribute non-triangular evidence without becoming uncapped or live-capable.

## Implementation

- Added `DirectionalSleeveStatusService`.
- Added `crypto-assistant strategy directional-sleeve-status`.
- Strategy rows include:
  - demo support and demo enablement
  - live support fixed to false
  - stage
  - validation executions
  - win rate
  - realized PnL
  - max drawdown
  - execution-quality status
  - runtime guard cooldown
  - configured max order value
  - reasons and recommended actions
- Summary includes directional size/risk caps:
  - `max_position_value_usdt`
  - `total_max_exposure_usdt`
  - `demo_max_order_value_usdt`
  - `single_trade_risk_equity_pct`
  - `daily_loss_pct`

## Safety Boundaries

- The feature is read-only.
- It reads validation and runtime guard state only.
- It does not call the strategy runner, demo executor, broker, live-agent executor, scanner, or exchange APIs.
- It does not write journal, retrospective, guard, evolution, or directional position state.
- It reports `directional_live_supported=false`.
- `demo_eligible_after_standard_gates` is advisory only and cannot bypass demo-window, runtime guard, risk, preflight, receipt, residual, or live gates.

## Verification

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_directional_strategies.py::test_directional_sleeve_status_reports_promotion_rules tests/integration/test_cli_core.py::test_cli_strategy_directional_sleeve_status_is_read_only -v
```

Result: first failed because `trading_assistant.strategies.directional_sleeve` and `strategy directional-sleeve-status` were missing, then passed after implementation.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_directional_strategies.py::test_directional_sleeve_status_reports_promotion_rules tests/unit/test_directional_strategies.py::test_directional_scanner_wraps_buy_signal_as_opportunity tests/integration/test_cli_core.py::test_cli_strategy_directional_sleeve_status_is_read_only tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -v
```

Result: `4 passed`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/carry_basis_optimizer.py src/trading_assistant/strategies/diversification.py src/trading_assistant/strategies/hedged_maker_candidate.py src/trading_assistant/strategies/directional_sleeve.py src/trading_assistant/application.py src/trading_assistant/cli/main.py tests/unit/test_strategy_platform.py tests/unit/test_advisory_ranker.py tests/unit/test_hedged_maker_demo.py tests/unit/test_directional_strategies.py tests/integration/test_cli_core.py
```

Result: `All checks passed!`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/strategies/carry_basis_optimizer.py src/trading_assistant/strategies/diversification.py src/trading_assistant/strategies/hedged_maker_candidate.py src/trading_assistant/strategies/directional_sleeve.py src/trading_assistant/application.py src/trading_assistant/cli/main.py
```

Result: `Success: no issues found in 6 source files`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy directional-sleeve-status --config ../configs/config.example.yaml --execution-mode paper --limit 20 --json
```

Result: exit `0`; JSON reported `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, `strategy_count=5`, `demo_enabled_strategy_count=4`, `demo_eligible_count=2`, `directional_live_supported=false`, and guardrail `directional_live_trading_not_supported`.

## Next Step

Use the sleeve status together with diversification reporting before deciding which non-triangular strategy family gets the next validation window.
