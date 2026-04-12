"""
API Relay Monitor - 配置管理
使用 pydantic-settings 管理环境变量配置
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置，从环境变量或 .env 文件加载"""

    # LLM 配置
    LLM_API_KEY: str = "sk-placeholder"
    LLM_API_BASE: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"

    # Telegram 通知配置（可选）
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    # 爬虫配置
    CRAWL_INTERVAL_MINUTES: int = 480  # 默认8小时爬取一次

    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/relay_monitor.db"

    # 应用配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False

    # 爬虫源配置
    LINUX_DO_BASE_URL: str = "https://linux.do"
    V2EX_BASE_URL: str = "https://www.v2ex.com"
    GITHUB_API_URL: str = "https://api.github.com"
    RSS_HUB_URL: str = "https://rsshub.app"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# 全局配置实例
settings = Settings()
