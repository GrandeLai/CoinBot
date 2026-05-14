"""Sandbox validation helpers for exchange adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from trading_assistant.exchanges.base import Exchange
from trading_assistant.utils.serialization import to_jsonable


@dataclass(frozen=True)
class SandboxCheck:
    """One sandbox validation check result."""

    ok: bool
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class SandboxValidationResult:
    """Complete sandbox validation result."""

    exchange: str
    symbol: str
    ok: bool
    live_orders_sent: bool
    checks: dict[str, SandboxCheck]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe result."""
        return to_jsonable(self)


class OKXSandboxValidator:
    """Run non-order OKX sandbox checks."""

    def __init__(self, exchange: Exchange) -> None:
        self.exchange = exchange

    def run(self, symbol: str, include_private: bool = False) -> SandboxValidationResult:
        """Run public checks and optional private account check without placing orders."""
        checks: dict[str, SandboxCheck] = {
            "ping": _capture(lambda: {"available": self.exchange.ping()}),
            "ticker": _capture(lambda: self._ticker_details(symbol)),
            "orderbook": _capture(lambda: self._orderbook_details(symbol)),
            "spot_perp_quote": _capture(lambda: self._spot_perp_details(symbol)),
        }
        if include_private:
            checks["account"] = _capture(self._account_details)
        return SandboxValidationResult(
            exchange=self.exchange.name,
            symbol=symbol,
            ok=all(check.ok for check in checks.values()),
            live_orders_sent=False,
            checks=checks,
        )

    def _ticker_details(self, symbol: str) -> dict[str, Any]:
        ticker = self.exchange.get_ticker(symbol)
        return {"bid": ticker.bid, "ask": ticker.ask, "last": ticker.last, "volume": ticker.volume}

    def _orderbook_details(self, symbol: str) -> dict[str, Any]:
        orderbook = self.exchange.get_orderbook(symbol)
        return {
            "best_bid": orderbook.best_bid.price,
            "best_ask": orderbook.best_ask.price,
            "bid_depth": orderbook.depth_notional("bid"),
            "ask_depth": orderbook.depth_notional("ask"),
        }

    def _spot_perp_details(self, symbol: str) -> dict[str, Any]:
        quote = self.exchange.get_spot_perp_quote(symbol)
        return {
            "spot_bid": quote.spot_bid,
            "spot_ask": quote.spot_ask,
            "perp_bid": quote.perp_bid,
            "perp_ask": quote.perp_ask,
            "funding_rate": quote.funding_rate,
        }

    def _account_details(self) -> dict[str, Any]:
        account = self.exchange.get_balances()
        return {"assets": sorted(account.balances)}


def _capture(callback: Callable[[], dict[str, Any]]) -> SandboxCheck:
    """Capture one validation callback as a structured check."""
    try:
        details = callback()
    except Exception as exc:
        return SandboxCheck(ok=False, error=str(exc))
    available = details.get("available")
    ok = bool(available) if isinstance(available, bool) else True
    return SandboxCheck(ok=ok, details=details)
