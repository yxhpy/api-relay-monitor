"""
Product Hunt 搜索爬虫
"""
import asyncio
import logging
import re
from typing import List

from .base import BaseCrawler, CrawlerConfig, CrawlResult

logger = logging.getLogger(__name__)


class ProductHuntCrawler(BaseCrawler):
    """Product Hunt 搜索爬虫"""

    name = "producthunt"
    config = CrawlerConfig(
        timeout=15.0,
        max_retries=2,
        rate_limit_delay=1.0,
    )

    SEARCH_QUERIES = [
        "LLM API",
        "OpenAI proxy",
        "API relay",
        "AI API gateway",
    ]

    # 第三方 PH 搜索 API
    THIRD_PARTY_API = "https://ph-api.toolkit.so/api/products/search"

    async def crawl(self) -> List[CrawlResult]:
        results = []
        async with self._build_client() as client:
            for query in self.SEARCH_QUERIES:
                # 尝试第三方 API
                try:
                    resp = await self._fetch_with_retry(
                        client,
                        self.THIRD_PARTY_API,
                        params={"q": query},
                    )
                    if resp and resp.status_code == 200:
                        data = resp.json()
                        items = data if isinstance(data, list) else data.get("products", data.get("data", []))
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            name = item.get("name", "") or item.get("title", "")
                            tagline = item.get("tagline", "") or item.get("description", "")
                            url = item.get("url", "") or item.get("website", "")
                            slug = item.get("slug", "")
                            combined = f"{name} {tagline}"
                            if not self._contains_keywords(combined):
                                continue
                            source_url = url or (
                                f"https://www.producthunt.com/posts/{slug}"
                                if slug else ""
                            )
                            results.append(CrawlResult(
                                source=self.name,
                                source_url=source_url,
                                title=name,
                                content=tagline[:2000],
                                raw_data={
                                    "slug": slug,
                                    "upvotes": item.get("votes_count", item.get("upvotes", 0)),
                                    "topics": item.get("topics", []),
                                },
                            ))
                except Exception as e:
                    logger.warning(
                        f"[{self.name}] 第三方 API 查询 '{query}' 失败: {e}"
                    )

                # 备选: 尝试 PH 官方搜索页面
                if not results:
                    try:
                        resp = await self._fetch_with_retry(
                            client,
                            "https://www.producthunt.com/search",
                            params={"q": query},
                        )
                        if resp and resp.status_code == 200:
                            # PH 页面是 SPA，可能无法直接解析，graceful 降级
                            pass
                    except Exception as e:
                        logger.warning(
                            f"[{self.name}] PH 官方搜索 '{query}' 失败: {e}"
                        )

                await asyncio.sleep(self.config.rate_limit_delay)

        if not results:
            logger.info(f"[{self.name}] 未获取到结果（API 可能不可用），graceful 返回空列表")

        return self._deduplicate(results)
