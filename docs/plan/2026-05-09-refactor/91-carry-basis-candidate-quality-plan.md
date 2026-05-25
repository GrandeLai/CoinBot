# Carry/Basis Candidate Quality Plan

Date: 2026-05-20

## Goal

Improve carry/basis candidate quality by scoring and filtering read-only sweep cards before any OKX Demo attempt.

## Scope

- Add quality metadata to carry/basis optimization cards.
- Add an optional `--min-quality-score` CLI filter for sweep ranked cards.
- Keep single-symbol reports and per-symbol sweep reports visible.
- Do not add any demo or live order path.

## Tasks

- [x] Add RED unit coverage requiring `quality_score`, `quality_bucket`, and quality-filtered sweep output.
- [x] Add RED CLI coverage requiring `--min-quality-score`.
- [x] Implement card quality scoring and bucket assignment.
- [x] Filter only `ranked_cards`; keep per-symbol reports intact.
- [x] Update README, design, traceability, phase report, and final acceptance addendum.
- [x] Run targeted pytest, ruff, mypy, and CLI smoke.

## Guardrails

- Scores are advisory and deterministic.
- A high score does not bypass `demo-window`, runtime guard, risk, preflight, receipt, residual, or live gates.
- Low-quality cards remain visible in per-symbol reports for diagnostics unless the caller chooses to inspect only ranked cards.
