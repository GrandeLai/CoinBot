"""Pydantic configuration schema for safe local trading workflows."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AppConfig(BaseModel):
    """Application identity and runtime mode."""

    name: str = "crypto-trading-assistant"
    mode: Literal["mock", "paper", "sandbox", "live"] = "paper"
    log_level: str = "INFO"
    env_file: str | None = None


class TradingConfig(BaseModel):
    """Trading safety switches."""

    live_trading: bool = False
    dry_run: bool = True
    require_confirm_before_order: bool = True

    @model_validator(mode="after")
    def validate_live_gate(self) -> "TradingConfig":
        """Reject contradictory live/dry-run settings."""
        if self.live_trading and self.dry_run:
            raise ValueError("live_trading=true requires dry_run=false")
        return self


class AgentTradingConfig(BaseModel):
    """Autonomous agent live-trading controls.

    These controls are intentionally stricter than the generic trading gate.
    Defaults never allow autonomous live orders.
    """

    enabled: bool = False
    allow_demo_orders: bool = False
    allow_live_orders: bool = False
    strategy_allowlist: list[str] = Field(default_factory=list)
    allowed_exchanges: list[str] = Field(default_factory=list)
    max_autonomous_order_value_usdt: Decimal = Decimal("100")
    max_autonomous_orders_per_day: int = 0
    require_audit_log: bool = True
    audit_log_path: str = "logs/agent-live-trading-audit.jsonl"
    operator_id_env: str = "COINBOT_AGENT_OPERATOR_ID"
    policy_id: str = "default-disabled"
    kill_switch_env: str = "COINBOT_AGENT_LIVE_KILL_SWITCH"

    @field_validator("max_autonomous_order_value_usdt")
    @classmethod
    def positive_agent_order_value(cls, value: Decimal) -> Decimal:
        """Require positive agent order cap."""
        if value <= 0:
            raise ValueError("must be positive")
        return value

    @field_validator("max_autonomous_orders_per_day")
    @classmethod
    def non_negative_order_limit(cls, value: int) -> int:
        """Require a non-negative daily order count."""
        if value < 0:
            raise ValueError("must be non-negative")
        return value


class ExchangeConfig(BaseModel):
    """Exchange adapter configuration."""

    enabled: bool = True
    sandbox: bool = True
    adapter: str = "mock"
    api_key_env: str | None = None
    api_secret_env: str | None = None
    passphrase_env: str | None = None
    okx_demo: bool | None = None

    @model_validator(mode="after")
    def validate_okx_demo_mode(self) -> "ExchangeConfig":
        """Ensure enabled OKX configs do not mix sandbox and live modes."""
        if self.enabled and self.adapter == "okx" and self.okx_demo is not None and self.okx_demo != self.sandbox:
            raise ValueError("okx_demo must match sandbox for enabled OKX exchange")
        return self

    def redacted_credentials(self) -> dict[str, str | None]:
        """Return credential status without exposing raw secret values."""
        return {
            "api_key": _redact_env(self.api_key_env),
            "api_secret": _redact_env(self.api_secret_env),
            "passphrase": _redact_env(self.passphrase_env),
        }


class CircuitBreakerConfig(BaseModel):
    """API failure circuit breaker settings."""

    enabled: bool = True
    max_consecutive_failures: int = 3
    cooldown_seconds: int = 300


class RiskConfig(BaseModel):
    """Risk limits checked before any execution."""

    max_order_value_usdt: Decimal = Decimal("1000")
    max_daily_loss_usdt: Decimal = Decimal("50")
    max_position_exposure_usdt: Decimal = Decimal("500")
    min_net_profit_pct: Decimal = Decimal("0.15")
    max_slippage_pct: Decimal = Decimal("0.05")
    min_orderbook_depth_usdt: Decimal = Decimal("1000")
    max_orders_per_minute: int = 5
    symbol_blacklist: list[str] = Field(default_factory=list)
    exchange_blacklist: list[str] = Field(default_factory=list)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)

    @field_validator(
        "max_order_value_usdt",
        "max_daily_loss_usdt",
        "max_position_exposure_usdt",
        "min_orderbook_depth_usdt",
    )
    @classmethod
    def positive_money(cls, value: Decimal) -> Decimal:
        """Require positive monetary limits."""
        if value <= 0:
            raise ValueError("must be positive")
        return value

    @field_validator("min_net_profit_pct", "max_slippage_pct")
    @classmethod
    def non_negative_pct(cls, value: Decimal) -> Decimal:
        """Require non-negative percentage thresholds."""
        if value < 0:
            raise ValueError("must be non-negative")
        return value


class ArbitrageConfig(BaseModel):
    """Arbitrage scanner settings."""

    enabled: bool = True
    scan_interval_seconds: int = 10
    min_net_profit_pct: Decimal = Decimal("0.15")
    symbols: list[str] = Field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    trade_size_usdt: Decimal = Decimal("100")
    fee_pct: Decimal = Decimal("0.001")
    maker_fee_pct: Decimal = Decimal("0.0008")
    taker_fee_pct: Decimal = Decimal("0.001")
    maker_ratio: Decimal = Decimal("0")
    slippage_pct: Decimal = Decimal("0.0001")
    withdrawal_fee_usdt: Decimal = Decimal("0.02")
    transfer_delay_risk_pct: Decimal = Decimal("0.0001")
    latency_ms: int = 500
    price_drift_bps_per_second: Decimal = Decimal("1")
    min_spread_persistence_pct: Decimal = Decimal("0.15")
    spread_persistence_windows: int = 3
    spread_persistence_samples_pct: list[Decimal] = Field(default_factory=lambda: [Decimal("0.54"), Decimal("0.50"), Decimal("0.45")])
    funding_holding_hours: Decimal = Decimal("8")
    funding_settlement_interval_hours: Decimal = Decimal("8")
    funding_hedge_cost_pct: Decimal = Decimal("0.0002")
    funding_min_annualized_pct: Decimal = Decimal("20")
    funding_max_basis_hedge_cost_pct: Decimal = Decimal("0.30")
    triangular_routes: list[list[str]] = Field(
        default_factory=lambda: [
            ["USDT", "BTC", "ETH", "USDT"],
            ["USDT", "BTC", "SOL", "USDT"],
        ]
    )
    min_route_depth_usdt: Decimal = Decimal("1000")
    basis_holding_hours: Decimal = Decimal("24")
    spot_perp_min_basis_pct: Decimal = Decimal("0.05")
    futures_basis_min_basis_pct: Decimal = Decimal("0.05")
    futures_basis_min_days_to_expiry: int = 3

    @field_validator(
        "funding_min_annualized_pct",
        "funding_max_basis_hedge_cost_pct",
        "spot_perp_min_basis_pct",
        "futures_basis_min_basis_pct",
    )
    @classmethod
    def non_negative_arbitrage_pct(cls, value: Decimal) -> Decimal:
        """Require non-negative carry/basis thresholds."""
        if value < 0:
            raise ValueError("must be non-negative")
        return value

    @field_validator("trade_size_usdt", "min_route_depth_usdt")
    @classmethod
    def positive_arbitrage_money(cls, value: Decimal) -> Decimal:
        """Require positive arbitrage capital/depth controls."""
        if value <= 0:
            raise ValueError("must be positive")
        return value

    @field_validator("futures_basis_min_days_to_expiry")
    @classmethod
    def positive_arbitrage_ints(cls, value: int) -> int:
        """Require positive futures expiry controls."""
        if value <= 0:
            raise ValueError("must be positive")
        return value


class BacktestConfig(BaseModel):
    """Backtest defaults."""

    initial_capital_usdt: Decimal = Decimal("10000")
    fee_pct: Decimal = Decimal("0.001")


class DirectionalConfig(BaseModel):
    """OKX-first long-only spot directional strategy controls."""

    enabled: bool = True
    exchange: str = "mock"
    symbols: list[str] = Field(default_factory=lambda: ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT", "ADA/USDT"])
    bar: str = "15m"
    candles_limit: int = 120
    max_position_value_usdt: Decimal = Decimal("250")
    total_max_exposure_usdt: Decimal = Decimal("750")
    single_trade_risk_equity_pct: Decimal = Decimal("0.20")
    daily_loss_pct: Decimal = Decimal("0.50")
    min_profit_factor: Decimal = Decimal("1.10")
    max_backtest_drawdown_pct: Decimal = Decimal("5")
    min_backtest_net_profit_usdt: Decimal = Decimal("0")
    demo_enabled_strategies: list[str] = Field(
        default_factory=lambda: [
            "trend-breakout",
            "mean-reversion-spot",
            "volatility-squeeze-breakout",
            "momentum-rotation",
        ]
    )
    demo_max_order_value_usdt: Decimal = Decimal("20")
    position_state_path: str = "logs/directional-demo-positions.json"
    fee_pct: Decimal = Decimal("0.001")
    slippage_pct: Decimal = Decimal("0.0002")

    @field_validator("candles_limit")
    @classmethod
    def positive_candle_limit(cls, value: int) -> int:
        """Require a positive candle limit."""
        if value <= 0:
            raise ValueError("must be positive")
        return value

    @field_validator(
        "max_position_value_usdt",
        "total_max_exposure_usdt",
        "demo_max_order_value_usdt",
    )
    @classmethod
    def positive_directional_money(cls, value: Decimal) -> Decimal:
        """Require positive directional money controls."""
        if value <= 0:
            raise ValueError("must be positive")
        return value

    @field_validator(
        "single_trade_risk_equity_pct",
        "daily_loss_pct",
        "min_profit_factor",
        "max_backtest_drawdown_pct",
        "min_backtest_net_profit_usdt",
        "fee_pct",
        "slippage_pct",
    )
    @classmethod
    def non_negative_directional_pct(cls, value: Decimal) -> Decimal:
        """Require non-negative directional percentages and thresholds."""
        if value < 0:
            raise ValueError("must be non-negative")
        return value


class UniverseConfig(BaseModel):
    """Read-only market universe and regime filter controls."""

    enabled: bool = True
    symbols: list[str] = Field(default_factory=lambda: ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT", "ADA/USDT"])
    bar: str = "15m"
    candles_limit: int = 80
    min_24h_volume_usdt: Decimal = Decimal("100000")
    min_depth_usdt: Decimal = Decimal("1000")
    max_spread_pct: Decimal = Decimal("0.10")
    trend_return_threshold_pct: Decimal = Decimal("1.00")
    range_volatility_max_pct: Decimal = Decimal("1.25")

    @field_validator("candles_limit")
    @classmethod
    def positive_universe_candle_limit(cls, value: int) -> int:
        """Require a positive universe candle limit."""
        if value <= 0:
            raise ValueError("must be positive")
        return value

    @field_validator(
        "min_24h_volume_usdt",
        "min_depth_usdt",
        "max_spread_pct",
        "trend_return_threshold_pct",
        "range_volatility_max_pct",
    )
    @classmethod
    def non_negative_universe_thresholds(cls, value: Decimal) -> Decimal:
        """Require non-negative universe thresholds."""
        if value < 0:
            raise ValueError("must be non-negative")
        return value


class ExitOptimizationConfig(BaseModel):
    """Read-only triple-barrier exit optimization controls."""

    enabled: bool = True
    take_profit_candidates_pct: list[Decimal] = Field(default_factory=lambda: [Decimal("1.00"), Decimal("2.00"), Decimal("3.00")])
    stop_loss_candidates_pct: list[Decimal] = Field(default_factory=lambda: [Decimal("0.50"), Decimal("1.00"), Decimal("1.50")])
    trailing_stop_candidates_pct: list[Decimal] = Field(default_factory=lambda: [Decimal("0"), Decimal("0.50"), Decimal("1.00")])
    time_limit_candidates_bars: list[int] = Field(default_factory=lambda: [8, 16, 32])
    max_candidates: int = 5

    @field_validator("take_profit_candidates_pct", "stop_loss_candidates_pct")
    @classmethod
    def positive_exit_candidate_pcts(cls, value: list[Decimal]) -> list[Decimal]:
        """Require positive take-profit and stop-loss candidates."""
        if not value or any(item <= 0 for item in value):
            raise ValueError("must contain positive values")
        return value

    @field_validator("trailing_stop_candidates_pct")
    @classmethod
    def non_negative_trailing_candidates(cls, value: list[Decimal]) -> list[Decimal]:
        """Require non-negative trailing-stop candidates."""
        if not value or any(item < 0 for item in value):
            raise ValueError("must contain non-negative values")
        return value

    @field_validator("time_limit_candidates_bars")
    @classmethod
    def positive_time_limit_candidates(cls, value: list[int]) -> list[int]:
        """Require positive time-limit candidates."""
        if not value or any(item <= 0 for item in value):
            raise ValueError("must contain positive values")
        return value

    @field_validator("max_candidates")
    @classmethod
    def positive_exit_max_candidates(cls, value: int) -> int:
        """Require a positive number of returned candidates."""
        if value <= 0:
            raise ValueError("must be positive")
        return value


class RangeGridConfig(BaseModel):
    """Paper-only range-grid strategy controls."""

    enabled: bool = True
    exchange: str = "mock"
    symbols: list[str] = Field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    grid_levels: int = 6
    lookback_candles: int = 48
    total_quote_usdt: Decimal = Decimal("100")
    min_grid_spacing_pct: Decimal = Decimal("0.80")
    max_range_width_pct: Decimal = Decimal("12")
    fee_pct: Decimal = Decimal("0.001")
    slippage_pct: Decimal = Decimal("0.0002")

    @field_validator("grid_levels")
    @classmethod
    def minimum_grid_levels(cls, value: int) -> int:
        """Require at least three grid levels."""
        if value < 3:
            raise ValueError("must be at least 3")
        return value

    @field_validator("lookback_candles")
    @classmethod
    def positive_grid_lookback(cls, value: int) -> int:
        """Require a positive grid lookback."""
        if value <= 0:
            raise ValueError("must be positive")
        return value

    @field_validator("total_quote_usdt")
    @classmethod
    def positive_grid_capital(cls, value: Decimal) -> Decimal:
        """Require positive grid capital."""
        if value <= 0:
            raise ValueError("must be positive")
        return value

    @field_validator("min_grid_spacing_pct", "max_range_width_pct", "fee_pct", "slippage_pct")
    @classmethod
    def non_negative_grid_thresholds(cls, value: Decimal) -> Decimal:
        """Require non-negative grid thresholds."""
        if value < 0:
            raise ValueError("must be non-negative")
        return value


class ReportingConfig(BaseModel):
    """Report generation settings."""

    output_dir: str = "reports"


class DemoStrategySizingConfig(BaseModel):
    """Optional per-strategy OKX demo canary sizing override."""

    order_size_multiplier: Decimal | None = None
    max_order_value_usdt: Decimal | None = None

    @field_validator("order_size_multiplier", "max_order_value_usdt")
    @classmethod
    def positive_optional_demo_size(cls, value: Decimal | None) -> Decimal | None:
        """Require positive override values when configured."""
        if value is not None and value <= 0:
            raise ValueError("must be positive")
        return value


class StrategyRuntimeConfig(BaseModel):
    """Controls for long-running strategy orchestration."""

    enabled: bool = True
    default_execution_mode: Literal["paper", "demo"] = "paper"
    enabled_strategies: list[str] = Field(
        default_factory=lambda: [
            "cross-exchange",
            "triangular-multi-route",
            "funding-carry-hedged",
            "spot-perp-carry",
            "futures-perp-basis",
            "trend-breakout",
            "mean-reversion-spot",
            "volatility-squeeze-breakout",
            "momentum-rotation",
            "orderbook-imbalance-scalp",
            "range-grid",
        ]
    )
    portfolio_max_concurrent_strategies: int = 3
    portfolio_min_score: Decimal = Decimal("50")
    max_position_value_usdt: Decimal = Decimal("100")
    max_strategy_capital_usdt: Decimal = Decimal("250")
    max_open_orders_per_strategy: int = 2
    order_ttl_seconds: int = 30
    reprice_threshold_pct: Decimal = Decimal("0.05")
    demo_max_order_value_usdt: Decimal = Decimal("10")
    demo_order_size_multiplier: Decimal = Decimal("1")
    demo_strategy_size_overrides: dict[str, DemoStrategySizingConfig] = Field(default_factory=dict)
    demo_order_wait_seconds: int = 3
    demo_order_poll_interval_seconds: Decimal = Decimal("0.5")
    demo_limit_price_buffer_pct: Decimal = Decimal("0.001")
    demo_require_profitable_preflight: bool = True
    demo_min_preflight_net_pnl_usdt: Decimal = Decimal("0")
    demo_preflight_adaptive_buffer_enabled: bool = True
    demo_preflight_adaptive_buffer_min_samples: int = 3
    demo_preflight_adaptive_buffer_quantile_pct: Decimal = Decimal("80")
    demo_preflight_adaptive_buffer_lookback: int = 50
    demo_preflight_adaptive_buffer_max_usdt: Decimal = Decimal("0.10")
    demo_stop_loss_usdt: Decimal = Decimal("1")
    demo_max_drawdown_usdt: Decimal = Decimal("1")
    demo_pnl_reconciliation_tolerance_usdt: Decimal = Decimal("0.05")
    demo_residual_inventory_tolerance_usdt: Decimal = Decimal("0.05")
    runtime_guard_enabled: bool = True
    runtime_guard_path: str = "logs/strategy-runtime-guard.json"
    max_consecutive_execution_failures: int = 3
    max_consecutive_losses: int = 3
    max_consecutive_market_data_failures: int = 3
    max_consecutive_rate_limit_failures: int = 2
    failure_cooldown_seconds: int = 300
    journal_path: str = "logs/strategy-events.jsonl"
    review_min_samples: int = 5
    min_review_win_rate_pct: Decimal = Decimal("40")
    learning_enabled: bool = True
    evolution_enabled: bool = True
    evolution_state_path: str = "docs/plan/2026-05-09-refactor/45-strategy-evolution.state.json"
    evolution_report_path: str = "docs/plan/2026-05-09-refactor/45-strategy-evolution.md"
    evolution_min_net_profit_usdt: Decimal = Decimal("0")
    evolution_archive_score_penalty: Decimal = Decimal("100")
    retrospective_enabled: bool = True
    retrospective_path: str = "docs/plan/2026-05-09-refactor/28-strategy-retrospective.md"
    retrospective_state_path: str = "docs/plan/2026-05-09-refactor/28-strategy-retrospective.state.json"
    retrospective_repeat_warning_threshold: int = 2
    retrospective_demo_preflight_score_penalty: Decimal = Decimal("30")
    validation_min_local_executions: int = 1
    validation_min_demo_executions: int = 10
    validation_min_win_rate_pct: Decimal = Decimal("60")
    validation_min_net_profit_usdt: Decimal = Decimal("0")
    validation_max_drawdown_usdt: Decimal = Decimal("1")
    validation_allow_live_canary: bool = False
    autopilot_state_path: str = "logs/autopilot-state.json"
    autopilot_default_interval_seconds: int = 60
    autopilot_max_consecutive_blocked_cycles: int = 3
    autopilot_stop_on_live_signal: bool = True

    @field_validator(
        "max_position_value_usdt",
        "max_strategy_capital_usdt",
        "demo_max_order_value_usdt",
        "demo_order_size_multiplier",
        "demo_stop_loss_usdt",
        "demo_max_drawdown_usdt",
    )
    @classmethod
    def positive_strategy_money(cls, value: Decimal) -> Decimal:
        """Require positive strategy capital controls."""
        if value <= 0:
            raise ValueError("must be positive")
        return value

    @field_validator(
        "max_open_orders_per_strategy",
        "order_ttl_seconds",
        "demo_order_wait_seconds",
        "max_consecutive_execution_failures",
        "max_consecutive_losses",
        "max_consecutive_market_data_failures",
        "max_consecutive_rate_limit_failures",
        "failure_cooldown_seconds",
        "review_min_samples",
        "retrospective_repeat_warning_threshold",
        "validation_min_local_executions",
        "validation_min_demo_executions",
        "portfolio_max_concurrent_strategies",
        "demo_preflight_adaptive_buffer_min_samples",
        "demo_preflight_adaptive_buffer_lookback",
        "autopilot_default_interval_seconds",
        "autopilot_max_consecutive_blocked_cycles",
    )
    @classmethod
    def positive_strategy_ints(cls, value: int) -> int:
        """Require positive runtime counts and TTLs."""
        if value <= 0:
            raise ValueError("must be positive")
        return value

    @field_validator(
        "reprice_threshold_pct",
        "demo_order_poll_interval_seconds",
        "demo_limit_price_buffer_pct",
        "demo_min_preflight_net_pnl_usdt",
        "demo_preflight_adaptive_buffer_quantile_pct",
        "demo_preflight_adaptive_buffer_max_usdt",
        "demo_pnl_reconciliation_tolerance_usdt",
        "demo_residual_inventory_tolerance_usdt",
        "min_review_win_rate_pct",
        "portfolio_min_score",
        "validation_min_win_rate_pct",
        "validation_min_net_profit_usdt",
        "validation_max_drawdown_usdt",
        "evolution_min_net_profit_usdt",
        "evolution_archive_score_penalty",
        "retrospective_demo_preflight_score_penalty",
    )
    @classmethod
    def non_negative_strategy_pct(cls, value: Decimal) -> Decimal:
        """Require non-negative strategy percentages."""
        if value < 0:
            raise ValueError("must be non-negative")
        return value

    @field_validator("demo_limit_price_buffer_pct")
    @classmethod
    def reasonable_demo_limit_buffer(cls, value: Decimal) -> Decimal:
        """Keep demo marketable-limit buffers bounded."""
        if value >= Decimal("0.05"):
            raise ValueError("must be below 0.05")
        return value

    @field_validator("demo_preflight_adaptive_buffer_quantile_pct")
    @classmethod
    def reasonable_preflight_buffer_quantile(cls, value: Decimal) -> Decimal:
        """Keep adaptive preflight buffer quantiles in percentile bounds."""
        if value > Decimal("100"):
            raise ValueError("must be at most 100")
        return value


class Settings(BaseModel):
    """Top-level settings model."""

    model_config = ConfigDict(validate_assignment=True)

    app: AppConfig = Field(default_factory=AppConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    exchanges: dict[str, ExchangeConfig] = Field(default_factory=lambda: default_exchanges())
    risk: RiskConfig = Field(default_factory=RiskConfig)
    arbitrage: ArbitrageConfig = Field(default_factory=ArbitrageConfig)
    agent_trading: AgentTradingConfig = Field(default_factory=AgentTradingConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    directional: DirectionalConfig = Field(default_factory=DirectionalConfig)
    universe: UniverseConfig = Field(default_factory=UniverseConfig)
    exit_optimization: ExitOptimizationConfig = Field(default_factory=ExitOptimizationConfig)
    range_grid: RangeGridConfig = Field(default_factory=RangeGridConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    strategy_runtime: StrategyRuntimeConfig = Field(default_factory=StrategyRuntimeConfig)

    def redacted_dict(self) -> dict[str, Any]:
        """Serialize settings while masking credential presence."""
        data = self.model_dump(mode="json")
        data["exchanges"] = {
            name: {
                **config.model_dump(mode="json"),
                "credentials": config.redacted_credentials(),
            }
            for name, config in self.exchanges.items()
        }
        return data


def default_exchanges() -> dict[str, ExchangeConfig]:
    """Return safe mock-first exchange defaults."""
    return {
        "mock": ExchangeConfig(
            enabled=True,
            sandbox=True,
            adapter="mock",
            api_key_env="COINBOT_MOCK_API_KEY",
            api_secret_env="COINBOT_MOCK_API_SECRET",
        ),
        "mock_alt": ExchangeConfig(enabled=True, sandbox=True, adapter="mock"),
        "okx": ExchangeConfig(
            enabled=False,
            sandbox=True,
            adapter="okx",
            okx_demo=True,
            api_key_env="COINBOT_OKX_API_KEY",
            api_secret_env="COINBOT_OKX_API_SECRET",
            passphrase_env="COINBOT_OKX_PASSPHRASE",
        ),
        "binance": ExchangeConfig(
            enabled=False,
            sandbox=True,
            adapter="ccxt",
            api_key_env="COINBOT_BINANCE_API_KEY",
            api_secret_env="COINBOT_BINANCE_API_SECRET",
        ),
        "bybit": ExchangeConfig(
            enabled=False,
            sandbox=True,
            adapter="ccxt",
            api_key_env="COINBOT_BYBIT_API_KEY",
            api_secret_env="COINBOT_BYBIT_API_SECRET",
        ),
    }


def _redact_env(env_name: str | None) -> str | None:
    """Return redacted marker when an environment variable is populated."""
    if not env_name:
        return None
    if os.getenv(env_name):
        return "***redacted***"
    return None
