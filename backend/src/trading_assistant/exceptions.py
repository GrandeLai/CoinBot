"""Typed exceptions for the trading assistant."""

from __future__ import annotations


class TradingAssistantError(Exception):
    """Base exception with a stable CLI exit code."""

    exit_code = 1


class ConfigError(TradingAssistantError):
    """Raised when configuration loading or validation fails."""

    exit_code = 2


class ExchangeError(TradingAssistantError):
    """Raised when an exchange adapter cannot fulfill a request."""

    exit_code = 3


class RiskError(TradingAssistantError):
    """Raised when risk checks reject an operation."""

    exit_code = 4


class SafetyError(TradingAssistantError):
    """Raised when a trading safety gate blocks an operation."""

    exit_code = 5


class NotFoundError(TradingAssistantError):
    """Raised when a requested resource does not exist."""

    exit_code = 6

