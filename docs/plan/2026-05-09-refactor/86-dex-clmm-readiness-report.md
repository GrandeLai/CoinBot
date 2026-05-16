# DEX/CLMM Readiness Gate Report

## Summary

Implemented a read-only readiness gate for the deferred CLMM/DEX liquidity-provision item. This keeps CoinBot honest about current capability: it can report whether prerequisites for future testnet LP work are present, but it cannot execute LP transactions, manage wallets, or send live orders.

## Files Changed

- `backend/src/trading_assistant/strategies/dex_readiness.py`
- `backend/src/trading_assistant/config/schema.py`
- `backend/src/trading_assistant/application.py`
- `backend/src/trading_assistant/cli/main.py`
- `backend/tests/unit/test_dex_lp_readiness.py`
- `backend/tests/integration/test_cli_core.py`
- `configs/config.example.yaml`
- `configs/okx.demo.example.yaml`
- `README.md`
- `docs/DESIGN.md`
- `docs/plan/2026-05-09-refactor/02-acceptance-checklist.md`
- `docs/plan/2026-05-09-refactor/03-traceability-matrix.md`
- `docs/plan/2026-05-09-refactor/85-dex-clmm-readiness-plan.md`
- `docs/plan/2026-05-09-refactor/86-dex-clmm-readiness-report.md`

## Behavior

- Added `dex_lp` config with safe defaults:
  - disabled
  - no gateway URL
  - `network=none`
  - `COINBOT_DEX_WALLET_ADDRESS` env-name placeholder only
  - wallet policy, gas model, MEV protection, and testnet evidence disabled/missing by default
- Added `crypto-assistant strategy dex-lp-readiness --json`.
- Default readiness reports `status=Deferred`, `testnet_ready=false`, and `execution_supported=false`.
- A fully configured testnet prerequisite set may report `testnet_ready=true`, but still reports `execution_supported=false`, `orders_sent=false`, and `live_orders_sent=false`.

## Safety

- No wallet secrets are read.
- No DEX/RPC/gateway network calls are made.
- No config mutation is performed.
- No LP transactions or exchange orders are sent.
- Live DEX/CLMM LP stays `Deferred` in the traceability matrix until a real DEX adapter, wallet policy, gas model, MEV controls, LP lifecycle manager, and testnet validation are implemented.

## Verification

RED:

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_dex_lp_readiness.py tests/integration/test_cli_core.py::test_cli_strategy_dex_lp_readiness_is_read_only tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -v
```

Expected failure observed before implementation:

```text
ModuleNotFoundError: No module named 'trading_assistant.strategies.dex_readiness'
```

Focused GREEN:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_dex_lp_readiness.py tests/integration/test_cli_core.py::test_cli_strategy_dex_lp_readiness_is_read_only tests/integration/test_cli_core.py::test_cli_strategy_retrospective_empty_history -v
```

Result:

```text
4 passed in 0.65s
```

Affected regression:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_dex_lp_readiness.py tests/unit/test_config.py tests/unit/test_advisory_ranker.py tests/unit/test_strategy_platform.py tests/integration/test_cli_core.py -v
```

Result:

```text
54 passed in 7.84s
```

Post evidence-path cleanup:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/unit/test_dex_lp_readiness.py tests/integration/test_cli_core.py::test_cli_strategy_dex_lp_readiness_is_read_only -v
UV_CACHE_DIR=.uv-cache uv run ruff check src/ tests/
UV_CACHE_DIR=.uv-cache uv run mypy src/
```

Result:

```text
3 passed in 0.31s
All checks passed!
Success: no issues found in 129 source files
```

CLI smoke:

```bash
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy dex-lp-readiness --config ../configs/config.example.yaml --json
UV_CACHE_DIR=.uv-cache uv run crypto-assistant strategy dex-lp-readiness --help
```

Result:

- JSON output included `status=Deferred`, `read_only=true`, `orders_sent=false`, `live_orders_sent=false`, and `execution_supported=false`.
- Help output included `--config` and `--json`.
