"""Persistent state for OKX demo directional spot positions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class DirectionalStoredPosition:
    """State row for one managed long-only directional spot position."""

    strategy_name: str
    symbol: str
    exchange: str
    state: str
    quantity: Decimal
    entry_price: Decimal
    entry_notional_usdt: Decimal
    stop_loss_pct: Decimal
    take_profit_pct: Decimal
    time_limit_minutes: int
    opened_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    exit_price: Decimal | None = None
    realized_pnl_usdt: Decimal = Decimal("0")
    exit_reason: str | None = None

    @property
    def key(self) -> str:
        """Return the unique strategy/symbol key."""
        return _key(self.strategy_name, self.symbol)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dictionary."""
        return to_jsonable(self)


class DirectionalPositionStore:
    """Read and write managed directional demo position state."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def get(self, strategy_name: str, symbol: str) -> DirectionalStoredPosition | None:
        """Return a stored position for a strategy/symbol pair."""
        row = self._read().get("positions", {}).get(_key(strategy_name, symbol))
        if not isinstance(row, dict):
            return None
        return _position_from_row(row)

    def first_open(self, strategy_name: str) -> DirectionalStoredPosition | None:
        """Return the first open position for a strategy."""
        rows = self._read().get("positions", {})
        if not isinstance(rows, dict):
            return None
        for row in rows.values():
            if not isinstance(row, dict):
                continue
            if row.get("strategy_name") == strategy_name and row.get("state") == "open":
                return _position_from_row(row)
        return None

    def save(self, position: DirectionalStoredPosition) -> None:
        """Upsert a position row."""
        data = self._read()
        rows = data.setdefault("positions", {})
        if not isinstance(rows, dict):
            rows = {}
            data["positions"] = rows
        rows[position.key] = position.to_dict()
        data["version"] = 1
        self._write(data)

    def mark_closed(
        self,
        position: DirectionalStoredPosition,
        *,
        exit_price: Decimal,
        realized_pnl_usdt: Decimal,
        exit_reason: str,
        closed_at: datetime | None = None,
    ) -> DirectionalStoredPosition:
        """Mark an open position closed and persist it."""
        now = closed_at or _utcnow()
        closed = DirectionalStoredPosition(
            strategy_name=position.strategy_name,
            symbol=position.symbol,
            exchange=position.exchange,
            state="closed",
            quantity=position.quantity,
            entry_price=position.entry_price,
            entry_notional_usdt=position.entry_notional_usdt,
            stop_loss_pct=position.stop_loss_pct,
            take_profit_pct=position.take_profit_pct,
            time_limit_minutes=position.time_limit_minutes,
            opened_at=position.opened_at,
            updated_at=now,
            closed_at=now,
            exit_price=exit_price,
            realized_pnl_usdt=realized_pnl_usdt,
            exit_reason=exit_reason,
        )
        self.save(closed)
        return closed

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "positions": {}}
        payload = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        if not isinstance(payload, dict):
            return {"version": 1, "positions": {}}
        payload.setdefault("version", 1)
        payload.setdefault("positions", {})
        return payload

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(to_jsonable(data), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _position_from_row(row: dict[str, Any]) -> DirectionalStoredPosition:
    return DirectionalStoredPosition(
        strategy_name=str(row["strategy_name"]),
        symbol=str(row["symbol"]),
        exchange=str(row.get("exchange", "okx")),
        state=str(row["state"]),
        quantity=Decimal(str(row.get("quantity", "0"))),
        entry_price=Decimal(str(row.get("entry_price", "0"))),
        entry_notional_usdt=Decimal(str(row.get("entry_notional_usdt", "0"))),
        stop_loss_pct=Decimal(str(row.get("stop_loss_pct", "0"))),
        take_profit_pct=Decimal(str(row.get("take_profit_pct", "0"))),
        time_limit_minutes=int(row.get("time_limit_minutes", 0)),
        opened_at=_parse_time(row.get("opened_at")),
        updated_at=_parse_time(row.get("updated_at")),
        closed_at=_parse_optional_time(row.get("closed_at")),
        exit_price=Decimal(str(row["exit_price"])) if row.get("exit_price") is not None else None,
        realized_pnl_usdt=Decimal(str(row.get("realized_pnl_usdt", "0"))),
        exit_reason=str(row["exit_reason"]) if row.get("exit_reason") is not None else None,
    )


def _key(strategy_name: str, symbol: str) -> str:
    return f"{strategy_name}|{symbol}"


def _parse_optional_time(value: Any) -> datetime | None:
    if value is None:
        return None
    return _parse_time(value)


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        return _utcnow()
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)
