"""
Match Repository for Opportunities and Matches.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func, or_

from src.database.models import Match, RedditPost, RedditComment, OpportunityScore, Analysis, ReplyDraft, MonitoringRule


class MatchRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_match(
        self,
        workspace_id: int,
        rule_id: int,
        post_id: Optional[int] = None,
        comment_id: Optional[int] = None,
        match_score: float = 0.0,
        match_reasons: Optional[List[str]] = None,
    ) -> Tuple[Match, bool]:
        """Record a match between a Reddit post/comment and a rule."""
        q = self.session.query(Match).filter(
            Match.rule_id == rule_id,
            Match.workspace_id == workspace_id,
        )
        if post_id:
            q = q.filter(Match.post_id == post_id)
        elif comment_id:
            q = q.filter(Match.comment_id == comment_id)

        existing = q.first()
        if existing:
            existing.match_score = max(existing.match_score, match_score)
            if match_reasons:
                existing.match_reasons = list(set((existing.match_reasons or []) + match_reasons))
            self.session.flush()
            return existing, False

        match = Match(
            workspace_id=workspace_id,
            rule_id=rule_id,
            post_id=post_id,
            comment_id=comment_id,
            match_score=match_score,
            match_reasons=match_reasons or [],
            status="new",
        )
        self.session.add(match)
        self.session.flush()
        return match, True

    def get_by_id(self, match_id: int) -> Optional[Match]:
        return (
            self.session.query(Match)
            .options(
                joinedload(Match.post).joinedload(RedditPost.analysis),
                joinedload(Match.post).joinedload(RedditPost.comments),
                joinedload(Match.rule),
                joinedload(Match.opportunity),
                joinedload(Match.reply_drafts),
            )
            .filter(Match.id == match_id)
            .first()
        )

    def get_opportunities(
        self,
        workspace_id: Optional[int] = None,
        rule_id: Optional[int] = None,
        status: Optional[str] = None,
        min_opportunity: Optional[int] = None,
        intent: Optional[str] = None,
        subreddit: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Match], int]:
        """Fetch Opportunity Inbox feed with rich relations."""
        q = (
            self.session.query(Match)
            .join(Match.post)
            .outerjoin(Match.opportunity)
            .outerjoin(RedditPost.analysis)
            .options(
                joinedload(Match.post).joinedload(RedditPost.analysis),
                joinedload(Match.post).joinedload(RedditPost.comments),
                joinedload(Match.rule),
                joinedload(Match.opportunity),
                joinedload(Match.reply_drafts),
            )
        )

        if workspace_id:
            q = q.filter(Match.workspace_id == workspace_id)

        if rule_id:
            q = q.filter(Match.rule_id == rule_id)

        if status:
            q = q.filter(Match.status == status)

        if min_opportunity:
            q = q.filter(OpportunityScore.total_score >= min_opportunity)

        if intent:
            q = q.filter(Analysis.intent_tag == intent)

        if subreddit:
            q = q.filter(RedditPost.subreddit == subreddit.replace("r/", "").lower())

        total = q.count()

        # Order by Opportunity score descending, then match score
        matches = (
            q.order_by(
                desc(func.coalesce(OpportunityScore.total_score, Match.match_score)),
                desc(Match.created_at),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        return matches, total

    def update_status(self, match_id: int, status: str) -> Optional[Match]:
        match = self.session.query(Match).filter(Match.id == match_id).first()
        if match:
            match.status = status
            self.session.flush()
        return match
