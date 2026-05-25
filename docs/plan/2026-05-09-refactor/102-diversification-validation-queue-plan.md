# Diversification Validation Queue Plan

Date: 2026-05-20

## Goal

Turn the family diversification report from passive concentration telemetry into an actionable, read-only validation queue that reduces triangular-only paper/demo window selection.

## Scope

- Extend `strategy diversification-report` JSON output with `validation_queue`.
- Rank queue items with non-triangular families first when they have current or recently observed candidate evidence.
- Include the recommended stage, advisory score, family budget share, candidate share, candidate counts, validation PnL, runtime guard state, reasons, and next action for each item.
- Add summary queue counts and a deterministic queue policy string.
- Do not add execution commands, portfolio mutation, config mutation, or demo/live gate changes.

## Tasks

- [x] Add RED unit coverage requiring a non-triangular-first validation queue.
- [x] Add RED CLI coverage requiring queue counts and queue output.
- [x] Implement queue item payloads inside `StrategyDiversificationService`.
- [x] Add queue summary fields and guardrail marker.
- [x] Update README, DESIGN, traceability, and final acceptance docs.
- [x] Run focused pytest, ruff, mypy, CLI smoke, and record results in the report.

## Guardrails

- The queue is advisory and read-only.
- It must report through the existing diversification command.
- It must not call the strategy runner, demo manager, broker, live agent, or exchange APIs.
- It must not lower preflight, risk, receipt, residual, demo, or live gates.
