"""Registry for productionized strategy definitions."""

from __future__ import annotations

from builtins import list as builtin_list
from dataclasses import replace

from trading_assistant.exceptions import ConfigError
from trading_assistant.strategies.models import StrategyDefinition


class StrategyRegistry:
    """Expose the supported autonomous strategy set."""

    def __init__(self) -> None:
        self._strategies = {
            "cross-exchange": StrategyDefinition(
                name="cross-exchange",
                scanner_type="cross-exchange",
                description="Cross-exchange spot arbitrage scanner with fee, slippage, depth, transfer, and latency costs.",
                required_markets=["spot"],
                risk_level="medium",
                demo_supported=True,
                live_supported=False,
                notes="Kept for local/paper validation; OKX-first phase does not promote it to demo/live without another CEX adapter.",
            ),
            "triangular-multi-route": StrategyDefinition(
                name="triangular-multi-route",
                scanner_type="triangular-multi-route",
                description="Configurable single-exchange multi-route triangular arbitrage scanner.",
                required_markets=["spot"],
                risk_level="low",
                aliases=["triangular"],
                demo_supported=True,
                live_supported=False,
                execution_alias="triangular",
                notes="Preferred OKX-first pure-arbitrage strategy; legacy name `triangular` is a compatibility alias.",
            ),
            "funding-carry-hedged": StrategyDefinition(
                name="funding-carry-hedged",
                scanner_type="funding-carry-hedged",
                description="Funding carry scanner requiring a spot hedge and net funding edge after costs.",
                required_markets=["spot", "swap"],
                risk_level="medium",
                aliases=["funding-rate"],
                demo_supported=True,
                live_supported=False,
                execution_alias="funding-carry-hedged",
                notes="OKX Demo Trading canary opens and closes a tiny spot/swap hedge after local validation; live remains disabled.",
            ),
            "spot-perp-carry": StrategyDefinition(
                name="spot-perp-carry",
                scanner_type="spot-perp-carry",
                description="Spot-long plus perpetual-short basis and funding carry scanner.",
                required_markets=["spot", "swap"],
                risk_level="medium",
                aliases=["spot-perp"],
                demo_supported=True,
                live_supported=False,
                execution_alias="spot-perp-carry",
                notes="OKX Demo Trading canary opens and closes a tiny spot/swap carry hedge after local validation; live remains disabled.",
            ),
            "futures-perp-basis": StrategyDefinition(
                name="futures-perp-basis",
                scanner_type="futures-perp-basis",
                description="Dated-futures versus perpetual basis scanner with spot/perp/futures market data.",
                required_markets=["spot", "swap", "futures"],
                risk_level="medium",
                demo_supported=True,
                live_supported=False,
                execution_alias="futures-perp-basis",
                notes="OKX Demo Trading canary uses a tiny swap/futures round trip when a dated futures instrument is available; live remains disabled.",
            ),
            "trend-breakout": StrategyDefinition(
                name="trend-breakout",
                scanner_type="trend-breakout",
                description="OKX spot long-only trend breakout using EMA trend, Donchian breakout, and volume confirmation.",
                category="directional",
                required_markets=["spot", "candles"],
                risk_level="medium",
                demo_supported=True,
                live_supported=False,
                notes="Directional OKX demo canary only after local scan, backtest, risk, guard, and demo gates pass; live remains disabled.",
            ),
            "mean-reversion-spot": StrategyDefinition(
                name="mean-reversion-spot",
                scanner_type="mean-reversion-spot",
                description="OKX spot long-only oversold rebound using RSI, Bollinger bands, ATR-style risk, and trend filtering.",
                category="directional",
                required_markets=["spot", "candles"],
                risk_level="medium",
                demo_supported=True,
                live_supported=False,
                notes="Directional OKX demo canary only after local scan, backtest, risk, guard, and demo gates pass; live remains disabled.",
            ),
            "volatility-squeeze-breakout": StrategyDefinition(
                name="volatility-squeeze-breakout",
                scanner_type="volatility-squeeze-breakout",
                description="OKX spot long-only breakout after Bollinger bandwidth compression, ATR expansion, and volume confirmation.",
                category="directional",
                required_markets=["spot", "candles"],
                risk_level="medium",
                demo_supported=True,
                live_supported=False,
                notes="Directional OKX demo canary only after local scan, backtest, risk, guard, and demo gates pass; live remains disabled.",
            ),
            "momentum-rotation": StrategyDefinition(
                name="momentum-rotation",
                scanner_type="momentum-rotation",
                description="OKX mainstream spot cross-sectional momentum rotation with volatility controls and max 1-2 selected symbols.",
                category="directional",
                required_markets=["spot", "candles"],
                risk_level="medium",
                demo_supported=True,
                live_supported=False,
                notes="Directional OKX demo canary only after local scan, backtest, risk, guard, and demo gates pass; live remains disabled.",
            ),
            "orderbook-imbalance-scalp": StrategyDefinition(
                name="orderbook-imbalance-scalp",
                scanner_type="orderbook-imbalance-scalp",
                description="OKX spot orderbook imbalance scalp scanner; first release is scan/backtest/paper only.",
                category="directional",
                required_markets=["spot", "orderbook"],
                risk_level="high",
                demo_supported=False,
                live_supported=False,
                notes="Demo disabled until the other directional strategies accumulate stable validation evidence.",
            ),
            "range-grid": StrategyDefinition(
                name="range-grid",
                scanner_type="range-grid",
                description="Paper-only range-bound grid strategy using regime filters, bounded levels, and fee/slippage-adjusted simulated cycles.",
                category="grid",
                required_markets=["spot", "candles", "orderbook"],
                risk_level="medium",
                demo_supported=False,
                live_supported=False,
                notes="Paper-only first release; OKX demo grid orders require a separate stateful order manager and are intentionally disabled.",
            ),
            "hedged-maker": StrategyDefinition(
                name="hedged-maker",
                scanner_type="hedged-maker",
                description="Paper-only hedged maker/XEMM planner that quotes passively and previews an immediate taker hedge.",
                category="market-making",
                required_markets=["spot", "orderbook", "balance"],
                risk_level="medium",
                demo_supported=False,
                live_supported=False,
                notes="Paper-only first release; real maker quotes require stateful own-order tracking, cancel/refresh, and sandbox parity tests.",
            ),
        }
        self._aliases = {
            alias: name
            for name, definition in self._strategies.items()
            for alias in definition.aliases
        }

    def list(self) -> builtin_list[StrategyDefinition]:
        """Return all concrete strategy definitions."""
        return list(self._strategies.values())

    def names(self) -> builtin_list[str]:
        """Return all concrete strategy names."""
        return list(self._strategies)

    def aliases(self) -> dict[str, str]:
        """Return compatibility aliases mapped to canonical strategy names."""
        return dict(self._aliases)

    def get(self, name: str) -> StrategyDefinition:
        """Return a strategy by name, allowing aggregate `all`."""
        if name == "all":
            return StrategyDefinition(
                name="all",
                scanner_type="all",
                description="Run every registered strategy in sequence.",
            )
        if name in {"arbitrage", "arbitrage-all"}:
            return StrategyDefinition(
                name=name,
                scanner_type="arbitrage-all",
                description="Run every registered arbitrage strategy in sequence.",
                category="arbitrage",
            )
        if name in {"directional", "directional-all"}:
            return StrategyDefinition(
                name=name,
                scanner_type="directional-all",
                description="Run every registered directional strategy in sequence.",
                category="directional",
            )
        if name in self._aliases:
            definition = self._strategies[self._aliases[name]]
            return replace(definition, name=name)
        try:
            return self._strategies[name]
        except KeyError as exc:
            raise ConfigError(f"Unsupported strategy: {name}") from exc

    def expand(self, name: str) -> builtin_list[StrategyDefinition]:
        """Expand `all` into concrete strategies."""
        if name == "all":
            return self.list()
        if name in {"arbitrage", "arbitrage-all"}:
            return [definition for definition in self.list() if definition.category == "arbitrage"]
        if name in {"directional", "directional-all"}:
            return [definition for definition in self.list() if definition.category == "directional"]
        return [self.get(name)]

    def demo_validation_names(self) -> builtin_list[str]:
        """Return demo-order validation names for supported demo-capable execution paths."""
        return [
            definition.execution_alias or definition.name
            for definition in self._strategies.values()
            if definition.demo_supported
        ]
