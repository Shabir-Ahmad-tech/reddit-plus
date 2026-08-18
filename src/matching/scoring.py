"""
Matching Engine Coordinator.
Evaluates posts against monitoring rules and produces explainable match results.
"""

from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime

from src.database.models import MonitoringRule, RedditPost, RedditComment
from .keyword import KeywordMatcher
from .filters import FilterEngine
from .semantic import SemanticMatcher


class MatchResult:
    def __init__(
        self,
        is_match: bool,
        match_score: float,
        match_reasons: List[str],
        rule_id: int,
        post_id: Optional[int] = None,
        comment_id: Optional[int] = None,
    ):
        self.is_match = is_match
        self.matched = is_match  # Alias for backward compatibility
        self.score = round(match_score, 1)  # Alias for backward compatibility
        self.reasons = match_reasons  # Alias for backward compatibility
        self.match_score = round(match_score, 1)
        self.match_reasons = match_reasons
        self.rule_id = rule_id
        self.post_id = post_id
        self.comment_id = comment_id


class MatchingEngine:
    def __init__(self):
        self.keyword_matcher = KeywordMatcher()
        self.filter_engine = FilterEngine()
        self.semantic_matcher = SemanticMatcher()

    def evaluate_post(self, post: RedditPost, rule: MonitoringRule) -> MatchResult:
        """
        Evaluate a single Reddit post against a monitoring rule.
        Returns MatchResult with score and explainable reasons.
        """
        if not rule.is_active:
            return MatchResult(False, 0.0, [], rule.id, post.id)

        # 1. Evaluate hard threshold filters (score, age, subreddit, author)
        passes_filters, fail_reason = self.filter_engine.evaluate(post, rule)
        if not passes_filters:
            return MatchResult(False, 0.0, [], rule.id, post.id)

        combined_text = f"{post.title or ''}\n{post.body or ''}"
        reasons: List[str] = []
        score_accum = 0.0

        # 2. Check negative exclusions
        neg_keywords = [
            exc.pattern
            for exc in (rule.exclusions or [])
            if exc.exclusion_type in ("keyword", "negative")
        ]
        is_excluded, exc_reason = self.keyword_matcher.check_exclusions(combined_text, neg_keywords)
        if is_excluded:
            return MatchResult(False, 0.0, [], rule.id, post.id)

        # 3. Check rule keywords
        matched_kws = 0
        total_kws = len(rule.keywords or [])

        for rk in (rule.keywords or []):
            if rk.is_negative:
                continue

            matched, conf, reason = self.keyword_matcher.match_keyword(
                combined_text, rk.keyword, rk.match_type
            )
            if matched:
                matched_kws += 1
                weight = rk.weight or 1.0
                score_accum += 40.0 * conf * weight
                reasons.append(reason)

                # Bonus for title match
                if post.title and rk.keyword.lower() in post.title.lower():
                    score_accum += 15.0
                    reasons.append(f"Title contains keyword: '{rk.keyword}'")

        # If rule has keywords but none matched -> no match
        if total_kws > 0 and matched_kws == 0:
            return MatchResult(False, 0.0, [], rule.id, post.id)

        # 4. Community fit signals
        if post.subreddit:
            reasons.append(f"Target subreddit: r/{post.subreddit}")
            score_accum += 10.0

        if post.score and post.score > 10:
            score_accum += min(15.0, post.score / 10.0)
            reasons.append(f"High engagement post ({post.score} upvotes)")

        if post.num_comments and post.num_comments > 5:
            score_accum += min(10.0, post.num_comments / 5.0)

        # Calculate final match score normalized 0-100
        final_score = min(100.0, max(20.0, score_accum))

        return MatchResult(
            is_match=True,
            match_score=final_score,
            match_reasons=reasons,
            rule_id=rule.id,
            post_id=post.id,
        )
