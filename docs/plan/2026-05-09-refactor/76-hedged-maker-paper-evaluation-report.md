# Hedged Maker Paper Evaluation Report

Date: 2026-05-16

## Summary

Added `crypto-assistant strategy hedged-maker-report`, a read-only paper evaluation report for hedged-maker/XEMM evidence. The command summarizes the strategy journal and persisted paper quote state so operators and agents can inspect lifecycle status, queue/partial-fill quality, adverse-selection samples, simulated hedge slippage, paper PnL, and active quote state before any sandbox order-manager work.

## Implementation

- Added `HedgedMakerPaperEvaluationReportService`.
- Aggregates only journal events where:
  - `event=strategy_cycle`
  - `strategy_name=hedged-maker`
  - `execution_mode=paper`
- Reads `hedged_maker.paper_state_path` to count current paper orders by status.
- Reports per-event evidence:
  - lifecycle status
  - expected edge
  - realized paper PnL
  - active order count
  - fill ratio
  - filled/remaining quantity
  - adverse-selection flag
  - hedge slippage multiplier
  - canceled order count
- Reports aggregate evidence:
  - lifecycle status counts
  - fill and partial-fill counts
  - adverse-selection sample count
  - cancel-pending sample count
  - total expected edge
  - total realized paper PnL
  - average fill ratio
  - max hedge slippage multiplier
  - active paper state order count
- Added conservative recommendations for no samples, partial fills, adverse selection, cancel latency, and negative realized paper PnL.
- Exposed the service through `TradingAssistantApp.strategy_hedged_maker_report`.
- Added CLI support for:

```bash
crypto-assistant strategy hedged-maker-report --config configs/config.example.yaml --limit 10 --json
```

## Safety

- The report is read-only.
- It does not access exchange APIs.
- It does not write the journal or paper state.
- It reports `orders_sent=false` and `live_orders_sent=false`.
- It does not change demo/live support for `hedged-maker`; the strategy remains paper-only.

## Verification

RED:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_report.py tests/integration/test_cli_core.py::test_cli_strategy_hedged_maker_scans_and_runs_in_paper tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -v
```

Result: failed during collection with `ModuleNotFoundError: No module named 'trading_assistant.strategies.hedged_maker_report'`, confirming the new tests described missing behavior.

Focused GREEN:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_report.py tests/integration/test_cli_core.py::test_cli_strategy_hedged_maker_scans_and_runs_in_paper tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -v
```

Result: `3 passed in 0.58s`.

Final verification:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_report.py tests/integration/test_cli_core.py -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy hedged-maker-report --config ../configs/config.example.yaml --limit 10 --json
```

Result:

- `25 passed in 6.14s`
- `All checks passed!`
- `Success: no issues found in 125 source files`
- CLI smoke returned `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, `scanned_events=0`, and `active_state_orders=1`.

## Follow-up

Next ordered item: include hedged-maker lifecycle state in capital/order budget so pending partial fills and cancel-pending maker quotes constrain future paper/demo sizing decisions.
