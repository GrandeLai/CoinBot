# 100 USDC Doubling Strategy Evaluation

Date: 2026-05-13

This report is simulation-only. It does not provide a guaranteed return, does not enable live trading, and did not send live or demo orders.

## Objective

Evaluate common crypto trading-bot strategy families for a 100 USDC starting balance, test the strategies already available in CoinBot, select the best candidate, and run paper validation until the simulated target reaches at least 200 USDC.

## External Bot Patterns Reviewed

- Hummingbot: modular scripts/controllers/executors, market making, arbitrage, cross-exchange market making, AMM arbitrage, and spot-perpetual arbitrage patterns.
- Freqtrade: multi-strategy backtesting, starting-balance/dry-run-wallet controls, hyperopt, stop-loss, trailing stop-loss, and strategy callbacks.
- Jesse: self-hosted Python strategy framework with multi-timeframe/symbol backtesting, indicators, smart ordering, metrics, and risk helpers.
- NautilusTrader: event-driven backtesting with portfolio, execution, and risk-engine concepts.
- CCXT: unified exchange adapter pattern, including explicit handling of precision and market limits.
- 3Commas: DCA, averaging orders, multiple take-profit targets, trailing take-profit, trailing stop-loss, and stop-loss breakeven.

References:

- https://hummingbot.org/docs/
- https://hummingbot.org/strategies/
- https://hummingbot.org/strategies/v1-strategies/
- https://hummingbot.org/strategies/v2-strategies/executors/arbitrage-executor/
- https://hummingbot.org/strategies/v1-strategies/spot-perpetual-arbitrage/
- https://docs.freqtrade.io/en/stable/backtesting/
- https://docs.freqtrade.io/en/stable/stoploss/
- https://docs.freqtrade.io/en/latest/hyperopt/
- https://docs.jesse.trade/
- https://nautilustrader.io/docs/latest/concepts/backtesting
- https://nautilustrader.io/docs/latest/api_reference/risk/
- https://github.com/ccxt/ccxt/wiki/manual
- https://help.3commas.io/en/articles/3108940-dca-bot-interface-and-main-settings
- https://help.3commas.io/en/articles/3108981-smarttrade-how-take-profit-works

## CoinBot Strategy Universe Tested

The local registry exposed 10 strategies:

| Strategy | Family | Result |
| --- | --- | --- |
| triangular-multi-route | Single-exchange triangular arbitrage | Best candidate |
| momentum-rotation | Directional momentum rotation | Second candidate |
| trend-breakout | Directional trend breakout | Viable but lower edge |
| cross-exchange | Cross-exchange spot arbitrage | Viable but lower edge |
| spot-perp-carry | Spot/perp carry | Viable but lower edge |
| funding-carry-hedged | Funding carry | Viable but lower edge |
| futures-perp-basis | Futures/perp basis | Viable but lower edge |
| mean-reversion-spot | Directional mean reversion | No current opportunity |
| volatility-squeeze-breakout | Directional squeeze breakout | No current opportunity |
| orderbook-imbalance-scalp | Orderbook scalp | No current opportunity |

## Safe 100 USDC Config

Created `configs/100usdc.paper.example.yaml` with:

- `trading.live_trading=false`
- `trading.dry_run=true`
- `trading.require_confirm_before_order=true`
- `backtest.initial_capital_usdt=100`
- `arbitrage.trade_size_usdt=100`
- `risk.max_order_value_usdt=100`
- `risk.max_daily_loss_usdt=5`
- `strategy_runtime.max_position_value_usdt=100`
- `strategy_runtime.max_strategy_capital_usdt=100`
- `strategy_runtime.portfolio_max_concurrent_strategies=1`
- isolated journal, guard, retrospective, and evolution files for this evaluation

## Test Commands And Results

