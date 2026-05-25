# Strategy Evolution

Updated at: 2026-05-18 03:41:14.615812+00:00

This report is simulation-only. It never enables live trading and never sends live orders.

## Market Regime

- Tag: unknown
- Source: journal
- Sample Count: 50

## Promoted Strategies

- None

## Archived Strategies

- None

## Revival Candidates

- None

## Parameter Candidates

- triangular-multi-route-watchlist-candidate-v1: strategy=triangular-multi-route, status=watchlist, overrides=arbitrage.min_route_depth_usdt=increase_by_20_percent, arbitrage.slippage_pct=stress_test_plus_0.00005
- momentum-rotation-watchlist-candidate-v1: strategy=momentum-rotation, status=watchlist, overrides=directional.min_profit_factor=increase_by_0.05, directional.max_backtest_drawdown_pct=reduce_by_1, directional.demo_max_order_value_usdt=keep_current_or_lower
- trend-breakout-watchlist-candidate-v1: strategy=trend-breakout, status=watchlist, overrides=directional.min_profit_factor=increase_by_0.05, directional.max_backtest_drawdown_pct=reduce_by_1, directional.demo_max_order_value_usdt=keep_current_or_lower
- smart-dca-basket-watchlist-candidate-v1: strategy=smart-dca-basket, status=watchlist, overrides=arbitrage.min_net_profit_pct=increase_by_0.05, arbitrage.trade_size_usdt=reduce_by_50_percent_for_probe
- spot-perp-carry-watchlist-candidate-v1: strategy=spot-perp-carry, status=watchlist, overrides=arbitrage.spot_perp_min_basis_pct=increase_by_0.02, arbitrage.basis_holding_hours=reduce_by_25_percent
- funding-carry-hedged-watchlist-candidate-v1: strategy=funding-carry-hedged, status=watchlist, overrides=arbitrage.funding_min_annualized_pct=increase_by_5, arbitrage.funding_max_basis_hedge_cost_pct=reduce_by_20_percent
- futures-perp-basis-watchlist-candidate-v1: strategy=futures-perp-basis, status=watchlist, overrides=arbitrage.futures_basis_min_basis_pct=increase_by_0.02, arbitrage.futures_basis_min_days_to_expiry=increase_by_1
- cross-exchange-watchlist-candidate-v1: strategy=cross-exchange, status=watchlist, overrides=arbitrage.min_net_profit_pct=increase_by_0.05, arbitrage.trade_size_usdt=reduce_by_50_percent_for_probe
- range-grid-watchlist-candidate-v1: strategy=range-grid, status=watchlist, overrides=arbitrage.min_net_profit_pct=increase_by_0.05, arbitrage.trade_size_usdt=reduce_by_50_percent_for_probe
- hedged-maker-watchlist-candidate-v1: strategy=hedged-maker, status=watchlist, overrides=arbitrage.min_net_profit_pct=increase_by_0.05, arbitrage.trade_size_usdt=reduce_by_50_percent_for_probe
- mean-reversion-spot-watchlist-candidate-v1: strategy=mean-reversion-spot, status=watchlist, overrides=directional.min_profit_factor=increase_by_0.05, directional.max_backtest_drawdown_pct=reduce_by_1, directional.demo_max_order_value_usdt=keep_current_or_lower
- orderbook-imbalance-scalp-watchlist-candidate-v1: strategy=orderbook-imbalance-scalp, status=watchlist, overrides=directional.min_profit_factor=increase_by_0.05, directional.max_backtest_drawdown_pct=reduce_by_1, directional.demo_max_order_value_usdt=keep_current_or_lower
- volatility-squeeze-breakout-watchlist-candidate-v1: strategy=volatility-squeeze-breakout, status=watchlist, overrides=directional.min_profit_factor=increase_by_0.05, directional.max_backtest_drawdown_pct=reduce_by_1, directional.demo_max_order_value_usdt=keep_current_or_lower

## All Decisions

- triangular-multi-route: status=watchlist, action=keep, samples=4, win_rate=100.00, net_profit=14.58885822835432913417316508, reasons=minimum_samples_not_met:4<5
- momentum-rotation: status=watchlist, action=keep, samples=3, win_rate=100.00, net_profit=8.880000, reasons=minimum_samples_not_met:3<5
- trend-breakout: status=watchlist, action=keep, samples=4, win_rate=100.00, net_profit=4.699844, reasons=minimum_samples_not_met:4<5
- smart-dca-basket: status=watchlist, action=keep, samples=1, win_rate=100.00, net_profit=4.138548439606553413017625649, reasons=minimum_samples_not_met:1<5
- spot-perp-carry: status=watchlist, action=keep, samples=4, win_rate=100.00, net_profit=1.519648070385922815436912617, reasons=minimum_samples_not_met:4<5
- funding-carry-hedged: status=watchlist, action=keep, samples=4, win_rate=100.00, net_profit=1.34000, reasons=minimum_samples_not_met:4<5
- futures-perp-basis: status=watchlist, action=keep, samples=4, win_rate=100.00, net_profit=1.272437810945273631840796020, reasons=minimum_samples_not_met:4<5
- cross-exchange: status=watchlist, action=keep, samples=4, win_rate=100.00, net_profit=1.139568086382723455308938052, reasons=minimum_samples_not_met:4<5
- range-grid: status=watchlist, action=keep, samples=1, win_rate=100.00, net_profit=0.2945929674008451713867240444, reasons=minimum_samples_not_met:1<5
- hedged-maker: status=watchlist, action=keep, samples=1, win_rate=0.00, net_profit=0, reasons=minimum_samples_not_met:1<5
- mean-reversion-spot: status=watchlist, action=keep, samples=0, win_rate=0, net_profit=0, reasons=no_simulated_samples
- orderbook-imbalance-scalp: status=watchlist, action=keep, samples=0, win_rate=0, net_profit=0, reasons=no_simulated_samples
- volatility-squeeze-breakout: status=watchlist, action=keep, samples=0, win_rate=0, net_profit=0, reasons=no_simulated_samples
