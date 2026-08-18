"""
Subreddit Directory & Community Profile Repository.
"""

from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from src.database.models import Subreddit, SubredditProfile


class SubredditRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_subreddit(
        self,
        name: str,
        display_name: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        subscribers: int = 0,
        over18: bool = False,
    ) -> Subreddit:
        clean_name = name.replace("r/", "").strip().lower()
        sub = self.session.query(Subreddit).filter(Subreddit.name == clean_name).first()

        if sub:
            if subscribers:
                sub.subscribers = subscribers
            if title:
                sub.title = title
            if description:
                sub.description = description
            sub.last_crawled_at = datetime.utcnow()
        else:
            sub = Subreddit(
                name=clean_name,
                display_name=display_name or f"r/{clean_name}",
                title=title,
                description=description,
                subscribers=subscribers,
                over18=over18,
                last_crawled_at=datetime.utcnow(),
            )
            self.session.add(sub)
            self.session.flush()

            # Seed default profile
            profile = SubredditProfile(
                subreddit_id=sub.id,
                promotion_tolerance=0.4 if clean_name in ["saas", "startups", "webdev"] else 0.5,
                technical_depth=0.8 if clean_name in ["python", "fastapi", "programming"] else 0.5,
                common_topics=["SaaS", "software", "troubleshooting"],
                reply_style="direct_helpful",
            )
            self.session.add(profile)

        self.session.flush()
        return sub

    def get_by_name(self, name: str) -> Optional[Subreddit]:
        clean = name.replace("r/", "").strip().lower()
        return (
            self.session.query(Subreddit)
            .options(joinedload(Subreddit.profile))
            .filter(Subreddit.name == clean)
            .first()
        )

    def get_all(self, limit: int = 100) -> List[Subreddit]:
        return (
            self.session.query(Subreddit)
            .options(joinedload(Subreddit.profile))
            .order_by(desc(Subreddit.subscribers))
            .limit(limit)
            .all()
        )

    def update_profile(
        self,
        subreddit_id: int,
        promotion_tolerance: Optional[float] = None,
        technical_depth: Optional[float] = None,
        reply_style: Optional[str] = None,
        common_topics: Optional[List[str]] = None,
        notes: Optional[str] = None,
    ) -> Optional[SubredditProfile]:
        profile = self.session.query(SubredditProfile).filter(SubredditProfile.subreddit_id == subreddit_id).first()
        if profile:
            if promotion_tolerance is not None:
                profile.promotion_tolerance = promotion_tolerance
            if technical_depth is not None:
                profile.technical_depth = technical_depth
            if reply_style:
                profile.reply_style = reply_style
            if common_topics is not None:
                profile.common_topics = common_topics
            if notes is not None:
                profile.notes = notes
            profile.updated_at = datetime.utcnow()
            self.session.flush()
        return profile
