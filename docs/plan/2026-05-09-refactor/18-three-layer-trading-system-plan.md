# Three-Layer Trading System Implementation Plan

Date: 2026-05-09

## Goal

Build a three-layer promotion system for strategy validation: local mock/paper validation, OKX Demo Trading validation windows, and live-canary readiness status. The system improves validation discipline and risk control; it does not guarantee stable profits.

## Scope

- Add a validation service under `backend/src/trading_assistant/validation/`.
- Add CLI commands under `crypto-assistant strategy`.
- Add promotion thresholds to `strategy_runtime`.
- Keep live trading disabled by default.
- Keep OKX Demo Trading behind explicit demo config and existing preflight/risk/receipt gates.

## Tasks

- Add validation models and service.
- Add application facade methods.
- Add CLI commands:
  - `strategy validate-local`
  - `strategy validate-demo-window`
  - `strategy promotion-status`
- Add unit and integration tests.
- Update README, DESIGN, traceability matrix, acceptance checklist, phase report, and final report.
- Run targeted and full validation.

## Safety

- Local validation runs paper mode only.
- Demo-window validation uses `execution_mode=demo` and existing OKX Demo Trading gates.
- Promotion status is advisory and never sends live orders.
- Live-canary promotion requires explicit live config plus `strategy_runtime.validation_allow_live_canary=true`; defaults remain false.
