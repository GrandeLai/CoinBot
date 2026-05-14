"""数据抓取器包."""

from coinbot_common.data.fetchers.base import BaseDataFetcher
from coinbot_common.data.fetchers.okx_fetcher import OKXFetcher

__all__ = ["BaseDataFetcher", "OKXFetcher"]
