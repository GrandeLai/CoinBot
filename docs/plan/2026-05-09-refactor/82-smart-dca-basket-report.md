# Smart DCA Basket Report

Date: 2026-05-16

## Summary

Added a paper-only `smart-dca-basket` strategy for drawdown-tiered accumulation and basket weight-band diagnostics across major crypto assets.

This feature is portfolio-management evidence rather than pure arbitrage. It estimates whether a configured asset has pulled back enough from its recent completed-candle high, whether it is underweight or inside its target basket band, and whether the estimated discount remains positive after fee and slippage assumptions. It then emits a normal paper `ArbitrageOpportunity` with a single simulated spot buy leg.

## Implementation

- Added `trading_assistant.strategies.smart_dca.SmartDcaStrategyService`.
- Added `smart_dca` settings:
  - symbols, base order size, max cycle quote cap
  - drawdown lookback, minimum drawdown, drawdown tiers, size multipliers
  - target basket weights and rebalance band
  - fee, slippage, and minimum depth controls
- Registered `smart-dca-basket` with alias `smart-dca`.
- Wired the strategy through:
  - `ArbitrageScanner`
  - `StrategyController`
  - `StrategyRunner`
  - `ExecutionEngine`
  - `arbitrage scan --type smart-dca-basket`
- Updated `configs/config.example.yaml` and `configs/okx.demo.example.yaml`.
- Updated README, design docs, acceptance checklist, and traceability.

## Behavior

- Reads completed candles, ticker, orderbook, and account balances through the exchange interface.
- Calculates drawdown from recent high to current price.
- Applies the highest configured drawdown tier multiplier.
- Calculates current basket weight from quote cash plus configured asset balances.
- Adds an underweight size boost when the symbol is below its target band.
- Blocks candidates when:
  - strategy is disabled
  - symbol is not enabled
  - drawdown is below the configured minimum
  - target weight is missing
  - the symbol is overweight
  - quote balance is insufficient
  - ask-side depth is insufficient
  - estimated discount after fee/slippage is not positive
- Emits `read_only=true`, `paper_only=true`, `demo_supported=false`, and `live_supported=false`.

## Safety

- Live trading remains disabled by default.
- `smart-dca-basket` is registered with `demo_supported=false` and `live_supported=false`.
- The strategy emits simulated paper opportunities only.
- OKX Demo and live DCA/rebalance order dispatch are not implemented.
- Output labels the edge as an estimated discount/accumulation edge, not guaranteed profit.

## Verification

RED:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_smart_dca_strategy.py tests/unit/test_config.py::test_loads_safe_example_config tests/unit/test_config.py::test_loads_separate_okx_demo_and_live_configs tests/unit/test_strategy_platform.py::test_strategy_catalog_registers_new_strategies_and_compatibility_aliases tests/unit/test_strategy_platform.py::test_strategy_controller_scans_smart_dca_basket tests/integration/test_cli_core.py::test_cli_strategy_smart_dca_scans_and_runs_in_paper -v
```

Result: failed during collection with `ModuleNotFoundError: No module named 'trading_assistant.strategies.smart_dca'`.

Focused GREEN:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_smart_dca_strategy.py tests/unit/test_config.py::test_loads_safe_example_config tests/unit/test_config.py::test_loads_separate_okx_demo_and_live_configs tests/unit/test_strategy_platform.py::test_strategy_catalog_registers_new_strategies_and_compatibility_aliases tests/unit/test_strategy_platform.py::test_strategy_controller_scans_smart_dca_basket tests/integration/test_cli_core.py::test_cli_strategy_smart_dca_scans_and_runs_in_paper -v
```

Result: `7 passed in 1.50s`.

Broader affected regression:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_smart_dca_strategy.py tests/unit/test_config.py tests/unit/test_strategy_platform.py tests/unit/test_strategy_runtime.py tests/integration/test_cli_core.py -v
```

Result: `109 passed in 9.71s`.

Static checks:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

Results:

- `All checks passed!`
- `Success: no issues found in 127 source files`

CLI smoke:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy scan --config ../configs/config.example.yaml --strategy smart-dca-basket --symbol SOL/USDT --exchange mock --json
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy run --config ../configs/config.example.yaml --strategy smart-dca-basket --symbol SOL/USDT --max-cycles 1 --interval-seconds 0 --execution-mode paper --json
UV_CACHE_DIR=.uv-cache uv run crypto-assistant arbitrage scan --type smart-dca-basket --symbol SOL/USDT --exchange mock --json
UV_CACHE_DIR=.uv-cache uv run crypto-assistant arbitrage scan --help
```

Results:

- `strategy scan` emitted `smart-dca-basket-mock-sol-usdt` with `paper_only=true`.
- `strategy run` executed one dry-run simulated SOL/USDT buy leg with no live orders.
- `arbitrage scan` emitted the same paper opportunity.
- `arbitrage scan --help` lists `smart-dca` and `smart-dca-basket`.

## Follow-Up

Next ordered item from the research backlog: ML/LLM advisory ranker over deterministic evidence, unless the operator prefers to deepen Smart DCA first with a stateful paper portfolio ledger, cooldowns, and sell-side rebalance simulation.
