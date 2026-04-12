"""
API Relay Monitor - 仪表盘路由
提供统计概览、趋势、推荐和风险提醒接口
"""

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import RelaySite, CrawlResult, PriceHistory, AnalysisReport
from app.schemas import (
    DashboardStats,
    TrendDataPoint,
    TopPick,
    RiskAlert,
    MessageResponse,
)

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@router.get("/stats", response_model=DashboardStats, summary="获取概览统计")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """获取仪表盘概览统计数据"""
    # 总站点数
    total_result = await db.execute(select(func.count(RelaySite.id)))
    total_sites = total_result.scalar() or 0

    # 各状态站点数
    active_result = await db.execute(
        select(func.count(RelaySite.id)).where(RelaySite.status == "active")
    )
    active_sites = active_result.scalar() or 0

    suspended_result = await db.execute(
        select(func.count(RelaySite.id)).where(RelaySite.status == "suspended")
    )
    suspended_sites = suspended_result.scalar() or 0

    unknown_sites = total_sites - active_sites - suspended_sites

    # 类型分布
    type_result = await db.execute(
        select(RelaySite.relay_type, func.count(RelaySite.id))
        .group_by(RelaySite.relay_type)
    )
    type_distribution = {row[0] or "未知": row[1] for row in type_result.all()}

    # 平均评分
    avg_score_result = await db.execute(
        select(func.avg(RelaySite.overall_score))
    )
    avg_overall_score = avg_score_result.scalar() or 0.0

    # 平均价格倍率
    avg_price_result = await db.execute(
        select(func.avg(RelaySite.price_multiplier)).where(RelaySite.price_multiplier.isnot(None))
    )
    avg_price_multiplier = avg_price_result.scalar() or 0.0

    # 风险分布
    risk_result = await db.execute(
        select(RelaySite.risk_level, func.count(RelaySite.id))
        .group_by(RelaySite.risk_level)
    )
    risk_counts = {row[0] or "medium": row[1] for row in risk_result.all()}

    # 爬取结果统计
    total_crawl = await db.execute(select(func.count(CrawlResult.id)))
    total_crawl_results = total_crawl.scalar() or 0

    unprocessed_crawl = await db.execute(
        select(func.count(CrawlResult.id)).where(CrawlResult.processed == False)
    )
    unprocessed_results = unprocessed_crawl.scalar() or 0

    # 最新报告日期
    latest_report = await db.execute(
        select(AnalysisReport.created_at).order_by(AnalysisReport.created_at.desc()).limit(1)
    )
    latest_report_date = latest_report.scalar()

    return DashboardStats(
        total_sites=total_sites,
        active_sites=active_sites,
        suspended_sites=suspended_sites,
        unknown_sites=unknown_sites,
        type_distribution=type_distribution,
        avg_overall_score=round(avg_overall_score, 2),
        avg_price_multiplier=round(avg_price_multiplier, 2),
        high_risk_count=risk_counts.get("high", 0),
        medium_risk_count=risk_counts.get("medium", 0),
        low_risk_count=risk_counts.get("low", 0),
        total_crawl_results=total_crawl_results,
        unprocessed_results=unprocessed_results,
        latest_report_date=latest_report_date,
    )


@router.get("/trends", response_model=List[TrendDataPoint], summary="获取价格趋势")
async def get_trends(
    days: int = 30,
    model_name: str = None,
    db: AsyncSession = Depends(get_db),
):
    """获取价格趋势数据"""
    since = datetime.utcnow() - timedelta(days=days)

    query = (
        select(
            func.date(PriceHistory.recorded_at).label("date"),
            PriceHistory.model_name,
            func.avg(PriceHistory.multiplier).label("avg_multiplier"),
            func.avg(PriceHistory.price_per_1k_tokens).label("avg_price"),
        )
        .where(PriceHistory.recorded_at >= since)
        .group_by("date", PriceHistory.model_name)
        .order_by("date")
    )

    if model_name:
        query = query.where(PriceHistory.model_name.ilike(f"%{model_name}%"))

    result = await db.execute(query)
    rows = result.all()

    return [
        TrendDataPoint(
            date=str(row.date),
            model_name=row.model_name,
            avg_multiplier=round(row.avg_multiplier or 0, 4),
            avg_price=round(row.avg_price or 0, 6),
        )
        for row in rows
    ]


@router.get("/top-picks", response_model=List[TopPick], summary="获取推荐站点")
async def get_top_picks(
    limit: int = 3,
    db: AsyncSession = Depends(get_db),
):
    """获取当前推荐的Top中转站"""
    result = await db.execute(
        select(RelaySite)
        .where(
            and_(
                RelaySite.status == "active",
                RelaySite.risk_level.in_(["low", "medium"]),
            )
        )
        .order_by(RelaySite.overall_score.desc())
        .limit(limit)
    )
    sites = result.scalars().all()

    return [
        TopPick(
            id=site.id,
            name=site.name,
            url=site.url,
            relay_type=site.relay_type,
            overall_score=site.overall_score or 0,
            price_multiplier=site.price_multiplier,
            risk_level=site.risk_level,
        )
        for site in sites
    ]


@router.get("/risk-alerts", response_model=List[RiskAlert], summary="获取风险提醒")
async def get_risk_alerts(db: AsyncSession = Depends(get_db)):
    """获取当前活跃的风险提醒"""
    result = await db.execute(
        select(RelaySite)
        .where(
            and_(
                RelaySite.risk_level.in_(["high", "medium"]),
                RelaySite.status != "suspended",
            )
        )
        .order_by(
            case(
                (RelaySite.risk_level == "high", 1),
                (RelaySite.risk_level == "medium", 2),
                else_=3,
            )
        )
    )
    sites = result.scalars().all()

    return [
        RiskAlert(
            site_id=site.id,
            site_name=site.name,
            risk_level=site.risk_level,
            risk_notes=site.risk_notes,
            overall_score=site.overall_score,
        )
        for site in sites
    ]