| Command | Result |
| --- | --- |
| `.venv/bin/crypto-assistant config validate --config configs/100usdc.paper.example.yaml --json` | Pass |
| `.venv/bin/crypto-assistant strategy score --config configs/100usdc.paper.example.yaml --strategy all --json` | Top scores: triangular-multi-route 77.52, momentum-rotation 75.12, trend-breakout 64.63 |
| `.venv/bin/crypto-assistant strategy portfolio-status --config configs/100usdc.paper.example.yaml --json` | Selected only `triangular-multi-route` because concurrency is capped at 1 |
| `.venv/bin/crypto-assistant strategy validate-local --config configs/100usdc.paper.example.yaml --strategy all --cycles 3 --json` | Pass: 30 cycles, 21 executed, 9 skipped, 0 blocked, 100% win rate on executed events, +27.29429834081243452801976886 USDC |
| `.venv/bin/crypto-assistant strategy run --config configs/100usdc.paper.example.yaml --strategy triangular-multi-route --max-cycles 28 --execution-mode paper --json` | Completed: 28/28 executed, 0 blocked, 0 skipped |
| `.venv/bin/crypto-assistant strategy validation-report --config configs/100usdc.paper.example.yaml --execution-mode paper --strategy triangular-multi-route --limit 50 --json` | 31 triangular events, 31 executed, 31 wins, 0 losses, +113.0019736052789442111577660 USDC |
| `.venv/bin/crypto-assistant strategy guard-status --config configs/100usdc.paper.example.yaml --strategy triangular-multi-route --execution-mode paper --json` | No cooldown, no consecutive failures, no consecutive losses |
| `.venv/bin/crypto-assistant strategy promotion-status --config configs/100usdc.paper.example.yaml --strategy triangular-multi-route --json` | Local Pass; demo needs more samples; live Fail by design because live gates are disabled |
| `.venv/bin/pytest backend/tests/unit/test_config.py -q` | 7 passed |

## Selected Strategy

`triangular-multi-route` is the current best paper strategy.

Reasons:

- Highest 100 USDC score among current strategies: 77.52.
- Portfolio selector chose it when capital concurrency was limited to one strategy.
- Best single-cycle paper opportunity: `triangular-multi-route-mock-usdt-btc-eth-usdt`.
- Expected net profit per fixed 100 USDC round: about 3.645224955 USDC.
- 31 recent paper executions: 31 wins, 0 losses, realized paper net PnL about 113.002 USDC.
- Runtime guard shows no failures, no losses, and no cooldown.
- Evolution promoted it from paper evidence as `active`.

## Doubling Math

Starting principal: 100 USDC.

Paper model used fixed 100 USDC position size per round:

- Required paper profit to double: 100 USDC.
- Per-round paper net profit: about 3.645224955 USDC.
- Fixed-size rounds needed: 28.
- 28-round paper run produced about 102.066298740252 USDC from those 28 cycles alone.
- Including the earlier 3 local-validation triangular samples, the validation report shows 31 triangular paper executions and about 113.001973605279 USDC net profit.

If a real compounding model were used, the theoretical round count at the same percentage edge would be lower, but CoinBot's current paper runtime records fixed-size simulated opportunities rather than continuously increasing trade size.

## Rejected Or Secondary Strategies

- `momentum-rotation`: strong paper edge around 2.96 USDC per 100 USDC round, but directional exposure makes it more market-regime sensitive than pure triangular arbitrage.
- `trend-breakout`: positive but lower edge around 1.174961 USDC per round and directional exposure.
- `spot-perp-carry`, `funding-carry-hedged`, `futures-perp-basis`, `cross-exchange`: lower per-round edge in the current mock market and more operational dependencies.
- `mean-reversion-spot`, `volatility-squeeze-breakout`, `orderbook-imbalance-scalp`: no current approved paper opportunity.

## Operational Recommendation

Use this sequence before any demo or live consideration:

