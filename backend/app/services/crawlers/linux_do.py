"""
linux.do 论坛爬虫 (Discourse API)
"""
import asyncio
import re
from typing import Any, Dict, List, Optional

from .base import BaseCrawler, CrawlResult, CrawlerConfig


class LinuxDoCrawler(BaseCrawler):
    """linux.do 论坛（Discourse）爬虫"""

    name = "linux_do"
    config = CrawlerConfig(
        extra_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Cache-Control": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        },
        verify_ssl=False,
        http2=True,
        connect_timeout=10.0,
        backoff_base=3.0,
        max_retries=3,
    )

    def __init__(self, base_url: str = "https://linux.do"):
        super().__init__()
        self.base_url = base_url

    def _endpoints(self) -> List[str]:
        return [
            f"{self.base_url}/latest.json",
            f"{self.base_url}/top.json",
            f"{self.base_url}/search.json?q=中转站%20order%3Alatest",
            f"{self.base_url}/search.json?q=API%20proxy%20order%3Alatest",
            f"{self.base_url}/search.json?q=官转%20性价比%20order%3Alatest",
            f"{self.base_url}/search.json?q=公益%20免费%20API%20order%3Alatest",
            f"{self.base_url}/tag/api.json",
        ]

    async def crawl(self) -> List[CrawlResult]:
        results = []
        async with self._build_client() as client:
            for endpoint in self._endpoints():
                resp = await self._fetch_with_retry(client, endpoint)
                if not resp:
                    continue
                try:
                    data = resp.json()
                    parsed = self._parse(data, endpoint)
                    results.extend(parsed)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"[{self.name}] 解析错误: {endpoint}, {e}")
                await asyncio.sleep(self.config.rate_limit_delay)

        return results

    def _parse(self, data: dict, endpoint: str) -> List[CrawlResult]:
        results = []

        # Discourse tag 页面
        if "/tag/" in endpoint:
            topics = data.get("topic_list", {}).get("topics", [])
            for t in topics[:30]:
                title = t.get("title", "")
                if not self._contains_keywords(title):
                    continue
                results.append(CrawlResult(
                    source=self.name,
                    source_url=f"{self.base_url}/t/{t.get('slug', '')}/{t.get('id', '')}",
                    title=title,
                    content=title,
                    raw_data={"topic_id": t.get("id"), "views": t.get("views", 0), "likes": t.get("like_count", 0)},
                ))
            return results

        # 搜索结果
        if "/search.json" in endpoint:
            for t in data.get("topics", []):
                title = t.get("title", "")
                if not self._contains_keywords(title):
                    continue
                results.append(CrawlResult(
                    source=self.name,
                    source_url=f"{self.base_url}/t/{t.get('slug', '')}/{t.get('id', '')}",
                    title=title,
                    content=title,
                    raw_data={"topic_id": t.get("id"), "category_id": t.get("category_id"),
                              "likes": t.get("like_count", 0), "views": t.get("views", 0), "endpoint": "search"},
                ))
            return results

        # latest / top 结果
        topics = data.get("topic_list", {}).get("topics", [])
        posts_map = {}
        for p in data.get("post_stream", {}).get("posts", []):
            posts_map[p.get("topic_id")] = p

        for t in topics[:80]:
            title = t.get("title", "")
            if not self._contains_keywords(title):
                continue
            content = ""
            tp = posts_map.get(t.get("id"))
            if tp:
                content = self._clean_html(tp.get("cooked", ""))
            results.append(CrawlResult(
                source=self.name,
                source_url=f"{self.base_url}/t/{t.get('slug', '')}/{t.get('id', '')}",
                title=title,
                content=content[:2000],
                raw_data={"topic_id": t.get("id"), "category_id": t.get("category_id"),
                          "likes": t.get("like_count", 0), "views": t.get("views", 0),
                          "reply_count": t.get("posts_count", 0)},
            ))
        return results
