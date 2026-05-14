"""Crypto broker type definitions used by the OKX adapter."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class TradingProviderKind(StrEnum):
    """Supported CoinBot trading providers."""

    OKX = "okx"


class TradingOrderSide(StrEnum):
    """Order side."""

    BUY = "buy"
    SELL = "sell"


class TradingOrderType(StrEnum):
    """Order types currently exposed by CoinBot."""

    MARKET = "market"
    LIMIT = "limit"


class TradingOrderStatus(StrEnum):
    """Normalized order state."""

    PENDING_SUBMIT = "pending_submit"
    SUBMITTED = "submitted"
    PARTIAL_FILLED = "partial_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class CryptoBalance(BaseModel):
    """Account balance row."""

    asset: str
    free: float
    locked: float
    total: float


class CryptoOrder(BaseModel):
    """Spot, swap, or option order row normalized from OKX."""

    order_id: str
    symbol: str
    display: str
    side: TradingOrderSide
    order_type: TradingOrderType
    status: TradingOrderStatus
    quantity: float
    executed_quantity: float = 0.0
    submitted_price: float | None = None
    executed_price: float | None = None
    submitted_at: str
    updated_at: str


class CryptoOrderRequest(BaseModel):
    """Spot order request."""

    symbol: str
    side: TradingOrderSide
    order_type: TradingOrderType
    quantity: float = Field(..., gt=0)
    price: float | None = Field(default=None, gt=0)


class CryptoAccountOverview(BaseModel):
    """OKX account overview."""

    provider: TradingProviderKind = TradingProviderKind.OKX
    testnet: bool = True
    balances: list[CryptoBalance] = Field(default_factory=list)
    total_usdt_value: float = 0.0
    updated_at: str


class CryptoPosition(BaseModel):
    """Derivative position row."""

    pos_id: str = ""
    inst_id: str
    inst_type: str
    pos_side: str
    pos: float
    avg_px: float
    mark_px: float
    upl: float
    upl_ratio: float
    lever: str
    liq_px: float | None = None
    margin_mode: str
    currency: str = ""
    updated_at: str = ""


class SwapTicker(BaseModel):
    """Perpetual swap ticker with funding metadata."""

    inst_id: str
    display: str
    last: float
    mark_px: float
    change_pct: float
    funding_rate: float
    next_funding_time: str
    open_interest: float
    volume_usdt: float
    high_24h: float
    low_24h: float


class OptionTicker(BaseModel):
    """Option ticker row with greeks."""

    inst_id: str
    uly: str
    strike_px: float
    opt_type: str
    exp_time: str
    last: float
    bid_px: float
    ask_px: float
    mark_vol: float
    delta: float
    gamma: float
    theta: float
    vega: float
    open_interest: float = 0.0


class SwapOrderRequest(BaseModel):
    """Perpetual swap order request."""

    inst_id: str
    side: TradingOrderSide
    order_type: TradingOrderType
    sz: float = Field(..., gt=0)
    price: float | None = Field(default=None, gt=0)
    pos_side: str = "long"
    margin_mode: str = "cross"
    lever: str = "10"


class TradingProviderError(Exception):
    """Provider-level exception carrying API-friendly metadata."""

    def __init__(self, message: str, *, code: str = "provider_error", status_code: int = 400) -> None:
        """Create a provider error."""
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
