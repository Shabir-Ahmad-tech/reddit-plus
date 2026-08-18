import logging
from typing import Optional
import httpx

from src.config import settings
from src.database import Mention, IntentTag, Reply

logger = logging.getLogger(__name__)


class PushAlertSender:
    def __init__(self):
        self.server = settings.alerts.ntfy.server.rstrip("/")
        self.client = httpx.AsyncClient(timeout=10.0)

    def get_topic(self) -> str:
        """Dynamically retrieve the active ntfy topic from settings or database."""
        # 1. Check runtime settings
        if settings.alerts.ntfy.topic:
            return settings.alerts.ntfy.topic.strip()
        # 2. Check SQLite database
        try:
            from src.database import get_session, get_alert_config
            with get_session() as session:
                cfg = get_alert_config(session)
                if cfg and cfg.ntfy_topic:
                    return cfg.ntfy_topic.strip()
        except Exception:
            pass
        return ""

    def is_configured(self) -> bool:
        return bool(self.get_topic())

    async def send_immediate_alert(
        self,
        mention: Mention,
        intent_tags: list[IntentTag],
        reply: Optional[Reply] = None,
        custom_topic: Optional[str] = None,
    ) -> bool:
        """Send push notification for a single mention."""
        topic = (custom_topic or self.get_topic()).strip()
        if not topic:
            logger.warning("ntfy topic not configured, skipping push")
            return False

        tags_str = ", ".join([t.tag for t in intent_tags])
        title = f"[{mention.source.upper()}] {tags_str}"
        message = f"{mention.title}\n\n{mention.content[:250]}..." if mention.content else (mention.title or "New mention detected")

        if reply and reply.content:
            message += f"\n\n💡 Suggested Reply:\n{reply.content[:200]}..."

        try:
            headers = {
                "Title": title[:200],
                "Tags": "bell,chart_with_upwards_trend",
                "Priority": "high",
            }
            if mention.url:
                headers["Click"] = mention.url

            response = await self.client.post(
                f"{self.server}/{topic}",
                content=message.encode("utf-8"),
                headers=headers,
            )
            response.raise_for_status()
            logger.info(f"Push notification successfully sent to ntfy.sh/{topic}")
            return True
        except Exception as e:
            logger.error(f"Failed to send push to ntfy.sh/{topic}: {e}")
            return False

    async def send_digest(
        self,
        mentions: list[tuple[Mention, list[IntentTag], Optional[Reply]]],
        custom_topic: Optional[str] = None,
    ) -> bool:
        """Send digest push notification."""
        topic = (custom_topic or self.get_topic()).strip()
        if not topic or not mentions:
            return False
            return False

        title = f"ParseStream Digest: {len(mentions)} mentions"
        lines = [f"• [{m.source}] {m.title[:60]}" for m, _, _ in mentions[:10]]
        message = "\n".join(lines)
        if len(mentions) > 10:
            message += f"\n... and {len(mentions) - 10} more"

        try:
            headers = {
                "Title": title,
                "Tags": "newspaper,chart_with_upwards_trend",
                "Priority": "low",
            }
            response = await self.client.post(
                f"{self.server}/{self.topic}",
                content=message.encode("utf-8"),
                headers=headers,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send digest push: {e}")
            return False

    async def close(self):
        await self.client.aclose()


# Singleton
_push_sender: Optional[PushAlertSender] = None


def get_push_sender() -> PushAlertSender:
    global _push_sender
    if _push_sender is None:
        _push_sender = PushAlertSender()
    return _push_sender