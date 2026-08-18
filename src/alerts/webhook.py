import logging
from typing import Optional, List, Tuple
import httpx

from src.database.models import Mention, IntentTag, Reply

logger = logging.getLogger(__name__)


class WebhookAlertSender:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or ""
        self.client = httpx.AsyncClient(timeout=15.0)

    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("http"))

    async def send_immediate_alert(
        self,
        mention: Mention,
        intent_tags: List[IntentTag],
        reply: Optional[Reply] = None,
    ) -> bool:
        """Send alert to Discord, Slack, or generic webhook."""
        if not self.is_configured():
            return False

        tags_str = ", ".join([f"{t.tag} ({t.confidence}%)" for t in intent_tags])
        title = f"[{mention.source.upper()}] {tags_str}"

        # Discord webhook format
        if "discord.com" in self.webhook_url:
            color = 0x22C55E if any(t.tag == "buy-intent" for t in intent_tags) else 0x3B82F6
            embed = {
                "title": mention.title or "New Social Mention",
                "url": mention.url,
                "description": mention.content[:1500] if mention.content else "No content",
                "color": color,
                "fields": [
                    {"name": "Source", "value": mention.source, "inline": True},
                    {"name": "Author", "value": mention.author or "unknown", "inline": True},
                    {"name": "Intents", "value": tags_str or "None", "inline": True},
                ],
                "footer": {"text": "ParseStream Free Social Monitor"},
            }
            if reply and reply.content:
                embed["fields"].append({
                    "name": "💡 Suggested Reply",
                    "value": reply.content[:1000],
                    "inline": False,
                })
            payload = {"content": f"🚨 **New Mention Alert**: {title}", "embeds": [embed]}
        # Slack webhook format
        elif "slack.com" in self.webhook_url:
            blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*<{mention.url}|{mention.title or 'New Mention'}>*\n*{tags_str}* | Source: `{mention.source}`\n\n{mention.content[:500]}"}
                }
            ]
            if reply and reply.content:
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"💡 *Suggested Reply:*\n>{reply.content}"}
                })
            payload = {"text": f"New ParseStream Mention: {mention.title}", "blocks": blocks}
        else:
            # Generic webhook JSON
            payload = {
                "source": mention.source,
                "title": mention.title,
                "url": mention.url,
                "content": mention.content,
                "author": mention.author,
                "score": mention.score,
                "intent_tags": [{"tag": t.tag, "confidence": t.confidence} for t in intent_tags],
                "suggested_reply": reply.content if reply else None,
            }

        try:
            resp = await self.client.post(self.webhook_url, json=payload)
            resp.raise_for_status()
            logger.info(f"Webhook alert dispatched to {self.webhook_url[:30]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to dispatch webhook: {e}")
            return False

    async def close(self):
        await self.client.aclose()


_webhook_sender: Optional[WebhookAlertSender] = None


def get_webhook_sender(url: Optional[str] = None) -> WebhookAlertSender:
    global _webhook_sender
    if url:
        return WebhookAlertSender(url)
    if _webhook_sender is None:
        _webhook_sender = WebhookAlertSender()
    return _webhook_sender
