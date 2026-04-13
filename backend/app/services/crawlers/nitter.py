"""
X/Twitter 爬虫 — 通过 Nitter 公共实例
"""
import asyncio
import logging
import re
from typing import List

from .base import BaseCrawler, CrawlerConfig, CrawlResult

logger = logging.getLogger(__name__)


class NitterCrawler(BaseCrawler):
    """X/Twitter 爬虫（通过 Nitter 实例）"""

    name = "nitter"
    config = CrawlerConfig(
        timeout=15.0,
        max_retries=2,
        rate_limit_delay=1.0,
    )

    NITTER_INSTANCES = [
        "https://nitter.privacydev.net",
        "https://nitter.poast.org",
        "https://nitter.woodland.cafe",
    ]

    SEARCH_QUERIES = [
        "API 中转",
        "LLM relay",
        "OpenAI proxy site",
    ]

    async def _try_instance(
        self, client, base_url: str, query: str
    ) -> List[CrawlResult]:
        """尝试从单个 Nitter 实例获取结果"""
        results = []
        try:
            resp = await self._fetch_with_retry(
                client,
                f"{base_url}/search",
                params={"q": query, "f": "tweets"},
            )
            if not resp:
                return results
            # Nitter 返回 HTML，解析推文内容
            text = resp.text
            # 提取推文时间线项 — Nitter 使用 timeline-item 类
            # 简单正则匹配推文内容
            tweet_blocks = re.findall(
                r'<div class="tweet-content[^"]*"[^>]*>(.*?)</div>',
                text,
                re.DOTALL,
            )
            tweet_links = re.findall(
                r'<a[^>]+class="tweet-link"[^>]+href="([^"]+)"',
                text,
            )
            for i, block in enumerate(tweet_blocks):
                content = self._clean_html(block).strip()
                if not content or not self._contains_keywords(content):
                    continue
                link = tweet_links[i] if i < len(tweet_links) else ""
                if link and not link.startswith("http"):
                    link = f"{base_url}{link}"
                # 将 nitter 链接转换回 twitter 链接
                source_url = link.replace(base_url, "https://x.com")
                if not source_url:
                    source_url = f"{base_url}/search?q={query}"
                results.append(CrawlResult(
                    source=self.name,
                    source_url=source_url,
                    title=content[:200],
                    content=content[:2000],
                    raw_data={
                        "instance": base_url,
                        "query": query,
                    },
                ))
        except Exception as e:
            logger.warning(f"[{self.name}] 实例 {base_url} 查询失败: {e}")
        return results

    async def crawl(self) -> List[CrawlResult]:
        results = []
        async with self._build_client() as client:
            for query in self.SEARCH_QUERIES:
                fetched = False
                for instance in self.NITTER_INSTANCES:
                    instance_results = await self._try_instance(
                        client, instance, query
                    )
                    if instance_results:
                        results.extend(instance_results)
                        fetched = True
                        break  # 一个实例成功即可
                    await asyncio.sleep(0.5)
                if not fetched:
                    logger.warning(
                        f"[{self.name}] 所有 Nitter 实例均失败，查询: {query}"
                    )
                await asyncio.sleep(self.config.rate_limit_delay)
        return self._deduplicate(results)
