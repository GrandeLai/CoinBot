"""Unit tests for operation validation hub."""

from __future__ import annotations

from trading_assistant.execution.operation_hub import OperationValidationHub, default_operation_contracts


def test_all_live_operations_have_demo_validation_contracts() -> None:
    hub = OperationValidationHub(default_operation_contracts())

    assert hub.assert_all_live_operations_have_demo_validation() == []
    payload = hub.to_dict()
    live_ops = [item for item in payload["operations"] if item["live_supported"]]
    operation_ids = {item["operation_id"] for item in payload["operations"]}
    assert live_ops
    assert "okx.hedged_maker_demo_order_manager" in operation_ids
    assert all(item["demo_supported"] for item in live_ops)
    assert all(item["demo_config"] == "configs/okx.demo.example.yaml" for item in live_ops)
    assert all(item["live_config"] == "configs/okx.live.example.yaml" for item in live_ops)
