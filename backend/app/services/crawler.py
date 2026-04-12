"""
API Relay Monitor - 多源爬虫服务
从 linux.do, V2EX, GitHub, RSS 等数据源爬取中转站相关信息
"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional

import httpx

from app.config import settings


class MultiSourceCrawler:
    """多源数据爬虫"""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/html, */*",
        }
        self.timeout = 30.0

    async def crawl_linux_do(self) -> List[Dict[str, Any]]:
        """
        爬取 linux.do 论坛（Discourse 格式）
        搜索与 API 中转站相关的帖子
        """
        results = []
        search_terms = [
            "API 中转",
            "API relay",
            "中转站",
            "one-api",
            "new-api",
            "GPT 代理",
            "Claude 中转",
        ]

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self.headers,
            follow_redirects=True,
        ) as client:
            for term in search_terms:
                try:
                    # Discourse 搜索 API
                    resp = await client.get(
                        f"{settings.LINUX_DO_BASE_URL}/search.json",
                        params={"q": term, "order": "latest"},
                    )
                    if resp.status_code != 200:
                        continue

                    data = resp.json()

                    # 处理帖子列表
                    topics = data.get("topics", [])
                    posts = data.get("posts", [])

                    for topic in topics[:10]:
                        # 查找对应的帖子内容
                        topic_posts = [
                            p for p in posts
                            if p.get("topic_id") == topic.get("id")
                        ]
                        content = topic_posts[0].get("cooked", "") if topic_posts else ""
                        # 去除 HTML 标签
                        import re
                        content_clean = re.sub(r"<[^>]+>", "", content)

                        results.append({
                            "source": "linux_do",
                            "source_url": f"{settings.LINUX_DO_BASE_URL}/t/{topic.get('slug', '')}/{topic.get('id', '')}",
                            "title": topic.get("title", ""),
                            "content": content_clean[:2000],  # 限制内容长度
                            "raw_data": {
                                "topic_id": topic.get("id"),
                                "category_id": topic.get("category_id"),
                                "likes": topic.get("like_count", 0),
                                "views": topic.get("views", 0),
                                "reply_count": topic.get("posts_count", 0),
                                "search_term": term,
                            },
                        })
                except Exception as e:
                    print(f"[linux.do 爬取错误] term={term}, error={e}")
                    continue

        return results

    async def crawl_v2ex(self) -> List[Dict[str, Any]]:
        """
        爬取 V2EX 论坛
        搜索与 API 中转站相关的主题
        """
        results = []
        search_terms = ["API 中转", "one-api", "中转站", "GPT API 代理", "LLM API relay"]

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self.headers,
            follow_redirects=True,
        ) as client:
            for term in search_terms:
                try:
                    # V2EX 搜索 API（通过 Google 自定义搜索）
                    # 先尝试 V2EX 的节点 API
                    # 常见相关节点：python, create, share
                    node_names = ["create", "share", "python", "programmer"]

                    for node in node_names:
                        try:
                            resp = await client.get(
                                f"{settings.V2EX_BASE_URL}/api/v2/nodes/{node}/topics",
                                params={"p": 1, "limit": 20},
                            )
                            if resp.status_code != 200:
                                continue

                            data = resp.json()
                            topics = data if isinstance(data, list) else data.get("items", [])

                            for topic in topics:
                                title = topic.get("title", "")
                                content = topic.get("content", "") or topic.get("content_rendered", "")

                                # 简单关键词匹配
                                keywords = ["中转", "relay", "one-api", "new-api", "API代理", "API转发"]
                                if not any(kw.lower() in title.lower() or kw.lower() in content.lower() for kw in keywords):
                                    continue

                                import re
                                content_clean = re.sub(r"<[^>]+>", "", content)

                                results.append({
                                    "source": "v2ex",
                                    "source_url": topic.get("url", ""),
                                    "title": title,
                                    "content": content_clean[:2000],
                                    "raw_data": {
                                        "topic_id": topic.get("id"),
                                        "node": node,
                                        "replies": topic.get("replies", 0),
                                        "member": topic.get("member", {}).get("username", ""),
                                        "search_term": term,
                                    },
                                })
                        except Exception:
                            continue

                except Exception as e:
                    print(f"[V2EX 爬取错误] term={term}, error={e}")
                    continue

        return results

    async def crawl_github(self) -> List[Dict[str, Any]]:
        """
        爬取 GitHub
        搜索与 API 中转/代理相关的仓库
        """
        results = []
        search_queries = [
            "one-api",
            "llm-relay",
            "api-proxy llm",
            "openai-proxy",
            "claude-proxy",
            "new-api",
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
                            "sort": "updated",
                            "order": "desc",
                            "per_page": 10,
                        },
                    )
                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    repos = data.get("items", [])

                    for repo in repos:
                        results.append({
                            "source": "github",
                            "source_url": repo.get("html_url", ""),
                            "title": repo.get("full_name", ""),
                            "content": (
                                f"Stars: {repo.get('stargazers_count', 0)} | "
                                f"Forks: {repo.get('forks_count', 0)} | "
                                f"Language: {repo.get('language', 'N/A')}\n"
                                f"{repo.get('description', '')}"
                            ),
                            "raw_data": {
                                "full_name": repo.get("full_name"),
                                "description": repo.get("description"),
                                "stars": repo.get("stargazers_count"),
                                "forks": repo.get("forks_count"),
                                "language": repo.get("language"),
                                "topics": repo.get("topics", []),
                                "homepage": repo.get("homepage"),
                                "search_query": query,
                            },
                        })
                except Exception as e:
                    print(f"[GitHub 爬取错误] query={query}, error={e}")
                    continue

        return results

    async def crawl_rss(self) -> List[Dict[str, Any]]:
        """
        爬取 RSS 源
        使用 RSSHub 获取相关内容
        """
        results = []
        import feedparser

        # RSSHub 源列表
        rss_feeds = [
            # V2EX 最新话题
            f"{settings.RSS_HUB_URL}/v2ex/topics/latest",
            # GitHub Trending
            f"{settings.RSS_HUB_URL}/github/trending/daily/python",
            # Hacker News
            f"{settings.RSS_HUB_URL}/hackernews/best",
        ]

        keywords = ["api", "relay", "proxy", "llm", "openai", "claude", "gpt", "中转", "代理"]

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self.headers,
            follow_redirects=True,
        ) as client:
            for feed_url in rss_feeds:
                try:
                    resp = await client.get(feed_url)
                    if resp.status_code != 200:
                        continue

                    # feedparser 解析
                    feed = feedparser.parse(resp.text)

                    for entry in feed.entries[:20]:
                        title = entry.get("title", "")
                        summary = entry.get("summary", "") or entry.get("description", "")

                        # 关键词匹配
                        text = f"{title} {summary}".lower()
                        if not any(kw.lower() in text for kw in keywords):
                            continue

                        import re
                        summary_clean = re.sub(r"<[^>]+>", "", summary)

                        results.append({
                            "source": "rss",
                            "source_url": entry.get("link", ""),
                            "title": title,
                            "content": summary_clean[:2000],
                            "raw_data": {
                                "feed_url": feed_url,
                                "author": entry.get("author", ""),
                                "published": entry.get("published", ""),
                                "tags": [tag.get("term", "") for tag in entry.get("tags", [])],
                            },
                        })
                except Exception as e:
                    print(f"[RSS 爬取错误] feed={feed_url}, error={e}")
                    continue

        return results

    async def crawl_all(self) -> List[Dict[str, Any]]:
        """执行所有爬取任务"""
        all_results = []

        tasks = [
            ("linux_do", self.crawl_linux_do),
            ("v2ex", self.crawl_v2ex),
            ("github", self.crawl_github),
            ("rss", self.crawl_rss),
        ]

        for source_name, crawl_func in tasks:
            try:
                results = await crawl_func()
                all_results.extend(results)
                print(f"[爬取完成] {source_name}: {len(results)} 条结果")
            except Exception as e:
                print(f"[爬取失败] {source_name}: {e}")

        return all_results