1. Keep `configs/100usdc.paper.example.yaml` as the default 100 USDC research profile.
2. Run `strategy scan`, `strategy score`, and `strategy portfolio-status`.
3. Run `strategy validate-local --strategy all --cycles 3`.
4. If `triangular-multi-route` remains top-ranked and guard status is clean, run bounded paper cycles.
5. Review `strategy validation-report`, `strategy review`, `strategy retrospective`, and `strategy guard-status`.
6. Only consider OKX demo after paper remains positive with realistic market data and demo credentials are configured separately.
7. Do not consider live trading unless demo layer passes, live-canary remains explicitly approved, and all CoinBot live gates pass.

## Safety Conclusion

The 100 USDC doubling target is achieved only in local paper simulation. Real-market profitability is not proven. Live trading remains disabled and should remain disabled until demo-market validation shows durable positive PnL after fees, spread, slippage, precision limits, residual inventory checks, and exchange receipt reconciliation.

## 2026-05-14 Follow-Up Paper Run

The 100 USDC paper route was rerun after the operator chose the practical path. No OKX demo or live orders were sent.

| Command | Result |
| --- | --- |
| `.venv/bin/crypto-assistant config validate --config configs/100usdc.paper.example.yaml --json` | Pass. Safety gates remained `live_trading=false`, `dry_run=true`, OKX disabled, agent live/demo orders disabled, `risk.max_order_value_usdt=100`, and `risk.max_daily_loss_usdt=5`. |
| `.venv/bin/crypto-assistant strategy score --config configs/100usdc.paper.example.yaml --strategy all --json` | `triangular-multi-route` ranked first with score `87.52`; `momentum-rotation` ranked second with score `85.12`; `trend-breakout` ranked third with score `74.63`. |
| `.venv/bin/crypto-assistant strategy portfolio-status --config configs/100usdc.paper.example.yaml --json` | Selected only `triangular-multi-route` because `portfolio_max_concurrent_strategies=1`. |
| `.venv/bin/crypto-assistant strategy validate-local --config configs/100usdc.paper.example.yaml --strategy all --cycles 3 --json` | Pass: 30 paper cycles, 21 executed, 9 skipped, 0 blocked, 21 wins, 0 losses, paper net profit `27.29429834081243452801976886` USDC, max drawdown `0`. |
| `.venv/bin/crypto-assistant strategy run --config configs/100usdc.paper.example.yaml --strategy triangular-multi-route --max-cycles 28 --execution-mode paper` | Completed 28 bounded paper cycles. |
| `.venv/bin/crypto-assistant strategy validation-report --config configs/100usdc.paper.example.yaml --execution-mode paper --strategy triangular-multi-route --limit 80 --json` | Current triangular paper window: 62 executed, 62 wins, 0 losses, 0 skipped, 0 blocked, realized paper net profit `226.0039472105578884223155309` USDC, max drawdown `0`, execution quality passed. |
| `.venv/bin/crypto-assistant strategy guard-status --config configs/100usdc.paper.example.yaml --strategy triangular-multi-route --execution-mode paper --json` | No cooldown. Consecutive failures, losses, market-data failures, and rate-limit failures were all `0`; last reason was `profitable_execution`. |
| `.venv/bin/crypto-assistant strategy promotion-status --config configs/100usdc.paper.example.yaml --strategy triangular-multi-route --json` | Local layer passed. Demo layer still needs samples (`0<10`). Live layer failed by design because demo has not passed, live canary is disabled, live trading is disabled, and agent live orders are disabled. |

Follow-up decision:

- Keep `triangular-multi-route` as the only selected 100 USDC paper strategy while the local mock route remains top-ranked and guard status is clean.
- Treat the paper doubling result as simulation evidence only. It is not live profitability evidence because preflight, real exchange fills, receipt reconciliation, precision limits, residual inventory checks, and OKX demo samples are still missing.
- The next safe progression, if requested, is an OKX Demo Trading validation window using `configs/okx.demo.example.yaml` and separated `.env.okx.demo` credentials. Live trading remains out of scope.

## 2026-05-14 OKX Demo Validation

