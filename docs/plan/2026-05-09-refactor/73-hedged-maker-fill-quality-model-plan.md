# Hedged Maker Fill Quality Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve `hedged-maker` paper lifecycle realism with deterministic queue position, partial fill, stale quote, cancel latency, adverse selection, and hedge slippage expansion.

**Architecture:** Extend `HedgedMakerConfig` with paper fill-quality controls and keep all behavior inside `HedgedMakerPaperLifecycleService`. The model remains deterministic so unit tests, CLI smoke, retrospective, and later reports can compare expected versus realized evidence without random noise or exchange dispatch.

**Tech Stack:** Python 3.12, Decimal, dataclasses, Pydantic v2 settings, existing exchange interface, pytest, ruff, mypy.

---

## Design

- Queue position uses `paper_queue_ahead_pct`; fill ratio is `max(paper_min_fill_pct, 100 - paper_queue_ahead_pct)`, capped at 100%.
- Partial fills keep a remaining maker quote open as `partial_open` and hedge only the filled quantity.
- Stale quote detection is controlled by `paper_stale_quote_seconds`; `0` disables stale canceling.
- Cancel latency is controlled by `paper_cancel_latency_seconds`; when positive, stale/TTL/reprice cancels first move to `cancel_pending` and only become `canceled` after the effective time.
- Cancel-pending quotes can still fill before the cancel becomes effective.
- Adverse selection is detected when:
  - maker buy quote is above current maker mid by `paper_adverse_selection_buffer_pct`
  - maker sell quote is below current maker mid by the same buffer
- Adverse fills multiply hedge slippage by `paper_adverse_hedge_slippage_multiplier`.
- Lifecycle payloads expose `fill_quality`, `filled_quantity`, `remaining_quantity`, `adverse_selection`, `hedge_slippage_multiplier`, and cancel-pending evidence.

## Files

- Modify `backend/src/trading_assistant/config/schema.py`
  - Add paper fill-quality config fields and validators.
- Modify `backend/src/trading_assistant/strategies/hedged_maker_lifecycle.py`
  - Add deterministic fill-quality model.
- Modify configs:
  - `configs/config.example.yaml`
  - `configs/okx.demo.example.yaml`
- Update tests:
  - `backend/tests/unit/test_hedged_maker_lifecycle.py`
  - `backend/tests/unit/test_config.py`
  - `backend/tests/integration/test_cli_core.py`
- Update docs:
  - `README.md`
  - `docs/DESIGN.md`
  - `docs/plan/2026-05-09-refactor/02-acceptance-checklist.md`
  - `docs/plan/2026-05-09-refactor/03-traceability-matrix.md`
  - add `docs/plan/2026-05-09-refactor/74-hedged-maker-fill-quality-model-report.md`

## Tasks

- [ ] Add RED tests for partial fill, stale quote cancel/requote, cancel latency, and adverse hedge slippage.
- [ ] Add `HedgedMakerConfig` fields:
  - `paper_queue_ahead_pct`
  - `paper_min_fill_pct`
  - `paper_stale_quote_seconds`
  - `paper_cancel_latency_seconds`
  - `paper_adverse_selection_buffer_pct`
  - `paper_adverse_hedge_slippage_multiplier`
- [ ] Implement fill quality calculation and partial-open state.
- [ ] Implement stale quote cancel/requote.
- [ ] Implement cancel-pending state and delayed cancellation.
- [ ] Implement adverse selection detection and hedge slippage multiplier.
- [ ] Update configs, README, DESIGN, acceptance checklist, traceability matrix, and phase report.
- [ ] Run verification:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_hedged_maker_lifecycle.py tests/unit/test_config.py tests/integration/test_cli_core.py -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

- [ ] Run CLI smoke with temp runtime paths:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy run --config /private/tmp/coinbot-hedged-maker-fill-quality-smoke.yaml --strategy hedged-maker --max-cycles 2 --interval-seconds 0 --execution-mode paper --symbol BTC/USDT --json
```
