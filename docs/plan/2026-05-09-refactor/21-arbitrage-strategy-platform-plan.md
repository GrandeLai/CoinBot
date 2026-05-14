# OKX-First Arbitrage Strategy Platform Plan

Date: 2026-05-10

## Tasks

- Add OKX/mock exchange metadata needed by basis strategies: instruments, swap/futures tickers, funding schedule, and futures basis quote.
- Implement `triangular-multi-route`, `spot-perp-carry`, `funding-carry-hedged`, and `futures-perp-basis` scanners.
- Register canonical strategy names and compatibility aliases in `StrategyRegistry`.
- Add `StrategyCatalog`, `StrategyController`, `StrategyScoreService`, and `StrategyPortfolioService`.
- Add CLI commands: `strategy catalog`, `strategy scan`, `strategy score`, and `strategy portfolio-status`.
- Keep `strategy run`, `review`, `guard-status`, `validate-local`, `validate-demo-window`, and `promotion-status` compatible.
- Add unit, integration, and e2e coverage for the strategy platform and new scanners.
- Update README, DESIGN, configs, traceability matrix, and final acceptance report.

## Acceptance

- `crypto-assistant strategy catalog --json` lists canonical strategies and aliases.
- `crypto-assistant strategy scan --strategy all --symbol BTC/USDT --json` returns mock opportunities across multiple strategies.
- `crypto-assistant strategy score --strategy all --json` returns transparent scorecards.
- `crypto-assistant strategy portfolio-status --json` selects a bounded strategy set.
- `crypto-assistant strategy run --strategy all --execution-mode paper --max-cycles 1 --json` executes the paper loop without real orders.
- OKX demo execution remains allowlisted and live trading remains disabled by default.

