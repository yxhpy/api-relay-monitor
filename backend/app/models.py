"""
API Relay Monitor - 数据库模型
定义所有 SQLAlchemy ORM 模型
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Text, Boolean, DateTime, JSON, ForeignKey,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class RelaySite(Base):
    """中转站信息表"""
    __tablename__ = "relay_sites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, comment="站点名称")
    url = Column(String(500), nullable=False, unique=True, index=True, comment="站点网址")
    api_url = Column(String(500), nullable=True, comment="API端点URL")
    relay_type = Column(
        SQLEnum("官转", "逆向", "聚合", "公益", "Bedrock", "自建", name="relay_type_enum"),
        default="聚合",
        comment="中转类型",
    )
    status = Column(
        SQLEnum("active", "suspended", "unknown", name="status_enum"),
        default="unknown",
        comment="状态",
    )
    description = Column(Text, nullable=True, comment="站点描述")
    pricing_info = Column(JSON, nullable=True, comment="定价信息JSON")
    price_multiplier = Column(Float, nullable=True, comment="价格倍率")
    supported_models = Column(JSON, nullable=True, comment="支持的模型列表JSON")
    registration_url = Column(String(500), nullable=True, comment="注册链接")
    telegram_group = Column(String(200), nullable=True, comment="Telegram群组")
    source = Column(String(100), nullable=True, comment="信息来源")
    community_rating = Column(Float, default=5.0, comment="社区评分 1-10")
    stability_score = Column(Float, default=5.0, comment="稳定性评分 1-10")
    price_score = Column(Float, default=5.0, comment="价格评分 1-10")
    update_speed_score = Column(Float, default=5.0, comment="更新速度评分 1-10")
    overall_score = Column(Float, default=5.0, comment="综合评分")
    risk_level = Column(
        SQLEnum("low", "medium", "high", name="risk_level_enum"),
        default="medium",
        comment="风险等级",
    )
    risk_notes = Column(Text, nullable=True, comment="风险备注")
    avg_response_ms = Column(Float, nullable=True, comment="平均响应时间(ms)")
    uptime_percent = Column(Float, nullable=True, comment="可用率(%)")
    user_reviews = Column(JSON, nullable=True, comment="用户评价列表JSON")
    last_verified_at = Column(DateTime, nullable=True, comment="最后验证时间")
    created_at = Column(DateTime, default=_utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, comment="更新时间")

    # 关系
    crawl_results = relationship("CrawlResult", back_populates="relay_site", lazy="noload")
    price_histories = relationship("PriceHistory", back_populates="relay_site", lazy="noload")


class CrawlResult(Base):
    """爬取结果表"""
    __tablename__ = "crawl_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False, comment="数据来源")
    source_url = Column(String(500), nullable=True, comment="来源URL")
    title = Column(String(500), nullable=True, comment="标题")
    content = Column(Text, nullable=True, comment="内容")
    raw_data = Column(JSON, nullable=True, comment="原始数据JSON")
    processed = Column(Boolean, default=False, comment="是否已处理")
    relay_site_id = Column(Integer, ForeignKey("relay_sites.id"), nullable=True, comment="关联中转站ID")
    crawl_date = Column(DateTime, default=_utcnow, comment="爬取日期")
    created_at = Column(DateTime, default=_utcnow, comment="创建时间")

    # 关系
    relay_site = relationship("RelaySite", back_populates="crawl_results")


class PriceHistory(Base):
    """价格历史表"""
    __tablename__ = "price_histories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    relay_site_id = Column(Integer, ForeignKey("relay_sites.id"), nullable=False, comment="中转站ID")
    model_name = Column(String(200), nullable=False, comment="模型名称")
    multiplier = Column(Float, nullable=True, comment="倍率")
    price_per_1k_tokens = Column(Float, nullable=True, comment="每1K token价格")
    recorded_at = Column(DateTime, default=_utcnow, comment="记录时间")

    # 关系
    relay_site = relationship("RelaySite", back_populates="price_histories")


class AnalysisReport(Base):
    """分析报告表"""
    __tablename__ = "analysis_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_type = Column(
        SQLEnum("daily", "weekly", "alert", name="report_type_enum"),
        nullable=False,
        comment="报告类型",
    )
    content = Column(Text, nullable=True, comment="报告内容(Markdown)")
    summary = Column(Text, nullable=True, comment="摘要")
    top_picks = Column(JSON, nullable=True, comment="推荐站点JSON")
    risk_alerts = Column(JSON, nullable=True, comment="风险提醒JSON")
    created_at = Column(DateTime, default=_utcnow, comment="创建时间")
