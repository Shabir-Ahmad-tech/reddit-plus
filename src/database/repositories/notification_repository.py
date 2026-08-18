"""
Notification Repository.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.database.models import Notification


class NotificationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_notification(
        self,
        workspace_id: int,
        title: str,
        message: str,
        channel: str = "ntfy",
        match_id: Optional[int] = None,
        status: str = "sent",
        error_message: Optional[str] = None,
    ) -> Notification:
        notif = Notification(
            workspace_id=workspace_id,
            match_id=match_id,
            title=title,
            message=message,
            channel=channel,
            status=status,
            error_message=error_message,
            delivered_at=datetime.utcnow(),
        )
        self.session.add(notif)
        self.session.flush()
        return notif

    def get_recent(self, workspace_id: Optional[int] = None, limit: int = 50) -> List[Notification]:
        q = self.session.query(Notification)
        if workspace_id:
            q = q.filter(Notification.workspace_id == workspace_id)
        return q.order_by(desc(Notification.delivered_at)).limit(limit).all()
