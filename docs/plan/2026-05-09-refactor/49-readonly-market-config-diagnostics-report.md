# Read-Only Market Config Diagnostics Report

Date: 2026-05-12

## Scope

This report records a small but important diagnostics improvement discovered during the next OKX scan cycle: read-only market commands needed explicit `--config` support so agents can use separated OKX demo/live profiles for ticker, orderbook, candle, exchange ping, and account diagnostics.

## Implementation

- Added `--config` to:
  - `crypto-assistant exchange list`
  - `crypto-assistant exchange ping`
  - `crypto-assistant market ticker`
  - `crypto-assistant market orderbook`
  - `crypto-assistant market candles`
  - `crypto-assistant account balance`
- No trading/execution logic was changed.
- No demo/live gates were weakened.
- README and design notes now show `market candles --config configs/okx.demo.example.yaml` for OKX read-only K-line diagnostics.

## Latest Strategy Scan Evidence

Before this CLI diagnostics fix, the current OKX read-only strategy sweep covered:

- `BTC/USDT`
- `ETH/USDT`
- `SOL/USDT`
- `XRP/USDT`
- `DOGE/USDT`
- `ADA/USDT`

Result:

- No `demo_preflight_candidate` was found.
- All strategy decisions remained `observe_only`.
- Triangular routes had `target_no_opportunity`.
- Carry/basis strategies were rejected by funding, basis, futures-data, or net-profit diagnostics.
- Directional strategies were rejected by `signal_hold`, `signal_sell`, insufficient backtest quality, or no trades.
- No OKX demo order was sent.

## CLI Evidence

Command:

```bash
uv run crypto-assistant market candles --config ../configs/okx.demo.example.yaml --exchange okx --symbol BTC/USDT --bar 15m --limit 5 --json
```

Result summary:

- Exit code: `0`
- Returned completed OKX `BTC/USDT` 15m candles.
- All returned rows had `complete=true`.
- No order endpoint was called.

## Validation

Targeted validation:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/integration/test_cli_core.py::test_cli_config_exchange_market_account_arbitrage_execution_and_report -q
```

Result: `1 passed`.

```bash
UV_CACHE_DIR=../.uv-cache uv run ruff check src/trading_assistant/cli/main.py tests/integration/test_cli_core.py
```

Result: `All checks passed!`.

```bash
UV_CACHE_DIR=../.uv-cache uv run mypy src/trading_assistant/cli/main.py
```

Result: `Success: no issues found in 1 source file`.

Full backend verification:

```bash
UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q
```

Result: `312 passed in 15.71s`.

```bash
UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/
```

Result: `All checks passed!`.

```bash
UV_CACHE_DIR=../.uv-cache uv run mypy src/
```

Result: `Success: no issues found in 107 source files`.

Directory and secret scans:

- `find docs/plan -maxdepth 1 -type f -print`: no output.
- `find backend/docs -maxdepth 5 -type f -print`: no output.
- Hardcoded key/secret/passphrase/token pattern scan: no matches.

## Safety

- Live trading remains disabled.
- This change only affects read-only diagnostics.
- OKX demo and live configs remain separate.
- No API keys or secrets are printed.
- No strategy was forced into demo execution when read-only scans returned `observe_only`.
