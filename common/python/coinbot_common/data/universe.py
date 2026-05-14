"""Crypto-only market universe shared by CoinBot API and frontend."""

from typing import Literal

from pydantic import BaseModel, Field

from coinbot_common.data.models import AssetType, Exchange

ProductId = Literal["coinbot"]
DataSource = Literal["auto", "okx"]


class SupportedInstrument(BaseModel):
    """Instrument metadata shared by CoinBot surfaces."""

    symbol: str = Field(..., description="Canonical symbol used by CoinBot APIs.")
    name: str = Field(..., description="Human-readable instrument name.")
    exchange: Exchange = Field(..., description="Primary listing or trading venue.")
    asset_type: AssetType = Field(..., description="Instrument asset type.")
    currency: str = Field(..., description="Quote currency.")
    default_source: DataSource = Field(..., description="Preferred data source.")
    products: list[ProductId] = Field(..., description="Products that should show this instrument.")
    aliases: list[str] = Field(default_factory=list, description="Common user input aliases.")
    description: str = Field(default="", description="Short product-facing explanation.")


_COINBOT_PRODUCTS: list[ProductId] = ["coinbot"]

DEFAULT_MARKET_UNIVERSE: tuple[SupportedInstrument, ...] = (
    SupportedInstrument(
        symbol="BTC-USDT",
        name="Bitcoin / USDT Spot",
        exchange=Exchange.OKX,
        asset_type=AssetType.CRYPTO,
        currency="USDT",
        default_source="okx",
        products=_COINBOT_PRODUCTS,
        aliases=["BTCUSDT", "BTC/USDT", "BTC-USD"],
        description="Crypto spot market pair.",
    ),
    SupportedInstrument(
        symbol="ETH-USDT",
        name="Ethereum / USDT Spot",
        exchange=Exchange.OKX,
        asset_type=AssetType.CRYPTO,
        currency="USDT",
        default_source="okx",
        products=_COINBOT_PRODUCTS,
        aliases=["ETHUSDT", "ETH/USDT", "ETH-USD"],
        description="Crypto spot market pair.",
    ),
    SupportedInstrument(
        symbol="SOL-USDT",
        name="Solana / USDT Spot",
        exchange=Exchange.OKX,
        asset_type=AssetType.CRYPTO,
        currency="USDT",
        default_source="okx",
        products=_COINBOT_PRODUCTS,
        aliases=["SOLUSDT", "SOL/USDT"],
        description="Crypto spot market pair.",
    ),
    SupportedInstrument(
        symbol="XRP-USDT",
        name="XRP / USDT Spot",
        exchange=Exchange.OKX,
        asset_type=AssetType.CRYPTO,
        currency="USDT",
        default_source="okx",
        products=_COINBOT_PRODUCTS,
        aliases=["XRPUSDT", "XRP/USDT"],
        description="Crypto spot market pair.",
    ),
    SupportedInstrument(
        symbol="DOGE-USDT",
        name="Dogecoin / USDT Spot",
        exchange=Exchange.OKX,
        asset_type=AssetType.CRYPTO,
        currency="USDT",
        default_source="okx",
        products=_COINBOT_PRODUCTS,
        aliases=["DOGEUSDT", "DOGE/USDT"],
        description="Crypto spot market pair.",
    ),
    SupportedInstrument(
        symbol="ADA-USDT",
        name="Cardano / USDT Spot",
        exchange=Exchange.OKX,
        asset_type=AssetType.CRYPTO,
        currency="USDT",
        default_source="okx",
        products=_COINBOT_PRODUCTS,
        aliases=["ADAUSDT", "ADA/USDT"],
        description="Crypto spot market pair.",
    ),
)


def list_supported_instruments(product: ProductId | None = None) -> list[SupportedInstrument]:
    """Return supported instruments, optionally filtered by product."""
    if product is None:
        return list(DEFAULT_MARKET_UNIVERSE)
    return [
        instrument
        for instrument in DEFAULT_MARKET_UNIVERSE
        if product in instrument.products
    ]


def find_supported_instrument(symbol: str) -> SupportedInstrument | None:
    """Find an instrument by canonical symbol or alias."""
    normalized = symbol.strip().upper()
    for instrument in DEFAULT_MARKET_UNIVERSE:
        candidates = {instrument.symbol.upper(), *(alias.upper() for alias in instrument.aliases)}
        if normalized in candidates:
            return instrument
    return None