After operator approval, the selected `triangular-multi-route` strategy was advanced from paper evidence into OKX Demo Trading. Live trading remained disabled throughout the run.

Safety preflight:

| Command | Result |
| --- | --- |
| `.venv/bin/crypto-assistant config validate --config configs/okx.demo.example.yaml --json` | Pass. OKX credentials loaded from `../.env.okx.demo` and redacted in output. `trading.live_trading=false`, `okx.sandbox=true`, `okx.okx_demo=true`, `agent_trading.allow_demo_orders=true`, `agent_trading.allow_live_orders=false`, and `strategy_runtime.validation_allow_live_canary=false`. |
| `.venv/bin/crypto-assistant exchange sandbox-check --config configs/okx.demo.example.yaml --exchange okx --symbol BTC/USDT --include-private --json` | Pass after network approval. Public ping, ticker, orderbook, spot/perp quote, and private account read all passed; `live_orders_sent=false`. |
| `.venv/bin/crypto-assistant strategy guard-status --config configs/okx.demo.example.yaml --strategy triangular-multi-route --execution-mode demo --json` | Guard was clean before validation: no cooldown, no consecutive failures, no consecutive losses, no market-data failures, and no rate-limit failures. |

Execution notes:

- The first 10-cycle attempt executed 5 new profitable demo cycles, then OKX rejected a later buy leg because the submitted marketable limit exceeded OKX's dynamic highest buy price.
- Residual risk was checked immediately after the rejection: `open_spot_orders=0`, `open_swap_orders=0`, and `swap_positions=0`.
- The demo execution price logic was hardened so spot demo buy prices are capped at OKX `buyLmt`, spot sell prices are floored at OKX `sellLmt`, and a spot price-limit rejection refreshes the dynamic limit and retries once.
- Regression coverage was added for both initial price-limit capping and price-limit shrinkage between price generation and submit.

Final validation:

| Command | Result |
| --- | --- |
| `.venv/bin/pytest backend/tests/unit/test_strategy_runtime.py backend/tests/unit/test_config.py -q` | Pass: 59 tests. |
| `.venv/bin/ruff check backend/src/trading_assistant/strategies/demo_execution.py backend/tests/unit/test_strategy_runtime.py` | Pass. |
| `.venv/bin/mypy backend/src/trading_assistant/strategies/demo_execution.py` | Pass. |
| `.venv/bin/crypto-assistant strategy validate-demo-window --config configs/okx.demo.example.yaml --strategy triangular-multi-route --cycles 3 --symbol BTC/USDT --json` | Completed the final 3 demo cycles after the price-limit hardening: 3 executed, 3 wins, net profit `0.600680` USDT, max drawdown `0`, post-run `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`, and `live_orders_sent=false`. |
| `.venv/bin/crypto-assistant strategy validation-report --config configs/okx.demo.example.yaml --execution-mode demo --strategy triangular-multi-route --limit 30 --json` | Aggregate demo evidence passed: 10 executed, 10 wins, 0 losses, 0 skipped, 0 blocked, realized net profit `2.164242` USDT, expected preflight net PnL `2.517948` USDT, max drawdown `0`, complete receipts, PnL within tolerance, residual inventory within tolerance, and execution quality passed. |
| `.venv/bin/crypto-assistant strategy promotion-status --config configs/okx.demo.example.yaml --strategy triangular-multi-route --json` | Local layer `Pass`; demo layer `Pass`; live layer `Fail` by design because live canary is disabled, live trading is disabled, and agent live orders are disabled. |
| Direct OKX demo residual-risk query | `configured=true`, `demo=true`, `open_spot_orders=0`, `open_swap_orders=0`, `swap_positions=0`. |

Decision:

- `triangular-multi-route` is the current champion for the 100 USDC route at paper and OKX demo layers.
- Keep the next runs at the same demo size. Do not increase size until more same-size demo windows pass across different market conditions.
- Live trading remains out of scope. The live layer is intentionally blocked even though local and demo validation now pass.
