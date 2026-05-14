# AGENTS.md — CoinBot

CoinBot is the crypto-only extraction of QuantPilot's crypto advisor, OKX trading, derivatives analytics, token unlock, whale monitoring, and Rust quant-core surfaces.

## Required References

- Read `docs/DESIGN.md` before making architecture or module changes.
- For the 2026-05-09 crypto trading assistant refactor, read `docs/plan/2026-05-09-refactor/00-refactor-spec.md` before implementation.
- Keep all refactor planning, task tracking, traceability, acceptance, phase reports, and final reports under `docs/plan/2026-05-09-refactor/`.
- Do not scatter refactor tracking documents into `docs/plan/`, `docs/`, or the repository root. The only project-level exception files are `AGENTS.md` and `CLAUDE.md`.
- Keep `docs/architecture/api.md`, `docs/architecture/frontend-routing.md`, and `docs/architecture/features.md` aligned with public routes and UI navigation.
- Historical migrated task records live under `docs/tasks/**` and `docs/acceptance/**`; active implementation specs should be summarized in `docs/DESIGN.md`.

## Coding Rules

- Python uses Python 3.12, FastAPI, Pydantic v2, loguru, uv, and module-level docstrings.
- Rust quant-core uses axum/tokio/rhai; run `cargo test` after quant-core changes.
- Frontend uses React, Vite, Tailwind v4, Zustand, and lucide icons.
- Environment variables use the `COINBOT_` prefix.
- CoinBot is crypto-only. Do not reintroduce stock, ETF, A-share, Hong Kong equity, Futu, or Longbridge surfaces.
- Python production code must use type annotations and module-level docstrings.
- Core money, price, and yield calculations must use `Decimal` instead of bare `float`.
- External exchange APIs must be isolated behind interfaces; the default implementation for tests and local agent use is mock exchange.
- CLI handlers must stay thin and call service/application layers for business logic.
- Each new feature must include tests.
- Every CLI command must support `--help`.
- Machine-readable CLI commands must support `--json`.
- Run the relevant tests after every refactor phase and record command/results in the phase report.
- Do not use empty implementations, fake implementations, or TODO placeholders as completed functionality.
- Do not remove, bypass, or weaken safety/risk logic just to make tests pass.
- Do not skip acceptance reports. If a capability cannot be fully implemented, mark it `Deferred` or `Blocked` in the traceability matrix and final acceptance report with reason, impact, and follow-up plan.

## Trading Safety Rules

- Live trading is disabled by default.
- Use dry-run, paper trading, and mock exchange by default.
- Real orders require all of these conditions: `trading.live_trading=true`, `trading.dry_run=false`, an enabled non-mock exchange, credentials loaded from environment variables, and risk manager approval.
- OKX simulated trading must use `configs/okx.demo.example.yaml` plus a local `.env.okx.demo`; OKX live trading must use `configs/okx.live.example.yaml` plus a local `.env.okx.live`. Never reuse demo and live credential files.
- OKX Demo Trading orders require `agent_trading.allow_demo_orders=true`, `trading.live_trading=false`, `trading.dry_run=false`, `sandbox=true`, `okx_demo=true`, environment credentials, operator id, execution-quality approval, risk approval, audit logging, and provider demo-mode verification.
- `crypto-assistant strategy validate-demo --allow-account-mode-switch` may switch only the OKX Demo Trading account from spot mode to futures mode for swap-strategy validation. It must never target live trading, must verify provider demo mode first, and must refuse to switch when open orders or swap positions exist. If OKX returns a first-time account-mode setup requirement, the operator must complete it in the OKX Web/App UI.
- `crypto-assistant strategy run --execution-mode demo` may send tiny OKX Demo Trading canary orders only with an OKX demo config. It must record PnL evidence, account snapshots, and post-run open-order/position checks; it must never reuse this path for live trading.
- Autonomous agent live trading requires an additional explicit gate: `agent_trading.enabled=true`, `agent_trading.allow_live_orders=true`, `trading.require_confirm_before_order=false`, an allowlisted strategy, allowlisted non-mock exchanges, environment credentials, `COINBOT_AGENT_OPERATOR_ID`, audit logging, daily/order-size caps, execution-quality approval, risk approval, and `COINBOT_AGENT_LIVE_KILL_SWITCH` not enabled.
- Every live-capable operation must be registered in the operation validation hub with a matching demo config and demo command; `crypto-assistant agent operation-catalog --json` must report no missing demo validation before treating the operation as covered.
- `crypto-assistant agent execute-live` must never dispatch live broker orders unless the autonomous agent gate passes and the target broker adapter is explicitly implemented and tested. At present, only OKX spot limit-order dispatch is wired in `trading_assistant`.
- Never hardcode API keys, secrets, passphrases, or tokens.
- Never commit `.env`, `.env.okx.demo`, or `.env.okx.live`; keep `.env.example`, `.env.okx.demo.example`, and `.env.okx.live.example` safe and secret-free.
- Logs, CLI output, errors, and reports must not print sensitive values in plaintext.
- Default trading configuration must remain equivalent to:

```yaml
trading:
  live_trading: false
  dry_run: true
  require_confirm_before_order: true
```

## Common Commands

```bash
cd backend && uv run pytest tests/ -v
cd backend && uv run ruff check src/ tests/
cd backend && uv run mypy src/
cd quant-core && cargo test
cd frontend && npm install && npm run build
```
