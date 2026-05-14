"""Account application service."""

from __future__ import annotations

from trading_assistant.exchanges.base import AccountSnapshot
from trading_assistant.exchanges.factory import ExchangeFactory


class AccountService:
    """Fetch balances through exchange adapters."""

    def __init__(self, exchanges: ExchangeFactory) -> None:
        self.exchanges = exchanges

    def get_balance(self, exchange: str) -> AccountSnapshot:
        """Return balances for one exchange."""
        return self.exchanges.get(exchange).get_balances()

