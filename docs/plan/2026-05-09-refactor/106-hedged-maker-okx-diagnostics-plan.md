# Hedged Maker OKX Target Diagnostics Plan

Date: 2026-05-21

## Goal

Make OKX-targeted hedged-maker diagnostics explain candidate quality using the explicit OKX Demo candidate path, instead of failing on the generic paper scanner's secondary hedge exchange setting.

## Problem

`strategy market-compare --strategy hedged-maker --target-exchange okx` used the generic `HedgedMakerStrategyService.diagnose` branch. That branch still reads `hedged_maker.hedge_exchange`, which can be `mock_alt` in local/paper configs. With OKX demo target settings and `mock_alt` disabled, diagnostics reported `diagnostic_error:Exchange is disabled: mock_alt`. That error hides the real preflight reason for the OKX single-exchange demo candidate.

## Scope

- Reuse `HedgedMakerDemoCandidateService` for OKX single-exchange `hedged-maker` diagnostics in `StrategyController`.
- Pass explicit scan exchange selection into diagnostics so `exchange=okx` scans and their diagnostic evidence stay aligned.
- Preserve the generic paper scanner and paper lifecycle behavior for non-OKX or non-targeted paper runs.
- Preserve `demo_supported=false` and the unsupported generic `strategy run --strategy hedged-maker --execution-mode demo` path.
- Add a regression test that disables `mock_alt` and verifies OKX diagnostics still return an OKX opportunity payload.
- Document the behavior and safety boundary.

## Non-Goals

- Do not relax `edge_below_minimum`, execution-quality, risk, budget, credential, operator, audit, or provider demo-mode gates.
- Do not submit OKX Demo orders from diagnostics.
- Do not enable live maker order dispatch.

## Verification Plan

- Targeted hedged-maker unit tests.
- Ruff on the touched source and test files.
- Mypy on the touched strategy controller.
- Read-only OKX demo `market-compare` smoke for `hedged-maker`.
- Read-only bounded OKX carry/basis observer to confirm current candidate-quality blockers.
