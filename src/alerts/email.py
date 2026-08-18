import logging
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

from src.config import settings
from src.database import Mention, IntentTag, Reply

logger = logging.getLogger(__name__)


class EmailAlertSender:
    def __init__(self):
        self.api_key = settings.alerts.sendgrid.api_key
        self.from_email = settings.alerts.sendgrid.from_email
        self.to_email = settings.alerts.sendgrid.to_email
        self.client = SendGridAPIClient(api_key=self.api_key) if self.api_key else None

    def is_configured(self) -> bool:
        return bool(self.api_key and self.from_email and self.to_email)

    def send_immediate_alert(
        self,
        mention: Mention,
        intent_tags: list[IntentTag],
        reply: Optional[Reply] = None,
    ) -> bool:
        """Send immediate alert for a single mention."""
        if not self.is_configured():
            logger.warning("SendGrid not configured, skipping email")
            return False

        # Build subject
        tags_str = ", ".join([t.tag for t in intent_tags])
        subject = f"[ParseStream] {mention.source}: {tags_str} - {mention.title[:80]}"

        # Build HTML content
        html_content = self._build_html(mention, intent_tags, reply)

        try:
            message = Mail(
                from_email=Email(self.from_email),
                to_emails=To(self.to_email),
                subject=subject,
                html_content=Content("text/html", html_content),
            )
            response = self.client.send(message)
            logger.info(f"Email sent: {response.status_code}")
            return response.status_code == 202
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_digest(
        self,
        mentions: list[tuple[Mention, list[IntentTag], Optional[Reply]]],
    ) -> bool:
        """Send digest email with multiple mentions."""
        if not self.is_configured() or not mentions:
            return False

        subject = f"[ParseStream] Daily Digest - {len(mentions)} new mentions"
        html_content = self._build_digest_html(mentions)

        try:
            message = Mail(
                from_email=Email(self.from_email),
                to_emails=To(self.to_email),
                subject=subject,
                html_content=Content("text/html", html_content),
            )
            response = self.client.send(message)
            logger.info(f"Digest email sent: {response.status_code}")
            return response.status_code == 202
        except Exception as e:
            logger.error(f"Failed to send digest email: {e}")
            return False

    def _build_html(
        self,
        mention: Mention,
        intent_tags: list[IntentTag],
        reply: Optional[Reply],
    ) -> str:
        tags_html = "".join(
            f'<span style="background:#e0e7ff;color:#3730a3;padding:2px 8px;border-radius:4px;font-size:12px;margin-right:4px;">{t.tag} ({t.confidence}%)</span>'
            for t in intent_tags
        )

        reply_html = ""
        if reply and reply.content:
            reply_html = f"""
            <div style="margin-top:16px;padding:12px;background:#f0fdf4;border-left:4px solid #22c55e;border-radius:4px;">
                <strong>Suggested Reply:</strong>
                <p style="margin:8px 0 0 0;white-space:pre-wrap;">{reply.content}</p>
            </div>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family:system-ui,-apple-system,sans-serif;line-height:1.6;max-width:600px;margin:0 auto;padding:20px;">
            <h2 style="color:#1f2937;margin-bottom:8px;">New Mention Detected</h2>
            <p style="color:#6b7280;margin-bottom:16px;">
                <strong>Source:</strong> {mention.source} |
                <strong>Subreddit:</strong> {mention.subreddit or 'N/A'} |
                <strong>Score:</strong> {mention.score}
            </p>
            <div style="margin-bottom:16px;">{tags_html}</div>
            <h3 style="margin:16px 0 8px 0;">{mention.title}</h3>
            <div style="background:#f9fafb;padding:12px;border-radius:4px;white-space:pre-wrap;">{mention.content[:1000]}{'...' if len(mention.content) > 1000 else ''}</div>
            <p style="margin-top:16px;">
                <a href="{mention.url}" style="color:#3b82f6;text-decoration:none;">View on {mention.source} →</a>
            </p>
            {reply_html}
            <hr style="margin:24px 0;border:none;border-top:1px solid #e5e7eb;">
            <p style="color:#9ca3af;font-size:12px;">ParseStream Free - Self-hosted social monitoring</p>
        </body>
        </html>
        """

    def _build_digest_html(
        self,
        mentions: list[tuple[Mention, list[IntentTag], Optional[Reply]]],
    ) -> str:
        items_html = ""
        for mention, intent_tags, reply in mentions:
            tags_html = "".join(
                f'<span style="background:#e0e7ff;color:#3730a3;padding:2px 6px;border-radius:3px;font-size:11px;margin-right:3px;">{t.tag}</span>'
                for t in intent_tags
            )
            items_html += f"""
            <div style="margin-bottom:20px;padding:16px;background:#fafafa;border-radius:6px;border:1px solid #e5e7eb;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <span style="font-weight:600;color:#1f2937;">{mention.source}</span>
                    <span style="color:#6b7280;font-size:12px;">Score: {mention.score}</span>
                </div>
                <div style="margin-bottom:8px;">{tags_html}</div>
                <h4 style="margin:8px 0;"><a href="{mention.url}" style="color:#3b82f6;text-decoration:none;">{mention.title}</a></h4>
                <p style="color:#4b5563;margin:8px 0;">{mention.content[:300]}{'...' if len(mention.content) > 300 else ''}</p>
            </div>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family:system-ui,-apple-system,sans-serif;line-height:1.6;max-width:600px;margin:0 auto;padding:20px;">
            <h2 style="color:#1f2937;">ParseStream Daily Digest</h2>
            <p style="color:#6b7280;">{len(mentions)} new mentions in the last 24 hours</p>
            {items_html}
            <hr style="margin:24px 0;border:none;border-top:1px solid #e5e7eb;">
            <p style="color:#9ca3af;font-size:12px;">ParseStream Free - Self-hosted social monitoring</p>
        </body>
        </html>
        """


# Singleton
_email_sender: Optional[EmailAlertSender] = None


def get_email_sender() -> EmailAlertSender:
    global _email_sender
    if _email_sender is None:
        _email_sender = EmailAlertSender()
    return _email_sender