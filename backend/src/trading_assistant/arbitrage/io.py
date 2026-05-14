"""Input helpers for arbitrage opportunities."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.exceptions import ConfigError


def load_opportunity_file(path: str | Path) -> ArbitrageOpportunity:
    """Load an arbitrage opportunity from a JSON file."""
    file_path = Path(path)
    if not file_path.exists():
        raise ConfigError(f"Opportunity file not found: {file_path}")
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid opportunity JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ConfigError("Opportunity file must contain a JSON object")
    return opportunity_from_dict(payload)


def opportunity_from_dict(payload: dict[str, Any]) -> ArbitrageOpportunity:
    """Create an opportunity from a JSON-like mapping."""
    try:
        created_at = _parse_created_at(payload.get("created_at"))
        kwargs = {
            "opportunity_id": str(payload["opportunity_id"]),
            "strategy_type": str(payload["strategy_type"]),
            "symbol": str(payload["symbol"]),
            "buy_exchange": _optional_str(payload.get("buy_exchange")),
            "sell_exchange": _optional_str(payload.get("sell_exchange")),
            "expected_profit": Decimal(str(payload["expected_profit"])),
            "expected_profit_pct": Decimal(str(payload["expected_profit_pct"])),
            "estimated_fee": Decimal(str(payload["estimated_fee"])),
            "estimated_slippage": Decimal(str(payload["estimated_slippage"])),
            "required_capital": Decimal(str(payload["required_capital"])),
            "net_profit": Decimal(str(payload["net_profit"])),
            "risk_score": Decimal(str(payload["risk_score"])),
            "confidence": Decimal(str(payload["confidence"])),
            "metadata": payload.get("metadata", {}),
        }
    except KeyError as exc:
        raise ConfigError(f"Opportunity file missing required field: {exc.args[0]}") from exc
    except Exception as exc:
        raise ConfigError(f"Invalid opportunity file: {exc}") from exc
    if not isinstance(kwargs["metadata"], dict):
        raise ConfigError("Opportunity metadata must be a JSON object")
    if created_at is not None:
        kwargs["created_at"] = created_at
    return ArbitrageOpportunity(**kwargs)


def _optional_str(value: Any) -> str | None:
    """Return a string value or None."""
    if value is None:
        return None
    return str(value)


def _parse_created_at(value: Any) -> datetime | None:
    """Parse an optional ISO timestamp."""
    if value is None:
        return None
    return datetime.fromisoformat(str(value))
