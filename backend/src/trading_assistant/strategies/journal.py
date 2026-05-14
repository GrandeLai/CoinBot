"""Append-only strategy runtime journal."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trading_assistant.utils.serialization import to_jsonable


class StrategyJournal:
    """Write and read strategy events as JSONL."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def append(self, event: dict[str, Any]) -> None:
        """Append one event to the strategy journal."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = to_jsonable(event)
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(rendered + "\n")

    def read_events(self) -> list[dict[str, Any]]:
        """Read all valid journal events."""
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                events.append(payload)
        return events
