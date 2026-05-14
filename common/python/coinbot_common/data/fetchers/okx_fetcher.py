"""OKX 公开 REST API 数据抓取器 — K 线 OHLCV.

无需 API Key，使用 OKX 公开行情接口。
符号格式统一为 OKX 格式：BTC-USDT（支持 BTCUSDT / BTC/USDT / btc-usdt 等输入）。
OKX K 线返回降序（最新在前），本模块自动翻转为升序后写入存储。
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

import httpx
from loguru import logger

from coinbot_common.data.fetchers.base import BaseDataFetcher
from coinbot_common.data.models import AssetType, Exchange, OHLCVBar, SymbolInfo

OKX_REST_URL = "https://www.okx.com"

POPULAR_PAIRS: list[tuple[str, str]] = [
    ("BTC-USDT",  "Bitcoin / USDT"),
    ("ETH-USDT",  "Ethereum / USDT"),
    ("OKB-USDT",  "OKB / USDT"),
    ("SOL-USDT",  "Solana / USDT"),
    ("XRP-USDT",  "XRP / USDT"),
    ("DOGE-USDT", "Dogecoin / USDT"),
    ("ADA-USDT",  "Cardano / USDT"),
    ("AVAX-USDT", "Avalanche / USDT"),
    ("DOT-USDT",  "Polkadot / USDT"),
    ("MATIC-USDT","Polygon / USDT"),
    ("LINK-USDT", "Chainlink / USDT"),
    ("LTC-USDT",  "Litecoin / USDT"),
    ("UNI-USDT",  "Uniswap / USDT"),
    ("ATOM-USDT", "Cosmos / USDT"),
]

# OKX bar 周期映射（OKX 使用大写 H/D/W/M）
TIMEFRAME_MAP: dict[str, str] = {
    "1m":  "1m",
    "5m":  "5m",
    "15m": "15m",
    "30m": "30m",
    "1h":  "1H",
    "4h":  "4H",
    "1d":  "1D",
    "1w":  "1W",
}

_QUOTE_ASSETS = ("USDT", "BUSD", "USDC", "BTC", "ETH", "OKB")

POPULAR_SWAPS: list[str] = [
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "SOL-USDT-SWAP",
    "XRP-USDT-SWAP",
    "BNB-USDT-SWAP",
    "DOGE-USDT-SWAP",
    "ADA-USDT-SWAP",
    "LINK-USDT-SWAP",
    "AVAX-USDT-SWAP",
    "DOT-USDT-SWAP",
]

OPTIONS_UNDERLYINGS: list[str] = ["BTC-USD", "ETH-USD", "SOL-USD"]


def display_swap_symbol(inst_id: str) -> str:
    """BTC-USDT-SWAP → BTC/USDT 永续."""
    parts = inst_id.split("-")
    if len(parts) >= 3 and parts[-1] == "SWAP":
        return f"{parts[0]}/{parts[1]} 永续"
    if len(parts) >= 3 and parts[-1] == "FUTURES":
        return f"{parts[0]}/{parts[1]} 交割"
    return inst_id


def normalize_symbol(symbol: str) -> str:
    """将任意格式的加密货币交易对规范化为 OKX 格式（BTC-USDT）.

    Examples::

        normalize_symbol("BTCUSDT")  -> "BTC-USDT"
        normalize_symbol("BTC/USDT") -> "BTC-USDT"
        normalize_symbol("btc-usdt") -> "BTC-USDT"
    """
    s = symbol.upper().strip()
    # 已有分隔符（/或-）：直接统一为 -
    if "/" in s or "-" in s:
        return re.sub(r"[^A-Z0-9]+", "-", s).strip("-")
    # 无分隔符：从末尾匹配 quote 资产并插入 -
    for quote in _QUOTE_ASSETS:
        if s.endswith(quote) and len(s) > len(quote):
            base = s[: -len(quote)]
            return f"{base}-{quote}"
    return s  # 无法识别时原样返回


def display_symbol(okx_symbol: str) -> str:
    """BTC-USDT → BTC/USDT（前端展示用）."""
    return okx_symbol.replace("-", "/")


class OKXFetcher(BaseDataFetcher):
    """从 OKX 公开接口拉取加密货币 OHLCV 数据."""

    @property
    def source_name(self) -> str:
        return "okx"

    def _timeframe_to_source(self, timeframe: str) -> str:
        return TIMEFRAME_MAP.get(timeframe, "1D")

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: date,
        end: date | None = None,
    ) -> list[OHLCVBar]:
        """拉取 OKX K 线数据，支持分页（每次最多 300 条）."""
        inst_id = normalize_symbol(symbol)
        bar = self._timeframe_to_source(timeframe)

        end_dt = end or date.today()
        # OKX after/before 均为毫秒时间戳
        # after = 早于该时间戳（分页向历史拉取）
        # before = 晚于该时间戳（分页向未来拉取）
        end_ms = int(
            datetime(end_dt.year, end_dt.month, end_dt.day, 23, 59, 59,
                     tzinfo=timezone.utc).timestamp() * 1000
        )
        start_ms = int(
            datetime(start.year, start.month, start.day,
                     tzinfo=timezone.utc).timestamp() * 1000
        )

        all_rows: list[list] = []
        # 以 after=end_ms 开始分页，向历史方向翻
        after_cursor: int | None = end_ms + 1  # +1 确保包含 end 当天

        while True:
            params: dict[str, str | int] = {
                "instId": inst_id,
                "bar": bar,
                "limit": 300,
            }
            if after_cursor is not None:
                params["after"] = after_cursor

            try:
                resp = httpx.get(
                    f"{OKX_REST_URL}/api/v5/market/candles",
                    params=params,
                    timeout=15.0,
                )
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error(f"[OKXFetcher] HTTP error for {inst_id}: {exc}")
                break

            payload = resp.json()
            if payload.get("code") != "0":
                logger.error(f"[OKXFetcher] API error: {payload.get('msg')}")
                break

            rows = payload.get("data", [])
            if not rows:
                break

            all_rows.extend(rows)

            # 最旧一条的时间戳
            oldest_ts = int(rows[-1][0])
            if oldest_ts <= start_ms:
                break  # 已覆盖所需范围
            after_cursor = oldest_ts  # 继续向更早翻页

        # OKX 返回降序，翻转为升序
        all_rows.reverse()

        bars: list[OHLCVBar] = []
        for row in all_rows:
            ts_ms = int(row[0])
            if ts_ms < start_ms:
                continue  # 过滤超出范围的数据
            ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            close = float(row[4])
            vol = float(row[5])
            bars.append(OHLCVBar(
                symbol=inst_id,
                timeframe=timeframe,
                timestamp=ts,
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=close,
                volume=vol,
                turnover=float(row[7]) if row[7] else close * vol,
            ))

        logger.info(f"[OKXFetcher] {len(bars)} bars for {inst_id}/{timeframe}")
        return bars

    def search_symbols(self, query: str) -> list[SymbolInfo]:
        """在热门交易对列表中模糊搜索."""
        q = query.upper().replace("/", "-").replace(" ", "")
        matched = [
            SymbolInfo(
                symbol=sym, name=name, exchange=Exchange.OKX,
                asset_type=AssetType.CRYPTO, currency="USDT",
            )
            for sym, name in POPULAR_PAIRS
            if q in sym or q in name.upper()
        ]
        return matched or [
            SymbolInfo(
                symbol=sym, name=name, exchange=Exchange.OKX,
                asset_type=AssetType.CRYPTO, currency="USDT",
            )
            for sym, name in POPULAR_PAIRS[:8]
        ]
