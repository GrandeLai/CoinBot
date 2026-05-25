# Carry/Basis Target Unlock Diagnostics Report

Date: 2026-05-19

## Goal

Improve the next profit-optimization loop without sending orders by connecting carry/basis offline diagnostics to read-only target-market comparison evidence.

## Implementation

- Added optional target-market diagnostics to `strategy carry-basis-optimize`.
- Added CLI flag:

```bash
crypto-assistant strategy carry-basis-optimize --target-exchange okx --json
```

- Each carry/basis optimization card can now include:
  - `target_exchange`
  - `target_verdict`
  - `target_reasons`
  - `target_best_net_profit_usdt`
  - `target_delta_net_profit_usdt`
  - `unlock_priority`
- The aggregate summary now includes:
  - `target_demo_preflight_candidate_count`
  - `high_priority_unlock_count`
- Updated `docs/DESIGN.md`, `README.md`, and the traceability matrix.

## Safety Boundaries

- The feature is read-only.
- It reuses `StrategyMarketComparisonService`.
- It does not call `StrategyRunner`, demo execution, brokers, or live-agent execution.
- It does not write journal, retrospective, guard, or evolution state.
- It does not mutate config.
- It does not lower any preflight, risk, demo, or live gate.
- Output keeps `orders_sent=false` and `live_orders_sent=false`.

## Verification

```bash
cd backend && uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_optimization_merges_target_market_unlock_diagnostics -v
```

Result: `1 passed`.

```bash
cd backend && uv run pytest tests/integration/test_cli_core.py::test_cli_strategy_carry_basis_optimize_is_read_only -v
```

Result: `1 passed`.

```bash
cd backend && uv run pytest tests/unit/test_strategy_platform.py::test_carry_basis_optimization_merges_target_market_unlock_diagnostics tests/unit/test_strategy_platform.py::test_carry_basis_optimization_reports_break_even_gaps_without_trading tests/unit/test_strategy_platform.py::test_strategy_market_compare_is_read_only_and_explains_target_delta tests/integration/test_cli_core.py::test_cli_strategy_carry_basis_optimize_is_read_only tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -v
```

Result: `5 passed`.

```bash
cd backend && uv run ruff check src/trading_assistant/strategies/carry_basis_optimizer.py src/trading_assistant/application.py src/trading_assistant/cli/main.py tests/unit/test_strategy_platform.py tests/integration/test_cli_core.py
```

Result: `All checks passed!`.

```bash
cd backend && uv run mypy src/trading_assistant/strategies/carry_basis_optimizer.py src/trading_assistant/application.py src/trading_assistant/cli/main.py
```

Result: `Success: no issues found in 3 source files`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy carry-basis-optimize --config ../configs/config.example.yaml --symbol BTC/USDT --target-exchange mock --json
```

Result: exit `0`; JSON reported `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, `target_exchange=mock`, `target_demo_preflight_candidate_count=3`, and `high_priority_unlock_count=3`.

## OKX Demo Validation

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant config validate --config ../configs/okx.demo.example.yaml --json
```

Result: exit `0`; config validation returned `valid=true` with OKX Demo settings loaded, `trading.live_trading=false`, `trading.dry_run=false`, `trading.require_confirm_before_order=false`, `agent_trading.allow_demo_orders=true`, and `agent_trading.allow_live_orders=false`.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant exchange sandbox-check --config ../configs/okx.demo.example.yaml --exchange okx --symbol BTC/USDT --include-private --json
```

Result: exit `0`; sandbox check returned `ok=true`, `live_orders_sent=false`, public market checks passed, spot/perp quote checks passed, and private account read-only check returned assets without printing secrets.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy carry-basis-optimize --config ../configs/okx.demo.example.yaml --symbol BTC/USDT --target-exchange okx --json
```

Result: exit `0`; JSON reported `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, `target_exchange=okx`, `target_demo_preflight_candidate_count=0`, `high_priority_unlock_count=0`, and all three carry/basis cards were `unlock_priority=observe_only`.

Observed target-market blockers:

- `funding-carry-hedged`: `funding_annualized_below_minimum`, `net_profit_below_minimum`, break-even gap about `0.193446` USDT.
- `spot-perp-carry`: `basis_below_minimum`, `funding_annualized_below_minimum`, `net_profit_below_minimum`, break-even gap about `0.216257` USDT.
- `futures-perp-basis`: `funding_annualized_below_minimum`, `net_profit_below_minimum`, break-even gap about `0.077492` USDT.

```bash
cd backend && UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy demo-window --config ../configs/okx.demo.example.yaml --strategy futures-perp-basis --cycles 1 --symbol BTC/USDT --target-exchange okx --json
```

Result: exit `0`; orchestration returned `status=Blocked`, `completed=false`, `block_reasons=["missing_demo_preflight_candidate"]`, `orders_attempted=false`, and `live_orders_sent=false`.

## Next Step

Do not force OKX Demo orders for the current carry/basis market state. Rerun the OKX target diagnostics when funding/basis conditions change, and only pass a strategy into demo-window execution when it reports `unlock_priority=demo_candidate` and the existing local validation, market-compare, runtime guard, and demo-window gates pass.
