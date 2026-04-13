"""
抖音热榜爬虫 — 监控 AI/API 相关热搜
"""
import asyncio
import logging
import re
from typing import List

from .base import BaseCrawler, CrawlerConfig, CrawlResult

logger = logging.getLogger(__name__)


class DouyinCrawler(BaseCrawler):
    """抖音热榜爬虫 — 筛选 AI/API 相关热点"""

    name = "douyin"
    config = CrawlerConfig(
        timeout=10.0,
        max_retries=2,
        rate_limit_delay=1.0,
    )

    # 第三方热榜聚合 API
    THIRD_PARTY_API = "https://api.vvhan.com/api/hotlist/douyinHot"

    # 抖音官方热榜 API（可能需要特殊处理）
    DOUYIN_API = "https://www.douyin.com/aweme/v1/web/hot/search/list/"

    # AI/API 相关热搜关键词
    AI_KEYWORDS = [
        "AI", "API", "LLM", "GPT", "Claude", "OpenAI",
        "大模型", "人工智能", "ChatGPT", "Gemini", "Llama",
        "人工智能", "AI大模型", "AI应用",
    ]

    def _is_ai_related(self, title: str) -> bool:
        """检查热搜标题是否与 AI/API 相关"""
        title_lower = title.lower()
        return any(kw.lower() in title_lower for kw in self.AI_KEYWORDS)

    async def crawl(self) -> List[CrawlResult]:
        results = []

        async with self._build_client() as client:
            # 优先尝试第三方热榜聚合 API
            fetched = False
            try:
                resp = await self._fetch_with_retry(client, self.THIRD_PARTY_API)
                if resp and resp.status_code == 200:
                    data = resp.json()
                    # 第三方 API 返回格式: { data: [ { title, url, hot }, ... ] }
                    items = (
                        data.get("data", [])
                        if isinstance(data.get("data"), list)
                        else []
                    )
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        title = item.get("title", "") or item.get("name", "")
                        url = item.get("url", "") or item.get("link", "")
                        hot = item.get("hot", "") or item.get("hotValue", "")
                        if not self._is_ai_related(title):
                            continue
                        # 同时检查是否包含中转站相关关键词
                        combined = title
                        results.append(CrawlResult(
                            source=self.name,
                            source_url=url or "https://www.douyin.com/hot",
                            title=f"[抖音热搜] {title}",
                            content=title[:2000],
                            raw_data={
                                "hot_value": str(hot),
                                "rank": item.get("rank", 0),
                            },
                        ))
                    fetched = True
                    logger.info(
                        f"[{self.name}] 第三方 API 获取 {len(results)} 条 AI 相关热搜"
                    )
            except Exception as e:
                logger.warning(f"[{self.name}] 第三方热榜 API 失败: {e}")

            # 备选: 尝试抖音官方 API
            if not fetched:
                try:
                    resp = await self._fetch_with_retry(
                        client,
                        self.DOUYIN_API,
                    )
                    if resp and resp.status_code == 200:
                        data = resp.json()
                        word_list = (
                            data.get("data", {})
                            .get("word_list", [])
                        )
                        for item in word_list:
                            title = item.get("word", "")
                            hot_value = item.get("hot_value", "")
                            url = (
                                f"https://www.douyin.com/hot/{item.get('sentence_tag', '')}"
                            )
                            if not self._is_ai_related(title):
                                continue
                            results.append(CrawlResult(
                                source=self.name,
                                source_url=url,
                                title=f"[抖音热搜] {title}",
                                content=title[:2000],
                                raw_data={
                                    "hot_value": str(hot_value),
                                    "event_time": item.get("event_time", ""),
                                },
                            ))
                        logger.info(
                            f"[{self.name}] 官方 API 获取 {len(results)} 条 AI 相关热搜"
                        )
                except Exception as e:
                    logger.warning(f"[{self.name}] 抖音官方 API 失败: {e}")

            # 如果都没有获取到结果，graceful 返回空
            if not results:
                logger.info(
                    f"[{self.name}] 未获取到 AI 相关热搜，graceful 返回空列表"
                )

        return self._deduplicate(results)
