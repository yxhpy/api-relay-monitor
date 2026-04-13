"""
已知中转站白名单种子数据
"""
from typing import Any, Dict, List

from .base import BaseCrawler, CrawlResult, CrawlerConfig


class KnownSitesCrawler(BaseCrawler):
    """内置已知中转站白名单"""

    name = "known_sites"
    config = CrawlerConfig()  # 无 HTTP 请求

    SEED_SITES = [
        # === 公益站 ===
        {"name": "ChatAnywhere", "url": "https://api.chatanywhere.org",
         "relay_type": "公益", "description": "知名公益 API 中转站，免费 OpenAI API 代理",
         "price_multiplier": 0.0, "note": "有速率限制"},
        {"name": "AnyRouter", "url": "https://anyrouter.top",
         "relay_type": "公益", "description": "Claude 公益站，注册送约50$额度",
         "price_multiplier": 0.0, "note": "edu邮箱优先"},
        {"name": "词元流动", "url": "https://router.daoge.me",
         "relay_type": "公益", "description": "半公益站，学生党运营，注册送10刀",
         "price_multiplier": 0.1, "note": "新站"},
        # === 官转 ===
        {"name": "硅基流动", "url": "https://siliconflow.cn",
         "relay_type": "官转", "description": "国内知名 AI 平台，部分模型免费",
         "price_multiplier": 0.5, "note": "注册送额度"},
        {"name": "CloseAI", "url": "https://console.closeai-asia.com",
         "relay_type": "官转", "description": "稳定官转站，亚洲节点加速",
         "price_multiplier": 1.4, "note": "可开票"},
        {"name": "OpenRouter", "url": "https://openrouter.ai",
         "relay_type": "聚合", "description": "全球最大 LLM 聚合平台，200+ 模型",
         "price_multiplier": 1.0, "note": "动态比价路由"},
    ]

    async def crawl(self) -> List[CrawlResult]:
        results = []
        for site in self.SEED_SITES:
            results.append(CrawlResult(
                source=self.name,
                source_url=site["url"],
                title=site["name"],
                content=(
                    f"类型: {site['relay_type']} | 倍率: {site.get('price_multiplier', 'N/A')}\n"
                    f"{site['description']}\n备注: {site.get('note', '')}"
                ),
                raw_data={
                    "is_seed": True,
                    "relay_type": site["relay_type"],
                    "price_multiplier": site.get("price_multiplier"),
                    "note": site.get("note"),
                },
            ))
        logger.info(f"[{self.name}] 加载 {len(results)} 个种子站点")
        return results


# 模块级 logger
import logging
logger = logging.getLogger(__name__)
