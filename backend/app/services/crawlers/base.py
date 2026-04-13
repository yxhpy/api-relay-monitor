"""
API Relay Monitor - 爬虫抽象基类
定义统一的数据源接口，所有渠道爬虫继承此类
"""
import asyncio
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class CrawlerConfig:
    """爬虫公共配置"""
    extra_headers: Dict[str, str] = field(default_factory=dict)
    verify_ssl: bool = False
    http2: bool = False
    timeout: float = 30.0
    connect_timeout: float = 10.0
    follow_redirects: bool = True
    max_retries: int = 3
    backoff_base: float = 2.0
    retryable_status_codes: tuple = (403, 429, 503, 502)
    rate_limit_delay: float = 0.5  # 请求间隔


@dataclass
class CrawlResult:
    """统一爬取结果"""
    source: str
    source_url: str
    title: str
    content: str
    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "source_url": self.source_url,
            "title": self.title,
            "content": self.content[:2000],
            "raw_data": self.raw_data,
        }


class BaseCrawler(ABC):
    """
    爬虫抽象基类 — 所有渠道爬虫的统一接口

    子类只需实现:
      - name: 数据源名称
      - config: CrawlerConfig 实例
      - crawl(): 具体爬取逻辑

    可选覆写:
      - build_endpoints(): 定义要抓取的 URL 列表
      - filter_keywords(): 关键词过滤
    """

    # 子类必须设置
    name: str = "base"
    config: CrawlerConfig = CrawlerConfig()

    # 中转站相关关键词
    RELAY_KEYWORDS = [
        "中转", "relay", "官转", "逆向", "公益", "免费", "性价比",
        "API代理", "API转发", "api 中转", "api 转发",
        "openai proxy", "claude proxy", "gpt 代理", "llm proxy",
        "api-proxy", "api relay", "倍率", "额度", "token",
        "大模型", "转发站", "中转站", "api站", "api 站",
        "openai 中转", "claude 中转", "gpt 中转", "gemini 中转",
        "注册送", "免费额度", "邀请码", "新站", "新开",
    ]

    EXCLUDE_KEYWORDS = [
        "github.com/", "awesome-", "sdk", "library", "framework",
        "tutorial", "教程", "学习", "course", "book",
    ]

    def __init__(self):
        self._seen_urls: set = set()

    def _contains_keywords(self, text: str) -> bool:
        """检查文本是否包含中转站相关关键词"""
        if not text:
            return False
        text_lower = text.lower()
        if any(kw.lower() in text_lower for kw in self.EXCLUDE_KEYWORDS):
            return False
        return any(kw.lower() in text_lower for kw in self.RELAY_KEYWORDS)

    @staticmethod
    def _clean_html(text: str) -> str:
        """清理 HTML 标签"""
        return re.sub(r"<[^>]+>", "", text) if text else ""

    def _build_client(self) -> httpx.AsyncClient:
        """构建 HTTP Client（统一配置）"""
        default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        default_headers.update(self.config.extra_headers)

        return httpx.AsyncClient(
            timeout=httpx.Timeout(
                self.config.timeout,
                connect=self.config.connect_timeout,
            ),
            headers=default_headers,
            follow_redirects=self.config.follow_redirects,
            verify=self.config.verify_ssl,
            http2=self.config.http2,
        )

    async def _fetch_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[dict] = None,
    ) -> Optional[httpx.Response]:
        """统一重试 + 错误处理"""
        for attempt in range(self.config.max_retries):
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    return resp
                if resp.status_code in self.config.retryable_status_codes and attempt < self.config.max_retries - 1:
                    wait = self.config.backoff_base ** attempt
                    logger.warning(
                        f"[{self.name}] {url} -> {resp.status_code}, "
                        f"retry {attempt+1}/{self.config.max_retries} after {wait:.1f}s"
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.warning(f"[{self.name}] {url} -> {resp.status_code}")
                return None
            except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError) as e:
                if attempt < self.config.max_retries - 1:
                    wait = self.config.backoff_base ** attempt
                    logger.warning(f"[{self.name}] 连接错误 retry {attempt+1}: {e}")
                    await asyncio.sleep(wait)
                    continue
                logger.error(f"[{self.name}] 请求失败: {url}, error={e}")
                return None
            except Exception as e:
                logger.error(f"[{self.name}] 未预期错误: {url}, error={e}")
                return None
        return None

    def _deduplicate(self, results: List[CrawlResult]) -> List[CrawlResult]:
        """统一去重"""
        unique = []
        for r in results:
            if r.source_url not in self._seen_urls:
                self._seen_urls.add(r.source_url)
                unique.append(r)
        return unique

    @abstractmethod
    async def crawl(self) -> List[CrawlResult]:
        """执行爬取，返回统一结果列表"""
        ...

    async def crawl_safe(self) -> List[Dict[str, Any]]:
        """带异常保护的外部调用入口"""
        try:
            results = await self.crawl()
            deduped = self._deduplicate(results)
            logger.info(f"[{self.name}] 爬取完成: {len(deduped)} 条 (去重前 {len(results)})")
            return [r.to_dict() for r in deduped]
        except Exception as e:
            logger.error(f"[{self.name}] 爬取异常: {e}")
            return []


class CrawlerRegistry:
    """
    爬虫注册中心 — 管理所有数据源

    用法:
        registry = CrawlerRegistry()
        registry.register("linux_do", LinuxDoCrawler())
        registry.register("v2ex", V2EXCrawler())
        ...
        results = await registry.crawl_all()
        results = await registry.crawl_source("linux_do")
    """

    def __init__(self):
        self._crawlers: Dict[str, BaseCrawler] = {}

    def register(self, name: str, crawler: BaseCrawler) -> "CrawlerRegistry":
        """注册爬虫"""
        self._crawlers[name] = crawler
        logger.info(f"[Registry] 注册爬虫: {name}")
        return self

    def unregister(self, name: str) -> "CrawlerRegistry":
        """注销爬虫"""
        self._crawlers.pop(name, None)
        return self

    def list_sources(self) -> List[str]:
        """列出所有已注册的数据源"""
        return list(self._crawlers.keys())

    async def crawl_source(self, name: str) -> List[Dict[str, Any]]:
        """爬取单个数据源"""
        crawler = self._crawlers.get(name)
        if not crawler:
            logger.error(f"[Registry] 未注册的数据源: {name}")
            return []
        return await crawler.crawl_safe()

    async def crawl_all(self) -> List[Dict[str, Any]]:
        """并发爬取所有数据源"""
        tasks = [(name, crawler.crawl_safe()) for name, crawler in self._crawlers.items()]
        results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

        all_results = []
        for (name, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(f"[Registry] {name} 爬取异常: {result}")
            else:
                all_results.extend(result)
        return all_results

    def get_crawler(self, name: str) -> Optional[BaseCrawler]:
        return self._crawlers.get(name)
