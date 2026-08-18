"""
Webhook Alert Sender for Discord, Slack, and generic webhooks in Reddit Plus v2.
Hardened with SSRF protection against private network and cloud metadata probes.
"""

import re
import ipaddress
import urllib.parse
import logging
from typing import Optional, List, Dict, Any
import httpx

from src.config import settings

logger = logging.getLogger(__name__)

# Cloud metadata and forbidden local IPs
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # AWS/GCP/Azure link-local metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def is_safe_webhook_url(url: str) -> bool:
    """Validate webhook URL against SSRF vulnerabilities."""
    if not url or not isinstance(url, str):
        return False

    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # Block localhost names directly
    if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "metadata.google.internal"):
        return False

    # If hostname is an IP, check forbidden ranges
    try:
        ip = ipaddress.ip_address(hostname)
        for net in BLOCKED_IP_NETWORKS:
            if ip in net:
                logger.warning(f"Blocked SSRF attempt to private/metadata IP: {hostname}")
                return False
    except ValueError:
        # It's a standard domain name (e.g. discord.com, hooks.slack.com)
        pass

    return True


class WebhookAlertSender:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.alerts.webhook_url or ""
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    def is_configured(self) -> bool:
        return bool(self.webhook_url and is_safe_webhook_url(self.webhook_url))

    async def send(
        self,
        title: str,
        message: str,
        url: Optional[str] = None,
        subreddit: Optional[str] = None,
        opportunity_score: Optional[int] = None,
    ) -> bool:
        """Send alert to Discord, Slack, or generic webhook with SSRF validation."""
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
