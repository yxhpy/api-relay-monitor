"""
API Relay Monitor - 多源爬虫服务
从 linux.do, V2EX, GitHub 等数据源爬取中转站相关信息
"""

import asyncio
import json
import logging
import re
import warnings
from datetime import datetime
from typing import List, Dict, Any, Optional

import httpx

from app.config import settings

# 抑制 verify=False 相关的 SSL 警告
warnings.filterwarnings("ignore", message=".*SSL.*")

logger = logging.getLogger(__name__)

# 中转站相关关键词（用于本地过滤）
RELAY_KEYWORDS = [
    "中转", "relay", "one-api", "new-api", "API代理", "API转发",
    "openai proxy", "claude proxy", "gpt 代理", "llm proxy",
    "api-proxy", "api relay", "官转", "逆向", "api 中转",
    "大模型", "api 转发", "token", "api key", "额度",
]


class MultiSourceCrawler:
    """多源数据爬虫"""

    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.timeout = 30.0

    def _contains_keywords(self, text: str) -> bool:
        """检查文本是否包含中转站相关关键词"""
        if not text:
            return False
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in RELAY_KEYWORDS)

    async def crawl_linux_do(self) -> List[Dict[str, Any]]:
        """
        爬取 linux.do 论坛（Discourse）
        策略：用 /latest.json 和 /top.json 获取最新/热门帖子，本地关键词过滤
        Cloudflare 反爬较严，需要完整浏览器 headers + 重试
        """
        results = []
        linux_do_headers = {
            **self.headers,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0, read=20.0, write=10.0),
            headers=linux_do_headers,
            follow_redirects=True,
            verify=False,
            http2=True,  # Cloudflare 对 HTTP/2 更友好
        ) as client:
            for endpoint in ["/latest.json", "/top.json"]:
                for attempt in range(3):
                    try:
                        resp = await client.get(
                            f"{settings.LINUX_DO_BASE_URL}{endpoint}",
                        )
                        if resp.status_code == 200:
                            break
                        if resp.status_code in (403, 429, 503) and attempt < 2:
                            wait = 3 * (attempt + 1)
                            logger.warning(f"[linux.do] {endpoint} returned {resp.status_code}, retry {attempt+1}/3 after {wait}s")
                            await asyncio.sleep(wait)
                            continue
                        logger.warning(f"[linux.do] {endpoint} returned {resp.status_code}")
                        break
                    except (httpx.RemoteProtocolError, httpx.ReadError) as e:
                        if attempt < 2:
                            wait = 3 * (attempt + 1)
                            logger.warning(f"[linux.do] 连接中断 retry {attempt+1}/3: {e}")
                            await asyncio.sleep(wait)
                            continue
                        logger.error(f"[linux.do 爬取错误] endpoint={endpoint}, error={e}")
                        break
                else:
                    continue

                if resp.status_code != 200:
                    continue

                try:
                    data = resp.json()
                    topics = data.get("topic_list", {}).get("topics", [])
                    # 获取帖子内容映射
                    posts_data = {}
                    for post in data.get("post_stream", {}).get("posts", []):
                        posts_data[post.get("topic_id")] = post

                    for topic in topics[:50]:
                        title = topic.get("title", "")
                        # 本地关键词匹配
                        if not self._contains_keywords(title):
                            continue

                        # 尝试获取帖子内容
                        content = ""
                        topic_post = posts_data.get(topic.get("id"))
                        if topic_post:
                            content = re.sub(r"<[^>]+>", "", topic_post.get("cooked", ""))

                        results.append({
                            "source": "linux_do",
                            "source_url": (
                                f"{settings.LINUX_DO_BASE_URL}/t/"
                                f"{topic.get('slug', '')}/{topic.get('id', '')}"
                            ),
                            "title": title,
                            "content": content[:2000],
                            "raw_data": {
                                "topic_id": topic.get("id"),
                                "category_id": topic.get("category_id"),
                                "likes": topic.get("like_count", 0),
                                "views": topic.get("views", 0),
                                "reply_count": topic.get("posts_count", 0),
                                "endpoint": endpoint,
                            },
                        })
                except Exception as e:
                    logger.error(f"[linux.do 解析错误] endpoint={endpoint}, error={e}")
                    continue

        logger.info(f"[linux.do] 获取 {len(results)} 条相关帖子")
        return results

    async def crawl_v2ex(self) -> List[Dict[str, Any]]:
        """
        爬取 V2EX 论坛
        使用公开 API: /api/topics/latest.json 和 /api/topics/hot.json
        """
        results = []

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self.headers,
            follow_redirects=True,
            verify=False,  # 容器内 SSL 兼容
        ) as client:
            for endpoint in [
                "https://www.v2ex.com/api/topics/latest.json",
                "https://www.v2ex.com/api/topics/hot.json",
            ]:
                for attempt in range(3):
                    try:
                        resp = await client.get(endpoint)
                        if resp.status_code == 200:
                            break
                        if resp.status_code in (429, 503) and attempt < 2:
                            wait = 2 ** attempt
                            logger.warning(f"[V2EX] {endpoint} returned {resp.status_code}, retry {attempt+1}/3 after {wait}s")
                            await asyncio.sleep(wait)
                            continue
                        logger.warning(f"[V2EX] {endpoint} returned {resp.status_code}")
                        break
                    except Exception as e:
                        if attempt < 2:
                            logger.warning(f"[V2EX] 请求失败 retry {attempt+1}/3: {e}")
                            await asyncio.sleep(2 ** attempt)
                            continue
                        logger.error(f"[V2EX 爬取错误] endpoint={endpoint}, error={e}")
                        break
                else:
                    continue

                if resp.status_code != 200:
                    continue

                try:
                    data = resp.json()
                    topics = data if isinstance(data, list) else data.get("items", [])

                    for topic in topics:
                        title = topic.get("title", "")
                        content = topic.get("content", "") or topic.get("content_rendered", "") or ""

                        # 本地关键词匹配
                        if not self._contains_keywords(f"{title} {content}"):
                            continue

                        content_clean = re.sub(r"<[^>]+>", "", content)

                        results.append({
                            "source": "v2ex",
                            "source_url": (
                                f"https://www.v2ex.com/t/{topic.get('id', '')}"
                                if topic.get("id") else topic.get("url", "")
                            ),
                            "title": title,
                            "content": content_clean[:2000],
                            "raw_data": {
                                "topic_id": topic.get("id"),
                                "node": topic.get("node", {}).get("name", ""),
                                "replies": topic.get("replies", 0),
                                "member": topic.get("member", {}).get("username", ""),
                                "endpoint": endpoint.split("/")[-1],
                            },
                        })
                except Exception as e:
                    logger.error(f"[V2EX 解析错误] endpoint={endpoint}, error={e}")

        logger.info(f"[V2EX] 获取 {len(results)} 条相关帖子")
        return results

    async def crawl_github(self) -> List[Dict[str, Any]]:
        """
        爬取 GitHub
        搜索与 API 中转/代理相关的仓库（精确查询，减少噪音）
        """
        results = []
        search_queries = [
            "one-api openai",
            "new-api llm",
            "openai-proxy",
            "claude-proxy",
            "llm-relay api",
            "api-gateway openai claude",
        ]

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                **self.headers,
                "Accept": "application/vnd.github.v3+json",
            },
            follow_redirects=True,
        ) as client:
            for query in search_queries:
                try:
                    resp = await client.get(
                        f"{settings.GITHUB_API_URL}/search/repositories",
                        params={
                            "q": query,
                            "sort": "stars",
                            "order": "desc",
                            "per_page": 10,
                        },
                    )
                    if resp.status_code != 200:
                        logger.warning(f"[GitHub] search '{query}' returned {resp.status_code}")
                        continue

                    data = resp.json()
                    repos = data.get("items", [])

                    for repo in repos:
                        # 过滤：stars > 0 或有描述
                        stars = repo.get("stargazers_count", 0)
                        desc = repo.get("description") or ""
                        if stars == 0 and not desc:
                            continue

                        results.append({
                            "source": "github",
                            "source_url": repo.get("html_url", ""),
                            "title": repo.get("full_name", ""),
                            "content": (
                                f"Stars: {stars} | "
                                f"Forks: {repo.get('forks_count', 0)} | "
                                f"Language: {repo.get('language', 'N/A')}\n"
                                f"{desc}"
                            ),
                            "raw_data": {
                                "full_name": repo.get("full_name"),
                                "description": desc,
                                "stars": stars,
                                "forks": repo.get("forks_count"),
                                "language": repo.get("language"),
                                "topics": repo.get("topics", []),
                                "homepage": repo.get("homepage"),
                                "search_query": query,
                            },
                        })
                except Exception as e:
                    logger.error(f"[GitHub 爬取错误] query={query}, error={e}")
                    continue

        # 去重（按 full_name）
        seen = set()
        unique_results = []
        for r in results:
            name = r.get("raw_data", {}).get("full_name", "")
            if name not in seen:
                seen.add(name)
                unique_results.append(r)

        logger.info(f"[GitHub] 获取 {len(unique_results)} 个相关仓库（去重前 {len(results)}）")
        return unique_results

    async def crawl_rss(self) -> List[Dict[str, Any]]:
        """
        爬取 RSS 源
        备选方案：直接从可用数据源获取补充数据
        """
        results = []

        # RSSHub 公共实例已限流，改用直接抓取补充数据
        # Hacker News Search API (Algolia) — 无需认证，稳定
        search_queries = [
            "openai proxy api relay",
            "llm api gateway",
            "claude proxy",
        ]
        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self.headers,
            follow_redirects=True,
        ) as client:
            for query in search_queries:
                try:
                    resp = await client.get(
                        "https://hn.algolia.com/api/v1/search",
                        params={
                            "query": query,
                            "tags": "story",
                            "hitsPerPage": 20,
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for hit in data.get("hits", []):
                            title = hit.get("title", "")
                            if not self._contains_keywords(title):
                                continue
                            # 去重
                            if any(r["source_url"] == hit.get("url", "") for r in results):
                                continue
                            results.append({
                                "source": "rss",
                                "source_url": hit.get("url", f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"),
                                "title": title,
                                "content": hit.get("title", "")[:2000],
                                "raw_data": {
                                    "points": hit.get("points", 0),
                                    "author": hit.get("author", ""),
                                    "created_at": hit.get("created_at", ""),
                                    "feed_type": "hackernews",
                                },
                            })
                        await asyncio.sleep(0.5)  # 避免 Algolia 限流
                except Exception as e:
                    logger.error(f"[RSS/HN 爬取错误] query={query}, error={e}")

        return results

    async def crawl_all(self) -> List[Dict[str, Any]]:
        """执行所有爬取任务"""
        tasks = [
            ("linux_do", self.crawl_linux_do),
            ("v2ex", self.crawl_v2ex),
            ("github", self.crawl_github),
            ("rss", self.crawl_rss),
        ]

        results = await asyncio.gather(
            *[crawl_func() for _, crawl_func in tasks],
            return_exceptions=True,
        )

        all_results = []
        for (source_name, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(f"[爬取失败] {source_name}: {result}")
            else:
                all_results.extend(result)
                logger.info(f"[爬取完成] {source_name}: {len(result)} 条结果")

        return all_results
