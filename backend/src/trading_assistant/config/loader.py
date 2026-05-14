"""YAML and environment-backed configuration loader."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

import yaml
from dotenv import load_dotenv
from pydantic import ValidationError

from trading_assistant.config.schema import Settings
from trading_assistant.exceptions import ConfigError


EnvParser = Callable[[str], Any]


def _parse_bool(value: str) -> bool:
    """Parse common boolean environment strings."""
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("expected boolean")


ENV_OVERRIDES: dict[str, tuple[tuple[str, ...], EnvParser]] = {
    "COINBOT_APP_NAME": (("app", "name"), str),
    "COINBOT_APP_MODE": (("app", "mode"), str),
    "COINBOT_LOG_LEVEL": (("app", "log_level"), str),
    "COINBOT_TRADING_LIVE_TRADING": (("trading", "live_trading"), _parse_bool),
    "COINBOT_TRADING_DRY_RUN": (("trading", "dry_run"), _parse_bool),
    "COINBOT_REQUIRE_CONFIRM_BEFORE_ORDER": (("trading", "require_confirm_before_order"), _parse_bool),
    "COINBOT_AGENT_TRADING_ENABLED": (("agent_trading", "enabled"), _parse_bool),
    "COINBOT_AGENT_ALLOW_DEMO_ORDERS": (("agent_trading", "allow_demo_orders"), _parse_bool),
    "COINBOT_AGENT_ALLOW_LIVE_ORDERS": (("agent_trading", "allow_live_orders"), _parse_bool),
    "COINBOT_AGENT_MAX_ORDER_VALUE_USDT": (("agent_trading", "max_autonomous_order_value_usdt"), Decimal),
    "COINBOT_AGENT_MAX_ORDERS_PER_DAY": (("agent_trading", "max_autonomous_orders_per_day"), int),
    "COINBOT_AGENT_AUDIT_LOG_PATH": (("agent_trading", "audit_log_path"), str),
    "COINBOT_AGENT_POLICY_ID": (("agent_trading", "policy_id"), str),
    "COINBOT_OKX_DEMO": (("exchanges", "okx", "okx_demo"), _parse_bool),
    "COINBOT_RISK_MAX_ORDER_VALUE_USDT": (("risk", "max_order_value_usdt"), Decimal),
    "COINBOT_RISK_MAX_DAILY_LOSS_USDT": (("risk", "max_daily_loss_usdt"), Decimal),
    "COINBOT_RISK_MAX_POSITION_EXPOSURE_USDT": (("risk", "max_position_exposure_usdt"), Decimal),
    "COINBOT_RISK_MIN_NET_PROFIT_PCT": (("risk", "min_net_profit_pct"), Decimal),
    "COINBOT_RISK_MAX_SLIPPAGE_PCT": (("risk", "max_slippage_pct"), Decimal),
    "COINBOT_RISK_MIN_ORDERBOOK_DEPTH_USDT": (("risk", "min_orderbook_depth_usdt"), Decimal),
    "COINBOT_ARBITRAGE_MIN_NET_PROFIT_PCT": (("arbitrage", "min_net_profit_pct"), Decimal),
    "COINBOT_ARBITRAGE_TRADE_SIZE_USDT": (("arbitrage", "trade_size_usdt"), Decimal),
}


def load_settings(config_path: str | Path | None = None) -> Settings:
    """Load settings from defaults, YAML, `.env`, and `COINBOT_` overrides."""
    root = _repo_root()
    load_dotenv(root / ".env", override=False)
    data = Settings().model_dump(mode="python")
    if config_path is not None:
        config_file = Path(config_path)
        if not config_file.exists():
            raise ConfigError(f"Config file not found: {config_file}")
        raw = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, Mapping):
            raise ConfigError("Config file must contain a YAML mapping at the top level")
        data = _deep_merge(data, dict(raw))
    env_file = data.get("app", {}).get("env_file") if isinstance(data.get("app"), Mapping) else None
    if env_file:
        load_dotenv(_resolve_env_file(root, Path(config_path).parent if config_path else root, str(env_file)), override=True)

    _apply_env_overrides(data)
    try:
        return Settings.model_validate(data)
    except ValidationError as exc:
        message = "; ".join(error["msg"] for error in exc.errors())
        raise ConfigError(message) from exc
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


def _repo_root() -> Path:
    """Resolve repository root from this package file."""
    return Path(__file__).resolve().parents[4]


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge dictionaries without mutating inputs."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(dict(merged[key]), dict(value))
        else:
            merged[key] = value
    return merged


def _resolve_env_file(root: Path, config_dir: Path, env_file: str) -> Path:
    """Resolve a configured dotenv file path."""
    candidate = Path(env_file)
    if candidate.is_absolute():
        return candidate
    config_relative = config_dir / candidate
    if config_relative.exists():
        return config_relative
    return root / candidate


def _apply_env_overrides(data: dict[str, Any]) -> None:
    """Apply known `COINBOT_` environment overrides to raw settings data."""
    import os

    for env_name, (path, parser) in ENV_OVERRIDES.items():
        raw_value = os.getenv(env_name)
        if raw_value is None or raw_value == "":
            continue
        cursor: dict[str, Any] = data
        for part in path[:-1]:
            cursor = cursor.setdefault(part, {})
        try:
            cursor[path[-1]] = parser(raw_value)
        except Exception as exc:  # pragma: no cover - defensive parser wrapper
            raise ConfigError(f"Invalid value for {env_name}: {raw_value}") from exc
