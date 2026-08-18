"""
Reply Drafts and Critic Scorecards Repository.
"""

from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.database.models import ReplyDraft


class ReplyRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_draft(
        self,
        match_id: int,
        content: str,
        strategy: str = "DIRECT_ANSWER",
        model_used: str = "AI",
        post_id: Optional[int] = None,
        comment_id: Optional[int] = None,
        critic_scorecard: Optional[Dict[str, Any]] = None,
        promotion_risk: int = 0,
        is_safe: bool = True,
    ) -> ReplyDraft:
        draft = ReplyDraft(
            match_id=match_id,
            post_id=post_id,
            comment_id=comment_id,
            strategy=strategy,
            content=content,
            model_used=model_used,
            critic_scorecard=critic_scorecard or {},
            promotion_risk=promotion_risk,
            is_safe=is_safe,
            status="draft",
        )
        self.session.add(draft)
        self.session.flush()
        return draft

    def get_by_match_id(self, match_id: int) -> List[ReplyDraft]:
        return (
            self.session.query(ReplyDraft)
            .filter(ReplyDraft.match_id == match_id)
            .order_by(desc(ReplyDraft.created_at))
            .all()
        )

    def get_by_id(self, reply_id: int) -> Optional[ReplyDraft]:
        return self.session.query(ReplyDraft).filter(ReplyDraft.id == reply_id).first()

    def mark_status(self, reply_id: int, status: str) -> Optional[ReplyDraft]:
        reply = self.get_by_id(reply_id)
        if reply:
            reply.status = status
            if status == "sent":
                reply.sent_at = datetime.utcnow()
            self.session.flush()
        return reply

    def update_content(self, reply_id: int, content: str) -> Optional[ReplyDraft]:
        reply = self.get_by_id(reply_id)
        if reply:
            reply.content = content
            self.session.flush()
        return reply
