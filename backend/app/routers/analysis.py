"""
API Relay Monitor - LLM 分析路由
提供 LLM 分析和报告相关接口
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models import CrawlResult, RelaySite, AnalysisReport
from app.schemas import (
    AnalysisReportResponse,
    EvaluateSiteRequest,
    MessageResponse,
    PaginatedResponse,
)
from app.services.llm_engine import LLMEngine
from app.services.scorer import Scorer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["LLM 分析"])


def _escape_like(s: str) -> str:
    """转义 LIKE/ILIKE 查询中的特殊字符 % 和 _"""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def _run_analysis(db_session_factory, site_id: Optional[int] = None):
    """后台运行LLM分析"""
    llm = LLMEngine()
    scorer = Scorer()

    async with db_session_factory() as db:
        try:
            if site_id:
                # 分析特定站点
                result = await db.execute(
                    select(RelaySite).where(RelaySite.id == site_id)
                )
                site = result.scalars().first()
                if not site:
                    return

                # 获取相关爬取结果
                escaped_name = _escape_like(site.name)
                crawl_result = await db.execute(
                    select(CrawlResult).where(
                        (CrawlResult.relay_site_id == site_id) |
                        (CrawlResult.title.ilike(f"%{escaped_name}%"))
                    ).limit(10)
                )
                feedbacks = crawl_result.scalars().all()

                # 评估风险
                risk_result = await llm.evaluate_risk(
                    {
                        "name": site.name,
                        "url": site.url,
                        "relay_type": site.relay_type,
                        "pricing_info": site.pricing_info,
                        "price_multiplier": site.price_multiplier,
                    },
                    [c.content for c in feedbacks if c.content],
                )

                # 更新站点评分
                scores = await llm.score_relay_site({
                    "name": site.name,
                    "url": site.url,
                    "relay_type": site.relay_type,
                    "pricing_info": site.pricing_info,
                    "community_feedback": [c.content for c in feedbacks if c.content],
                })

                if scores:
                    site.stability_score = scores.get("stability", site.stability_score)
                    site.price_score = scores.get("price", site.price_score)
                    site.update_speed_score = scores.get("update_speed", site.update_speed_score)
                    site.community_rating = scores.get("community", site.community_rating)
                    site.overall_score = scorer.calculate_overall_score(
                        site.stability_score, site.price_score,
                        site.update_speed_score, site.community_rating,
                    )

                if risk_result:
                    site.risk_level = risk_result.get("risk_level", site.risk_level)
                    site.risk_notes = risk_result.get("notes", site.risk_notes)

                # 不手动设置 updated_at，依赖模型的 onupdate
            else:
                # 批量分析未处理的爬取结果
                result = await db.execute(
                    select(CrawlResult).where(CrawlResult.processed.is_(False)).limit(50)
                )
                unprocessed = result.scalars().all()

                for crawl_item in unprocessed:
                    text = f"{crawl_item.title or ''}\n{crawl_item.content or ''}"
                    if not text.strip():
                        crawl_item.processed = True
                        continue

                    # 使用 LLM 提取中转站信息
                    extracted = await llm.analyze_relay_info(text)
                    if extracted and extracted.get("name"):
                        # 查找或创建中转站记录
                        escaped_name = _escape_like(extracted['name'])
                        existing = await db.execute(
                            select(RelaySite).where(
                                (RelaySite.name.ilike(f"%{escaped_name}%")) |
                                (RelaySite.url == extracted.get("url", ""))
                            )
                        )
                        site = existing.scalars().first()

                        if not site and extracted.get("url"):
                            site = RelaySite(
                                name=extracted.get("name", "未知"),
                                url=extracted.get("url", ""),
                                api_url=extracted.get("api_url"),
                                relay_type=extracted.get("relay_type", "聚合"),
                                description=extracted.get("description"),
                                pricing_info=extracted.get("pricing_info"),
                                price_multiplier=extracted.get("price_multiplier"),
                                supported_models=extracted.get("supported_models"),
                                source=crawl_item.source,
                                overall_score=5.0,
                            )
                            db.add(site)
                            await db.flush()

                        if site:
                            crawl_item.relay_site_id = site.id

                    crawl_item.processed = True

                # 生成日报
                all_sites_result = await db.execute(select(RelaySite))
                all_sites = all_sites_result.scalars().all()

                if all_sites:
                    report_content = await llm.generate_daily_report(
                        [{"name": s.name, "url": s.url, "overall_score": s.overall_score,
                          "risk_level": s.risk_level, "relay_type": s.relay_type}
                         for s in all_sites],
                        [{"title": c.title, "content": c.content, "source": c.source}
                         for c in unprocessed[:20]],
                    )

                    if report_content:
                        # 获取推荐和风险
                        top_picks = sorted(all_sites, key=lambda s: s.overall_score or 0, reverse=True)[:3]
                        high_risk = [s for s in all_sites if s.risk_level == "high"]

                        report = AnalysisReport(
                            report_type="daily",
                            content=report_content.get("content", ""),
                            summary=report_content.get("summary", ""),
                            top_picks=[
                                {"id": s.id, "name": s.name, "score": s.overall_score}
                                for s in top_picks
                            ],
                            risk_alerts=[
                                {"id": s.id, "name": s.name, "notes": s.risk_notes}
                                for s in high_risk
                            ],
                        )
                        db.add(report)

            await db.commit()
        except Exception as e:
            logger.error(f"[分析错误] {e}")
            await db.rollback()


@router.post("/run", response_model=MessageResponse, summary="运行LLM分析")
async def run_analysis(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """对未处理的爬取结果运行 LLM 分析"""
    # 检查是否有未处理的结果
    result = await db.execute(
        select(func.count()).select_from(
            select(CrawlResult).where(CrawlResult.processed.is_(False)).subquery()
        )
    )
    count = result.scalar() or 0

    if count == 0:
        return MessageResponse(message="没有未处理的爬取结果", success=True, data={"processed": 0})

    background_tasks.add_task(_run_analysis, async_session)

    return MessageResponse(
        message=f"分析任务已启动，待处理 {count} 条结果",
        success=True,
        data={"unprocessed_count": count},
    )


@router.get("/reports", response_model=PaginatedResponse, summary="获取分析报告列表")
async def list_reports(
    report_type: Optional[str] = Query(None, description="报告类型: daily/weekly/alert"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取分析报告列表"""
    query = select(AnalysisReport)

    if report_type:
        query = query.where(AnalysisReport.report_type == report_type)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(AnalysisReport.created_at.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    reports = result.scalars().all()

    items = [AnalysisReportResponse.model_validate(r) for r in reports]
    total_pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        items=items, total=total, page=page,
        page_size=page_size, total_pages=total_pages,
    )


@router.get("/reports/{report_id}", response_model=AnalysisReportResponse, summary="获取报告详情")
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取指定分析报告的详细信息"""
    result = await db.execute(
        select(AnalysisReport).where(AnalysisReport.id == report_id)
    )
    report = result.scalars().first()

    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    return AnalysisReportResponse.model_validate(report)


@router.post("/evaluate-site", response_model=MessageResponse, summary="评估指定站点")
async def evaluate_site(
    request: EvaluateSiteRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """使用 LLM 评估指定中转站"""
    result = await db.execute(
        select(RelaySite).where(RelaySite.id == request.site_id)
    )
    site = result.scalars().first()

    if not site:
        raise HTTPException(status_code=404, detail="中转站不存在")

    background_tasks.add_task(_run_analysis, async_session, request.site_id)

    return MessageResponse(
        message=f"评估任务已启动，站点: {site.name}",
        success=True,
        data={"site_id": request.site_id, "site_name": site.name},
    )
