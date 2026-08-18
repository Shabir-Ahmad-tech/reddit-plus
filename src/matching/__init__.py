"""
Matching Engine module for Reddit Plus v2.
"""

from .keyword import KeywordMatcher
from .filters import FilterEngine
from .semantic import SemanticMatcher
from .scoring import MatchingEngine, MatchResult

__all__ = [
    "KeywordMatcher",
    "FilterEngine",
    "SemanticMatcher",
    "MatchingEngine",
    "MatchResult",
]
