"""
Analysis & Opportunity Score Repository.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.database.models import Analysis, OpportunityScore, Match, RedditPost


class AnalysisRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_analysis(
        self,
        post_id: int,
        summary: Optional[str] = None,
        what_it_means: Optional[str] = None,
        what_it_requires: Optional[str] = None,
        urgency: str = "Medium",
        sentiment: str = "Inquiring",
        intent_tag: str = "question",
        intent_confidence: float = 0.0,
        buy_signal_strength: int = 0,
        pain_strength: int = 0,
        engagement_potential: int = 50,
        mentioned_products: Optional[List[str]] = None,
        pain_keywords: Optional[List[str]] = None,
        requirements: Optional[List[str]] = None,
        goals: Optional[List[str]] = None,
        competitors: Optional[List[str]] = None,
        recommended_angle: Optional[str] = None,
        reddit_context: Optional[str] = None,
        community_signals: Optional[str] = None,
        is_fallback: bool = False,
    ) -> Analysis:
        analysis = self.session.query(Analysis).filter(Analysis.post_id == post_id).first()

        if not analysis:
            analysis = Analysis(post_id=post_id)
            self.session.add(analysis)

        analysis.summary = summary
        analysis.what_it_means = what_it_means
        analysis.what_it_requires = what_it_requires
        analysis.urgency = urgency
        analysis.sentiment = sentiment
        analysis.intent_tag = intent_tag
        analysis.intent_confidence = intent_confidence
        analysis.buy_signal_strength = buy_signal_strength
        analysis.pain_strength = pain_strength
        analysis.engagement_potential = engagement_potential
        analysis.mentioned_products = mentioned_products or []
        analysis.pain_keywords = pain_keywords or []
        analysis.requirements = requirements or []
        analysis.goals = goals or []
        analysis.competitors = competitors or []
        analysis.recommended_angle = recommended_angle
        analysis.reddit_context = reddit_context
        analysis.community_signals = community_signals
        analysis.is_fallback = is_fallback
        analysis.analyzed_at = datetime.utcnow()

        self.session.flush()
        return analysis

    def save_opportunity_score(
        self,
        match_id: int,
        total_score: int,
        relevance_score: float = 0.0,
        buying_signal_score: float = 0.0,
        pain_score: float = 0.0,
        urgency_score: float = 0.0,
        engagement_score: float = 0.0,
        freshness_score: float = 0.0,
        community_fit_score: float = 0.0,
        recommended_action: str = "Monitor",
    ) -> OpportunityScore:
        opp = self.session.query(OpportunityScore).filter(OpportunityScore.match_id == match_id).first()

        if not opp:
            opp = OpportunityScore(match_id=match_id)
            self.session.add(opp)

        opp.total_score = total_score
        opp.relevance_score = relevance_score
        opp.buying_signal_score = buying_signal_score
        opp.pain_score = pain_score
        opp.urgency_score = urgency_score
        opp.engagement_score = engagement_score
        opp.freshness_score = freshness_score
        opp.community_fit_score = community_fit_score
        opp.recommended_action = recommended_action
        opp.calculated_at = datetime.utcnow()

        self.session.flush()
        return opp

    def get_by_post_id(self, post_id: int) -> Optional[Analysis]:
        return self.session.query(Analysis).filter(Analysis.post_id == post_id).first()
