# Phase 56 - Directional Managed Exit Controls

## Goal

Make OKX Demo Trading directional positions safer to manage by adding explicit reverse-signal exits and loss-cooldown audit evidence, without adding live trading or any new entry bypass.

## Implementation

- `StrategyDemoExecutionService` now treats an explicit directional `sell`/exit context as a managed `reverse_signal` exit for an existing long-only demo spot position.
- Directional exit checks now cover:
  - take profit
  - stop loss
  - explicit reverse signal
  - time limit
- Closed directional exits include `managed_exit_audit` with:
  - exit reason
  - realized net PnL
  - loss cooldown recommendation
  - runtime guard loss-recording evidence
- `StrategyRunner` can pass a failed local directional buy gate through to demo execution only when:
  - local context contains an explicit exit signal, and
  - no-order preflight confirms a `directional_exit_*` managed close.
- Managed directional exits may proceed with negative expected PnL because they reduce existing inventory. Entry attempts still require the normal local validation and demo preflight gates.
- Directional local-validation diagnostics now preserve scanner signal context, so filtered `signal_sell` cases remain machine-readable.

## Safety Boundaries

- No live trading path was added.
- No fresh directional entry can bypass local validation.
- Reverse-signal override is limited to existing managed demo positions and requires preflight reason `directional_exit_*`.
- The path remains long-only spot demo inventory management; `orderbook-imbalance-scalp` remains demo-disabled.
- Losing managed exits are recorded as negative executions so the stateful runtime guard can trigger cooldown using existing limits.

## Verification

```bash
cd backend && uv run pytest tests/unit/test_strategy_runtime.py -k 'reverse_signal or local_buy_gate' -v
```

Result: `2 passed`.

```bash
cd backend && uv run pytest tests/unit/test_strategy_runtime.py -v
```

Result: `57 passed`.

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

Result: `334 passed`.

## Next Step

Continue with remaining improvements such as richer per-strategy sizing policy or operator dashboards.
