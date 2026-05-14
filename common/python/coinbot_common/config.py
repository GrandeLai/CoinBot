"""CoinBot 配置管理模块."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置，从环境变量或 .env 文件读取."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="COINBOT_",
        case_sensitive=False,
    )

    # 应用基础配置
    app_name: str = "CoinBot"
    app_version: str = "0.1.0"
    debug: bool = False

    # 数据库配置
    duckdb_path: Path = Path("data/coinbot.duckdb")
    sqlite_path: Path = Path("data/coinbot.sqlite")

    # API 服务配置
    host: str = "127.0.0.1"
    port: int = 8000

    # 交易 provider 配置
    trading_provider: str = "okx"
    trading_risk_enabled: bool = True
    trading_risk_max_position_count: int = 10
    trading_risk_max_single_position_pct: float = 0.30
    trading_risk_daily_loss_limit_pct: float = 0.05
    trading_risk_max_order_value: float = 0.0

    # 数据目录
    data_dir: Path = Path("data")
    strategy_dir: Path = Path("data/strategies")

    # LLM 配置
    llm_default_model: str = Field(default="gpt-4o", description="默认 LLM 模型")
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    anthropic_api_key: str = Field(default="", description="Anthropic API Key")

    # 日志配置
    log_level: str = "INFO"
    log_dir: Path = Path("logs")

    # OKX 加密货币交易配置
    okx_api_key: str = Field(default="", description="OKX API Key")
    okx_api_secret: str = Field(default="", description="OKX API Secret")
    okx_passphrase: str = Field(default="", description="OKX API Passphrase（创建 API Key 时设定）")
    okx_demo: bool = Field(default=True, description="使用 OKX demo sandbox（True = x-simulated-trading:1）")


def get_settings() -> Settings:
    """获取全局配置单例."""
    return Settings()
