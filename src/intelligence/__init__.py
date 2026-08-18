"""
Intelligence & AI module for Reddit Plus v2.
"""

from .router import AIRouter, get_ai_router
from .intent import IntentClassifier, IntentResult, VALID_INTENT_TAGS
from .analysis import PostAnalyzer, DeepAnalysisResult
from .opportunity import OpportunityScorer, OpportunityScoreBreakdown
from .keyword_expander import KeywordExpander

__all__ = [
    "AIRouter",
    "get_ai_router",
    "IntentClassifier",
    "IntentResult",
    "VALID_INTENT_TAGS",
    "PostAnalyzer",
    "DeepAnalysisResult",
    "OpportunityScorer",
    "OpportunityScoreBreakdown",
    "KeywordExpander",
]
