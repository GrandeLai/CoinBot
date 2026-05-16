# Advisory Ranker Report

## Summary

Implemented `crypto-assistant strategy advisory-rank` as a read-only deterministic evidence ranker for strategy prioritization. The service composes strategy scorecards, rolling validation aggregates, opportunity-density buckets, and runtime guard state into bounded advisory scores, reason codes, and conservative next-step recommendations.

This is an ML/LLM-ready evidence layer, not an ML trading agent. The emitted model policy is `deterministic_evidence_ranker` with `external_model_called=false`, `llm_direct_ordering_allowed=false`, `config_mutation_allowed=false`, `orders_sent=false`, and `live_orders_sent=false`.

## Files Changed

- `backend/src/trading_assistant/strategies/advisory_ranker.py`
- `backend/src/trading_assistant/application.py`
- `backend/src/trading_assistant/cli/main.py`
- `backend/tests/unit/test_advisory_ranker.py`
- `backend/tests/integration/test_cli_core.py`
- `README.md`
- `docs/DESIGN.md`
- `docs/plan/2026-05-09-refactor/02-acceptance-checklist.md`
- `docs/plan/2026-05-09-refactor/03-traceability-matrix.md`
- `docs/plan/2026-05-09-refactor/83-advisory-ranker-plan.md`
- `docs/plan/2026-05-09-refactor/84-advisory-ranker-report.md`

## Behavior

- `StrategyAdvisoryRankerService.rank(...)` reads existing local evidence and returns `StrategyAdvisoryRankReport`.
- Ranking rows include platform score, validation executions, win rate, realized PnL, max drawdown, opportunity density, break-even gap, demo/live support flags, guard cooldown status, reasons, and source evidence.
- Recommendations are conservative:
  - `prioritize_paper_validation`
  - `collect_more_samples`
  - `paper_only`
  - `wait_for_runtime_guard_cooldown`
  - `watchlist`
- Demo-unsupported strategies such as `smart-dca-basket` return `paper_only` when requested with `--execution-mode demo`; they are not promoted into demo order paths.
- Validation thresholds use `strategy_runtime.validation_min_local_executions`, `validation_min_demo_executions`, `validation_min_win_rate_pct`, and `validation_min_net_profit_usdt`.

## Verification

RED:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_advisory_ranker.py tests/integration/test_cli_core.py::test_cli_strategy_advisory_rank_is_read_only tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -v
```

Expected failure observed before implementation:

```text
ModuleNotFoundError: No module named 'trading_assistant.strategies.advisory_ranker'
```

Focused GREEN:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_advisory_ranker.py tests/integration/test_cli_core.py::test_cli_strategy_advisory_rank_is_read_only tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -v
```

Result:

```text
4 passed in 0.61s
```

Affected regression:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_advisory_ranker.py tests/unit/test_config.py tests/unit/test_strategy_platform.py tests/unit/test_strategy_runtime.py tests/integration/test_cli_core.py -v
```

Result:

```text
110 passed in 9.84s
```

Post-threshold cleanup:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_advisory_ranker.py tests/integration/test_cli_core.py::test_cli_strategy_advisory_rank_is_read_only -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

Result:

```text
3 passed in 0.43s
All checks passed!
Success: no issues found in 128 source files
```

CLI smoke:

```bash
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy advisory-rank --config ../configs/config.example.yaml --strategy smart-dca-basket --symbol SOL/USDT --execution-mode paper --limit 10 --window 24h --json
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy advisory-rank --help
```

Result:

- JSON output included `read_only=true`, `orders_sent=false`, `live_orders_sent=false`.
- `model_policy.external_model_called=false`.
- Help output included `--config`, `--strategy`, `--symbol`, `--execution-mode`, `--limit`, `--window`, and `--json`.

## Safety

- No exchange order APIs are called.
- No external model APIs are called.
- No config or strategy parameter files are mutated.
- Live trading gates remain unchanged.
- Demo/live support flags from the registry are preserved in the advisory row and influence recommendations.

