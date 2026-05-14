"""数据抓取器抽象基类."""

from abc import ABC, abstractmethod
from datetime import date

from coinbot_common.data.models import OHLCVBar, SymbolInfo


class BaseDataFetcher(ABC):
    """数据抓取器接口，所有数据源适配器均需继承此类."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源名称."""
        ...

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: date,
        end: date | None = None,
    ) -> list[OHLCVBar]:
        """抓取 K 线数据.

        Args:
            symbol: 标的代码（数据源原生格式）
            timeframe: K 线周期（1m/5m/1h/1d 等）
            start: 开始日期
            end: 结束日期（None 表示今天）

        Returns:
            OHLCVBar 列表，按时间升序
        """
        ...

    @abstractmethod
    def search_symbols(self, query: str) -> list[SymbolInfo]:
        """搜索标的.

        Args:
            query: 搜索关键词（代码或名称）

        Returns:
            匹配的 SymbolInfo 列表
        """
        ...

    def _timeframe_to_source(self, timeframe: str) -> str:
        """将通用 timeframe 转换为数据源特定格式（子类可覆盖）."""
        return timeframe
