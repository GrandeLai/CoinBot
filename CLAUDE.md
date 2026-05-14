# CLAUDE.md — CoinBot Agent Constraints

CoinBot is a crypto-only quant trading and research workspace. All agents must preserve the safety-first trading posture and keep refactor documentation centralized.

## Required Refactor References

- Refactor spec: `docs/plan/2026-05-09-refactor/00-refactor-spec.md`
- Refactor document directory: `docs/plan/2026-05-09-refactor/`
- All plans, task checklists, traceability matrices, acceptance checklists, phase reports, and final reports from this refactor must stay in `docs/plan/2026-05-09-refactor/`.
- Do not place refactor tracking documents in `docs/plan/`, `docs/`, or the repository root. The only project-level constraint files are `AGENTS.md` and `CLAUDE.md`.

## Engineering Rules

- Python uses Python 3.12, Pydantic v2, FastAPI where applicable, loguru, uv, and module-level docstrings.
- New production code must include type annotations.
- Money, price, fee, slippage, yield, and PnL calculations must prefer `Decimal`.
- Each new feature must have tests.
- Each CLI command must support `--help`.
- Machine-readable CLI output must support `--json`.
- CLI commands must call service/application layers; do not bury complex business logic in CLI parsing code.
- Run relevant tests after each phase and record command/results in the phase report.
- Do not use empty implementations, fake implementations, or TODO placeholders in place of complete behavior.
- Do not delete or bypass safety logic to make tests pass.
- Do not skip traceability or acceptance reporting.
- If a feature cannot be completed, mark it `Deferred` or `Blocked` in the traceability matrix and final acceptance report with reason, impact, and follow-up plan.

## Trading Safety Rules

- Live trading is disabled by default.
- Default mode is dry-run / paper trading / mock exchange.
- Real orders require all conditions: `trading.live_trading=true`, `trading.dry_run=false`, an enabled real exchange, credentials sourced from environment variables, and risk manager approval.
- OKX simulated trading must use `configs/okx.demo.example.yaml` plus a local `.env.okx.demo`; OKX live trading must use `configs/okx.live.example.yaml` plus a local `.env.okx.live`. Demo and live credentials must stay separated.
- OKX Demo Trading orders require `agent_trading.allow_demo_orders=true`, `trading.live_trading=false`, `trading.dry_run=false`, `sandbox=true`, `okx_demo=true`, environment credentials, operator id, execution-quality approval, risk approval, audit logging, and provider demo-mode verification.
- `crypto-assistant strategy validate-demo --allow-account-mode-switch` may switch only the OKX Demo Trading account from spot mode to futures mode for swap-strategy validation. It must never target live trading, must verify provider demo mode first, and must refuse to switch when open orders or swap positions exist. If OKX returns a first-time account-mode setup requirement, the operator must complete it in the OKX Web/App UI.
- `crypto-assistant strategy run --execution-mode demo` may send tiny OKX Demo Trading canary orders only with an OKX demo config. It must record PnL evidence, account snapshots, and post-run open-order/position checks; it must never reuse this path for live trading.
- Autonomous agent live trading additionally requires `agent_trading.enabled=true`, `agent_trading.allow_live_orders=true`, `trading.require_confirm_before_order=false`, allowlisted strategy/exchange, environment credentials, `COINBOT_AGENT_OPERATOR_ID`, audit logging, daily/order-size caps, execution-quality approval, risk approval, and `COINBOT_AGENT_LIVE_KILL_SWITCH` not enabled.
- Every live-capable operation must be registered in the operation validation hub with a matching demo config and demo command; `crypto-assistant agent operation-catalog --json` must report no missing demo validation before treating the operation as covered.
- `crypto-assistant agent execute-live` must not dispatch live broker orders unless the autonomous agent gate passes and the target broker adapter is explicitly implemented and tested. At present, only OKX spot limit-order dispatch is wired in `trading_assistant`.
- Never hardcode API keys, secrets, passphrases, or tokens.
- Never commit `.env`, `.env.okx.demo`, or `.env.okx.live`; maintain `.env.example`, `.env.okx.demo.example`, and `.env.okx.live.example` without real secrets.
- Logs, CLI output, error messages, and reports must redact sensitive values.
- Default trading config must remain:

```yaml
trading:
  live_trading: false
  dry_run: true
  require_confirm_before_order: true
```
