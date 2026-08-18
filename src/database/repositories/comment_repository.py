"""
Comment Repository for Reddit Comments CRUD and query operations.
"""

from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.database.models import RedditComment


class CommentRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_comment(
        self,
        reddit_id: str,
        post_id: int,
        body: str,
        author: Optional[str] = None,
        score: int = 0,
        parent_reddit_id: Optional[str] = None,
        is_submitter: bool = False,
        depth: int = 0,
        permalink: Optional[str] = None,
        posted_at: Optional[datetime] = None,
    ) -> Tuple[RedditComment, bool]:
        """Upsert a Reddit comment. Returns (comment, is_new)."""
        comment = self.session.query(RedditComment).filter(RedditComment.reddit_id == reddit_id).first()
        is_new = False

        if comment:
            comment.score = score
            if body and len(body) > len(comment.body or ""):
                comment.body = body
            comment.fetched_at = datetime.utcnow()
        else:
            comment = RedditComment(
                reddit_id=reddit_id,
                post_id=post_id,
                parent_reddit_id=parent_reddit_id,
                body=body,
                author=author,
                score=score,
                is_submitter=is_submitter,
                depth=depth,
                permalink=permalink,
                posted_at=posted_at or datetime.utcnow(),
                fetched_at=datetime.utcnow(),
            )
            self.session.add(comment)
            is_new = True

        self.session.flush()
        return comment, is_new

    def get_by_post(self, post_id: int, limit: int = 50) -> List[RedditComment]:
        return (
            self.session.query(RedditComment)
            .filter(RedditComment.post_id == post_id)
            .order_by(desc(RedditComment.score))
            .limit(limit)
            .all()
        )
