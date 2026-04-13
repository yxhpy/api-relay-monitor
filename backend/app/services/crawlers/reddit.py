"""
Reddit 搜索爬虫 — 使用公共 JSON API
"""
import asyncio
import logging
from typing import List

from .base import BaseCrawler, CrawlerConfig, CrawlResult

logger = logging.getLogger(__name__)


class RedditCrawler(BaseCrawler):
    """Reddit 搜索爬虫"""

    name = "reddit"
    config = CrawlerConfig(
        timeout=20.0,
        max_retries=2,
        rate_limit_delay=2.0,
        extra_headers={
            "User-Agent": "ApiRelayMonitor/1.0",
        },
    )

    SEARCH_QUERIES = [
        "API relay",
        "OpenAI proxy",
        "LLM API 中转",
        "ChatGPT alternative API",
    ]

    async def crawl(self) -> List[CrawlResult]:
        results = []
        async with self._build_client() as client:
            for query in self.SEARCH_QUERIES:
                try:
                    resp = await self._fetch_with_retry(
                        client,
                        "https://www.reddit.com/search.json",
                        params={
                            "q": query,
                            "sort": "relevance",
                            "t": "month",
                            "limit": 25,
                        },
                    )
                    if not resp:
                        continue
                    data = resp.json()
                    children = data.get("data", {}).get("children", [])
                    for child in children:
                        post = child.get("data", {})
                        if not post:
                            continue
                        title = post.get("title", "")
                        selftext = post.get("selftext", "") or ""
                        combined = f"{title} {selftext}"
                        if not self._contains_keywords(combined):
                            continue
                        permalink = post.get("permalink", "")
                        url = post.get("url", "")
                        source_url = (
                            f"https://www.reddit.com{permalink}"
                            if permalink
                            else url
                        )
                        results.append(CrawlResult(
                            source=self.name,
                            source_url=source_url,
                            title=title,
                            content=selftext[:2000],
                            raw_data={
                                "score": post.get("score", 0),
                                "num_comments": post.get("num_comments", 0),
                                "author": post.get("author", ""),
                                "subreddit": post.get("subreddit", ""),
                                "permalink": permalink,
                                "url": url,
                            },
                        ))
                except Exception as e:
                    logger.error(f"[{self.name}] 查询 '{query}' 解析错误: {e}")
                await asyncio.sleep(self.config.rate_limit_delay)
        return self._deduplicate(results)
