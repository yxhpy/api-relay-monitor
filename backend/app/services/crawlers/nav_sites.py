"""
API 导航站爬虫 — 爬取免费 LLM API 资源聚合列表
"""
import asyncio
import logging
import re
from typing import List

from .base import BaseCrawler, CrawlerConfig, CrawlResult

logger = logging.getLogger(__name__)


class NavSitesCrawler(BaseCrawler):
    """API 导航/聚合站爬虫"""

    name = "nav_sites"
    config = CrawlerConfig(
        timeout=15.0,
        max_retries=2,
        rate_limit_delay=1.0,
    )

    # GitHub raw README 地址
    AWESOME_README_URL = (
        "https://raw.githubusercontent.com/cheahjs/free-llm-api-resources/main/README.md"
    )

    # Markdown 表格行正则: | name | url | description | ...
    TABLE_ROW_RE = re.compile(
        r"\|\s*\[([^\]]*)\]\(([^)]*)\)\s*\|\s*([^|]*)\|"
    )
    # 备选: 普通表格行 (可能没有链接)
    PLAIN_ROW_RE = re.compile(
        r"\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|"
    )

    def _parse_markdown_table(self, md_text: str) -> List[CrawlResult]:
        """解析 Markdown 表格，提取站点名、URL、描述"""
        results = []
        lines = md_text.split("\n")
        for line in lines:
            line = line.strip()
            if not line.startswith("|"):
                continue
            # 跳过分隔行 |---|---|
            if re.match(r"^\|[\s\-:|]+\|$", line):
                continue

            # 尝试带链接的格式: | [name](url) | description | ... |
            m = self.TABLE_ROW_RE.search(line)
            if m:
                name, url, desc = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            else:
                # 普通表格: | name | url | description |
                m2 = self.PLAIN_ROW_RE.search(line)
                if not m2:
                    continue
                name, url, desc = (
                    m2.group(1).strip(),
                    m2.group(2).strip(),
                    m2.group(3).strip(),
                )

            # 跳过表头
            if name.lower() in ("name", "site", "resource", "项目", "名称"):
                continue

            combined = f"{name} {url} {desc}"
            if not self._contains_keywords(combined):
                continue

            # 清理 URL
            if url and not url.startswith("http"):
                # 可能是纯文本 URL
                url_extract = re.search(r"https?://[^\s)>]+", url)
                url = url_extract.group(0) if url_extract else ""

            results.append(CrawlResult(
                source=self.name,
                source_url=url or f"https://github.com/cheahjs/free-llm-api-resources",
                title=name,
                content=desc[:2000],
                raw_data={
                    "source_list": "free-llm-api-resources",
                    "url": url,
                    "description": desc,
                },
            ))
        return results

    async def crawl(self) -> List[CrawlResult]:
        results = []
        async with self._build_client() as client:
            # 爬取 free-llm-api-resources README
            try:
                resp = await self._fetch_with_retry(client, self.AWESOME_README_URL)
                if resp and resp.status_code == 200:
                    md_text = resp.text
                    table_results = self._parse_markdown_table(md_text)
                    results.extend(table_results)
                    logger.info(
                        f"[{self.name}] 从 free-llm-api-resources 解析到 "
                        f"{len(table_results)} 条记录"
                    )
                else:
                    logger.warning(f"[{self.name}] 获取 README 失败")
            except Exception as e:
                logger.error(f"[{self.name}] 爬取 free-llm-api-resources 失败: {e}")

            await asyncio.sleep(self.config.rate_limit_delay)

            # 尝试 api-search.io（可能无公开 API，graceful 降级）
            try:
                resp = await self._fetch_with_retry(
                    client,
                    "https://api-search.io/",
                )
                if resp and resp.status_code == 200:
                    # 简单解析 HTML 中的链接和描述
                    text = resp.text
                    # 提取页面中的站点引用
                    links = re.findall(
                        r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>',
                        text,
                    )
                    for href, anchor in links:
                        anchor_clean = self._clean_html(anchor).strip()
                        if not self._contains_keywords(f"{anchor_clean} {href}"):
                            continue
                        results.append(CrawlResult(
                            source=f"{self.name}_apiseek",
                            source_url=href,
                            title=anchor_clean or href,
                            content=anchor_clean[:2000],
                            raw_data={"source_list": "api-search.io"},
                        ))
            except Exception as e:
                logger.warning(f"[{self.name}] api-search.io 不可用: {e}")

        return self._deduplicate(results)
