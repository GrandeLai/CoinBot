# Carry/Basis Bounded Observer Plan

Date: 2026-05-20

## Goal

Make carry/basis multi-symbol sweeps practical for routine OKX observation by bounding slow public-market reads and explaining every skipped or failed symbol without sending orders.

## Scope

- Add sweep-level request budgeting.
- Add per-symbol timeout classification.
- Add a small in-process report cache for repeated service calls.
- Expose bounded observer controls through `strategy carry-basis-optimize`.
- Keep all behavior read-only and outside demo/live execution paths.

## Tasks

- [x] Add RED unit coverage for request-budget skips and timeout classification.
- [x] Add RED CLI coverage for new bounded observer flags and JSON output.
- [x] Implement sweep observations and summary counts.
- [x] Add `--max-symbols`, `--request-budget-seconds`, and `--per-symbol-timeout-seconds`.
- [x] Update README, design, traceability, phase report, and final acceptance addendum.
- [x] Run focused pytest, ruff, mypy, CLI smoke, and record results in the report.

## Guardrails

- The observer must report `orders_sent=false` and `live_orders_sent=false`.
- Timeouts and budget skips must not create demo-window approval.
- Do not lower profit, risk, preflight, receipt, residual, or live gates.
- Do not write journal, retrospective, guard, or evolution state.
