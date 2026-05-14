"""Controlled autonomous live-trading gates for agents."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_assistant.arbitrage.opportunity import ArbitrageOpportunity
from trading_assistant.config.schema import ExchangeConfig, Settings
from trading_assistant.risk.manager import RiskDecision
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class AgentLiveReadiness:
    """Readiness result for autonomous live-trading controls."""

    ready: bool
    reasons: list[str]
    checks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe readiness payload."""
        return to_jsonable(self)


class AgentLiveTradingGate:
    """Evaluate whether an agent may progress toward autonomous live orders."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate(
        self,
        opportunity: ArbitrageOpportunity | None,
        risk_decision: RiskDecision | None,
    ) -> AgentLiveReadiness:
        """Return readiness after checking every autonomous live-trading gate."""
        config = self.settings.agent_trading
        reasons: list[str] = []

        if not config.enabled:
            reasons.append("agent_trading_disabled")
        if self.settings.trading.dry_run:
            reasons.append("dry_run_enabled")
        if self.settings.trading.require_confirm_before_order:
            reasons.append("manual_confirmation_required")
        if _env_truthy(os.getenv(config.kill_switch_env)):
            reasons.append("agent_live_kill_switch_enabled")

        if opportunity is None:
            reasons.append("opportunity_missing")
            involved: set[str] = set()
            strategy_allowed = False
            order_value_allowed = False
            execution_quality_approved = False
        else:
            involved = {name for name in (opportunity.buy_exchange, opportunity.sell_exchange) if name}
            strategy_allowed = opportunity.strategy_type in config.strategy_allowlist
            order_value_allowed = opportunity.required_capital <= config.max_autonomous_order_value_usdt
            execution_quality_approved = _execution_quality_approved(opportunity)
            if not strategy_allowed:
                reasons.append("strategy_not_allowlisted")
            if not order_value_allowed:
                reasons.append("agent_max_order_value_usdt")
            if not execution_quality_approved:
                reasons.append("execution_quality_not_approved")

        if config.max_autonomous_orders_per_day <= 0:
            reasons.append("agent_daily_order_limit_zero")
        if config.require_audit_log and not config.audit_log_path.strip():
            reasons.append("audit_log_missing")

        operator_id_present = bool(os.getenv(config.operator_id_env))
        if not operator_id_present:
            reasons.append("operator_id_missing")

        if not involved:
            reasons.append("exchange_missing")

        exchange_checks: dict[str, dict[str, Any]] = {}
        credentials_by_exchange: dict[str, bool] = {}
        for name in sorted(involved):
            exchange_config = self.settings.exchanges.get(name)
            checks = _exchange_checks(name, exchange_config, config.allowed_exchanges)
            exchange_checks[name] = checks
            credentials_by_exchange[name] = bool(checks["credentials_from_environment"])
            if checks["mock_exchange"]:
                reasons.append("mock_exchange_involved")
            if not checks["configured"]:
                reasons.append("exchange_config_missing")
            if not checks["enabled"]:
                reasons.append("exchange_disabled")
            if not checks["allowed"]:
                reasons.append("exchange_not_allowed")
            if not checks["non_mock_adapter"]:
                reasons.append("non_mock_exchange_missing")
            if not checks["credentials_from_environment"]:
                reasons.append("credentials_missing")

        demo_operation = bool(involved) and all(
            bool(exchange_checks.get(name, {}).get("sandbox")) and bool(exchange_checks.get(name, {}).get("okx_demo"))
            for name in involved
        )
        operation_mode = "demo" if demo_operation else "live"
        if demo_operation:
            if not config.allow_demo_orders:
                reasons.append("agent_demo_orders_disabled")
            if self.settings.trading.live_trading:
                reasons.append("demo_requires_live_trading_disabled")
        else:
            if not config.allow_live_orders:
                reasons.append("agent_live_orders_disabled")
            if not self.settings.trading.live_trading:
                reasons.append("live_trading_disabled")

        risk_approved = bool(risk_decision and risk_decision.approved)
        if not risk_approved:
            reasons.append("risk_not_approved")

        unique_reasons = list(dict.fromkeys(reasons))
        return AgentLiveReadiness(
            ready=not unique_reasons,
            reasons=unique_reasons,
            checks={
                "agent_trading_enabled": config.enabled,
                "agent_demo_orders_allowed": config.allow_demo_orders,
                "agent_live_orders_allowed": config.allow_live_orders,
                "operation_mode": operation_mode,
                "live_trading": self.settings.trading.live_trading,
                "dry_run": self.settings.trading.dry_run,
                "manual_confirmation_required": self.settings.trading.require_confirm_before_order,
                "kill_switch_env": config.kill_switch_env,
                "kill_switch_enabled": _env_truthy(os.getenv(config.kill_switch_env)),
                "strategy_allowed": strategy_allowed,
                "strategy_allowlist": config.strategy_allowlist,
                "allowed_exchanges": config.allowed_exchanges,
                "involved_exchanges": sorted(involved),
                "exchange_checks": exchange_checks,
                "credentials_from_environment": credentials_by_exchange,
                "risk_approved": risk_approved,
                "order_value_allowed": order_value_allowed,
                "max_autonomous_order_value_usdt": config.max_autonomous_order_value_usdt,
                "max_autonomous_orders_per_day": config.max_autonomous_orders_per_day,
                "execution_quality_approved": execution_quality_approved,
                "audit_log_configured": bool(config.audit_log_path.strip()),
                "operator_id_env": config.operator_id_env,
                "operator_id_present": operator_id_present,
                "policy_id": config.policy_id,
            },
        )

    def append_audit_event(self, event: dict[str, Any]) -> None:
        """Append one redacted JSONL audit event for agent live-trading decisions."""
        audit_path = Path(self.settings.agent_trading.audit_log_path)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        safe_event = to_jsonable(event)
        if not isinstance(safe_event, dict):
            safe_event = {"event": safe_event}
        payload = {
            "created_at": datetime.now(UTC).isoformat(),
            "policy_id": self.settings.agent_trading.policy_id,
            **safe_event,
        }
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(_redact_known_secret_values(rendered, self.settings) + "\n")


def _exchange_checks(name: str, config: ExchangeConfig | None, allowed_exchanges: list[str]) -> dict[str, Any]:
    """Return per-exchange safety checks."""
    configured = config is not None
    adapter = config.adapter if config else None
    enabled = bool(config and config.enabled)
    mock_exchange = name.startswith("mock") or adapter == "mock"
    credentials_from_environment = _credentials_ready(config)
    return {
        "configured": configured,
        "enabled": enabled,
        "adapter": adapter,
        "sandbox": bool(config and config.sandbox),
        "okx_demo": config.okx_demo if config else None,
        "allowed": name in allowed_exchanges,
        "mock_exchange": mock_exchange,
        "non_mock_adapter": bool(config and config.adapter != "mock"),
        "credentials_from_environment": credentials_from_environment,
    }


def _credentials_ready(config: ExchangeConfig | None) -> bool:
    """Return whether all configured credential env vars are populated."""
    if config is None:
        return False
    required = [config.api_key_env, config.api_secret_env]
    if config.passphrase_env:
        required.append(config.passphrase_env)
    return all(bool(env_name and os.getenv(env_name)) for env_name in required)


def _execution_quality_approved(opportunity: ArbitrageOpportunity) -> bool:
    """Return whether execution-quality metadata clears live-agent gating."""
    quality = opportunity.metadata.get("execution_quality")
    if not isinstance(quality, dict):
        return False
    spread = quality.get("spread_persistence", {})
    depth_fill = quality.get("depth_fill", {})
    buy_fill = depth_fill.get("buy", {}) if isinstance(depth_fill, dict) else {}
    sell_fill = depth_fill.get("sell", {}) if isinstance(depth_fill, dict) else {}
    return bool(spread.get("passed") and buy_fill.get("complete") and sell_fill.get("complete"))


def _env_truthy(value: str | None) -> bool:
    """Return whether an environment value should be treated as enabled."""
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _redact_known_secret_values(rendered: str, settings: Settings) -> str:
    """Redact raw configured secret env values from audit JSON."""
    redacted = rendered
    for exchange in settings.exchanges.values():
        for env_name in (exchange.api_key_env, exchange.api_secret_env, exchange.passphrase_env):
            if not env_name:
                continue
            raw = os.getenv(env_name)
            if raw:
                redacted = redacted.replace(raw, "***redacted***")
    return redacted
