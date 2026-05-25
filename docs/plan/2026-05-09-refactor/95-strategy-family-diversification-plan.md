# Strategy Family Diversification Plan

Date: 2026-05-20

## Goal

Reduce triangular-arbitrage dependence by making strategy-family concentration visible before validation windows are allocated.

## Scope

- Add a read-only `strategy diversification-report` command.
- Aggregate existing advisory ranking evidence by strategy family.
- Report candidate share, demo candidate evidence, validation PnL, and advisory validation-budget shares.
- Add a configurable maximum family share percentage.
- Do not change strategy execution, demo-window, or live gates.

## Tasks

- [x] Add RED unit coverage requiring family-level validation-budget caps.
- [x] Add RED CLI coverage requiring `strategy diversification-report`.
- [x] Implement strategy family mapping and report payloads.
- [x] Expose `--max-family-share-pct`.
- [x] Update README, design, traceability, phase report, and final acceptance addendum.
- [x] Run focused pytest, ruff, mypy, CLI smoke, and record results in the report.

## Guardrails

- The report is advisory and read-only.
- It must report `orders_sent=false` and `live_orders_sent=false`.
- It must not mutate config, portfolio selection, strategy ranking, or runtime state.
- It must not lower preflight, risk, receipt, residual, demo, or live gates.
