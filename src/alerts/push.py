"""
Push Alert Sender using ntfy.sh for Reddit Plus v2.
"""

import logging
from typing import Optional, List
import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class PushAlertSender:
    def __init__(self):
        self.server = (settings.alerts.ntfy_server or "https://ntfy.sh").rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    def get_topic(self) -> str:
        return (settings.alerts.ntfy_topic or "").strip()

    def is_configured(self) -> bool:
        return bool(self.get_topic())

    async def send(
        self,
        title: str,
        message: str,
        url: Optional[str] = None,
        tags: Optional[List[str]] = None,
        priority: str = "default",
        custom_topic: Optional[str] = None,
    ) -> bool:
        """Send push notification to ntfy.sh."""
        topic = (custom_topic or self.get_topic()).strip()
        if not topic:
            logger.debug("ntfy topic not configured, skipping push")
            return False

        client = await self.get_client()
        headers = {
            "Title": title[:200],
            "Priority": priority,
            "Tags": ",".join(tags or ["bell", "reddit"]),
        }
        if url:
            headers["Click"] = url

        try:
            resp = await client.post(
                f"{self.server}/{topic}",
                content=message.encode("utf-8"),
                headers=headers,
            )
            resp.raise_for_status()
            logger.info(f"Push notification sent to ntfy.sh/{topic}")
            return True
        except Exception as e:
            logger.warning(f"Failed to send push to ntfy.sh/{topic}: {e}")
            return False

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_push_sender: Optional[PushAlertSender] = None


def get_push_sender() -> PushAlertSender:
    global _push_sender
    if _push_sender is None:
        _push_sender = PushAlertSender()
    return _push_sender