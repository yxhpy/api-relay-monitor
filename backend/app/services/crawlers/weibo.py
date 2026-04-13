"""
微博搜索爬虫 — 使用微博移动端 API
"""
import asyncio
import logging
from typing import List
from urllib.parse import quote

from .base import BaseCrawler, CrawlerConfig, CrawlResult

logger = logging.getLogger(__name__)


class WeiboCrawler(BaseCrawler):
    """微博搜索爬虫"""

    name = "weibo"
    config = CrawlerConfig(
        timeout=15.0,
        max_retries=2,
        rate_limit_delay=2.0,
        extra_headers={
            "Referer": "https://m.weibo.cn/",
        },
    )

    SEARCH_QUERIES = [
        "API中转",
        "LLM API",
        "OpenAI代理",
    ]

    SEARCH_API = "https://m.weibo.cn/api/container/getIndex"

    async def crawl(self) -> List[CrawlResult]:
        results = []
        async with self._build_client() as client:
            for query in self.SEARCH_QUERIES:
                try:
                    containerid = f"100103type=1&q={query}"
                    resp = await self._fetch_with_retry(
                        client,
                        self.SEARCH_API,
                        params={
                            "containerid": containerid,
                        },
                    )
                    if not resp:
                        continue
                    # 确保正确编码: 微博API返回UTF-8, 显式解码避免乱码
                    try:
                        data = resp.json()
                    except Exception:
                        # fallback: 手动UTF-8解码
                        resp.encoding = "utf-8"
                        data = resp.json()
                    # 微博返回结构: data.cards -> card_group -> mblog
                    cards = data.get("data", {}).get("cards", [])
                    for card in cards:
                        # card_group 包含多条微博，或 card 直接包含 mblog
                        card_group = card.get("card_group", [])
                        mblogs = []
                        if card_group:
                            for cg in card_group:
                                mblog = cg.get("mblog")
                                if mblog:
                                    mblogs.append(mblog)
                        else:
                            mblog = card.get("mblog")
                            if mblog:
                                mblogs.append(mblog)

                        for mblog in mblogs:
                            try:
                                text = mblog.get("text", "") or ""
                                text_clean = self._clean_html(text).strip()
                                if not self._contains_keywords(text_clean):
                                    continue
                                # 提取微博 ID 构造 URL
                                bid = mblog.get("bid", "") or str(mblog.get("id", ""))
                                user = mblog.get("user", {}) or {}
                                screen_name = user.get("screen_name", "")
                                source_url = (
                                    f"https://m.weibo.cn/detail/{bid}"
                                    if bid
                                    else ""
                                )
                                results.append(CrawlResult(
                                    source=self.name,
                                    source_url=source_url,
                                    title=f"@{screen_name}: {text_clean[:100]}",
                                    content=text_clean[:2000],
                                    raw_data={
                                        "bid": bid,
                                        "screen_name": screen_name,
                                        "reposts_count": mblog.get("reposts_count", 0),
                                        "comments_count": mblog.get("comments_count", 0),
                                        "attitudes_count": mblog.get("attitudes_count", 0),
                                        "text_length": mblog.get("textLength", 0),
                                    },
                                ))
                            except Exception as e:
                                logger.warning(
                                    f"[{self.name}] 解析单条微博失败: {e}"
                                )
                except Exception as e:
                    logger.error(f"[{self.name}] 查询 '{query}' 解析错误: {e}")
                await asyncio.sleep(self.config.rate_limit_delay)
        return self._deduplicate(results)
