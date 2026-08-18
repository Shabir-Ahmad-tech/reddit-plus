"""
Notifications & Alerts Router (RedditScout Alert Engine).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from src.database.session import get_db
from src.database.repositories.notification_repository import NotificationRepository
from src.config import settings
from src.alerts.push import get_push_sender
from src.alerts.email import get_email_sender
from src.alerts.webhook import get_webhook_sender

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("")
def list_notifications(limit: int = 50, db: Session = Depends(get_db)):
    """List recent notification delivery records."""
    notif_repo = NotificationRepository(db)
    notifs = notif_repo.get_recent(limit=limit)
    return [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "channel": n.channel,
            "status": n.status,
            "error_message": n.error_message,
            "delivered_at": n.delivered_at.isoformat() if n.delivered_at else None,
        }
        for n in notifs
    ]


@router.post("/test-alert")
async def test_alert(channel: str = "ntfy", db: Session = Depends(get_db)):
    """Send a test push, email, or webhook notification."""
    notif_repo = NotificationRepository(db)

    if channel == "ntfy":
        if not settings.alerts.ntfy_topic:
            raise HTTPException(status_code=400, detail="ntfy topic is not configured in Settings.")
        sender = get_push_sender()
        success = await sender.send(
            title="🔔 Reddit Plus Test Alert",
            message="Your high-intent Reddit opportunity alert system is active and running!",
            url="https://reddit.com",
            tags=["test", "bell"],
            priority="default",
        )
        notif_repo.create(
            title="🔔 Reddit Plus Test Alert",
            message="Your high-intent Reddit opportunity alert system is active and running!",
            channel="ntfy",
            status="sent" if success else "failed",
            error_message=None if success else "Failed to dispatch to ntfy server",
        )
        return {"success": success, "channel": "ntfy", "topic": settings.alerts.ntfy_topic}

    elif channel == "email":
        if not settings.alerts.email:
            raise HTTPException(status_code=400, detail="Email recipient is not configured.")
        sender = get_email_sender()
        success = await sender.send(
            subject="🔔 Reddit Plus Test Alert",
            body="Your email alert system is operational.",
            recipient=settings.alerts.email,
        )
        notif_repo.create(
            title="🔔 Reddit Plus Email Test",
            message=f"Dispatched test alert to {settings.alerts.email}",
            channel="email",
            status="sent" if success else "failed",
        )
        return {"success": success, "channel": "email", "to": settings.alerts.email}

    elif channel == "webhook":
        if not settings.alerts.webhook_url:
            raise HTTPException(status_code=400, detail="Webhook URL is not configured.")
        sender = get_webhook_sender()
        success = await sender.send(
            title="Reddit Plus Webhook Test",
            message="High-intent Reddit lead engine operational.",
            subreddit="SaaS",
            opportunity_score=95,
        )
        notif_repo.create(
            title="Reddit Plus Webhook Test",
            message=f"Dispatched test webhook to {settings.alerts.webhook_url[:35]}...",
            channel="webhook",
            status="sent" if success else "failed",
        )
        return {"success": success, "channel": "webhook", "url": settings.alerts.webhook_url}

    raise HTTPException(status_code=400, detail="Unsupported channel. Use 'ntfy', 'email', or 'webhook'.")
