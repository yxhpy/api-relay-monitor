"""
通用 RSS 订阅爬虫 — 订阅 AI/API 相关 RSS 源
"""
import asyncio
import logging
from typing import List
from xml.etree import ElementTree as ET

from .base import BaseCrawler, CrawlerConfig, CrawlResult

logger = logging.getLogger(__name__)


class RSSFeedCrawler(BaseCrawler):
    """通用 RSS 订阅爬虫"""

    name = "rss_feed"
    config = CrawlerConfig(
        timeout=20.0,
        max_retries=2,
        rate_limit_delay=1.5,
        verify_ssl=False,
    )

    RSS_SOURCES = [
        {
            "name": "reddit_localLLaMA",
            "url": "https://www.reddit.com/r/LocalLLaMA/.rss",
        },
        {
            "name": "hackernews",
            "url": "https://news.ycombinator.com/rss",
        },
        {
            "name": "ruanyifeng",
            "url": "https://feeds.feedburner.com/ruanyifeng",
        },
    ]

    # RSS 命名空间
    NAMESPACES = {
        "atom": "http://www.w3.org/2005/Atom",
        "dc": "http://purl.org/dc/elements/1.1/",
        "content": "http://purl.org/rss/1.0/modules/content/",
    }

    def _parse_rss(self, xml_text: str, source_name: str) -> List[CrawlResult]:
        """解析 RSS/Atom XML"""
        results = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning(f"[{self.name}] XML 解析失败 ({source_name}): {e}")
            return results

        # RSS 2.0 格式: <rss><channel><item>...</item></channel></rss>
        items = root.findall(".//item")
        if not items:
            # Atom 格式: <feed><entry>...</entry></feed>
            items = root.findall(".//atom:entry", self.NAMESPACES)
        if not items:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        for item in items:
            try:
                title = self._get_text(item, "title") or ""
                link = (
                    self._get_text(item, "link")
                    or self._get_attr(item, "link", "href")
                    or ""
                )
                description = (
                    self._get_text(item, "description")
                    or self._get_text(item, "summary")
                    or self._get_text(item, "content:encoded", self.NAMESPACES)
                    or ""
                )
                description = self._clean_html(description).strip()
                author = (
                    self._get_text(item, "dc:creator", self.NAMESPACES)
                    or self._get_text(item, "author")
                    or ""
                )
                pub_date = (
                    self._get_text(item, "pubDate")
                    or self._get_text(item, "published")
                    or self._get_text(item, "updated")
                    or ""
                )

                combined = f"{title} {description}"
                if not self._contains_keywords(combined):
                    continue

                results.append(CrawlResult(
                    source=f"{self.name}_{source_name}",
                    source_url=link,
                    title=title,
                    content=description[:2000],
                    raw_data={
                        "author": author,
                        "pub_date": pub_date,
                        "rss_source": source_name,
                    },
                ))
            except Exception as e:
                logger.warning(
                    f"[{self.name}] 解析 RSS item 失败 ({source_name}): {e}"
                )
        return results

    @staticmethod
    def _get_text(element, tag: str, namespaces=None) -> str:
        """安全获取元素文本"""
        # 处理带命名空间的标签
        if ":" in tag and namespaces:
            ns_tag = tag
            el = element.find(ns_tag, namespaces)
        else:
            el = element.find(tag)
        if el is not None and el.text:
            return el.text.strip()
        return ""

    @staticmethod
    def _get_attr(element, tag: str, attr: str) -> str:
        """安全获取元素属性"""
        el = element.find(tag)
        if el is not None:
            return el.get(attr, "")
        # Atom link: <link href="..." />
        return ""

    async def crawl(self) -> List[CrawlResult]:
        results = []
        async with self._build_client() as client:
            for source in self.RSS_SOURCES:
                source_name = source["name"]
                url = source["url"]
                try:
                    resp = await self._fetch_with_retry(client, url)
                    if not resp or resp.status_code != 200:
                        logger.warning(
                            f"[{self.name}] 获取 RSS 失败: {source_name}"
                        )
                        continue
                    rss_results = self._parse_rss(resp.text, source_name)
                    results.extend(rss_results)
                    logger.info(
                        f"[{self.name}] {source_name}: "
                        f"{len(rss_results)} 条相关内容"
                    )
                except Exception as e:
                    logger.error(
                        f"[{self.name}] 爬取 {source_name} 失败: {e}"
                    )
                await asyncio.sleep(self.config.rate_limit_delay)
        return self._deduplicate(results)
