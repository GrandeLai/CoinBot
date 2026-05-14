# OKX Read-Only Market Compare Report

Date: 2026-05-11

## Goal

Close the evidence gap between local mock validation and OKX Demo Trading by adding a scan-only comparison layer:

```text
mock baseline scan -> target exchange scan -> per-strategy verdict -> demo preflight decision
```

This step must not send orders, mutate strategy runtime state, write journal entries, or update the retrospective document.

## Implementation

Added:

- `StrategyMarketComparisonService`
- `crypto-assistant strategy market-compare`

The command returns:

- `baseline_exchange`
- `target_exchange`
- `read_only=true`
- `orders_sent=false`
- scan-only safety context
- per-strategy baseline and target snapshots
- best net PnL delta versus mock baseline
- verdict:
  - `observe_only`
  - `paper_only`
  - `demo_preflight_candidate`
- diagnostic reasons from carry/basis scanners
- structured `scan_error:*` diagnostics when a target market-data source is unavailable

## OKX Read-Only Run

Command:

```bash
UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy market-compare \
  --config ../configs/okx.demo.example.yaml \
  --strategy all \
  --symbol BTC/USDT \
  --target-exchange okx \
  --json
```

Result:

- Exit code: `0`.
- `read_only=true`.
- `orders_sent=false`.
- `journal_written=false`.
- `retrospective_updated=false`.
- Demo-preflight candidates: `0`.

Sandboxed no-network check:

- The same command shape under restricted DNS exits `0` and returns `observe_only` with `diagnostic:scan_error:ConnectError`.
- This keeps the gate conservative: unavailable target market data cannot promote a strategy to demo preflight.

Per-strategy result:

| Strategy | OKX Target Opportunities | Verdict | Key Reason |
| --- | ---: | --- | --- |
| `cross-exchange` | 0 | `observe_only` | OKX-only target has no cross-exchange venue pair. |
| `triangular-multi-route` | 0 | `observe_only` | Current OKX route scan found no positive route at configured thresholds. |
| `funding-carry-hedged` | 0 | `observe_only` | `funding_annualized_below_minimum`, `net_profit_below_minimum`; best break-even gap `0.1900000000000000000000000000 USDT`. |
| `spot-perp-carry` | 0 | `observe_only` | `basis_below_minimum`, `funding_annualized_below_minimum`, `net_profit_below_minimum`; target basis pct `-0.04030627825921387920727689053`, best break-even gap `0.2001531391296069396036384453 USDT`. |
| `futures-perp-basis` | 0 | `observe_only` | `funding_annualized_below_minimum`, `net_profit_below_minimum`; target net PnL `0.0036928296119332114094084217 USDT`, best break-even gap `0.0713071703880667885905915783 USDT`. |

Decision:

- Do not run OKX demo orders for the non-triangular strategies based on this market snapshot.
- Keep them in observe/local-paper mode until OKX read-only scans produce `demo_preflight_candidate`.
- Keep triangular as the only strategy with prior profitable OKX demo evidence, but current read-only scan still found no immediate OKX target opportunity in this snapshot.

## Validation

Targeted tests:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest \
  tests/unit/test_strategy_platform.py::test_strategy_market_compare_is_read_only_and_explains_target_delta \
  tests/integration/test_cli_core.py::test_cli_strategy_list_run_and_review \
  tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history \
  -q
```

Result:

- `3 passed in 0.87s`.

Targeted lint/type checks:

```bash
UV_CACHE_DIR=../.uv-cache uv run ruff check \
  src/trading_assistant/strategies/market_compare.py \
  src/trading_assistant/application.py \
  src/trading_assistant/cli/main.py \
  tests/unit/test_strategy_platform.py \
  tests/integration/test_cli_core.py
```

Result:

- `All checks passed!`

```bash
UV_CACHE_DIR=../.uv-cache uv run mypy \
  src/trading_assistant/strategies/market_compare.py \
  src/trading_assistant/application.py \
  src/trading_assistant/cli/main.py
```

Result:

- `Success: no issues found in 3 source files`.

Full verification:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q
UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=../.uv-cache uv run mypy src/
```

Result:

- `291 passed in 10.42s`.
- `All checks passed!`.
- `Success: no issues found in 96 source files`.

## Safety

- No OKX orders were sent.
- No live path was enabled.
- The command forces `live_trading=false`, `dry_run=true`, and `require_confirm_before_order=true` for scan context.
- The command does not call `StrategyRunner`, `StrategyDemoExecutionService`, `AgentLiveExecutionService`, or any broker.
- The command does not write the strategy journal.
- The command does not update the retrospective Markdown/state files.
- The command is suitable as a gate before any future OKX demo preflight attempt.
- If target market data is unavailable, the command reports structured diagnostics and keeps the strategy in `observe_only`.
