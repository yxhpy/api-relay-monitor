"""
知乎搜索爬虫 — 使用知乎搜索 API
"""
import asyncio
import logging
from typing import List

from .base import BaseCrawler, CrawlerConfig, CrawlResult

logger = logging.getLogger(__name__)


class ZhihuCrawler(BaseCrawler):
    """知乎搜索爬虫"""

    name = "zhihu"
    config = CrawlerConfig(
        timeout=15.0,
        max_retries=2,
        rate_limit_delay=2.0,
        extra_headers={
            "Referer": "https://www.zhihu.com/",
            "Origin": "https://www.zhihu.com",
        },
    )

    SEARCH_QUERIES = [
        "API中转",
        "LLM API 代理",
        "OpenAI 中转站推荐",
    ]

    SEARCH_API = "https://www.zhihu.com/api/v4/search_v3"

    async def crawl(self) -> List[CrawlResult]:
        results = []
        async with self._build_client() as client:
            for query in self.SEARCH_QUERIES:
                try:
                    resp = await self._fetch_with_retry(
                        client,
                        self.SEARCH_API,
                        params={
                            "q": query,
                            "t": "general",
                            "correction": 1,
                            "offset": 0,
                            "limit": 20,
                        },
                    )
                    if not resp:
                        continue
                    data = resp.json()
                    items = data.get("data", [])
                    for item in items:
                        # 知乎搜索结果结构: item.object 包含具体内容
                        obj = item.get("object", {}) or item
                        if isinstance(obj, str):
                            continue
                        title = obj.get("title", "") or obj.get("name", "")
                        excerpt = obj.get("excerpt", "") or obj.get("content", "")
                        url = obj.get("url", "")

                        # 清理 title 中可能的 HTML
                        title = self._clean_html(title).strip()
                        excerpt = self._clean_html(excerpt).strip()

                        combined = f"{title} {excerpt}"
                        if not self._contains_keywords(combined):
                            continue

                        # 知乎 URL 可能需要补全
                        if url and not url.startswith("http"):
                            url = f"https://www.zhihu.com{url}"

                        results.append(CrawlResult(
                            source=self.name,
                            source_url=url or "",
                            title=title,
                            content=excerpt[:2000],
                            raw_data={
                                "type": item.get("type", ""),
                                "id": obj.get("id", ""),
                                "author": (
                                    obj.get("author", {}).get("name", "")
                                    if isinstance(obj.get("author"), dict)
                                    else ""
                                ),
                                "voteup_count": obj.get("voteup_count", 0),
                                "comment_count": obj.get("comment_count", 0),
                            },
                        ))
                except Exception as e:
                    logger.error(f"[{self.name}] 查询 '{query}' 解析错误: {e}")
                await asyncio.sleep(self.config.rate_limit_delay)
        return self._deduplicate(results)
