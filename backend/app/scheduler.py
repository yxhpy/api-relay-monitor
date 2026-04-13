"""
API Relay Monitor - 定时任务调度器
使用 APScheduler 安排爬取、分析和报告生成任务
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.config import settings

logger = logging.getLogger(__name__)

# 全局调度器实例
scheduler: Optional[AsyncIOScheduler] = None


async def scheduled_crawl():
    """定时爬取任务"""
    logger.info(f"[调度器] 开始定时爬取 - {datetime.utcnow().isoformat()}")
    try:
        from app.services.crawler import MultiSourceCrawler
        from app.database import async_session
        from app.models import CrawlResult
        from sqlalchemy import select

        crawler = MultiSourceCrawler()
        results = await crawler.crawl_all()

        # 保存结果
        async with async_session() as db:
            saved_count = 0
            for result_data in results:
                # 去重检查
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
                    crawl_date=datetime.utcnow(),
                )
                db.add(crawl_result)
                saved_count += 1

            await db.commit()
            logger.info(f"[调度器] 爬取完成，保存 {saved_count} 条新结果")

    except Exception as e:
        logger.error(f"[调度器] 爬取任务错误: {e}")


async def scheduled_analysis():
    """定时分析任务"""
    logger.info(f"[调度器] 开始定时分析 - {datetime.utcnow().isoformat()}")
    try:
        from app.services.llm_engine import LLMEngine
        from app.services.scorer import Scorer
        from app.database import async_session
        from app.models import CrawlResult, RelaySite, AnalysisReport
        from sqlalchemy import select, func

        llm = LLMEngine()
        scorer = Scorer()

        async with async_session() as db:
            # 检查是否有未处理结果
            count_result = await db.execute(
                select(func.count(CrawlResult.id)).where(CrawlResult.processed.is_(False))
            )
            unprocessed_count = count_result.scalar() or 0

            if unprocessed_count == 0:
                logger.info("[调度器] 没有未处理的结果")
                return

            # 获取未处理结果
            result = await db.execute(
                select(CrawlResult)
                .where(CrawlResult.processed.is_(False))
                .limit(20)
            )
            unprocessed = result.scalars().all()

            for crawl_item in unprocessed:
                text = f"{crawl_item.title or ''}\n{crawl_item.content or ''}"
                if not text.strip():
                    crawl_item.processed = True
                    continue

                # 使用 LLM 提取中转站信息
                extracted = await llm.analyze_relay_info(text)
                if extracted and extracted.get("name") and extracted.get("url"):
                    # 查找或创建站点
                    existing = await db.execute(
                        select(RelaySite).where(RelaySite.url == extracted.get("url", ""))
                    )
                    site = existing.scalars().first()

                    if not site:
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

                        # 通知新站点
                        try:
                            from app.services.notifier import Notifier
                            notifier = Notifier()
                            await notifier.notify_new_site(
                                site.name, site.url,
                                site.relay_type or "未知",
                                crawl_item.source,
                            )
                        except Exception as e:
                            logger.warning(f"通知发送失败: {e}")

                    if site:
                        crawl_item.relay_site_id = site.id

                crawl_item.processed = True

            await db.commit()
            logger.info(f"[调度器] 分析完成，处理 {len(unprocessed)} 条结果")

    except Exception as e:
        logger.error(f"[调度器] 分析任务错误: {e}")


async def scheduled_daily_report():
    """定时生成日报"""
    logger.info(f"[调度器] 生成日报 - {datetime.utcnow().isoformat()}")
    try:
        from app.services.llm_engine import LLMEngine
        from app.database import async_session
        from app.models import RelaySite, AnalysisReport
        from sqlalchemy import select

        llm = LLMEngine()

        async with async_session() as db:
            # 获取所有站点
            result = await db.execute(select(RelaySite))
            sites = result.scalars().all()

            if not sites:
                logger.info("[调度器] 无站点数据，跳过日报生成")
                return

            sites_data = [
                {
                    "name": s.name,
                    "url": s.url,
                    "overall_score": s.overall_score,
                    "risk_level": s.risk_level,
                    "relay_type": s.relay_type,
                    "price_multiplier": s.price_multiplier,
                }
                for s in sites
            ]

            report_content = await llm.generate_daily_report(sites_data, [])

            if report_content:
                # 获取 Top 3
                top_sites = sorted(sites, key=lambda s: s.overall_score or 0, reverse=True)[:3]
                high_risk = [s for s in sites if s.risk_level == "high"]

                report = AnalysisReport(
                    report_type="daily",
                    content=report_content.get("content", ""),
                    summary=report_content.get("summary", ""),
                    top_picks=[
                        {"id": s.id, "name": s.name, "score": s.overall_score}
                        for s in top_sites
                    ],
                    risk_alerts=[
                        {"id": s.id, "name": s.name, "notes": s.risk_notes}
                        for s in high_risk
                    ],
                )
                db.add(report)
                await db.commit()

                # 发送通知
                try:
                    from app.services.notifier import Notifier
                    notifier = Notifier()
                    await notifier.notify_daily_report(
                        report_content.get("summary", ""),
                        [{"name": s.name, "score": s.overall_score} for s in top_sites],
                        [{"name": s.name, "notes": s.risk_notes} for s in high_risk],
                    )
                except Exception as e:
                    logger.warning(f"通知发送失败: {e}")

                logger.info("[调度器] 日报已生成并发送")

    except Exception as e:
        logger.error(f"[调度器] 日报生成错误: {e}")


def start_scheduler():
    """启动定时任务调度器"""
    global scheduler

    if scheduler is not None:
        return

    scheduler = AsyncIOScheduler(timezone="UTC")

    # 爬取任务 - 每N小时执行
    interval_minutes = settings.CRAWL_INTERVAL_MINUTES
    scheduler.add_job(
        scheduled_crawl,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="crawl_task",
        name="定时爬取",
        replace_existing=True,
    )

    # 分析任务 - 爬取后30分钟执行
    analysis_interval = max(60, interval_minutes // 2)
    scheduler.add_job(
        scheduled_analysis,
        trigger=IntervalTrigger(minutes=analysis_interval),
        id="analysis_task",
        name="定时分析",
        replace_existing=True,
    )

    # 日报 - 每天UTC 08:00生成
    scheduler.add_job(
        scheduled_daily_report,
        trigger=CronTrigger(hour=8, minute=0),
        id="daily_report",
        name="每日报告",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"[调度器] 已启动，爬取间隔: {interval_minutes} 分钟, 分析间隔: {analysis_interval} 分钟")


def stop_scheduler():
    """停止调度器"""
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        scheduler = None
        logger.info("[调度器] 已停止")
