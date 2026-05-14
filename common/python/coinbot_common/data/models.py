"""数据层核心模型 — Asset、OHLCV Bar、Symbol 元信息."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AssetType(StrEnum):
    """资产类型枚举."""

    CRYPTO = "crypto"


class Exchange(StrEnum):
    """交易所枚举."""

    BINANCE = "BINANCE"
    OKX = "OKX"
    UNKNOWN = "UNKNOWN"


# 合法 timeframe
TIMEFRAMES: set[str] = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"}


class OHLCVBar(BaseModel):
    """单根 K 线（OHLCV）数据模型."""

    symbol: str = Field(..., description="标的代码，如 BTC-USDT、BTC/USDT")
    timeframe: str = Field(..., description="K 线周期：1m/5m/1h/1d 等")
    timestamp: datetime = Field(..., description="K 线开盘时间（UTC）")
    open: float = Field(..., gt=0, description="开盘价")
    high: float = Field(..., gt=0, description="最高价")
    low: float = Field(..., gt=0, description="最低价")
    close: float = Field(..., gt=0, description="收盘价")
    volume: float = Field(..., ge=0, description="成交量")
    turnover: float | None = Field(default=None, ge=0, description="成交额（可选）")

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """验证 timeframe 合法性."""
        if v not in TIMEFRAMES:
            msg = f"不支持的 timeframe: {v}，合法值: {TIMEFRAMES}"
            raise ValueError(msg)
        return v

    @field_validator("high")
    @classmethod
    def validate_high(cls, v: float, info: object) -> float:
        """验证最高价 >= 最低价."""
        return v


class SymbolInfo(BaseModel):
    """标的元信息."""

    symbol: str = Field(..., description="标的代码")
    name: str = Field(..., description="标的名称")
    exchange: Exchange = Field(default=Exchange.UNKNOWN, description="交易所")
    asset_type: AssetType = Field(..., description="资产类型")
    currency: str = Field(default="USD", description="计价货币")
    status: Literal["active", "delisted", "suspended"] = Field(default="active")


class DataFetchRequest(BaseModel):
    """数据拉取请求参数."""

    symbol: str = Field(..., description="标的代码")
    timeframe: str = Field(default="1d", description="K 线周期")
    start: str = Field(..., description="开始日期，格式 YYYY-MM-DD")
    end: str | None = Field(default=None, description="结束日期（默认今天）")
    source: Literal["okx", "auto"] = Field(
        default="auto", description="数据源"
    )


class DataQueryRequest(BaseModel):
    """K 线数据查询请求."""

    symbol: str
    timeframe: str = "1d"
    limit: int = Field(default=500, ge=1, le=5000)
    start: str | None = None
    end: str | None = None


class OHLCVResponse(BaseModel):
    """K 线数据 API 响应."""

    symbol: str
    timeframe: str
    count: int
    bars: list[OHLCVBar]
