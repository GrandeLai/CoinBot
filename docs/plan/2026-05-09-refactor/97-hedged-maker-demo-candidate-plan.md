# Hedged Maker Demo Candidate Plan

Date: 2026-05-20

## Goal

Move hedged-maker sandbox parity from manually assembled opportunity files toward scanner-produced, reviewable OKX Demo manager candidate payloads.

## Scope

- Add a read-only `strategy hedged-maker-demo-candidate` command.
- Generate an `opportunity_file_payload` compatible with the explicit `hedged-maker-demo` manager.
- Include maker quote, hedge preview, execution-quality metadata, diagnostics, and compatibility blockers.
- Keep the generic `strategy run --strategy hedged-maker --execution-mode demo` path unsupported.

## Tasks

- [x] Add RED unit coverage requiring an OKX demo-manager compatible payload.
- [x] Add RED CLI coverage requiring read-only local mock compatibility reporting.
- [x] Implement candidate generation service.
- [x] Expose CLI command and app facade method.
- [x] Update README, design, traceability, phase report, and final acceptance addendum.
- [x] Run focused pytest, ruff, mypy, CLI smoke, and record results in the report.

## Guardrails

- The candidate command must report `orders_sent=false` and `live_orders_sent=false`.
- It must not submit maker or hedge orders.
- It must not write the demo manager state file.
- It must not make the generic hedged-maker demo runtime available.
- The explicit `hedged-maker-demo` gate remains responsible for credentials, operator id, audit logging, risk, budget, provider demo mode, and order dispatch.
