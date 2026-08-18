"""
Deterministic Opportunity Scoring Engine.
Calculates actionable opportunity scores from mathematical formula, NOT random LLM generation.
"""

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Dict, Any, Tuple

from src.database.models import RedditPost, Match, Analysis


@dataclass
class OpportunityScoreBreakdown:
    total_score: int  # 0 to 100
    relevance_score: float  # 0 to 100
    buying_signal_score: float  # 0 to 100
    pain_score: float  # 0 to 100
    urgency_score: float  # 0 to 100
    engagement_score: float  # 0 to 100
    freshness_score: float  # 0 to 100
    community_fit_score: float  # 0 to 100
    recommended_action: str  # Reply Now, Monitor, Bookmark, Skip


class OpportunityScorer:
    """Calculates deterministic opportunity scores according to the Reddit Plus v2 formula."""

    WEIGHT_RELEVANCE = 0.25
    WEIGHT_BUYING_SIGNAL = 0.25
    WEIGHT_PAIN = 0.15
    WEIGHT_URGENCY = 0.10
    WEIGHT_ENGAGEMENT = 0.10
    WEIGHT_FRESHNESS = 0.10
    WEIGHT_COMMUNITY_FIT = 0.05

    @classmethod
    def calculate(
        cls,
        match: Match,
        post: RedditPost,
        analysis: Analysis,
    ) -> OpportunityScoreBreakdown:
        # 1. Relevance Score (from match score and keyword matches)
        relevance = float(match.match_score or 50.0)

        # 2. Buying Signal Score
        buying_signal = float(analysis.buy_signal_strength or 30.0)
        if analysis.intent_tag in ("buy-intent", "seeking-alternatives"):
            buying_signal = max(buying_signal, 85.0)

        # 3. Pain Score
        pain = float(analysis.pain_strength or 30.0)
        if analysis.intent_tag in ("pain-point", "competitor-complaint"):
            pain = max(pain, 80.0)

        # 4. Urgency Score
        urgency_map = {"High": 95.0, "Medium": 60.0, "Low": 30.0}
        urgency = urgency_map.get(analysis.urgency, 50.0)

        # 5. Engagement Score (votes & comments balance)
        score = post.score or 0
        comments = post.num_comments or 0
        engagement = min(100.0, max(20.0, (score * 1.5) + (comments * 2.5) + 30.0))

        # 6. Freshness Score (exponential decay over hours)
        freshness = 100.0
        if post.posted_at:
            age_hours = (datetime.utcnow() - post.posted_at).total_seconds() / 3600.0
            if age_hours <= 2:
                freshness = 100.0
            elif age_hours <= 12:
                freshness = 90.0
            elif age_hours <= 24:
                freshness = 75.0
            elif age_hours <= 72:
                freshness = 55.0
            elif age_hours <= 168:
                freshness = 35.0
            else:
                freshness = 15.0

        # 7. Community Fit Score
        community_fit = 70.0
        if post.upvote_ratio and post.upvote_ratio > 0.85:
            community_fit += 20.0
        if post.post_flair:
            community_fit += 10.0
        community_fit = min(100.0, community_fit)

        # Weighted calculation
        total_float = (
            relevance * cls.WEIGHT_RELEVANCE
            + buying_signal * cls.WEIGHT_BUYING_SIGNAL
            + pain * cls.WEIGHT_PAIN
            + urgency * cls.WEIGHT_URGENCY
            + engagement * cls.WEIGHT_ENGAGEMENT
            + freshness * cls.WEIGHT_FRESHNESS
            + community_fit * cls.WEIGHT_COMMUNITY_FIT
        )

        total_score = int(round(max(0.0, min(100.0, total_float))))

        # Determine recommended action
        if total_score >= 80:
            action = "Reply Now"
        elif total_score >= 60:
            action = "Monitor"
        elif total_score >= 40:
            action = "Bookmark"
        else:
            action = "Skip"

        return OpportunityScoreBreakdown(
            total_score=total_score,
            relevance_score=round(relevance, 1),
            buying_signal_score=round(buying_signal, 1),
            pain_score=round(pain, 1),
            urgency_score=round(urgency, 1),
            engagement_score=round(engagement, 1),
            freshness_score=round(freshness, 1),
            community_fit_score=round(community_fit, 1),
            recommended_action=action,
        )
