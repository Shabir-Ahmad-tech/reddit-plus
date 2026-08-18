"""
Unit Tests for Deterministic Opportunity Scoring.
"""

from datetime import datetime, timedelta
from src.intelligence.opportunity import OpportunityScorer
from src.database.models import RedditPost, Match, Analysis


def test_high_opportunity_score_calculation():
    post = RedditPost(
        subreddit="saas",
        score=25,
        num_comments=12,
        upvote_ratio=0.94,
        posted_at=datetime.utcnow() - timedelta(minutes=30),
    )
    match = Match(match_score=95.0)
    analysis = Analysis(
        intent_tag="buy-intent",
        buy_signal_strength=90,
        pain_strength=85,
        urgency="High",
    )

    breakdown = OpportunityScorer.calculate(match, post, analysis)
    assert breakdown.total_score >= 80
    assert breakdown.recommended_action == "Reply Now"


def test_low_opportunity_score_calculation():
    post = RedditPost(
        subreddit="general",
        score=1,
        num_comments=0,
        upvote_ratio=0.5,
        posted_at=datetime.utcnow() - timedelta(days=5),
    )
    match = Match(match_score=30.0)
    analysis = Analysis(
        intent_tag="other",
        buy_signal_strength=10,
        pain_strength=10,
        urgency="Low",
    )

    breakdown = OpportunityScorer.calculate(match, post, analysis)
    assert breakdown.total_score < 40
    assert breakdown.recommended_action == "Skip"
