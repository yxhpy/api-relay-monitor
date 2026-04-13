"""
V2EX 论坛爬虫
"""
import re
from typing import Any, Dict, List

from .base import BaseCrawler, CrawlResult, CrawlerConfig


class V2EXCrawler(BaseCrawler):
    """V2EX 论坛爬虫"""

    name = "v2ex"
    config = CrawlerConfig(
        verify_ssl=False,
        backoff_base=2.0,
        max_retries=3,
    )

    ENDPOINTS = [
        "https://www.v2ex.com/api/topics/latest.json",
        "https://www.v2ex.com/api/topics/hot.json",
        "https://www.v2ex.com/api/nodes/python/topics.json?p=1",
        "https://www.v2ex.com/api/nodes/ai/topics.json?p=1",
    ]

    async def crawl(self) -> List[CrawlResult]:
        import asyncio
        results = []
        async with self._build_client() as client:
            for endpoint in self.ENDPOINTS:
                resp = await self._fetch_with_retry(client, endpoint)
                if not resp:
                    continue
                try:
                    data = resp.json()
                    topics = data if isinstance(data, list) else data.get("items", [])
                    for t in topics:
                        title = t.get("title", "")
                        content = t.get("content", "") or t.get("content_rendered", "") or ""
                        if not self._contains_keywords(f"{title} {content}"):
                            continue
                        content_clean = self._clean_html(content)
                        url = f"https://www.v2ex.com/t/{t['id']}" if t.get("id") else t.get("url", "")
                        results.append(CrawlResult(
                            source=self.name,
                            source_url=url,
                            title=title,
                            content=content_clean[:2000],
                            raw_data={
                                "topic_id": t.get("id"),
                                "node": t.get("node", {}).get("name", ""),
                                "replies": t.get("replies", 0),
                                "member": t.get("member", {}).get("username", ""),
                            },
                        ))
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"[{self.name}] 解析错误: {endpoint}, {e}")
                await asyncio.sleep(self.config.rate_limit_delay)
        return results
