"""
爬虫模块 — 统一注册入口
"""
from .base import BaseCrawler, CrawlerConfig, CrawlResult, CrawlerRegistry
from .known_sites import KnownSitesCrawler
from .linux_do import LinuxDoCrawler
from .v2ex import V2EXCrawler
from .github import GitHubCrawler
from .hackernews import HackerNewsCrawler


def create_registry(
    linux_do_url: str = "https://linux.do",
    github_api_url: str = "https://api.github.com",
) -> CrawlerRegistry:
    """创建并注册所有爬虫"""
    registry = CrawlerRegistry()
    registry.register("known_sites", KnownSitesCrawler())
    registry.register("linux_do", LinuxDoCrawler(base_url=linux_do_url))
    registry.register("v2ex", V2EXCrawler())
    registry.register("github", GitHubCrawler(api_url=github_api_url))
    registry.register("hackernews", HackerNewsCrawler())
    return registry


__all__ = [
    "BaseCrawler", "CrawlerConfig", "CrawlResult", "CrawlerRegistry",
    "KnownSitesCrawler", "LinuxDoCrawler", "V2EXCrawler",
    "GitHubCrawler", "HackerNewsCrawler", "create_registry",
]
