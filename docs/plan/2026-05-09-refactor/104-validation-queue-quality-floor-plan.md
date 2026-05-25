# Validation Queue Quality Floor Plan

Date: 2026-05-20

## Goal

Improve candidate quality in the family diversification validation queue so the shortlist prefers actionable, better-evidenced candidates instead of merely non-triangular candidates.

## Scope

- Add deterministic quality fields to each `validation_queue` item.
- Add `--min-queue-quality-score` to filter only the queue shortlist.
- Keep `families` and concentration diagnostics unfiltered so operators still see the full opportunity distribution.
- Keep the command read-only and advisory.

## Quality Model

- Reward high advisory score, current opportunity evidence, recent candidate evidence, validation samples, positive validation PnL, validation win-rate evidence, and non-triangular diversification value.
- Penalize runtime guard cooldown, repeated demo preflight pressure, observed break-even gaps, validation quality failures, and watchlist/paper-only stages.
- Bucket scores as `high`, `medium`, or `low`.

## Tasks

- [x] Add RED unit coverage for queue quality fields.
- [x] Add RED service coverage for queue quality-floor filtering.
- [x] Add RED CLI coverage for `--min-queue-quality-score`.
- [x] Implement quality scoring, buckets, reasons, queue filtering, and rank renumbering.
- [x] Update README, DESIGN, traceability, and final acceptance docs.
- [x] Run focused pytest, ruff, mypy, CLI smoke, and record results in the report.

## Guardrails

- The quality floor filters only `validation_queue`.
- It must not hide or rewrite family concentration diagnostics.
- It must not call the strategy runner, demo manager, broker, live agent, or exchange APIs.
- It must not lower preflight, risk, receipt, residual, demo, or live gates.
