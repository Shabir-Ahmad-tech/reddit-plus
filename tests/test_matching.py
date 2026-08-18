"""
Unit Tests for Matching Engine.
"""

from src.matching.keyword import KeywordMatcher
from src.matching.filters import FilterEngine
from src.database.models import MonitoringRule, RuleKeyword, RuleSubreddit, RuleExclusion, RedditPost
from datetime import datetime, timedelta


def test_exact_phrase_matching():
    matcher = KeywordMatcher()
    text = "I am looking for an AI automation solution for our CRM."
    matched, conf, reason = matcher.match_keyword(text, "AI automation")
    assert matched is True
    assert conf == 1.0
    assert "Exact phrase match" in reason


def test_token_matching():
    matcher = KeywordMatcher()
    text = "We need good workflow automation tools for our team."
    matched, conf, reason = matcher.match_keyword(text, "workflow automation")
    assert matched is True
    assert conf >= 0.85


def test_negative_exclusions():
    matcher = KeywordMatcher()
    text = "This is a free tutorial on how to build scrapers."
    is_exc, reason = matcher.check_exclusions(text, ["tutorial", "free course"])
    assert is_exc is True
    assert "Negative keyword exclusion" in reason


def test_filter_engine_subreddit():
    rule = MonitoringRule(
        name="SaaS Only",
        is_active=True,
        rule_subreddits=[RuleSubreddit(subreddit_name="saas", is_excluded=False)],
    )
    post_pass = RedditPost(subreddit="saas", score=10, num_comments=2, posted_at=datetime.utcnow())
    passes, _ = FilterEngine.evaluate(post_pass, rule)
    assert passes is True

    post_fail = RedditPost(subreddit="gaming", score=10, num_comments=2, posted_at=datetime.utcnow())
    passes, fail_reason = FilterEngine.evaluate(post_fail, rule)
    assert passes is False
    assert "not in rule's target subreddits" in fail_reason
