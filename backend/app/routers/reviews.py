"""
站点评价 API — 下钻、检索、分析、LLM 分析
"""
import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import RelaySite, SiteReview
from app.schemas import (
    MessageResponse,
    ReviewAnalysisRequest,
    ReviewAnalysisResponse,
    SiteReviewCreate,
    SiteReviewResponse,
)

router = APIRouter(prefix="/api/reviews", tags=["评价系统"])


# ──────────── CRUD ────────────

@router.get("", response_model=dict, summary="检索评价（支持多条件筛选）")
async def list_reviews(
    site_id: Optional[int] = Query(None, description="站点 ID（下钻指定站点的全部评价）"),
    platform: Optional[str] = Query(None, description="来源: linux_do/v2ex/x/telegram/reddit"),
    sentiment: Optional[str] = Query(None, description="情感: positive/negative/neutral/mixed"),
    keyword: Optional[str] = Query(None, description="全文关键词搜索"),
    min_rating: Optional[float] = Query(None, ge=1, le=10),
    max_rating: Optional[float] = Query(None, ge=1, le=10),
    sort_by: str = Query("posted_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向 asc/desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """多维度检索评价 — 支持站点下钻、平台筛选、情感过滤、关键词搜索"""
    query = select(SiteReview)

    if site_id is not None:
        query = query.where(SiteReview.relay_site_id == site_id)
    if platform:
        query = query.where(SiteReview.platform == platform)
    if sentiment:
        query = query.where(SiteReview.sentiment == sentiment)
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(SiteReview.content.ilike(f"%{escaped}%"))
    if min_rating is not None:
        query = query.where(SiteReview.rating >= min_rating)
    if max_rating is not None:
        query = query.where(SiteReview.rating <= max_rating)

    # 排序
    sort_map = {
        "posted_at": SiteReview.posted_at,
        "likes": SiteReview.likes,
        "rating": SiteReview.rating,
        "sentiment_score": SiteReview.sentiment_score,
        "created_at": SiteReview.created_at,
    }
    col = sort_map.get(sort_by, SiteReview.posted_at)
    query = query.order_by(desc(col) if sort_order == "desc" else col.asc())

    # 分页
    total_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_q)).scalar() or 0
    total_pages = math.ceil(total / page_size) if total else 0

    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    reviews = result.scalars().all()

    return {
        "items": [SiteReviewResponse.model_validate(r) for r in reviews],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.post("", response_model=SiteReviewResponse, summary="添加评价")
async def create_review(body: SiteReviewCreate, db: AsyncSession = Depends(get_db)):
    """手动添加一条评价"""
    # 验证站点存在
    site = (await db.execute(select(RelaySite).where(RelaySite.id == body.relay_site_id))).scalars().first()
    if not site:
        raise HTTPException(404, "站点不存在")

    review = SiteReview(**body.model_dump())
    db.add(review)
    await db.flush()
    await db.refresh(review)
    return SiteReviewResponse.model_validate(review)


@router.get("/stats", response_model=dict, summary="评价统计概览")
async def review_stats(
    site_id: Optional[int] = Query(None, description="站点 ID"),
    platform: Optional[str] = Query(None, description="平台筛选"),
    db: AsyncSession = Depends(get_db),
):
    """评价统计 — 情感分布、平均分、平台分布"""
    base = select(SiteReview)
    if site_id is not None:
        base = base.where(SiteReview.relay_site_id == site_id)
    if platform:
        base = base.where(SiteReview.platform == platform)

    # 情感分布
    sent_q = select(SiteReview.sentiment, func.count(SiteReview.id)).group_by(SiteReview.sentiment)
    if site_id is not None:
        sent_q = sent_q.where(SiteReview.relay_site_id == site_id)
    if platform:
        sent_q = sent_q.where(SiteReview.platform == platform)
    sent_rows = (await db.execute(sent_q)).all()
    sentiment_dist = {row[0]: row[1] for row in sent_rows}

    # 平均评分
    avg_q = select(func.avg(SiteReview.rating))
    if site_id is not None:
        avg_q = avg_q.where(SiteReview.relay_site_id == site_id)
    if platform:
        avg_q = avg_q.where(SiteReview.platform == platform)
    avg_rating = (await db.execute(avg_q)).scalar()

    # 平台分布
    plat_q = select(SiteReview.platform, func.count(SiteReview.id)).group_by(SiteReview.platform)
    if site_id is not None:
        plat_q = plat_q.where(SiteReview.relay_site_id == site_id)
    plat_rows = (await db.execute(plat_q)).all()
    platform_dist = {row[0]: row[1] for row in plat_rows}

    # 总数
    cnt_q = select(func.count(SiteReview.id))
    if site_id is not None:
        cnt_q = cnt_q.where(SiteReview.relay_site_id == site_id)
    if platform:
        cnt_q = cnt_q.where(SiteReview.platform == platform)
    total = (await db.execute(cnt_q)).scalar() or 0

    return {
        "total_reviews": total,
        "sentiment_distribution": sentiment_dist,
        "avg_rating": round(avg_rating, 2) if avg_rating else None,
        "platform_distribution": platform_dist,
    }


# ──────────── 下钻：某站点的评价全景 ────────────

@router.get("/site/{site_id}/drilldown", response_model=dict, summary="站点评价下钻")
async def site_review_drilldown(
    site_id: int,
    platform: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    sort_by: str = Query("posted_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """站点评价下钻 — 统计 + 评价列表 + 平台分布"""
    site = (await db.execute(select(RelaySite).where(RelaySite.id == site_id))).scalars().first()
    if not site:
        raise HTTPException(404, "站点不存在")

    # 复用 list_reviews 的检索逻辑
    base_q = select(SiteReview).where(SiteReview.relay_site_id == site_id)
    if platform:
        base_q = base_q.where(SiteReview.platform == platform)
    if sentiment:
        base_q = base_q.where(SiteReview.sentiment == sentiment)

    # 统计
    sent_q = select(SiteReview.sentiment, func.count(SiteReview.id)).where(
        SiteReview.relay_site_id == site_id
    ).group_by(SiteReview.sentiment)
    if platform:
        sent_q = sent_q.where(SiteReview.platform == platform)
    sent_dist = {r[0]: r[1] for r in (await db.execute(sent_q)).all()}

    plat_q = select(SiteReview.platform, func.count(SiteReview.id)).where(
        SiteReview.relay_site_id == site_id
    ).group_by(SiteReview.platform)
    plat_dist = {r[0]: r[1] for r in (await db.execute(plat_q)).all()}

    avg_q = select(func.avg(SiteReview.rating)).where(SiteReview.relay_site_id == site_id)
    if platform:
        avg_q = avg_q.where(SiteReview.platform == platform)
    avg_rating = (await db.execute(avg_q)).scalar()

    total_q = select(func.count(SiteReview.id)).where(SiteReview.relay_site_id == site_id)
    if platform:
        total_q = total_q.where(SiteReview.platform == platform)
    if sentiment:
        total_q = total_q.where(SiteReview.sentiment == sentiment)
    total = (await db.execute(total_q)).scalar() or 0

    # 排序 + 分页
    sort_map = {
        "posted_at": SiteReview.posted_at,
        "likes": SiteReview.likes,
        "rating": SiteReview.rating,
        "sentiment_score": SiteReview.sentiment_score,
    }
    col = sort_map.get(sort_by, SiteReview.posted_at)
    base_q = base_q.order_by(desc(col) if sort_order == "desc" else col.asc())

    reviews = (await db.execute(base_q.offset((page - 1) * page_size).limit(page_size))).scalars().all()

    return {
        "site": {
            "id": site.id,
            "name": site.name,
            "overall_score": site.overall_score,
            "risk_level": site.risk_level,
        },
        "stats": {
            "total_reviews": total,
            "sentiment_distribution": sent_dist,
            "platform_distribution": plat_dist,
            "avg_rating": round(avg_rating, 2) if avg_rating else None,
        },
        "reviews": [SiteReviewResponse.model_validate(r) for r in reviews],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total else 0,
        },
    }


# ──────────── LLM 分析 ────────────

@router.post("/analyze", response_model=ReviewAnalysisResponse, summary="LLM 评价分析")
async def analyze_reviews(body: ReviewAnalysisRequest, db: AsyncSession = Depends(get_db)):
    """调用 LLM 分析评价 — 情感分析 + 关键词提取 + 摘要生成"""
    query = select(SiteReview)
    if body.site_id:
        query = query.where(SiteReview.relay_site_id == body.site_id)
    if body.platform:
        query = query.where(SiteReview.platform == body.platform)
    query = query.order_by(desc(SiteReview.posted_at)).limit(body.limit)

    reviews = (await db.execute(query)).scalars().all()
    if not reviews:
        return ReviewAnalysisResponse()

    site_name = None
    if body.site_id:
        site = (await db.execute(select(RelaySite).where(RelaySite.id == body.site_id))).scalars().first()
        site_name = site.name if site else None

    # 本地统计（不依赖 LLM）
    sentiment_dist = {}
    total_rating = 0
    rating_count = 0
    highlights = []
    risks = []
    all_tags = []

    for r in reviews:
        sentiment_dist[r.sentiment] = sentiment_dist.get(r.sentiment, 0) + 1
        if r.rating is not None:
            total_rating += r.rating
            rating_count += 1
        if r.llm_tags:
            all_tags.extend(r.llm_tags)

        # 挑选代表性评价
        if r.sentiment == "positive" and r.likes >= 3 and len(highlights) < 5:
            highlights.append({"content": r.content[:200], "platform": r.platform, "likes": r.likes})
        if r.sentiment == "negative" and len(risks) < 5:
            risks.append({"content": r.content[:200], "platform": r.platform})

    avg_rating = round(total_rating / rating_count, 2) if rating_count else None

    # 去重 tag
    from collections import Counter
    tag_counts = Counter(all_tags)
    top_keywords = [t for t, _ in tag_counts.most_common(20)]

    # 生成 LLM 摘要（如果有配置）
    llm_summary = None
    llm_tags = top_keywords[:10] if top_keywords else None

    try:
        import httpx
        # 检查是否有 Ollama 或其他 LLM 可用
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 尝试调用本地 LLM (Ollama)
            review_texts = "\n".join([f"- [{r.platform}] ({r.sentiment}) {r.content[:150]}" for r in reviews[:30]])
            prompt = (
                f"分析以下用户对「{site_name or 'API中转站'}」的评价，给出：\n"
                f"1. 一句话总结（50字内）\n"
                f"2. 主要优点（3条）\n"
                f"3. 主要问题（3条）\n"
                f"4. 关键词标签（逗号分隔）\n\n"
                f"评价内容：\n{review_texts}"
            )
            resp = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": "qwen2.5:7b", "prompt": prompt, "stream": False},
            )
            if resp.status_code == 200:
                llm_summary = resp.json().get("response", "")[:500]
    except Exception:
        pass  # LLM 不可用，返回基础统计

    result = ReviewAnalysisResponse(
        site_id=body.site_id,
        site_name=site_name,
        total_reviews=len(reviews),
        sentiment_distribution=sentiment_dist,
        avg_rating=avg_rating,
        top_keywords=top_keywords[:20],
        llm_summary=llm_summary,
        llm_tags=llm_tags,
        highlights=highlights,
        risks=risks,
    )

    # 如果指定了站点，把摘要写回站点
    if body.site_id and llm_summary:
        site_obj = (await db.execute(select(RelaySite).where(RelaySite.id == body.site_id))).scalars().first()
        if site_obj:
            # 更新 community_rating 基于真实评价
            if avg_rating:
                # 加权平均：现有评分 70% + 评价均分 30%
                site_obj.community_rating = round(
                    (site_obj.community_rating or 5.0) * 0.7 + avg_rating * 0.3, 1
                )
            await db.flush()

    return result
