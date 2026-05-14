"""Report formatting helpers."""

from __future__ import annotations

from typing import Any

from trading_assistant.utils.serialization import to_jsonable


def format_report_text(report: dict[str, Any]) -> str:
    """Format a compact human-readable report."""
    payload = to_jsonable(report)
    lines = [f"Report: {payload['type']}", f"Mode: {payload['sections']['safety']['mode']}"]
    lines.append(f"Dry run: {payload['sections']['safety']['dry_run']}")
    lines.append(f"Opportunities: {payload['sections']['arbitrage']['opportunity_count']}")
    return "\n".join(lines)

