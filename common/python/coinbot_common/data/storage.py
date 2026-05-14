"""DuckDB 行情数据存储层.

提供 K 线数据的读写、查询、管理功能。
使用单例连接模式保证线程安全（DuckDB 单写者限制）。
"""

from __future__ import annotations

import threading
from datetime import date, datetime
from pathlib import Path

import duckdb
import polars as pl
from loguru import logger

from coinbot_common.data.models import OHLCVBar, SymbolInfo

# DuckDB 建表 DDL
_DDL_MARKET_DATA = """
CREATE TABLE IF NOT EXISTS market_data (
    symbol    VARCHAR     NOT NULL,
    timeframe VARCHAR     NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open      DOUBLE      NOT NULL,
    high      DOUBLE      NOT NULL,
    low       DOUBLE      NOT NULL,
    close     DOUBLE      NOT NULL,
    volume    DOUBLE      NOT NULL,
    turnover  DOUBLE,
    PRIMARY KEY (symbol, timeframe, timestamp)
)
"""

_DDL_SYMBOLS = """
CREATE TABLE IF NOT EXISTS symbols (
    symbol     VARCHAR PRIMARY KEY,
    name       VARCHAR NOT NULL,
    exchange   VARCHAR NOT NULL DEFAULT 'UNKNOWN',
    asset_type VARCHAR NOT NULL,
    currency   VARCHAR NOT NULL DEFAULT 'USD',
    status     VARCHAR NOT NULL DEFAULT 'active'
)
"""


class MarketDataStorage:
    """DuckDB 行情数据存储，线程安全单例."""

    _lock = threading.Lock()

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        """初始化存储，创建表结构.

        Args:
            db_path: DuckDB 文件路径，或 ':memory:' 内存数据库
        """
        self._db_path = str(db_path)
        self._conn: duckdb.DuckDBPyConnection = duckdb.connect(self._db_path)
        self._init_schema()
        logger.debug(f"MarketDataStorage 初始化：{self._db_path}")

    def _init_schema(self) -> None:
        """创建表结构."""
        with self._lock:
            self._conn.execute(_DDL_MARKET_DATA)
            self._conn.execute(_DDL_SYMBOLS)

    # ── 写入操作 ────────────────────────────────────────────────────────────

    def upsert_bars(self, bars: list[OHLCVBar]) -> int:
        """批量插入/更新 K 线数据（已有则跳过）.

        Returns:
            成功写入的条数
        """
        if not bars:
            return 0

        rows = [
            (
                b.symbol,
                b.timeframe,
                b.timestamp,
                b.open,
                b.high,
                b.low,
                b.close,
                b.volume,
                b.turnover,
            )
            for b in bars
        ]

        with self._lock:
            self._conn.executemany(
                """
                INSERT OR IGNORE INTO market_data
                    (symbol, timeframe, timestamp, open, high, low, close, volume, turnover)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

        logger.debug(f"upsert_bars: {len(bars)} 条写入 ({bars[0].symbol} {bars[0].timeframe})")
        return len(bars)

    def upsert_symbols(self, symbols: list[SymbolInfo]) -> int:
        """批量插入/更新标的元信息."""
        if not symbols:
            return 0

        rows = [
            (s.symbol, s.name, s.exchange.value, s.asset_type.value, s.currency, s.status)
            for s in symbols
        ]
        with self._lock:
            self._conn.executemany(
                """
                INSERT OR REPLACE INTO symbols
                    (symbol, name, exchange, asset_type, currency, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(symbols)

    # ── 查询操作 ────────────────────────────────────────────────────────────

    def query_bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> pl.DataFrame:
        """查询 K 线数据，返回 Polars DataFrame.

        结果按 timestamp 升序排列。
        """
        params: list[object] = [symbol, timeframe]
        where_clauses = ["symbol = ?", "timeframe = ?"]

        if start is not None:
            where_clauses.append("timestamp >= ?")
            params.append(start)
        if end is not None:
            where_clauses.append("timestamp <= ?")
            params.append(end)

        where = " AND ".join(where_clauses)
        sql = f"""
            SELECT timestamp, open, high, low, close, volume, turnover
            FROM market_data
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(limit)

        with self._lock:
            result = self._conn.execute(sql, params).pl()

        # 转为升序
        return result.sort("timestamp")

    def query_latest_bar(self, symbol: str, timeframe: str) -> OHLCVBar | None:
        """查询最新一根 K 线."""
        with self._lock:
            row = self._conn.execute(
                """
                SELECT timestamp, open, high, low, close, volume, turnover
                FROM market_data
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC LIMIT 1
                """,
                [symbol, timeframe],
            ).fetchone()

        if row is None:
            return None

        return OHLCVBar(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=row[0],
            open=row[1],
            high=row[2],
            low=row[3],
            close=row[4],
            volume=row[5],
            turnover=row[6],
        )

    def count_bars(self, symbol: str, timeframe: str) -> int:
        """查询指定标的和周期的 K 线数量."""
        with self._lock:
            result = self._conn.execute(
                "SELECT COUNT(*) FROM market_data WHERE symbol = ? AND timeframe = ?",
                [symbol, timeframe],
            ).fetchone()
        return int(result[0]) if result else 0  # type: ignore[index]

    def list_symbols(self) -> list[str]:
        """列出数据库中已有数据的所有标的."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT symbol FROM market_data ORDER BY symbol"
            ).fetchall()
        return [r[0] for r in rows]

    def get_date_range(
        self, symbol: str, timeframe: str
    ) -> tuple[datetime | None, datetime | None]:
        """获取标的数据的时间范围（最早 ~ 最新）."""
        with self._lock:
            row = self._conn.execute(
                """
                SELECT MIN(timestamp), MAX(timestamp)
                FROM market_data
                WHERE symbol = ? AND timeframe = ?
                """,
                [symbol, timeframe],
            ).fetchone()

        if row is None or row[0] is None:  # type: ignore[index]
            return None, None
        return row[0], row[1]  # type: ignore[index]

    def delete_bars(
        self,
        symbol: str,
        timeframe: str,
        start: date | None = None,
        end: date | None = None,
    ) -> int:
        """删除指定范围内的 K 线数据."""
        params: list[object] = [symbol, timeframe]
        clauses = ["symbol = ?", "timeframe = ?"]

        if start:
            clauses.append("timestamp >= ?")
            params.append(datetime(start.year, start.month, start.day))
        if end:
            clauses.append("timestamp <= ?")
            params.append(datetime(end.year, end.month, end.day, 23, 59, 59))

        sql = f"DELETE FROM market_data WHERE {' AND '.join(clauses)}"
        with self._lock:
            self._conn.execute(sql, params)
        return 0

    def close(self) -> None:
        """关闭数据库连接."""
        self._conn.close()
        logger.debug("MarketDataStorage 连接已关闭")
