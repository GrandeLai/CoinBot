# OKX Demo API Validation Report

Date: 2026-05-09

## Scope

Validate that `configs/okx.demo.example.yaml` can load local OKX demo credentials from `.env.okx.demo`, reach OKX Demo Trading APIs, and complete a tiny demo order submit/cancel/query loop without touching live trading.

## Commands And Results

- `test -f .env.okx.demo`
  - Result: exit 0; local demo env file exists.
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant config validate --config configs/okx.demo.example.yaml --json`
  - Result: exit 0; OKX config is enabled with `sandbox=true`, `okx_demo=true`, `live_trading=false`, `dry_run=false`, `allow_demo_orders=true`; API key, secret, and passphrase were detected and redacted.
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant agent operation-catalog --json`
  - Result: exit 0; `missing_demo_validation=[]`.
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant exchange sandbox-check --config configs/okx.demo.example.yaml --exchange okx --symbol BTC/USDT --json`
  - Initial sandbox result: local command failed DNS resolution due restricted network.
  - Escalated network result: exit 0; `ok=true`; public ping, ticker, orderbook, and spot/perp quote checks passed; `live_orders_sent=false`.
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant exchange sandbox-check --config configs/okx.demo.example.yaml --exchange okx --symbol BTC/USDT --include-private --json`
  - Result: exit 0; `ok=true`; public checks passed; private account read passed; returned assets were BTC, ETH, OKB, and USDT; `live_orders_sent=false`.
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline python - <<'PY' ...`
  - Result: exit 0; OKX Demo Trading spot limit buy order was submitted and then canceled.
  - Sanitized result: `provider_demo=true`, `live_trading=false`, `dry_run=false`, `order_submitted=true`, `symbol=BTC/USDT`, `side=buy`, `quantity=0.0001`, `last_price_before_submit=80366.1`, `limit_price=79562.4`, `required_capital_usdt=7.9562`, `submit_status=submitted`, `cancel_status=canceled`, `open_after_cancel=false`, `live_orders_sent=false`.
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant strategy validate-demo --config configs/okx.demo.example.yaml --strategy all --allow-account-mode-switch --json`
  - Initial result before account-mode switch: exit 0; spot-based `cross-exchange` and `triangular` passed, while swap-based `funding-rate` and `spot-perp` were blocked before swap order submission because OKX returned account-mode code `51070` with current demo account `acctLv=1`.
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache /opt/homebrew/bin/uv run --project backend --offline crypto-assistant strategy validate-demo --config configs/okx.demo.example.yaml --strategy all --allow-account-mode-switch --json`
  - Final result after operator switched account mode: exit 0; `completed=true`, `provider_demo=true`, `live_trading=false`, `dry_run=false`, account mode `before=3`, `after=3`, and `live_orders_sent=false`.
  - `cross-exchange`: passed. One tiny OKX demo spot `BTC/USDT` buy limit order (`quantity=0.0001`) was submitted, canceled, and confirmed not open.
  - `triangular`: passed. Three tiny OKX demo spot orders (`BTC/USDT` buy `0.0001`, `ETH/BTC` buy `0.001`, `ETH/USDT` sell `0.001`) were submitted, canceled, and confirmed not open.
  - `funding-rate`: passed. One tiny OKX demo swap `BTC/USDT` sell limit order (`quantity=0.01`) was submitted, canceled, and confirmed not open.
  - `spot-perp`: passed. One tiny OKX demo spot `BTC/USDT` buy limit order (`quantity=0.0001`) and one tiny OKX demo swap `BTC/USDT` sell limit order (`quantity=0.01`) were submitted, canceled, and confirmed not open.
- `UV_CACHE_DIR=/Users/bytedance/code/CoinBot/.uv-cache uv run --project backend --offline crypto-assistant strategy validate-demo --help`
  - Result: exit 0; command help includes `--allow-account-mode-switch` and `--json`.

## Safety Result

- A tiny OKX Demo Trading order endpoint call was made after explicit operator approval.
- The order used OKX demo mode only and was canceled immediately.
- No live orders were sent.
- Credentials were not printed in CLI output or this report.
- OKX Demo Trading mode is active through `okx_demo=true`, which makes the provider add `x-simulated-trading: 1` for OKX demo requests.
- The account-mode switch path is demo-only. It checks provider demo mode, rejects live trading, checks for open orders/positions, and treats OKX account-mode blockers as operator action items.
- After the account moved to `acctLv=3`, spot validation uses account-mode-aware `tdMode=cross`; live trading remains disabled.

## External Blocker

Resolved. OKX API v5 documents account modes as `1` spot mode, `2` futures mode, `3` multi-currency margin, and `4` portfolio margin. OKX initially returned code `51070` while the demo account was `acctLv=1`; after the operator switched the demo account to `acctLv=3`, all four strategy demo validations passed.

## Status

OKX demo API connectivity is validated for public market data, private account reads, spot demo order submission, swap demo order submission, demo order cancellation, and open-order absence after cancellation. Strategy demo validation is complete for all four strategies with no live orders sent.
