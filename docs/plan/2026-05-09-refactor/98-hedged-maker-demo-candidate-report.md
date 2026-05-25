# Hedged Maker Demo Candidate Report

Date: 2026-05-20

## Goal

Create a read-only bridge from hedged-maker market observation to the explicit OKX Demo maker quote manager, reducing manual opportunity-file assembly without weakening sandbox gates.

## Implementation

- Added `HedgedMakerDemoCandidateService`.
- Added `crypto-assistant strategy hedged-maker-demo-candidate`.
- Candidate output includes:
  - `approved`
  - `demo_manager_compatible`
  - `reasons`
  - `opportunity_file_payload`
  - `diagnostics`
  - `next_actions`
- The `opportunity_file_payload` contains:
  - `strategy_type=hedged-maker`
  - OKX maker quote metadata
  - OKX hedge preview metadata
  - execution-quality metadata required by agent/demo gates
- Local mock OKX configs can generate the payload shape but report `target_exchange_adapter_is_mock`, so they are not treated as demo-manager compatible.

## Safety Boundaries

- The feature is read-only.
- It does not call the strategy runner, demo executor, broker, or live-agent executor.
- It does not write journal, retrospective, guard, evolution, paper state, demo state, or audit state.
- It does not submit maker or hedge orders.
- It does not make `strategy run --strategy hedged-maker --execution-mode demo` available.
- `strategy hedged-maker-demo` still requires OKX Demo credentials, operator id, audit logging, strategy/exchange allowlists, execution-quality approval, risk approval, budget approval, provider demo-mode verification, and all existing safety gates.

## Verification

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_hedged_maker_demo.py::test_hedged_maker_demo_candidate_builds_okx_opportunity_payload tests/integration/test_cli_core.py::test_cli_strategy_hedged_maker_demo_candidate_is_read_only -v
```

Result: first failed because `trading_assistant.strategies.hedged_maker_candidate` and `strategy hedged-maker-demo-candidate` were missing, then passed after implementation.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_hedged_maker_demo.py::test_hedged_maker_demo_candidate_builds_okx_opportunity_payload tests/unit/test_hedged_maker_demo.py::test_hedged_maker_demo_manager_submits_post_only_maker_quote tests/integration/test_cli_core.py::test_cli_strategy_hedged_maker_demo_candidate_is_read_only tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -v
```

Result: `4 passed`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/strategies/hedged_maker_candidate.py src/trading_assistant/application.py src/trading_assistant/cli/main.py tests/unit/test_hedged_maker_demo.py tests/integration/test_cli_core.py
```

Result: `All checks passed!`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/strategies/hedged_maker_candidate.py src/trading_assistant/application.py src/trading_assistant/cli/main.py
```

Result: `Success: no issues found in 3 source files`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy hedged-maker-demo-candidate --config ../configs/config.example.yaml --symbol BTC/USDT --target-exchange mock --json
```

Result: exit `0`; JSON reported `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, `approved=false`, `demo_manager_compatible=false`, `target_exchange_not_okx`, `target_exchange_adapter_is_mock`, and an `opportunity_file_payload` for inspection only.

## Next Step

Use this command to generate candidate payloads for operator review, then run the explicit `hedged-maker-demo` manager only after the OKX Demo gate passes.
