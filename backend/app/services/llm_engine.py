"""
API Relay Monitor - LLM 分析引擎
使用 OpenAI 兼容 API 进行中转站信息提取、评估和分析
"""

import json
from typing import Dict, List, Any, Optional

import httpx

from app.config import settings


class LLMEngine:
    """LLM 分析引擎"""

    def __init__(self):
        self.api_key = settings.LLM_API_KEY
        self.api_base = settings.LLM_API_BASE.rstrip("/")
        self.model = settings.LLM_MODEL
        self.timeout = 60.0

    async def _call_llm(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> Optional[str]:
        """调用 LLM API（OpenAI 兼容格式）"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[LLM 调用错误] {e}")
            return None

    async def analyze_relay_info(self, text: str) -> Optional[Dict[str, Any]]:
        """
        从文本中提取中转站结构化信息
        返回: name, url, type, pricing, models 等
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个专业的 API 中转站信息提取助手。请从给定的文本中提取中转站的关键信息。"
                    "请以 JSON 格式返回，包含以下字段：\n"
                    "- name: 站点名称\n"
                    "- url: 站点网址\n"
                    "- api_url: API端点（如果有）\n"
                    "- relay_type: 中转类型（官转/逆向/聚合/Bedrock，根据描述判断）\n"
                    "- description: 简短描述\n"
                    "- pricing_info: 定价信息对象\n"
                    "- price_multiplier: 价格倍率（数字）\n"
                    "- supported_models: 支持的模型列表\n"
                    "- registration_url: 注册链接\n"
                    "\n如果某个字段无法确定，请设为 null。只返回 JSON，不要其他内容。"
                ),
            },
            {
                "role": "user",
                "content": f"请从以下文本中提取 API 中转站信息：\n\n{text[:3000]}",
            },
        ]

        result = await self._call_llm(messages, temperature=0.1)

        if result:
            try:
                # 尝试解析 JSON
                cleaned = result.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                return json.loads(cleaned.strip())
            except json.JSONDecodeError:
                print(f"[JSON解析错误] {result[:200]}")
                return None
        return None

    async def evaluate_risk(
        self,
        site_data: Dict[str, Any],
        community_feedback: List[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        评估中转站风险
        返回: risk_level (low/medium/high), notes, reasoning
        """
        feedback_text = "\n".join(community_feedback[:5]) if community_feedback else "无社区反馈"

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个 API 中转站风险评估专家。请根据站点信息和社区反馈评估风险等级。\n"
                    "风险因素包括但不限于：\n"
                    "- 逆向工程类服务通常风险较高\n"
                    "- 价格异常低可能是骗局\n"
                    "- 缺乏透明度（无注册信息、无联系方式）\n"
                    "- 社区负面反馈\n"
                    "- 服务不稳定（频繁宕机）\n\n"
                    "请以 JSON 格式返回：\n"
                    "- risk_level: low/medium/high\n"
                    "- notes: 简短风险说明\n"
                    "- reasoning: 详细分析过程\n"
                    "- confidence: 评估置信度 0-1\n"
                    "只返回 JSON。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"站点信息：{json.dumps(site_data, ensure_ascii=False, default=str)}\n\n"
                    f"社区反馈：\n{feedback_text}"
                ),
            },
        ]

        result = await self._call_llm(messages, temperature=0.2)

        if result:
            try:
                cleaned = result.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                return json.loads(cleaned.strip())
            except json.JSONDecodeError:
                return {"risk_level": "medium", "notes": "LLM 分析结果解析失败", "reasoning": result}

        return None

    async def score_relay_site(
        self, site_data: Dict[str, Any]
    ) -> Optional[Dict[str, float]]:
        """
        使用 LLM 对中转站进行评分
        返回: stability, price, update_speed, community (各1-10分)
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个 API 中转站评估专家。请根据站点信息和社区反馈进行评分。\n"
                    "评分维度（各1-10分）：\n"
                    "- stability: 稳定性（服务可用性、响应速度）\n"
                    "- price: 价格合理性（与官方对比、性价比）\n"
                    "- update_speed: 更新速度（新模型支持速度、维护频率）\n"
                    "- community: 社区口碑（用户评价、推荐程度）\n\n"
                    "请以 JSON 格式返回：\n"
                    '{"stability": X, "price": X, "update_speed": X, "community": X}\n'
                    "只返回 JSON。"
                ),
            },
            {
                "role": "user",
                "content": f"站点信息：{json.dumps(site_data, ensure_ascii=False, default=str)[:2000]}",
            },
        ]

        result = await self._call_llm(messages, temperature=0.2)

        if result:
            try:
                cleaned = result.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                scores = json.loads(cleaned.strip())
                # 确保分数在1-10范围内
                for key in ["stability", "price", "update_speed", "community"]:
                    if key in scores:
                        scores[key] = max(1, min(10, float(scores[key])))
                return scores
            except (json.JSONDecodeError, ValueError):
                return None
        return None

    async def generate_daily_report(
        self,
        sites: List[Dict[str, Any]],
        crawl_results: List[Dict[str, Any]],
    ) -> Optional[Dict[str, str]]:
        """
        生成每日分析报告
        返回: content (markdown), summary
        """
        # 截断数据以避免 token 过多
        sites_text = json.dumps(sites[:30], ensure_ascii=False, default=str)
        crawl_text = json.dumps(
            [{"title": r.get("title", ""), "source": r.get("source", "")}
             for r in crawl_results[:20]],
            ensure_ascii=False,
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "你是 API 中转站监控系统的分析师。请根据当前站点数据和最新爬取结果生成日报。\n"
                    "报告要求：\n"
                    "1. 使用 Markdown 格式\n"
                    "2. 包含：概览、推荐站点（Top 3）、风险提醒、价格变化分析\n"
                    "3. 语言简洁专业\n"
                    "4. 提供可操作的建议\n\n"
                    "请以 JSON 格式返回：\n"
                    "- content: 完整的 Markdown 报告内容\n"
                    "- summary: 一句话摘要（不超过100字）\n"
                    "只返回 JSON。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"当前监控站点数据：\n{sites_text[:3000]}\n\n"
                    f"最新爬取结果：\n{crawl_text[:2000]}"
                ),
            },
        ]

        result = await self._call_llm(messages, temperature=0.5, max_tokens=3000)

        if result:
            try:
                cleaned = result.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                return json.loads(cleaned.strip())
            except json.JSONDecodeError:
                return {"content": result, "summary": "报告已生成（格式解析异常）"}

        return None

    async def generate_search_queries(self) -> List[str]:
        """
        使用 LLM 生成搜索查询变体
        返回10个搜索查询
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "你是搜索优化专家。请生成10个用于搜索 API 中转站相关信息的查询关键词。\n"
                    "这些查询将用于搜索论坛、GitHub、RSS 等数据源。\n"
                    "混合使用中英文，覆盖不同的表述方式。\n\n"
                    "请以 JSON 数组格式返回，只包含字符串。例如：\n"
                    '["API中转站", "OpenAI proxy", ...]'
                ),
            },
            {
                "role": "user",
                "content": "请生成10个搜索 API LLM 中转站相关信息的查询关键词。",
            },
        ]

        result = await self._call_llm(messages, temperature=0.8)

        if result:
            try:
                cleaned = result.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                queries = json.loads(cleaned.strip())
                if isinstance(queries, list):
                    return queries[:10]
            except json.JSONDecodeError:
                pass

        # 默认查询列表
        return [
            "API 中转站",
            "OpenAI API relay",
            "GPT API 代理",
            "Claude API 中转",
            "one-api 部署",
            "new-api 搭建",
            "LLM API proxy",
            "API转发站推荐",
            "API relay site",
            "大模型 API 代理",
        ]
