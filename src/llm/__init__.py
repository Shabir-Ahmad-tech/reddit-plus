"""
LLM / AI compatibility package pointing to src.intelligence and src.replies.
"""

from src.intelligence import (
    AIRouter,
    get_ai_router,
    IntentClassifier,
    IntentResult,
    VALID_INTENT_TAGS,
    PostAnalyzer,
    DeepAnalysisResult,
    OpportunityScorer,
    OpportunityScoreBreakdown,
    KeywordExpander,
)
from src.replies import ReplyGenerator, GeneratedReplyResult, ReplyCritic, CriticEvaluation

# Aliases
get_llm_client = get_ai_router

__all__ = [
    "AIRouter",
    "get_ai_router",
    "get_llm_client",
    "IntentClassifier",
    "IntentResult",
    "VALID_INTENT_TAGS",
    "PostAnalyzer",
    "DeepAnalysisResult",
    "OpportunityScorer",
    "OpportunityScoreBreakdown",
    "KeywordExpander",
    "ReplyGenerator",
    "GeneratedReplyResult",
    "ReplyCritic",
    "CriticEvaluation",
]