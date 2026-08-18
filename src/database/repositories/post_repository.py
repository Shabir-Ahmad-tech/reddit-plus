"""
Post Repository for Reddit Posts CRUD and query operations.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func, select, or_

from src.database.models import RedditPost, RedditComment, Analysis


class PostRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_post(
        self,
        reddit_id: str,
        subreddit: str,
        title: str,
        body: Optional[str] = None,
        author: Optional[str] = None,
        url: Optional[str] = None,
        permalink: Optional[str] = None,
        score: int = 0,
        num_comments: int = 0,
        upvote_ratio: float = 0.0,
        post_flair: Optional[str] = None,
        post_type: str = "text",
        thumbnail_url: Optional[str] = None,
        awards_count: int = 0,
        posted_at: Optional[datetime] = None,
    ) -> Tuple[RedditPost, bool]:
        """Upsert a Reddit post. Returns (post, is_new)."""
        post = self.session.query(RedditPost).filter(RedditPost.reddit_id == reddit_id).first()
        is_new = False

        if post:
            # Update dynamic signals
            post.score = score
            post.num_comments = num_comments
            post.upvote_ratio = upvote_ratio
            post.awards_count = awards_count
            if body and len(body) > len(post.body or ""):
                post.body = body
            if post_flair:
                post.post_flair = post_flair
            post.fetched_at = datetime.utcnow()
        else:
            post = RedditPost(
                reddit_id=reddit_id,
                subreddit=subreddit.replace("r/", "").lower(),
                title=title,
                body=body,
                author=author,
                url=url,
                permalink=permalink,
                score=score,
                num_comments=num_comments,
                upvote_ratio=upvote_ratio,
                post_flair=post_flair,
                post_type=post_type,
                thumbnail_url=thumbnail_url,
                awards_count=awards_count,
                posted_at=posted_at or datetime.utcnow(),
                fetched_at=datetime.utcnow(),
            )
            self.session.add(post)
            is_new = True

        self.session.flush()
        return post, is_new

    def get_by_id(self, post_id: int) -> Optional[RedditPost]:
        return (
            self.session.query(RedditPost)
            .options(joinedload(RedditPost.comments), joinedload(RedditPost.analysis))
            .filter(RedditPost.id == post_id)
            .first()
        )

    def get_by_reddit_id(self, reddit_id: str) -> Optional[RedditPost]:
        return self.session.query(RedditPost).filter(RedditPost.reddit_id == reddit_id).first()

    def get_recent(
        self,
        subreddit: Optional[str] = None,
        query: Optional[str] = None,
        hours: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[RedditPost], int]:
        q = self.session.query(RedditPost).options(
            joinedload(RedditPost.analysis),
            joinedload(RedditPost.comments),
        )

        if subreddit:
            q = q.filter(RedditPost.subreddit == subreddit.replace("r/", "").lower())

        if query:
            pattern = f"%{query}%"
            q = q.filter(or_(RedditPost.title.ilike(pattern), RedditPost.body.ilike(pattern)))

        if hours:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            q = q.filter(RedditPost.posted_at >= cutoff)

        total = q.count()
        posts = q.order_by(desc(RedditPost.posted_at)).offset(offset).limit(limit).all()
        return posts, total

    def delete(self, post_id: int) -> bool:
        post = self.get_by_id(post_id)
        if post:
            self.session.delete(post)
            self.session.flush()
            return True
        return False
