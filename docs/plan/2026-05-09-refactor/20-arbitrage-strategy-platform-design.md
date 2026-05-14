# OKX-First Arbitrage Strategy Platform Design

Date: 2026-05-10

## Scope

This design extends the existing crypto trading assistant without relaxing live-trading gates. The first implementation targets local mock and paper validation, with OKX Demo Trading reserved for explicitly supported and allowlisted canary execution paths.

## Platform Layers

- `StrategyCatalog`: canonical strategy metadata, aliases, required markets, supported modes, risk level, and live/demo capability flags.
- `StrategyController`: scan-only controller. It asks registered scanners for opportunities and never submits orders.
- `StrategyScoreService`: transparent scorecards using net edge, confidence, risk score, history, demo sample count, and free-balance/sell-leg restrictions.
- `StrategyPortfolioService`: bounded strategy selection using score floors, max concurrency, and configured capital caps.
- `StrategyValidationService`: remains the promotion gate from local paper to demo-window to live-canary. Live-canary stays disabled by default.

## Strategies

- `triangular-multi-route`: configured routes such as `USDT -> BTC -> ETH -> USDT` and `USDT -> BTC -> SOL -> USDT`; legacy alias `triangular`.
- `spot-perp-carry`: spot-long plus perpetual-short basis/funding carry; scan and paper first.
- `funding-carry-hedged`: funding carry ranking that requires a spot hedge and filters insufficient net edge.
- `futures-perp-basis`: dated futures versus perpetual basis using futures metadata; returns no opportunities when data is unavailable.
- `cross-exchange`: retained for local/paper validation, not promoted in OKX-first mode until more real CEX adapters exist.

## Safety

- New strategies default to scan/paper validation.
- Demo execution is blocked unless the strategy is demo-supported and allowlisted.
- Live execution remains blocked by the existing live and autonomous agent gates.
- Scoring treats frozen or unavailable sell inventory as a downgrade/blocking signal.
- All calculations continue to use `Decimal`; API keys remain environment-only.

