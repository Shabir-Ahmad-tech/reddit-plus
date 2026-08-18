"""
Email Alert Sender using SendGrid or SMTP for Reddit Plus v2.
"""

import logging
from typing import Optional, List
from src.config import settings

logger = logging.getLogger(__name__)


class EmailAlertSender:
    def __init__(self):
        self.api_key = settings.alerts.sendgrid_api_key
        self.from_email = settings.alerts.from_email
        self.to_email = settings.alerts.email

    def is_configured(self) -> bool:
        return bool(self.api_key and self.from_email and self.to_email)

    async def send(self, subject: str, body: str, recipient: Optional[str] = None) -> bool:
        to_addr = recipient or self.to_email
        if not self.is_configured() or not to_addr:
            logger.debug("Email alert not configured, skipping")
            return False

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content

            client = SendGridAPIClient(api_key=self.api_key)
            message = Mail(
                from_email=Email(self.from_email),
                to_emails=To(to_addr),
                subject=subject,
                html_content=Content("text/html", f"<div style='font-family:sans-serif;'>{body}</div>"),
            )
            resp = client.send(message)
            return resp.status_code in (200, 202)
        except Exception as e:
            logger.warning(f"SendGrid email failed: {e}")
            return False


_email_sender: Optional[EmailAlertSender] = None


def get_email_sender() -> EmailAlertSender:
    global _email_sender
    if _email_sender is None:
        _email_sender = EmailAlertSender()
    return _email_sender