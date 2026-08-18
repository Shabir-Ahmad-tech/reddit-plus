"""
Semantic Similarity Matcher.
"""

import math
from typing import List, Tuple, Optional


class SemanticMatcher:
    """Calculates cosine similarity between text embeddings."""

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return max(0.0, min(1.0, dot_product / (norm_a * norm_b)))

    @staticmethod
    def match(
        post_embedding: Optional[List[float]],
        rule_embedding: Optional[List[float]],
        threshold: float = 0.75,
    ) -> Tuple[bool, float, Optional[str]]:
        if not post_embedding or not rule_embedding:
            return False, 0.0, None

        sim = SemanticMatcher.cosine_similarity(post_embedding, rule_embedding)
        if sim >= threshold:
            return True, sim, f"Semantic similarity match: {sim:.2f}"
        return False, sim, None
