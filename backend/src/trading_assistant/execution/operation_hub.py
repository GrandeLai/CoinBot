"""Operation validation hub for demo/live trading parity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class OperationContract:
    """Contract proving a live operation has a demo validation path."""

    operation_id: str
    exchange: str
    description: str
    demo_supported: bool
    live_supported: bool
    demo_config: str
    live_config: str
    demo_command: str
    live_command: str


class OperationValidationHub:
    """Central registry for demo/live operation validation parity."""

    def __init__(self, operations: list[OperationContract]) -> None:
        self.operations = operations

    def assert_all_live_operations_have_demo_validation(self) -> list[str]:
        """Return live operations that do not have a demo validation path."""
        return [
            operation.operation_id
            for operation in self.operations
            if operation.live_supported and (not operation.demo_supported or not operation.demo_command or not operation.demo_config)
        ]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe operation catalog."""
        return {"operations": to_jsonable(self.operations)}


def default_operation_contracts() -> list[OperationContract]:
    """Return the OKX operation catalog used by the CLI and tests."""
    return [
        OperationContract(
            operation_id="okx.sandbox_check",
            exchange="okx",
            description="Validate OKX public market and optional private account read paths without orders.",
            demo_supported=True,
            live_supported=True,
            demo_config="configs/okx.demo.example.yaml",
            live_config="configs/okx.live.example.yaml",
            demo_command="crypto-assistant exchange sandbox-check --config configs/okx.demo.example.yaml --exchange okx --symbol BTC/USDT --json",
            live_command="crypto-assistant exchange sandbox-check --config configs/okx.live.example.yaml --exchange okx --symbol BTC/USDT --json",
        ),
        OperationContract(
            operation_id="okx.agent_spot_limit_order",
            exchange="okx",
            description="Submit guarded OKX spot limit-order legs from an approved opportunity JSON file.",
            demo_supported=True,
            live_supported=True,
            demo_config="configs/okx.demo.example.yaml",
            live_config="configs/okx.live.example.yaml",
            demo_command="crypto-assistant agent execute-live --config configs/okx.demo.example.yaml --opportunity-file okx-opportunity.json --json",
            live_command="crypto-assistant agent execute-live --config configs/okx.live.example.yaml --opportunity-file okx-opportunity.json --json",
        ),
    ]
