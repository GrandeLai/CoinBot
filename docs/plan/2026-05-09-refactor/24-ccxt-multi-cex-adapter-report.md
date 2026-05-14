# CCXT Multi-CEX Adapter Report

Date: 2026-05-10

## Scope

- Continue the Deferred multi-CEX adapter work without enabling live trading.
- Add a sandbox-first CCXT market-data adapter for Binance/Bybit-style exchanges.
- Keep all tests offline by using fake CCXT clients.
- Do not add CCXT order dispatch or non-OKX live broker support.

## Code Changes

- Added `backend/src/trading_assistant/exchanges/ccxt.py`.
  - Maps CCXT ticker, orderbook, balances, funding rates, instruments, spot/perp quotes, and futures basis data into the shared Decimal domain models.
  - Raises a clear `ExchangeError` when futures markets are unavailable instead of fabricating data.
  - Uses an optional `ccxt` import only when a CCXT-backed exchange is enabled.
- Updated `ExchangeFactory` to instantiate `CCXTExchange` for `adapter: ccxt`.
- Updated `CrossExchangeScanner` to scan directed pairs across enabled exchanges instead of hardcoding only `mock` and `mock_alt`.
  - The default mock path still preserves `test-opportunity`.
  - Real or CCXT-backed paths get stable ids such as `cross-exchange-binance-bybit-btc-usdt`.

## Validation

- Command:
  - `uv run pytest tests/unit/test_ccxt_exchange_adapter.py tests/unit/test_exchange_market_account.py tests/integration/test_cli_core.py -q`
- Result:
  - `19 passed in 0.57s`.
- Command:
  - `uv run ruff check src/trading_assistant/exchanges/ccxt.py src/trading_assistant/exchanges/factory.py src/trading_assistant/arbitrage/cross_exchange.py tests/unit/test_ccxt_exchange_adapter.py`
- Result:
  - `All checks passed!`.
- Command:
  - `uv run mypy src/trading_assistant/exchanges/ccxt.py src/trading_assistant/arbitrage/cross_exchange.py`
- Result:
  - `Success: no issues found in 2 source files`.
- Command:
  - `uv run pytest tests/ -q`
- Result:
  - `272 passed in 10.40s`.
- Command:
  - `uv run ruff check src/ tests/`
- Result:
  - `All checks passed!`.
- Command:
  - `uv run mypy src/`
- Result:
  - `Success: no issues found in 93 source files`.
- CLI spot checks:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant config validate --config ../configs/config.example.yaml --json`: exit 0.
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant arbitrage scan --type cross-exchange --symbol BTC/USDT --json`: exit 0, default mock `test-opportunity` preserved.
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy catalog --json`: exit 0.

## Safety Result

- Safe default config still keeps `binance` and `bybit` disabled.
- CCXT is used only for enabled exchanges.
- The adapter does not implement order placement.
- Live execution remains OKX-spot-only behind existing agent live gates.
- Missing futures data is surfaced as an explicit error, not a fake opportunity.
- Refactor document compliance check returned no files directly under `docs/plan/`.
- Hardcoded secret scan returned no matches.
- Live switch scan found `live_trading: true` only in `configs/okx.live.example.yaml` and unit-test fixtures.

## Remaining Follow-Up

- Install and validate `ccxt` in a controlled sandbox environment before enabling any real Binance/Bybit config.
- Add real sandbox integration tests for Binance/Bybit public market reads.
- Keep non-OKX broker dispatch Deferred until exchange-specific order semantics, demo/sandbox validation, and operation-catalog coverage are added.
