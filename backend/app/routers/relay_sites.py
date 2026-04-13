"""
API Relay Monitor - 中转站 CRUD 路由
提供中转站信息的增删改查接口
"""

import ipaddress
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import RelaySite
from app.schemas import (
    RelaySiteCreate,
    RelaySiteUpdate,
    RelaySiteResponse,
    MessageResponse,
    PaginatedResponse,
)
from app.services.scorer import Scorer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sites", tags=["中转站管理"])

# 私有 IP 网段（用于 SSRF 防护）
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
]


def _is_private_url(url: str) -> bool:
    """检查 URL 是否指向私有 IP 或 localhost"""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True
        if hostname.lower() in ("localhost", "localhost.localdomain"):
            return True
        try:
            ip = ipaddress.ip_address(hostname)
            for network in _PRIVATE_NETWORKS:
                if ip in network:
                    return True
        except ValueError:
            pass  # 不是 IP 地址（可能是域名），允许
        return False
    except Exception:
        return True


@router.get("", response_model=PaginatedResponse, summary="获取中转站列表")
async def list_sites(
    relay_type: Optional[str] = Query(None, description="中转类型筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    risk_level: Optional[str] = Query(None, description="风险等级筛选"),
    min_score: Optional[float] = Query(None, description="最低综合评分"),
    sort_by: str = Query("updated_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向 asc/desc"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """获取中转站列表，支持筛选、排序和分页"""
    # 构建查询
    query = select(RelaySite)

    # 应用筛选条件
    if relay_type:
        query = query.where(RelaySite.relay_type == relay_type)
    if status:
        query = query.where(RelaySite.status == status)
    if risk_level:
        query = query.where(RelaySite.risk_level == risk_level)
    if min_score is not None:
        query = query.where(RelaySite.overall_score >= min_score)

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 排序（白名单校验防止注入）
    ALLOWED_SORT_FIELDS = {"updated_at", "created_at", "overall_score", "name", "status", "risk_level", "price_multiplier"}
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = "updated_at"
    sort_column = getattr(RelaySite, sort_by, RelaySite.updated_at)
    if sort_order == "desc":
        sort_column = sort_column.desc()
    else:
        sort_column = sort_column.asc()
    query = query.order_by(sort_column)

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    sites = result.scalars().all()

    # 转为响应模型
    items = [RelaySiteResponse.model_validate(site) for site in sites]
    total_pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=RelaySiteResponse, summary="创建中转站")
async def create_site(
    site_data: RelaySiteCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建新的中转站记录"""
    # 检查URL是否已存在
    existing = await db.execute(
        select(RelaySite).where(RelaySite.url == site_data.url)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="该URL的中转站已存在")

    # 创建记录
    site = RelaySite(**site_data.model_dump())

    # 计算初始评分
    scorer = Scorer()
    site.overall_score = scorer.calculate_overall_score(
        stability=site.stability_score,
        price=site.price_score,
        update_speed=site.update_speed_score,
        community=site.community_rating,
    )
    site.risk_level = scorer.calculate_risk_level(site.overall_score, site.price_multiplier, site.relay_type)

    db.add(site)
    await db.flush()
    await db.refresh(site)

    return RelaySiteResponse.model_validate(site)


@router.get("/{site_id}", response_model=RelaySiteResponse, summary="获取中转站详情")
async def get_site(
    site_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取指定中转站的详细信息"""
    result = await db.execute(
        select(RelaySite).where(RelaySite.id == site_id)
    )
    site = result.scalars().first()

    if not site:
        raise HTTPException(status_code=404, detail="中转站不存在")

    return RelaySiteResponse.model_validate(site)


@router.put("/{site_id}", response_model=RelaySiteResponse, summary="更新中转站")
async def update_site(
    site_id: int,
    site_data: RelaySiteUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新中转站信息"""
    result = await db.execute(
        select(RelaySite).where(RelaySite.id == site_id)
    )
    site = result.scalars().first()

    if not site:
        raise HTTPException(status_code=404, detail="中转站不存在")

    # 更新非空字段
    update_data = site_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(site, key, value)

    # 重新计算评分
    scorer = Scorer()
    site.overall_score = scorer.calculate_overall_score(
        stability=site.stability_score,
        price=site.price_score,
        update_speed=site.update_speed_score,
        community=site.community_rating,
    )
    site.risk_level = scorer.calculate_risk_level(site.overall_score, site.price_multiplier, site.relay_type)

    await db.flush()
    await db.refresh(site)

    return RelaySiteResponse.model_validate(site)


@router.delete("/{site_id}", response_model=MessageResponse, summary="删除中转站")
async def delete_site(
    site_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除指定中转站"""
    result = await db.execute(
        select(RelaySite).where(RelaySite.id == site_id)
    )
    site = result.scalars().first()

    if not site:
        raise HTTPException(status_code=404, detail="中转站不存在")

    await db.delete(site)

    return MessageResponse(message="中转站已删除", success=True)


@router.post("/{site_id}/verify", response_model=MessageResponse, summary="验证中转站")
async def verify_site(
    site_id: int,
    db: AsyncSession = Depends(get_db),
):
    """触发中转站验证，检查站点是否可达"""
    result = await db.execute(
        select(RelaySite).where(RelaySite.id == site_id)
    )
    site = result.scalars().first()

    if not site:
        raise HTTPException(status_code=404, detail="中转站不存在")

    # SSRF 防护：检查 URL 是否指向私有 IP
    check_url = site.api_url or site.url
    if _is_private_url(check_url):
        raise HTTPException(status_code=400, detail="不允许验证私有网络地址")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(check_url, follow_redirects=True)
            if resp.status_code < 500:
                site.status = "active"
            else:
                site.status = "suspended"
    except Exception:
        site.status = "suspended"

    site.last_verified_at = datetime.now(timezone.utc)
    # 不手动设置 updated_at，依赖模型的 onupdate
    await db.flush()

    return MessageResponse(
        message=f"验证完成，状态：{site.status}",
        success=True,
        data={"status": site.status, "verified_at": site.last_verified_at.isoformat()},
    )
