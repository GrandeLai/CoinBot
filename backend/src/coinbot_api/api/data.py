"""Crypto market data API backed by OKX and DuckDB."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from loguru import logger

from coinbot_common.data.fetchers.okx_fetcher import OKXFetcher, normalize_symbol
from coinbot_common.data.models import DataFetchRequest, OHLCVBar, OHLCVResponse
from coinbot_common.data.storage import MarketDataStorage
from coinbot_common.data.universe import ProductId, find_supported_instrument, list_supported_instruments

router = APIRouter(prefix="/data", tags=["data"])

_storage: MarketDataStorage | None = None


def get_storage() -> MarketDataStorage:
    """Return the process-local DuckDB storage instance."""
    global _storage
    if _storage is None:
        from coinbot_common.config import get_settings

        settings = get_settings()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        _storage = MarketDataStorage(settings.duckdb_path)
    return _storage


StorageDep = Annotated[MarketDataStorage, Depends(get_storage)]


def _parse_date(value: str, field_name: str) -> datetime:
    """Parse an ISO date used by data query endpoints."""
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} 日期格式错误: {value}") from exc


@router.get("/bars", response_model=OHLCVResponse)
def get_bars(
    storage: StorageDep,
    symbol: str = Query(..., description="OKX symbol, e.g. BTC-USDT"),
    timeframe: str = Query(default="1d", description="K line timeframe"),
    limit: int = Query(default=500, ge=1, le=5000, description="返回条数"),
    start: str | None = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end: str | None = Query(default=None, description="结束日期 YYYY-MM-DD"),
) -> OHLCVResponse:
    """Query locally stored OHLCV bars."""
    normalized = normalize_symbol(symbol)
    start_dt = _parse_date(start, "start") if start else None
    end_dt = _parse_date(end, "end") if end else None

    df = storage.query_bars(
        symbol=normalized,
        timeframe=timeframe,
        start=start_dt,
        end=end_dt,
        limit=limit,
    )

    bars = [
        OHLCVBar(
            symbol=normalized,
            timeframe=timeframe,
            timestamp=row["timestamp"],
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
            turnover=row.get("turnover"),
        )
        for row in df.iter_rows(named=True)
    ]
    return OHLCVResponse(symbol=normalized, timeframe=timeframe, count=len(bars), bars=bars)


@router.post("/fetch")
def fetch_data(
    req: DataFetchRequest,
    background_tasks: BackgroundTasks,
    storage: StorageDep,
) -> dict[str, str]:
    """Fetch OKX OHLCV bars in the background and upsert them into DuckDB."""

    def _do_fetch() -> None:
        try:
            symbol = normalize_symbol(req.symbol)
            start_date = datetime.strptime(req.start, "%Y-%m-%d").date()
            end_date = datetime.strptime(req.end, "%Y-%m-%d").date() if req.end else Date.today()
            bars = OKXFetcher().fetch_ohlcv(symbol, req.timeframe, start_date, end_date)
            if bars:
                written = storage.upsert_bars(bars)
                logger.info("[data/fetch] {} wrote {} bars", symbol, written)
        except Exception as exc:  # pragma: no cover - background task logs only
            logger.exception("[data/fetch] background fetch failed: {}", exc)

    background_tasks.add_task(_do_fetch)
    return {
        "status": "accepted",
        "message": f"OKX data fetch queued: {normalize_symbol(req.symbol)} {req.timeframe}",
    }


@router.get("/symbols")
def list_symbols(storage: StorageDep) -> dict[str, list[str]]:
    """List symbols that already have local data."""
    return {"symbols": storage.list_symbols()}


@router.get("/universe")
def get_market_universe(
    product: ProductId | None = Query(default=None, description="按产品过滤：coinbot"),
) -> dict[str, Any]:
    """Return CoinBot's crypto-only instrument universe."""
    instruments = list_supported_instruments(product)
    return {
        "count": len(instruments),
        "product": product,
        "instruments": [instrument.model_dump(mode="json") for instrument in instruments],
    }


@router.get("/range")
def get_range(
    storage: StorageDep,
    symbol: str = Query(...),
    timeframe: str = Query(default="1d"),
) -> dict[str, str | None]:
    """Return local data coverage for one symbol/timeframe."""
    normalized = normalize_symbol(symbol)
    earliest, latest = storage.get_date_range(normalized, timeframe)
    return {
        "symbol": normalized,
        "timeframe": timeframe,
        "earliest": earliest.isoformat() if earliest else None,
        "latest": latest.isoformat() if latest else None,
        "count": str(storage.count_bars(normalized, timeframe)),
    }


@router.get("/resolve/{symbol}")
def resolve_symbol(symbol: str) -> dict[str, Any]:
    """Resolve a canonical crypto symbol or alias from the supported universe."""
    instrument = find_supported_instrument(symbol)
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"unsupported crypto symbol: {symbol}")
    return instrument.model_dump(mode="json")
