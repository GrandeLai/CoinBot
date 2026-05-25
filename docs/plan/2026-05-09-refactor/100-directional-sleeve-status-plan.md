# Directional Sleeve Status Plan

Date: 2026-05-20

## Goal

Make directional strategies usable as a controlled, low-correlation sleeve by reporting promotion status and caps without enabling directional live trading.

## Scope

- Add a read-only `strategy directional-sleeve-status` command.
- Report each directional strategy's validation evidence, runtime guard state, demo enablement, and stage.
- Surface configured size/risk caps.
- Keep directional live trading unsupported.

## Tasks

- [x] Add RED unit coverage requiring directional promotion stage rules.
- [x] Add RED CLI coverage requiring read-only sleeve status.
- [x] Implement status service and CLI command.
- [x] Update README, design, traceability, phase report, and final acceptance addendum.
- [x] Run focused pytest, ruff, mypy, CLI smoke, and record results in the report.

## Guardrails

- The report must return `orders_sent=false` and `live_orders_sent=false`.
- It must not run a scanner, demo executor, broker, or live-agent executor.
- It must not write journal, guard, retrospective, evolution, or position state.
- Directional live trading remains unsupported.
- Demo eligibility remains advisory and still requires the normal demo-window, guard, risk, preflight, receipt, and residual checks.
