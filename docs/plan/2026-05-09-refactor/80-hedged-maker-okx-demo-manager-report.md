# Hedged Maker OKX Demo Manager Report

Date: 2026-05-16

## Summary

Added an explicit OKX Demo Trading stateful order manager for `hedged-maker` without enabling the generic `strategy run --execution-mode demo` path or any live maker-order dispatch.

The manager accepts only an opportunity JSON file that already describes an OKX `hedged-maker` opportunity with maker quote, hedge preview, and passing execution-quality metadata. It then applies the autonomous demo gate, risk gate, strategy budget gate, provider demo-mode check, and audit logging before it can touch OKX Demo orders.

## Implementation

- Added `trading_assistant.strategies.hedged_maker_demo.HedgedMakerDemoOrderManager`.
- Added `hedged_maker.demo_state_path`, defaulting to `logs/hedged-maker-demo-state.json`.
- Added CLI:

```bash
crypto-assistant strategy hedged-maker-demo --config configs/okx.demo.example.yaml --opportunity-file hedged-maker-okx-opportunity.json --json
```

- Added app facade method `TradingAssistantApp.strategy_hedged_maker_demo`.
- Added operation catalog entry `okx.hedged_maker_demo_order_manager`.
- Added OKX demo config allowlist entry for `hedged-maker`.
- Added docs for the explicit opportunity-file workflow.

## Behavior

- Submits maker quote as OKX Demo spot `ordType=post_only`.
- Persists own-order state under `hedged_maker.demo_state_path`.
- Keeps an existing active quote open when it is still fresh and within reprice threshold.
- Cancels and replaces a stale or repriced quote.
- Reconciles order detail before replacement.
- Submits the hedge only for newly observed maker fill quantity.
- Appends redacted audit events through the existing agent trading gate.
- Reports `live_orders_sent=false`.

## Safety

- Live trading remains disabled by default.
- `hedged-maker` remains `demo_supported=false` and `live_supported=false` in the strategy registry.
- The generic `strategy run --strategy hedged-maker --execution-mode demo` path is still unavailable.
- The manager requires:
  - `trading.live_trading=false`
  - `trading.dry_run=false`
  - `trading.require_confirm_before_order=false`
  - enabled OKX sandbox with `okx_demo=true`
  - `agent_trading.enabled=true`
  - `agent_trading.allow_demo_orders=true`
  - `hedged-maker` in `agent_trading.strategy_allowlist`
  - `okx` in `agent_trading.allowed_exchanges`
  - OKX credentials from environment variables
  - `COINBOT_AGENT_OPERATOR_ID`
  - execution-quality metadata approval
  - risk approval
  - strategy budget approval
  - provider `configured=true` and `demo=true`
  - audit logging

## Verification

RED:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_demo.py tests/unit/test_config.py::test_loads_safe_example_config tests/unit/test_config.py::test_loads_separate_okx_demo_and_live_configs tests/unit/test_operation_hub.py::test_all_live_operations_have_demo_validation_contracts tests/integration/test_cli_core.py::test_cli_agent_operation_catalog_reports_demo_validation tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -v
```

Result: failed during collection with `ModuleNotFoundError: No module named 'trading_assistant.strategies.hedged_maker_demo'`.

Focused GREEN:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_demo.py tests/unit/test_config.py::test_loads_safe_example_config tests/unit/test_config.py::test_loads_separate_okx_demo_and_live_configs tests/unit/test_operation_hub.py::test_all_live_operations_have_demo_validation_contracts tests/integration/test_cli_core.py::test_cli_agent_operation_catalog_reports_demo_validation tests/integration/test_cli_core.py::test_cli_strategy_hedged_maker_demo_blocks_default_config tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -v
```

Result: `10 passed in 0.59s`.

Broader affected regression:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_demo.py tests/unit/test_hedged_maker_lifecycle.py tests/unit/test_hedged_maker_report.py tests/unit/test_strategy_platform.py tests/unit/test_strategy_runtime.py tests/unit/test_config.py tests/unit/test_operation_hub.py tests/integration/test_cli_core.py -v
```

Result: `120 passed in 8.99s`.

Static checks:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

Results:

- `All checks passed!`
- `Success: no issues found in 126 source files`

CLI smoke:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run crypto-assistant agent operation-catalog --json
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy hedged-maker-demo --help
```

Results:

- Operation catalog includes `okx.hedged_maker_demo_order_manager` and `missing_demo_validation=[]`.
- CLI help exposes required `--config`, `--opportunity-file`, and `--json` flags.

## Notes

OKX official API documentation for `POST /api/v5/trade/order` lists `post_only` as an accepted order type for order placement, matching the maker quote behavior used here.

## Follow-Up

Next ordered item: register a full hedged-maker demo validation workflow once real OKX demo opportunity generation and second-venue sandbox parity are available. Until then, the manager is intentionally explicit and opportunity-file driven.
