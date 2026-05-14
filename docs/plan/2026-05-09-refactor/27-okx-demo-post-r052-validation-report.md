# OKX Demo Post-R052 Validation Report

Date: 2026-05-10

## Scope

- Continue the OKX-only follow-up after R052 orderbook-based triangular demo pricing.
- Keep the first layer local: run local paper validation before OKX Demo Trading.
- Keep the current 2x demo canary size and do not increase position size.
- Keep live trading and non-OKX broker dispatch disabled.

## Commands And Results

- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy guard-status --config ../configs/okx.demo.example.yaml --execution-mode demo --json`
- Result:
  - exit 0; no active cooldown before the new demo windows.
  - `triangular-multi-route` last state was `profitable_execution`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`
- Result:
  - exit 0; `local_validation.status=Pass`, `executed=5`, `skipped=0`, `net_profit=4.967117651096646342373316272`, `max_drawdown_usdt=0`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 3 --symbol BTC/USDT --json`
- Result:
  - exit 0; `demo_window_validation.status=Needs More Samples` because `3<10`.
  - `executed=3`, `skipped=12`, `wins=3`, `losses=0`, `net_profit=4.749252`, `max_drawdown_usdt=0`.
  - Post-run open-risk check: `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-local --config ../configs/config.example.yaml --strategy all --cycles 1 --symbol BTC/USDT --json`
- Result:
  - exit 0; second local precheck before the 10-cycle window passed with `executed=5`, `skipped=0`, `net_profit=4.967117651096646342373316272`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy validate-demo-window --config ../configs/okx.demo.example.yaml --strategy all --cycles 10 --symbol BTC/USDT --json`
- Result:
  - exit 0; `demo_window_validation.status=Pass`.
  - `cycles_completed=10`, `total=50`, `executed=10`, `blocked=0`, `skipped=40`, `wins=10`, `losses=0`.
  - `net_profit=15.863852`, `win_rate_pct=100.00`, `max_drawdown_usdt=0`.
  - Post-run open-risk check: `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`.
- Command:
  - `tail -n 50 logs/okx-demo-strategy-events.jsonl | jq -s '{...}'`
- Result:
  - latest 50 demo journal events: `executed=10`, `skipped=40`.
  - `triangular-multi-route`: `executed=10`, `skipped=0`, `net_profit=15.863852`.
  - `cross-exchange`, `funding-carry-hedged`, `spot-perp-carry`, and `futures-perp-basis`: each `executed=0`, `skipped=10` by `demo_preflight_not_profitable`.
  - `receipt_incomplete=0`, `pnl_out_of_tolerance=0`, `residual_out_of_tolerance=0`, `max_residual_inventory_usdt=0.058822`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy guard-status --config ../configs/okx.demo.example.yaml --execution-mode demo --json`
- Result:
  - exit 0; no active cooldown after the 10-cycle run.
  - `triangular-multi-route` last state: `profitable_execution`, `last_net_profit=1.582559`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy review --config ../configs/okx.demo.example.yaml --execution-mode demo --json`
- Result:
  - exit 0; demo journal review now has `total_events=225`.
  - `triangular-multi-route`: `total=45`, `executed=45`, `wins=44`, `losses=1`, `net_profit=71.827094`, `win_rate_pct=97.78`.
  - Other strategies remain skipped-only in demo review because current real-market preflight was not profitable.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run crypto-assistant strategy promotion-status --config ../configs/okx.demo.example.yaml --strategy all --json`
- Result:
  - exit 0; `triangular-multi-route` local and demo layers are `Pass`.
  - `triangular-multi-route` live layer remains `Fail` because live-canary promotion is disabled, live trading gates are not enabled, and agent live orders are disabled.
  - The other strategies are local `Pass`, demo `Needs More Samples` because they had `0` demo executions after preflight skips, and live `Fail`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run pytest tests/ -q`
- Result:
  - `275 passed in 7.62s`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run ruff check src/ tests/`
- Result:
  - `All checks passed!`.
- Command:
  - `UV_CACHE_DIR=../.uv-cache uv run mypy src/`
- Result:
  - `Success: no issues found in 93 source files`.
- Command:
  - `find docs/plan -maxdepth 1 -type f -print`
- Result:
  - no files; refactor tracking docs remain centralized under `docs/plan/2026-05-09-refactor/`.
- Command:
  - `rg -n -S "(api[_-]?key|api[_-]?secret|passphrase|token)\\s*[:=]\\s*['\\\"][A-Za-z0-9_\\-]{12,}" backend configs docs README.md AGENTS.md CLAUDE.md .env.example .env.okx.demo.example .env.okx.live.example`
- Result:
  - no hardcoded secret values found.
- Command:
  - `rg -n "allow_live_orders: true|validation_allow_live_canary: true|live_trading: true" backend configs README.md docs/DESIGN.md docs/plan/2026-05-09-refactor/99-final-acceptance-report.md AGENTS.md CLAUDE.md`
- Result:
  - only the known live example config, unit-test fixtures, and the scan command text in the final acceptance report matched; no default `allow_live_orders: true` or `validation_allow_live_canary: true` was found.

## Safety Result

- No live orders were sent.
- No non-OKX broker dispatch was added or enabled.
- The 10-cycle window did not increase position size beyond the existing OKX demo 2x stage.
- Negative real-market preflight paths were skipped before any demo order.
- All executed triangular events in the latest 10-cycle window had complete exchange receipts, PnL within tolerance, and residual inventory within tolerance.
- Post-run open-risk checks reported zero open spot orders, zero open swap orders, and zero swap positions.

## Decision

- The R052 orderbook-based triangular pricing follow-up passed a fresh 10-cycle OKX Demo Trading validation window.
- This supports continued OKX demo sampling of `triangular-multi-route` at the current size.
- It does not justify live trading or a position-size increase yet.

## Next Follow-Up

- Keep collecting market-regime-diverse OKX demo windows before any size increase.
- Add a summarized rolling validation report command so future runs do not require manual `tail | jq` analysis.
- Keep `cross-exchange`, `funding-carry-hedged`, `spot-perp-carry`, and `futures-perp-basis` demo-order paths gated by profitable preflight; do not force execution when current market data is negative.
