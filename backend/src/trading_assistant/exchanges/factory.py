"""Exchange factory for configured adapters."""

from __future__ import annotations

from trading_assistant.config.schema import Settings
from trading_assistant.exchanges.base import Exchange
from trading_assistant.exchanges.ccxt import CCXTExchange
from trading_assistant.exchanges.mock import MockExchange
from trading_assistant.exchanges.okx import OKXExchange
from trading_assistant.exceptions import ExchangeError


class ExchangeFactory:
    """Create exchange adapters from configuration."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def list_enabled(self) -> list[str]:
        """Return enabled exchange names."""
        return [name for name, config in self.settings.exchanges.items() if config.enabled]

    def get(self, name: str) -> Exchange:
        """Return an exchange adapter by name."""
        try:
            config = self.settings.exchanges[name]
        except KeyError as exc:
            raise ExchangeError(f"Unknown exchange: {name}") from exc
        if not config.enabled:
            raise ExchangeError(f"Exchange is disabled: {name}")
        if config.adapter == "mock":
            return MockExchange(name=name)
        if config.adapter == "okx":
            return OKXExchange(name=name)
        if config.adapter == "ccxt":
            return CCXTExchange(name=name, exchange_id=name, sandbox=config.sandbox)
        raise ExchangeError(f"Unsupported exchange adapter '{config.adapter}' for {name}")
