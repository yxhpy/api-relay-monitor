"""
API Relay Monitor - 通知服务
支持 Telegram 机器人推送和 Webhook 通知
"""

import json
from typing import Optional, List, Dict, Any

import httpx

from app.config import settings


class Notifier:
    """通知服务"""

    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.telegram_api = "https://api.telegram.org"

    @property
    def is_telegram_configured(self) -> bool:
        """检查 Telegram 是否已配置"""
        return bool(self.bot_token and self.chat_id)

    async def send_telegram_message(
        self,
        text: str,
        parse_mode: str = "Markdown",
        disable_notification: bool = False,
    ) -> bool:
        """
        发送 Telegram 消息
        """
        if not self.is_telegram_configured:
            print("[通知] Telegram 未配置，跳过发送")
            return False

        url = f"{self.telegram_api}/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    return True
                else:
                    print(f"[Telegram 发送失败] status={resp.status_code}, body={resp.text[:200]}")
                    return False
        except Exception as e:
            print(f"[Telegram 发送错误] {e}")
            return False

    async def send_webhook(
        self,
        webhook_url: str,
        data: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        发送 Webhook 通知
        """
        default_headers = {
            "Content-Type": "application/json",
            "User-Agent": "API-Relay-Monitor/1.0",
        }
        if headers:
            default_headers.update(headers)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    webhook_url,
                    json=data,
                    headers=default_headers,
                )
                return resp.status_code < 400
        except Exception as e:
            print(f"[Webhook 发送错误] {e}")
            return False

    def format_alert_message(
        self,
        site_name: str,
        risk_level: str,
        risk_notes: str,
        overall_score: float,
    ) -> str:
        """格式化风险提醒消息"""
        emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(risk_level, "⚪")

        message = (
            f"{emoji} *风险提醒: {site_name}*\n\n"
            f"风险等级: *{risk_level.upper()}*\n"
            f"综合评分: {overall_score}/10\n"
        )

        if risk_notes:
            message += f"备注: {risk_notes}\n"

        message += f"\n_来自 API Relay Monitor_"
        return message

    def format_daily_report_message(
        self,
        summary: str,
        top_picks: List[Dict[str, Any]],
        risk_alerts: List[Dict[str, Any]],
    ) -> str:
        """格式化日报推送消息"""
        message = "📊 *API 中转站日报*\n\n"

        if summary:
            message += f"{summary}\n\n"

        if top_picks:
            message += "🏆 *推荐站点:*\n"
            for i, pick in enumerate(top_picks[:3], 1):
                name = pick.get("name", "未知")
                score = pick.get("score", 0)
                message += f"  {i}. {name} (评分: {score})\n"
            message += "\n"

        if risk_alerts:
            message += "⚠️ *风险提醒:*\n"
            for alert in risk_alerts[:5]:
                name = alert.get("name", "未知")
                notes = alert.get("notes", "")
                message += f"  • {name}: {notes}\n"

        message += f"\n_来自 API Relay Monitor_"
        return message

    def format_new_site_message(
        self,
        site_name: str,
        url: str,
        relay_type: str,
        source: str,
    ) -> str:
        """格式化新站点发现消息"""
        message = (
            f"🆕 *发现新中转站: {site_name}*\n\n"
            f"网址: {url}\n"
            f"类型: {relay_type}\n"
            f"来源: {source}\n\n"
            f"_来自 API Relay Monitor_"
        )
        return message

    async def notify_risk_alert(
        self,
        site_name: str,
        risk_level: str,
        risk_notes: str,
        overall_score: float,
    ) -> bool:
        """发送风险提醒通知"""
        if not self.is_telegram_configured:
            return False

        message = self.format_alert_message(
            site_name, risk_level, risk_notes, overall_score
        )
        return await self.send_telegram_message(message)

    async def notify_daily_report(
        self,
        summary: str,
        top_picks: List[Dict[str, Any]],
        risk_alerts: List[Dict[str, Any]],
    ) -> bool:
        """发送日报通知"""
        if not self.is_telegram_configured:
            return False

        message = self.format_daily_report_message(summary, top_picks, risk_alerts)
        return await self.send_telegram_message(message)

    async def notify_new_site(
        self,
        site_name: str,
        url: str,
        relay_type: str,
        source: str,
    ) -> bool:
        """发送新站点发现通知"""
        if not self.is_telegram_configured:
            return False

        message = self.format_new_site_message(site_name, url, relay_type, source)
        return await self.send_telegram_message(message)
