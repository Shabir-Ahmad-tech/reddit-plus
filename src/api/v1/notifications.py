"""
Notifications & Alerts Router.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from src.database.session import get_db
from src.database.repositories.notification_repository import NotificationRepository
from src.config import settings
from src.alerts.push import get_push_sender
from src.alerts.email import get_email_sender

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
async def test_alert(channel: str = "ntfy"):
    """Send a test push or email notification."""
    if channel == "ntfy":
        if not settings.alerts.ntfy_topic:
            raise HTTPException(status_code=400, detail="ntfy topic is not configured in Settings.")
        sender = get_push_sender()
        success = await sender.send(
            title="🔔 Reddit Plus Test Alert",
            message="Your notification setup is working perfectly!",
            url="https://reddit.com",
            tags=["test", "bell"],
            priority="default",
        )
        return {"success": success, "channel": "ntfy", "topic": settings.alerts.ntfy_topic}

    elif channel == "email":
        if not settings.alerts.email:
            raise HTTPException(status_code=400, detail="Email is not configured.")
        sender = get_email_sender()
        success = await sender.send(
            subject="🔔 Reddit Plus Test Alert",
            body="Your email alert setup is working.",
            recipient=settings.alerts.email,
        )
        return {"success": success, "channel": "email", "to": settings.alerts.email}

    raise HTTPException(status_code=400, detail="Unsupported channel")
