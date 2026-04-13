"""
API Relay Monitor - 多源爬虫服务
从 linux.do, V2EX, GitHub Discussions、中转站导航站等数据源爬取实际运营的中转站信息
重点：只收录实际可用的中转站（公益站、官转、性价比站），不收录开源项目代码仓库
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
    "中转", "relay", "官转", "逆向", "公益", "免费", "性价比",
    "API代理", "API转发", "api 中转", "api 转发",
    "openai proxy", "claude proxy", "gpt 代理", "llm proxy",
    "api-proxy", "api relay", "倍率", "额度", "token",
    "大模型", "转发站", "中转站", "api站", "api 站",
    "openai 中转", "claude 中转", "gpt 中转", "gemini 中转",
    "注册送", "免费额度", "邀请码", "新站", "新开",
]

# 排除关键词（开源项目、代码仓库相关，不感兴趣）
EXCLUDE_KEYWORDS = [
    "github.com/", "awesome-", "sdk", "library", "framework",
    "tutorial", "教程", "学习", "course", "book",
]


class MultiSourceCrawler:
    """多源数据爬虫 — 只发现实际运营的中转站"""

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
        # 先排除
        if any(kw.lower() in text_lower for kw in EXCLUDE_KEYWORDS):
            return False
        return any(kw.lower() in text_lower for kw in RELAY_KEYWORDS)

    async def crawl_known_sites(self) -> List[Dict[str, Any]]:
        """
        已知中转站白名单种子数据
        这些是社区公认的实际运营中转站，作为基础数据源
        """
        known_sites = [
            # === 公益站 / 免费站 ===
            {
                "name": "ChatAnywhere",
                "url": "https://api.chatanywhere.org",
                "relay_type": "公益",
                "description": "知名公益 API 中转站，提供免费 OpenAI API 代理，支持 GPT-4o 等模型",
                "price_multiplier": 0.0,
                "note": "公益免费站，有速率限制",
            },
            {
                "name": "硅基流动 SiliconFlow",
                "url": "https://siliconflow.cn",
                "relay_type": "官转",
                "description": "国内知名 AI 平台，提供 OpenAI/Claude 等模型 API，价格优惠，支持免费额度",
                "price_multiplier": 0.5,
                "note": "注册送额度，部分模型免费",
            },
            # === 高性价比官转 ===
            {
                "name": "CloseAI",
                "url": "https://console.closeai-asia.com",
                "relay_type": "官转",
                "description": "稳定官转站，支持 OpenAI 全系列模型，亚洲节点加速",
                "price_multiplier": 1.4,
                "note": "官网直连转发，稳定可靠",
            },
            {
                "name": "GPT API Shop",
                "url": "https://gptapi.us",
                "relay_type": "官转",
                "description": "GPT API 中转服务，支持 GPT-4/GPT-4o，价格较优惠",
                "price_multiplier": 1.3,
                "note": "支持支付宝/微信支付",
            },
            {
                "name": "OhMyGPT",
                "url": "https://ohmygpt.com",
                "relay_type": "聚合",
                "description": "多模型 API 聚合平台，支持 OpenAI/Anthropic/Google 等",
                "price_multiplier": 1.5,
                "note": "模型种类多",
            },
            {
                "name": "API2D",
                "url": "https://api2d.net",
                "relay_type": "官转",
                "description": "国内老牌 API 中转站，支持 OpenAI/Google/Anthropic，按量计费",
                "price_multiplier": 1.8,
                "note": "运营时间长，口碑一般",
            },
            {
                "name": "AI Hub (aiproxy.io)",
                "url": "https://aiproxy.io",
                "relay_type": "聚合",
                "description": "多模型 API 代理，支持 GPT-4/Claude/Gemini 等",
                "price_multiplier": 1.2,
                "note": "新站，价格有竞争力",
            },
            {
                "name": "OpenRouter",
                "url": "https://openrouter.ai",
                "relay_type": "聚合",
                "description": "全球最大的 LLM API 聚合平台，支持 100+ 模型，按量计费，部分模型免费",
                "price_multiplier": 1.0,
                "note": "官方聚合，最全的模型选择",
            },
            # === 逆向 / 低价站 ===
            {
                "name": "CCNexus",
                "url": "https://ccnexus.com",
                "relay_type": "逆向",
                "description": "Claude API 中转站，低价提供 Claude 系列模型",
                "price_multiplier": 0.3,
                "note": "逆向站，风险较高但价格极低",
            },
            {
                "name": "CloseAI-Biz",
                "url": "https://console.closeai.biz",
                "relay_type": "官转",
                "description": "CloseAI 旗下企业版，支持更多模型和更高并发",
                "price_multiplier": 1.2,
                "note": "适合团队/企业使用",
            },
            {
                "name": "AiHubMix",
                "url": "https://aihubmix.com",
                "relay_type": "聚合",
                "description": "多模型 API 聚合服务，支持 GPT-4o/Claude 3.5/Gemini Pro 等",
                "price_multiplier": 1.0,
                "note": "新站，注册送额度",
            },
            {
                "name": "咒语商店 (API)",
                "url": "https://api.shared.chat",
                "relay_type": "官转",
                "description": "提供 OpenAI API 中转，支持最新模型",
                "price_multiplier": 1.0,
                "note": "中文社区运营",
            },
        ]

        results = []
        for site in known_sites:
            results.append({
                "source": "known_sites",
                "source_url": site["url"],
                "title": site["name"],
                "content": (
                    f"类型: {site['relay_type']} | 倍率: {site.get('price_multiplier', 'N/A')}\n"
                    f"{site['description']}\n"
                    f"备注: {site.get('note', '')}"
                ),
                "raw_data": {
                    "is_seed": True,
                    "relay_type": site["relay_type"],
                    "price_multiplier": site.get("price_multiplier"),
                    "note": site.get("note"),
                },
            })

        logger.info(f"[已知站点] 加载 {len(results)} 个种子站点")
        return results

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
            http2=True,
        ) as client:
            # 搜索中转站相关板块 + 最新/热门
            endpoints = [
                "/latest.json",
                "/top.json",
                "/search.json?q=中转站%20order%3Alatest",
                "/search.json?q=API%20proxy%20order%3Alatest",
                "/search.json?q=官转%20性价比%20order%3Alatest",
                "/search.json?q=公益%20免费%20API%20order%3Alatest",
            ]
            for endpoint in endpoints:
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

                    # 处理搜索结果
                    if "/search.json" in endpoint:
                        topics_data = {}
                        for topic in data.get("topics", []):
                            title = topic.get("title", "")
                            if not self._contains_keywords(title):
                                continue
                            results.append({
                                "source": "linux_do",
                                "source_url": (
                                    f"{settings.LINUX_DO_BASE_URL}/t/"
                                    f"{topic.get('slug', '')}/{topic.get('id', '')}"
                                ),
                                "title": title,
                                "content": title,  # 搜索结果只有标题
                                "raw_data": {
                                    "topic_id": topic.get("id"),
                                    "category_id": topic.get("category_id"),
                                    "likes": topic.get("like_count", 0),
                                    "views": topic.get("views", 0),
                                    "endpoint": "search",
                                },
                            })
                        continue

                    # 处理 latest/top 结果
                    topics = data.get("topic_list", {}).get("topics", [])
                    posts_data = {}
                    for post in data.get("post_stream", {}).get("posts", []):
                        posts_data[post.get("topic_id")] = post

                    for topic in topics[:80]:
                        title = topic.get("title", "")
                        if not self._contains_keywords(title):
                            continue

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

        # 去重
        seen_urls = set()
        unique = []
        for r in results:
            if r["source_url"] not in seen_urls:
                seen_urls.add(r["source_url"])
                unique.append(r)

        logger.info(f"[linux.do] 获取 {len(unique)} 条相关帖子（去重前 {len(results)}）")
        return unique

    async def crawl_v2ex(self) -> List[Dict[str, Any]]:
        """
        爬取 V2EX 论坛
        使用公开 API: /api/topics/latest.json 和 /api/topics/hot.json
        同时搜索相关节点
        """
        results = []

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self.headers,
            follow_redirects=True,
            verify=False,
        ) as client:
            for endpoint in [
                "https://www.v2ex.com/api/topics/latest.json",
                "https://www.v2ex.com/api/topics/hot.json",
                "https://www.v2ex.com/api/nodes/python/topics.json?p=1",
                "https://www.v2ex.com/api/nodes/ai/topics.json?p=1",
            ]:
                for attempt in range(3):
                    try:
                        resp = await client.get(endpoint)
                        if resp.status_code == 200:
                            break
                        if resp.status_code in (429, 503) and attempt < 2:
                            wait = 2 ** attempt
                            logger.warning(f"[V2EX] {endpoint} returned {resp.status_code}, retry after {wait}s")
                            await asyncio.sleep(wait)
                            continue
                        logger.warning(f"[V2EX] {endpoint} returned {resp.status_code}")
                        break
                    except Exception as e:
                        if attempt < 2:
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
                            },
                        })
                except Exception as e:
                    logger.error(f"[V2EX 解析错误] endpoint={endpoint}, error={e}")

        logger.info(f"[V2EX] 获取 {len(results)} 条相关帖子")
        return results

    async def crawl_github(self) -> List[Dict[str, Any]]:
        """
        爬取 GitHub Discussions/Issues — 搜索实际中转站推荐帖
        不再搜索代码仓库，改为搜索实际运营中转站的讨论帖
        """
        results = []

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                **self.headers,
                "Accept": "application/vnd.github.v3+json",
            },
            follow_redirects=True,
        ) as client:
            # 搜索 GitHub Issues/Discussions 中关于中转站推荐的帖子
            search_queries = [
                "API中转站 推荐 site:github.com",
                "openai relay site cheap",
                "claude api proxy cheap free",
                "gpt api 中转 公益 免费",
                "one-api new-api 中转站推荐 倍率",
            ]

            for query in search_queries:
                try:
                    # 搜索 issues（包含 discussions）
                    resp = await client.get(
                        f"{settings.GITHUB_API_URL}/search/issues",
                        params={
                            "q": query,
                            "sort": "updated",
                            "order": "desc",
                            "per_page": 10,
                        },
                    )
                    if resp.status_code != 200:
                        logger.warning(f"[GitHub Issues] search '{query}' returned {resp.status_code}")
                        continue

                    data = resp.json()
                    for item in data.get("items", []):
                        title = item.get("title", "")
                        body = item.get("body", "") or ""
                        html_url = item.get("html_url", "")

                        # 排除纯代码仓库
                        if "/issues/" not in html_url and "/pull/" not in html_url:
                            continue
                        if not self._contains_keywords(f"{title} {body[:500]}"):
                            continue

                        results.append({
                            "source": "github_discussions",
                            "source_url": html_url,
                            "title": title,
                            "content": body[:2000],
                            "raw_data": {
                                "issue_number": item.get("number"),
                                "state": item.get("state"),
                                "comments": item.get("comments", 0),
                                "reactions": item.get("reactions", {}).get("total_count", 0),
                                "repository": item.get("repository_url", ""),
                            },
                        })
                except Exception as e:
                    logger.error(f"[GitHub Issues 爬取错误] query={query}, error={e}")

            # 同时搜索 awesome 列表类型的仓库（它们通常汇总实际中转站）
            awesome_queries = [
                "awesome openai api relay proxy list",
                "awesome llm api gateway list",
            ]
            for query in awesome_queries:
                try:
                    resp = await client.get(
                        f"{settings.GITHUB_API_URL}/search/repositories",
                        params={
                            "q": query,
                            "sort": "stars",
                            "order": "desc",
                            "per_page": 5,
                        },
                    )
                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    for repo in data.get("items", []):
                        desc = repo.get("description") or ""
                        homepage = repo.get("homepage", "")
                        # 只收录 awesome 列表，且要确保 README 中有实际中转站链接
                        if not desc or "awesome" not in desc.lower():
                            continue
                        results.append({
                            "source": "github_awesome_list",
                            "source_url": repo.get("html_url", ""),
                            "title": repo.get("full_name", ""),
                            "content": f"Awesome List | Stars: {repo.get('stargazers_count', 0)}\n{desc}\nHomepage: {homepage}",
                            "raw_data": {
                                "is_awesome_list": True,
                                "full_name": repo.get("full_name"),
                                "stars": repo.get("stargazers_count", 0),
                                "homepage": homepage,
                            },
                        })
                except Exception as e:
                    logger.error(f"[GitHub Awesome 爬取错误] query={query}, error={e}")

        # 去重
        seen_urls = set()
        unique = []
        for r in results:
            if r["source_url"] not in seen_urls:
                seen_urls.add(r["source_url"])
                unique.append(r)

        logger.info(f"[GitHub] 获取 {len(unique)} 条中转站相关讨论（去重前 {len(results)}）")
        return unique

    async def crawl_rss(self) -> List[Dict[str, Any]]:
        """
        爬取 RSS/HN 源 — 搜索实际中转站推荐
        """
        results = []

        search_queries = [
            "openai api proxy relay site cheap",
            "claude api 中转站 推荐",
            "gpt api free relay service",
            "llm api gateway cheap alternative",
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
                            "hitsPerPage": 15,
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for hit in data.get("hits", []):
                            title = hit.get("title", "")
                            url = hit.get("url", "")
                            if not self._contains_keywords(title):
                                continue
                            # 排除 GitHub 仓库链接
                            if "github.com/" in url and "/issues/" not in url:
                                continue
                            if any(r["source_url"] == url for r in results):
                                continue
                            results.append({
                                "source": "rss",
                                "source_url": url or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                                "title": title,
                                "content": hit.get("title", "")[:2000],
                                "raw_data": {
                                    "points": hit.get("points", 0),
                                    "author": hit.get("author", ""),
                                    "created_at": hit.get("created_at", ""),
                                    "feed_type": "hackernews",
                                },
                            })
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"[RSS/HN 爬取错误] query={query}, error={e}")

        return results

    async def crawl_nav_sites(self) -> List[Dict[str, Any]]:
        """
        从中转站导航/聚合页面抓取实际运营站点
        """
        results = []

        # 已知的中转站导航页 / 信息聚合页
        nav_urls = [
            {
                "url": "https://linux.do/tag/api.json",
                "name": "linux.do API 标签",
                "source": "linux_do_tag",
            },
        ]

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                **self.headers,
                "Accept": "application/json",
            },
            follow_redirects=True,
            verify=False,
        ) as client:
            for nav in nav_urls:
                try:
                    resp = await client.get(nav["url"])
                    if resp.status_code != 200:
                        logger.warning(f"[导航站] {nav['name']} returned {resp.status_code}")
                        continue

                    data = resp.json()
                    # Discourse tag 页面格式
                    topics = data.get("topic_list", {}).get("topics", [])
                    for topic in topics[:30]:
                        title = topic.get("title", "")
                        if not self._contains_keywords(title):
                            continue
                        results.append({
                            "source": nav["source"],
                            "source_url": f"{settings.LINUX_DO_BASE_URL}/t/{topic.get('slug', '')}/{topic.get('id', '')}",
                            "title": title,
                            "content": title,
                            "raw_data": {
                                "topic_id": topic.get("id"),
                                "views": topic.get("views", 0),
                                "likes": topic.get("like_count", 0),
                            },
                        })
                except Exception as e:
                    logger.error(f"[导航站爬取错误] {nav['name']}: {e}")

        logger.info(f"[导航站] 获取 {len(results)} 条结果")
        return results

    async def crawl_all(self) -> List[Dict[str, Any]]:
        """执行所有爬取任务"""
        tasks = [
            ("known_sites", self.crawl_known_sites),
            ("linux_do", self.crawl_linux_do),
            ("v2ex", self.crawl_v2ex),
            ("github", self.crawl_github),
            ("rss", self.crawl_rss),
            ("nav_sites", self.crawl_nav_sites),
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
