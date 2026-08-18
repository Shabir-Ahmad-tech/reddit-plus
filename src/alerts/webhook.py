"""
Webhook Alert Sender for Discord, Slack, and generic webhooks in Reddit Plus v2.
"""

import logging
from typing import Optional, List, Dict, Any
import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class WebhookAlertSender:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.alerts.webhook_url or ""
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("http"))

    async def send(
        self,
        title: str,
        message: str,
        url: Optional[str] = None,
        subreddit: Optional[str] = None,
        opportunity_score: Optional[int] = None,
    ) -> bool:
        """Send alert to Discord, Slack, or generic webhook."""
        if not self.is_configured():
            return False

        client = await self.get_client()

        if "discord.com" in self.webhook_url:
            payload = {
                "content": f"🚨 **Reddit Plus Alert**: {title}",
                "embeds": [
                    {
                        "title": title,
                        "url": url,
                        "description": message[:1500],
                        "color": 0xFF4500,
                        "fields": [
                            {"name": "Subreddit", "value": f"r/{subreddit}" if subreddit else "all", "inline": True},
                            {"name": "Opportunity", "value": f"{opportunity_score}/100" if opportunity_score else "N/A", "inline": True},
                        ],
                        "footer": {"text": "Reddit Plus v2 Intelligence"},
                    }
                ],
            }
        elif "slack.com" in self.webhook_url:
            payload = {
                "text": f"🚨 *{title}*\n<{url}|View Discussion>\n{message[:400]}",
            }
        else:
            payload = {
                "title": title,
                "message": message,
                "url": url,
                "subreddit": subreddit,
                "opportunity_score": opportunity_score,
            }

        try:
            resp = await client.post(self.webhook_url, json=payload)
            resp.raise_for_status()
            logger.info("Webhook alert dispatched successfully")
            return True
        except Exception as e:
            logger.warning(f"Webhook alert failed: {e}")
            return False

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_webhook_sender: Optional[WebhookAlertSender] = None


def get_webhook_sender(url: Optional[str] = None) -> WebhookAlertSender:
    global _webhook_sender
    if url:
        return WebhookAlertSender(url)
    if _webhook_sender is None:
        _webhook_sender = WebhookAlertSender()
    return _webhook_sender
