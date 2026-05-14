# OKX Demo Run And Optimization Report

Date: 2026-05-11

## Scope

Started a new optimization loop:

1. Run local validation.
2. Check strategy portfolio and retrospective issues.
3. Run OKX Demo Trading only for the currently selected strategy.
4. Review PnL and safety evidence.
5. Optimize the workflow based on observed issues.
6. Re-run after the optimization and guard cooldown.

No live trading was enabled. The only external orders sent in this loop were tiny OKX Demo Trading canary orders for `triangular-multi-route`.

## Pre-Run State

Commands:

- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant config validate --config ../configs/okx.demo.example.yaml --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy retrospective --config ../configs/okx.demo.example.yaml --execution-mode demo --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy guard-status --config ../configs/okx.demo.example.yaml --execution-mode demo --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy portfolio-status --config ../configs/config.example.yaml --symbol BTC/USDT --json`
- `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`

Results:

- OKX demo config validation: Pass, credentials redacted.
- Local validation: Pass, `executed=5`, `net_profit=4.967117651096646342373316272 USDT`, `win_rate_pct=100.00`.
- Portfolio selected only `triangular-multi-route`.
- `cross-exchange`, `spot-perp-carry`, `funding-carry-hedged`, and `futures-perp-basis` remained blocked below score floor by repeated OKX demo `preflight_not_profitable` pressure.

## First Demo Attempt

Command:

`UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy triangular-multi-route --cycles 3 --symbol BTC/USDT --json`

Result:

- Initial sandboxed network attempt failed with `ConnectError: [Errno 8] nodename nor servname provided, or not known`.
- After approved OKX Demo Trading network access, the strategy was in runtime guard cooldown.
- Demo window returned `executed=0`, `skipped=3`, `net_profit=0`.
- Post-run open-risk check returned `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`.

Review:

- This was not a strategy loss.
- The issue was workflow noise: a network/DNS failure tripped market-data guard, and a later demo-window command spent all requested cycles on guard skips.

## Optimization Implemented

Implemented a pre-run guard check in `StrategyValidationService.validate_demo_window`.

Behavior after this change:

- If every requested strategy is already in demo runtime-guard cooldown, validation returns immediately.
- It reports `status=Fail`, `reasons=["runtime_guard_cooldown"]`, `cycles_completed=0`, and `executed=0`.
- It does not call the runner.
- It does not perform a post-run open-risk network call because no orders were sent in that invocation.

Implemented a retrospective cleanup rule:

- If a later profitable execution exists for the same strategy and execution mode, older transient `market_data_failure`, `rate_limit_failure`, and `demo_preflight_not_profitable` results from the journal are no longer reopened as current issues.
- This prevents a successful recovery from being hidden by stale historical noise.

Changed files:

- `backend/src/trading_assistant/validation/service.py`
- `backend/src/trading_assistant/strategies/retrospective.py`
- `backend/tests/unit/test_strategy_validation.py`
- `backend/tests/unit/test_strategy_runtime.py`

## Re-Run After Cooldown

After the guard cooldown naturally expired, guard status showed:

- `triangular-multi-route`: `cooldown_active=false`
- last demo reason before rerun: `market_data_error:SafetyError: Unable to fetch OKX demo price for BTC/USDT`

Command:

`UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy triangular-multi-route --cycles 3 --symbol BTC/USDT --json`

Result:

- Demo status: `Needs More Samples`, only because validation requires `10` demo executions and this run intentionally used `3`.
- Cycles completed: `3`
- Executed: `3`
- Skipped: `0`
- Wins: `3`
- Losses: `0`
- Net profit: `0.749803 USDT`
- Win rate: `100.00%`
- Max drawdown: `0`
- Post-run open spot orders: `0`
- Post-run open swap orders: `0`
- Post-run swap positions: `0`

Per-cycle net PnL:

| Cycle | Net PnL USDT | PnL Reconciliation | Receipt Completeness | Residual Inventory |
| --- | ---: | --- | --- | --- |
| 1 | `0.246403` | within tolerance | complete, 3/3 orders | within tolerance |
| 2 | `0.246880` | within tolerance | complete, 3/3 orders | within tolerance |
| 3 | `0.256520` | within tolerance | complete, 3/3 orders | within tolerance |

## Post-Run Review

Command:

`UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy review --config ../configs/okx.demo.example.yaml --execution-mode demo --json`

Result:

- Total demo events: `234`
- `triangular-multi-route`: `executed=48`, `wins=47`, `losses=1`, `net_profit=72.576897 USDT`, `win_rate_pct=97.92`
- Other four strategies still have `executed=0`; they remain wait-only until preflight turns positive.

Promotion status:

- `triangular-multi-route` local: Pass.
- `triangular-multi-route` demo: Pass.
- Live: Fail, as expected, because `validation_allow_live_canary=false`, live trading gate is not enabled, and agent live orders remain disabled.

## Current Retrospective

After the retrospective cleanup optimization and refresh:

- Open issues: `4`
- Highest severity: `warning`
- Current open issues are only the four repeated OKX demo `preflight_not_profitable` issues for non-selected strategies.
- The transient triangular market-data/cooldown issue is no longer treated as current after the successful profitable rerun.

## Tests

- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_runtime.py::test_strategy_retrospective_treats_transient_market_data_failure_as_improved_after_profit tests/unit/test_strategy_validation.py::test_validate_demo_window_fast_blocks_when_target_guard_is_cooling_down -q`
  - Result: `2 passed in 0.44s`.
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/unit/test_strategy_validation.py tests/unit/test_strategy_runtime.py::test_strategy_retrospective_treats_transient_market_data_failure_as_improved_after_profit tests/integration/test_cli_core.py::test_cli_strategy_validate_demo_window_blocks_with_safe_default_config -q`
  - Result: `8 passed in 0.37s`.
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/validation/service.py src/trading_assistant/strategies/retrospective.py tests/unit/test_strategy_validation.py tests/unit/test_strategy_runtime.py`
  - Result: `All checks passed!`.
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/validation/service.py src/trading_assistant/strategies/retrospective.py`
  - Result: `Success: no issues found in 2 source files`.
- `UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q`
  - Result: `286 passed in 9.95s`.
- `UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/`
  - Result: `All checks passed!`.
- `UV_CACHE_DIR=../.uv-cache uv run mypy src/`
  - Result: `Success: no issues found in 94 source files`.

## Safety And Directory Checks

- Refactor document scan: `find docs/plan -maxdepth 1 -type f -print` returned no files.
- Hardcoded secret scan returned no matches.
- Live-switch scan found only known safe locations: OKX live example config, OKX demo dry-run-off config, historical report command text, and unit-test fixtures.

## Next Optimization

- Keep `triangular-multi-route` as the only OKX demo execution candidate.
- Run a 10-cycle `triangular-multi-route` demo window next if continuing validation, because current 3-cycle run is profitable but below the configured sample threshold.
- Do not run the four blocked strategies in OKX demo until their preflight pressure clears.
- Do not increase demo size yet; the next evidence gap is sample count, not size.
- Keep live trading disabled.
