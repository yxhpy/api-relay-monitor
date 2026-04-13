"""
GitHub Issues/Discussions 爬虫
"""
from typing import Any, Dict, List

from .base import BaseCrawler, CrawlResult, CrawlerConfig


class GitHubCrawler(BaseCrawler):
    """GitHub Issues/Discussions 搜索爬虫"""

    name = "github"
    config = CrawlerConfig(
        extra_headers={"Accept": "application/vnd.github.v3+json"},
        max_retries=2,
    )

    ISSUE_QUERIES = [
        "API中转站 推荐 site:github.com",
        "openai relay site cheap",
        "claude api proxy cheap free",
        "gpt api 中转 公益 免费",
        "one-api new-api 中转站推荐 倍率",
    ]

    AWESOME_QUERIES = [
        "awesome openai api relay proxy list",
        "awesome llm api gateway list",
    ]

    def __init__(self, api_url: str = "https://api.github.com"):
        super().__init__()
        self.api_url = api_url

    async def crawl(self) -> List[CrawlResult]:
        import asyncio
        results = []
        async with self._build_client() as client:
            # 搜索 Issues/Discussions
            for query in self.ISSUE_QUERIES:
                resp = await self._fetch_with_retry(
                    client,
                    f"{self.api_url}/search/issues",
                    params={"q": query, "sort": "updated", "order": "desc", "per_page": 10},
                )
                if not resp:
                    continue
                try:
                    for item in resp.json().get("items", []):
                        title = item.get("title", "")
                        body = item.get("body", "") or ""
                        html_url = item.get("html_url", "")
                        if "/issues/" not in html_url and "/pull/" not in html_url:
                            continue
                        if not self._contains_keywords(f"{title} {body[:500]}"):
                            continue
                        results.append(CrawlResult(
                            source=f"{self.name}_discussions",
                            source_url=html_url,
                            title=title,
                            content=body[:2000],
                            raw_data={
                                "issue_number": item.get("number"),
                                "state": item.get("state"),
                                "comments": item.get("comments", 0),
                                "reactions": item.get("reactions", {}).get("total_count", 0),
                            },
                        ))
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"[{self.name}] issues 解析错误: {e}")
                await asyncio.sleep(self.config.rate_limit_delay)

            # 搜索 Awesome 列表
            for query in self.AWESOME_QUERIES:
                resp = await self._fetch_with_retry(
                    client,
                    f"{self.api_url}/search/repositories",
                    params={"q": query, "sort": "stars", "order": "desc", "per_page": 5},
                )
                if not resp:
                    continue
                try:
                    for repo in resp.json().get("items", []):
                        desc = repo.get("description") or ""
                        if not desc or "awesome" not in desc.lower():
                            continue
                        results.append(CrawlResult(
                            source=f"{self.name}_awesome",
                            source_url=repo.get("html_url", ""),
                            title=repo.get("full_name", ""),
                            content=f"Stars: {repo.get('stargazers_count', 0)}\n{desc}",
                            raw_data={"is_awesome_list": True, "stars": repo.get("stargazers_count", 0)},
                        ))
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"[{self.name}] awesome 解析错误: {e}")
        return results
