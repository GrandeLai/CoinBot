# Phase 57 - Strategy Demo Sizing Policy

## Goal

Add per-strategy OKX Demo Trading size controls so tiny canary order sizes can be staged conservatively by strategy while preserving the existing global safety caps.

## Implementation

- Added `DemoStrategySizingConfig` and `strategy_runtime.demo_strategy_size_overrides`.
- Overrides support:
  - `order_size_multiplier`
  - `max_order_value_usdt`
- `StrategyDemoExecutionService` now resolves an effective `sizing_policy` for each preflight and execution.
- Per-strategy multipliers are used by spot, swap, futures, triangular, carry/basis, and directional demo specs.
- Per-strategy max order values are constrained by existing global caps:
  - `strategy_runtime.max_position_value_usdt`
  - `strategy_runtime.demo_max_order_value_usdt`
  - `agent_trading.max_autonomous_order_value_usdt`
  - `directional.demo_max_order_value_usdt` for directional entries/exits
- `strategy demo-sampling` now records `demo_strategy_size_overrides` in its fixed size stage.
- Example configs include an empty `demo_strategy_size_overrides` map as the safe default.

## Safety Boundaries

- No live trading path was added.
- Overrides cannot bypass global runtime, directional, or autonomous-agent caps.
- Invalid override values must be positive.
- Size policy is explicit in preflight/execution output so operators can verify the active stage from JSON evidence.

## Verification

```bash
cd backend && uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_demo_execution_service_uses_strategy_size_override -v
```

Result: `1 passed`.

```bash
cd backend && uv run pytest tests/unit/test_strategy_runtime.py -v
```

Result: `58 passed`.

```bash
cd backend && uv run ruff check src/ tests/
```

Result: `All checks passed!`.

```bash
cd backend && uv run mypy src/
```

Result: `Success: no issues found in 114 source files`.

```bash
cd backend && uv run pytest tests/ -v
```

Result: `335 passed`.

## Next Step

Continue with operator-facing visibility improvements.
