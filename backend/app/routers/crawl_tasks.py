"""
API Relay Monitor - 爬取任务路由
管理数据爬取任务的触发和结果查询
基于 BaseCrawler 抽象层 + CrawlerRegistry 注册中心
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models import CrawlResult
from app.schemas import (
    CrawlResultResponse,
    CrawlTriggerRequest,
    MessageResponse,
    PaginatedResponse,
)
from app.services.crawlers import create_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crawl", tags=["爬取任务"])

# 全局爬虫注册中心（单例）
_registry = create_registry()

# 并发控制标志
_is_crawling = False


def get_registry():
    """获取爬虫注册中心"""
    return _registry


async def _run_crawl(source: str, db_session_factory):
    """后台执行爬取任务 — 通过 Registry 分发"""
    global _is_crawling

    try:
        if source == "all":
            results = await _registry.crawl_all()
        else:
            results = await _registry.crawl_source(source)
    except Exception as e:
        logger.error(f"[爬取错误] source={source}, error={e}")
        results = []

    # 保存结果到数据库
    saved = 0
    async with db_session_factory() as db:
        for result_data in results:
            # 检查是否已存在相同来源URL的结果（去重）
            if result_data.get("source_url"):
                existing = await db.execute(
                    select(CrawlResult).where(
                        CrawlResult.source_url == result_data["source_url"]
                    )
                )
                if existing.scalars().first():
                    continue

            crawl_result = CrawlResult(
                source=result_data.get("source", "other"),
                source_url=result_data.get("source_url"),
                title=result_data.get("title"),
                content=result_data.get("content"),
                raw_data=result_data.get("raw_data"),
                processed=False,
                crawl_date=datetime.now(timezone.utc),
            )
            db.add(crawl_result)
            saved += 1

        await db.commit()

    logger.info(f"[爬取完成] source={source}, 获取 {len(results)} 条, 新增保存 {saved} 条")
    _is_crawling = False
    return saved


@router.get("/sources", summary="获取可用数据源列表")
async def list_sources():
    """返回所有已注册的爬虫数据源（动态获取）"""
    sources = _registry.list_sources()
    # 中文标签映射
    labels = {
        "known_sites": "白名单种子",
        "linux_do": "linux.do",
        "v2ex": "V2EX",
        "github": "GitHub",
        "hackernews": "HackerNews",
    }
    return {
        "sources": [
            {"key": s, "label": labels.get(s, s)}
            for s in sources
        ],
    }


@router.post("/trigger", response_model=MessageResponse, summary="手动触发爬取")
async def trigger_crawl(
    request: CrawlTriggerRequest,
    background_tasks: BackgroundTasks,
):
    """手动触发爬取任务，支持指定数据源或 all"""
    global _is_crawling

    available = _registry.list_sources()
    valid_sources = ("all",) + tuple(available)
    if request.source not in valid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"无效的数据源，可用: {', '.join(valid_sources)}",
        )

    if _is_crawling:
        raise HTTPException(
            status_code=409,
            detail="已有爬取任务正在运行，请稍后再试",
        )

    _is_crawling = True
    background_tasks.add_task(_run_crawl, request.source, async_session)

    return MessageResponse(
        message=f"爬取任务已启动，数据源: {request.source}",
        success=True,
        data={"source": request.source, "triggered_at": datetime.now(timezone.utc).isoformat()},
    )


@router.get("/results", response_model=PaginatedResponse, summary="获取爬取结果列表")
async def list_crawl_results(
    source: Optional[str] = Query(None, description="数据源筛选"),
    processed: Optional[bool] = Query(None, description="是否已处理"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """获取爬取结果列表，支持筛选和分页"""
    query = select(CrawlResult)

    if source:
        # 支持模糊匹配（如 github 匹配 github_discussions, github_awesome_list）
        query = query.where(CrawlResult.source.ilike(f"{source}%"))
    if processed is not None:
        query = query.where(CrawlResult.processed == processed)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(CrawlResult.created_at.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    results = result.scalars().all()

    items = [CrawlResultResponse.model_validate(r) for r in results]
    total_pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/results/{result_id}", response_model=CrawlResultResponse, summary="获取爬取结果详情")
async def get_crawl_result(
    result_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取指定爬取结果的详细信息"""
    result = await db.execute(
        select(CrawlResult).where(CrawlResult.id == result_id)
    )
    crawl_result = result.scalars().first()

    if not crawl_result:
        raise HTTPException(status_code=404, detail="爬取结果不存在")

    return CrawlResultResponse.model_validate(crawl_result)


@router.put("/results/{result_id}", response_model=CrawlResultResponse, summary="更新爬取结果")
async def update_crawl_result(
    result_id: int,
    db: AsyncSession = Depends(get_db),
):
    """更新爬取结果（标记为已处理等）"""
    result = await db.execute(
        select(CrawlResult).where(CrawlResult.id == result_id)
    )
    crawl_result = result.scalars().first()

    if not crawl_result:
        raise HTTPException(status_code=404, detail="爬取结果不存在")

    crawl_result.processed = True
    await db.flush()
    await db.refresh(crawl_result)

    return CrawlResultResponse.model_validate(crawl_result)
