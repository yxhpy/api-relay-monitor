"""
HackerNews 爬虫 (via Algolia API)
"""
import asyncio
from typing import Any, Dict, List

from .base import BaseCrawler, CrawlResult, CrawlerConfig


class HackerNewsCrawler(BaseCrawler):
    """HackerNews 搜索爬虫"""

    name = "hackernews"
    config = CrawlerConfig(max_retries=2)

    SEARCH_QUERIES = [
        "openai api proxy relay site cheap",
        "claude api 中转站 推荐",
        "gpt api free relay service",
        "llm api gateway cheap alternative",
    ]

    async def crawl(self) -> List[CrawlResult]:
        results = []
        async with self._build_client() as client:
            for query in self.SEARCH_QUERIES:
                resp = await self._fetch_with_retry(
                    client,
                    "https://hn.algolia.com/api/v1/search",
                    params={"query": query, "tags": "story", "hitsPerPage": 15},
                )
                if not resp:
                    continue
                try:
                    for hit in resp.json().get("hits", []):
                        title = hit.get("title", "")
                        url = hit.get("url", "")
                        if not self._contains_keywords(title):
                            continue
                        if "github.com/" in url and "/issues/" not in url:
                            continue
                        results.append(CrawlResult(
                            source=self.name,
                            source_url=url or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                            title=title,
                            content=title[:2000],
                            raw_data={
                                "points": hit.get("points", 0),
                                "author": hit.get("author", ""),
                                "created_at": hit.get("created_at", ""),
                            },
                        ))
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"[{self.name}] 解析错误: {e}")
                await asyncio.sleep(self.config.rate_limit_delay)
        return results
