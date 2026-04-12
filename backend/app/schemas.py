"""
API Relay Monitor - Pydantic 数据模型
定义请求/响应的数据校验模型
"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, HttpUrl


# ============ RelaySite Schemas ============

class RelaySiteCreate(BaseModel):
    """创建中转站"""
    name: str = Field(..., max_length=200, description="站点名称")
    url: str = Field(..., max_length=500, description="站点网址")
    api_url: Optional[str] = Field(None, max_length=500, description="API端点URL")
    relay_type: Optional[str] = Field("聚合", description="中转类型：官转/逆向/聚合/Bedrock")
    status: Optional[str] = Field("unknown", description="状态：active/suspended/unknown")
    description: Optional[str] = Field(None, description="站点描述")
    pricing_info: Optional[dict] = Field(None, description="定价信息")
    price_multiplier: Optional[float] = Field(None, description="价格倍率")
    supported_models: Optional[List[str]] = Field(None, description="支持的模型列表")
    registration_url: Optional[str] = Field(None, max_length=500, description="注册链接")
    telegram_group: Optional[str] = Field(None, max_length=200, description="Telegram群组")
    source: Optional[str] = Field(None, max_length=100, description="信息来源")


class RelaySiteUpdate(BaseModel):
    """更新中转站"""
    name: Optional[str] = Field(None, max_length=200)
    url: Optional[str] = Field(None, max_length=500)
    api_url: Optional[str] = Field(None, max_length=500)
    relay_type: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    pricing_info: Optional[dict] = None
    price_multiplier: Optional[float] = None
    supported_models: Optional[List[str]] = None
    registration_url: Optional[str] = Field(None, max_length=500)
    telegram_group: Optional[str] = Field(None, max_length=200)
    source: Optional[str] = Field(None, max_length=100)
    community_rating: Optional[float] = Field(None, ge=1, le=10)
    stability_score: Optional[float] = Field(None, ge=1, le=10)
    price_score: Optional[float] = Field(None, ge=1, le=10)
    update_speed_score: Optional[float] = Field(None, ge=1, le=10)
    overall_score: Optional[float] = None
    risk_level: Optional[str] = None
    risk_notes: Optional[str] = None
    last_verified_at: Optional[datetime] = None


class RelaySiteResponse(BaseModel):
    """中转站响应"""
    id: int
    name: str
    url: str
    api_url: Optional[str] = None
    relay_type: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    pricing_info: Optional[dict] = None
    price_multiplier: Optional[float] = None
    supported_models: Optional[List[str]] = None
    registration_url: Optional[str] = None
    telegram_group: Optional[str] = None
    source: Optional[str] = None
    community_rating: Optional[float] = None
    stability_score: Optional[float] = None
    price_score: Optional[float] = None
    update_speed_score: Optional[float] = None
    overall_score: Optional[float] = None
    risk_level: Optional[str] = None
    risk_notes: Optional[str] = None
    last_verified_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ============ CrawlResult Schemas ============

class CrawlResultResponse(BaseModel):
    """爬取结果响应"""
    id: int
    source: str
    source_url: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    raw_data: Optional[dict] = None
    processed: bool = False
    relay_site_id: Optional[int] = None
    crawl_date: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ============ PriceHistory Schemas ============

class PriceHistoryCreate(BaseModel):
    """创建价格记录"""
    relay_site_id: int
    model_name: str
    multiplier: Optional[float] = None
    price_per_1k_tokens: Optional[float] = None


class PriceHistoryResponse(BaseModel):
    """价格历史响应"""
    id: int
    relay_site_id: int
    model_name: str
    multiplier: Optional[float] = None
    price_per_1k_tokens: Optional[float] = None
    recorded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ============ AnalysisReport Schemas ============

class AnalysisReportResponse(BaseModel):
    """分析报告响应"""
    id: int
    report_type: str
    content: Optional[str] = None
    summary: Optional[str] = None
    top_picks: Optional[dict] = None
    risk_alerts: Optional[dict] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ============ 通用响应模型 ============

class PaginatedResponse(BaseModel):
    """分页响应"""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str
    success: bool = True
    data: Optional[Any] = None


class CrawlTriggerRequest(BaseModel):
    """触发爬取请求"""
    source: str = Field("all", description="数据源：all/linux_do/v2ex/github/rss")


class EvaluateSiteRequest(BaseModel):
    """评估站点请求"""
    site_id: int = Field(..., description="中转站ID")


# ============ Dashboard Schemas ============

class DashboardStats(BaseModel):
    """仪表盘统计"""
    total_sites: int = 0
    active_sites: int = 0
    suspended_sites: int = 0
    unknown_sites: int = 0
    type_distribution: dict = {}
    avg_overall_score: float = 0.0
    avg_price_multiplier: float = 0.0
    high_risk_count: int = 0
    medium_risk_count: int = 0
    low_risk_count: int = 0
    total_crawl_results: int = 0
    unprocessed_results: int = 0
    latest_report_date: Optional[datetime] = None


class TrendDataPoint(BaseModel):
    """趋势数据点"""
    date: str
    model_name: str
    avg_multiplier: float
    avg_price: float


class TopPick(BaseModel):
    """推荐站点"""
    id: int
    name: str
    url: str
    relay_type: Optional[str] = None
    overall_score: float
    price_multiplier: Optional[float] = None
    risk_level: Optional[str] = None


class RiskAlert(BaseModel):
    """风险提醒"""
    site_id: int
    site_name: str
    risk_level: str
    risk_notes: Optional[str] = None
    overall_score: Optional[float] = None
