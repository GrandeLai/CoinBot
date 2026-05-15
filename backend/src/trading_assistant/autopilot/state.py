"""State persistence for detached autopilot runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trading_assistant.autopilot.models import AutopilotState


class AutopilotStateStore:
    """Read and atomically write the latest autopilot state."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read(self) -> AutopilotState:
        """Return persisted state or a NeverRun state when no file exists."""
        if not self.path.exists():
            return AutopilotState(status="NeverRun")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return AutopilotState(**_state_payload(payload))

    def write(self, state: AutopilotState) -> None:
        """Write state with a same-directory temp file followed by replace."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_name(f".{self.path.name}.tmp")
        tmp_path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self.path)


def _state_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop unknown state keys for forward-compatible reads."""
    allowed = set(AutopilotState.__dataclass_fields__)
    return {key: value for key, value in payload.items() if key in allowed}
