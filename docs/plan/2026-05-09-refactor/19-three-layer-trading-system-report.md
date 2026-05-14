# Three-Layer Trading System Report

Date: 2026-05-09

## Scope

Implemented the approved three-layer strategy validation path:

1. Local mock/paper validation.
2. OKX Demo Trading validation windows.
3. Advisory live-canary promotion status.

This improves validation discipline and risk control. It does not claim or guarantee stable profits.

## Implemented

- Added `trading_assistant.validation.StrategyValidationService`.
- Added `strategy_runtime.validation_*` thresholds:
  - `validation_min_local_executions`
  - `validation_min_demo_executions`
  - `validation_min_win_rate_pct`
  - `validation_min_net_profit_usdt`
  - `validation_max_drawdown_usdt`
  - `validation_allow_live_canary`
- Added CLI commands:
  - `crypto-assistant strategy validate-local`
  - `crypto-assistant strategy validate-demo-window`
  - `crypto-assistant strategy promotion-status`
- Added local validation result status values: `Pass`, `Fail`, `Needs More Samples`.
- Demo-window validation checks:
  - OKX provider is in demo mode.
  - No live orders were sent.
  - PnL reconciliation is within tolerance.
  - OKX fill receipts are complete.
  - No residual spot orders, swap orders, or swap positions remain after the window.
- Promotion status reads paper/demo strategy journal statistics and runtime guard state.
- Live-canary promotion remains advisory and disabled by default.

## Safety Result

- Default config still has `trading.live_trading=false`, `trading.dry_run=true`, and `trading.require_confirm_before_order=true`.
- `configs/okx.demo.example.yaml` remains demo-only with `okx_demo=true`.
- `strategy_runtime.validation_allow_live_canary=false` by default.
- `promotion-status` never sends orders.
- `validate-local` uses paper mode only.
- `validate-demo-window` uses the existing OKX Demo Trading gates and fails with a non-zero safety error under the safe default config where OKX demo is disabled.

## Tests Run

- `uv run pytest tests/unit/test_strategy_validation.py -q`
  - Result: `4 passed in 0.58s`
- `uv run pytest tests/integration/test_cli_core.py -q`
  - Result: `12 passed in 0.66s`
- `uv run pytest tests/unit/test_strategy_runtime.py -q`
  - Result: `19 passed in 0.37s`
- `uv run pytest tests/ -q`
  - Final result after config/docs updates: `255 passed in 5.15s`
- `uv run ruff check src/ tests/`
  - Result: `All checks passed!`
- `uv run mypy src/`
  - Result: `Success: no issues found in 87 source files`

## CLI Acceptance

- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache uv run crypto-assistant strategy validate-local --help`
  - Result: exit 0; command supports `--config`, `--strategy`, `--cycles`, `--symbol`, and `--json`.
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache uv run crypto-assistant strategy validate-demo-window --help`
  - Result: exit 0; command supports `--config`, `--strategy`, `--cycles`, `--symbol`, and `--json`.
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache uv run crypto-assistant strategy promotion-status --help`
  - Result: exit 0; command supports `--config`, `--strategy`, and `--json`.
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --json`
  - Result: exit 0; `local_validation.status=Pass`, `executed=2`, and `net_profit=0.5248040391921615676864626674`.
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/config.example.yaml --strategy all --cycles 1 --json`
  - Result: exit 5; safe default config correctly blocks with `SafetyError: strategy demo execution requires enabled OKX sandbox with okx_demo=true`.
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache uv run crypto-assistant strategy promotion-status --config ../configs/config.example.yaml --strategy all --json`
  - Result: exit 0; live status is `Fail` for all strategies because demo has not passed and live-canary gates remain disabled.

## Notes

- The live layer remains a gate report, not autonomous live dispatch.
- A strategy can only be marked promotable to live canary if local and demo layers pass and all live trading gates are explicitly enabled.
- Profit stability still requires longer demo windows, market-regime diversity, drawdown monitoring, and operator review before any live-canary consideration.
