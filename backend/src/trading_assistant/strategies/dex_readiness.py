"""Read-only DEX/CLMM liquidity provision readiness gate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trading_assistant.config.schema import Settings
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class DexLpPrerequisite:
    """One DEX/CLMM prerequisite check."""

    name: str
    required: bool
    configured: bool
    reason: str | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(self)


@dataclass(frozen=True)
class DexLpReadinessReport:
    """Machine-readable readiness report for future DEX/CLMM LP work."""

    status: str
    network: str
    gateway_url: str | None
    wallet_address_env: str
    testnet_ready: bool
    execution_supported: bool
    prerequisites: list[DexLpPrerequisite]
    reasons: list[str]
    read_only: bool = True
    orders_sent: bool = False
    live_orders_sent: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe representation."""
        return to_jsonable(
            {
                "status": self.status,
                "network": self.network,
                "gateway_url": self.gateway_url,
                "wallet_address_env": self.wallet_address_env,
                "testnet_ready": self.testnet_ready,
                "execution_supported": self.execution_supported,
                "prerequisites": [item.to_dict() for item in self.prerequisites],
                "reasons": self.reasons,
                "read_only": self.read_only,
                "orders_sent": self.orders_sent,
                "live_orders_sent": self.live_orders_sent,
            }
        )


class DexLpReadinessService:
    """Evaluate DEX/CLMM LP prerequisites without touching wallets or networks."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def report(self) -> DexLpReadinessReport:
        """Return a no-order DEX/CLMM readiness report."""
        config = self.settings.dex_lp
        prerequisites = [
            DexLpPrerequisite(
                name="dex_lp_enabled",
                required=True,
                configured=config.enabled,
                reason=None if config.enabled else "dex_lp_disabled",
            ),
            DexLpPrerequisite(
                name="dex_gateway",
                required=True,
                configured=config.gateway_enabled and bool(config.gateway_url),
                reason=None if config.gateway_enabled and config.gateway_url else "dex_gateway_missing",
                details={"gateway_enabled": config.gateway_enabled, "gateway_url": config.gateway_url},
            ),
            DexLpPrerequisite(
                name="testnet_network",
                required=True,
                configured=config.network == "testnet",
                reason=None if config.network == "testnet" else "testnet_network_required",
                details={"network": config.network},
            ),
            DexLpPrerequisite(
                name="wallet_policy",
                required=True,
                configured=config.wallet_policy_ack,
                reason=None if config.wallet_policy_ack else "wallet_policy_missing",
                details={"wallet_address_env": config.wallet_address_env},
            ),
            DexLpPrerequisite(
                name="gas_model",
                required=True,
                configured=config.gas_model_enabled,
                reason=None if config.gas_model_enabled else "gas_model_missing",
            ),
            DexLpPrerequisite(
                name="mev_protection",
                required=True,
                configured=config.mev_protection_enabled,
                reason=None if config.mev_protection_enabled else "mev_protection_missing",
            ),
            self._testnet_evidence_prerequisite(),
            DexLpPrerequisite(
                name="execution_adapter",
                required=True,
                configured=False,
                reason="execution_adapter_not_implemented",
            ),
            DexLpPrerequisite(
                name="live_order_support",
                required=True,
                configured=False,
                reason="live_orders_unsupported",
            ),
        ]
        blocking_reasons = _reasons(prerequisites)
        testnet_ready = _configured_before_execution(prerequisites)
        return DexLpReadinessReport(
            status="Testnet Ready" if testnet_ready else "Deferred",
            network=config.network,
            gateway_url=config.gateway_url,
            wallet_address_env=config.wallet_address_env,
            testnet_ready=testnet_ready,
            execution_supported=False,
            prerequisites=prerequisites,
            reasons=blocking_reasons,
        )

    def _testnet_evidence_prerequisite(self) -> DexLpPrerequisite:
        config = self.settings.dex_lp
        if not config.testnet_validation_required:
            return DexLpPrerequisite(
                name="testnet_validation_evidence",
                required=False,
                configured=True,
                details={"path": config.testnet_validation_evidence_path},
            )
        evidence_path = Path(config.testnet_validation_evidence_path)
        configured = evidence_path.exists()
        return DexLpPrerequisite(
            name="testnet_validation_evidence",
            required=True,
            configured=configured,
            reason=None if configured else "testnet_validation_missing",
            details={"path": str(evidence_path)},
        )


def _configured_before_execution(prerequisites: list[DexLpPrerequisite]) -> bool:
    for item in prerequisites:
        if item.name in {"execution_adapter", "live_order_support"}:
            continue
        if item.required and not item.configured:
            return False
    return True


def _reasons(prerequisites: list[DexLpPrerequisite]) -> list[str]:
    return [item.reason for item in prerequisites if item.reason is not None]
