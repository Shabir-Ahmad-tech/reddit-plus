"""
Metadata & Threshold Filters for Monitoring Rules.
"""

from datetime import datetime, timedelta
from typing import Tuple, Optional, List
from src.database.models import MonitoringRule, RedditPost


class FilterEngine:
    """Evaluates score, age, comments, subreddit, and author thresholds."""

    @staticmethod
    def evaluate(post: RedditPost, rule: MonitoringRule) -> Tuple[bool, Optional[str]]:
        """
        Check if a post passes a monitoring rule's threshold filters.
        Returns (passes, failure_reason).
        """
        # 1. Subreddit filter
        rule_subs = [s.subreddit_name.lower().replace("r/", "") for s in (rule.rule_subreddits or []) if not s.is_excluded]
        excluded_subs = [s.subreddit_name.lower().replace("r/", "") for s in (rule.rule_subreddits or []) if s.is_excluded]

        post_sub = post.subreddit.lower().replace("r/", "")

        if excluded_subs and post_sub in excluded_subs:
            return False, f"Subreddit r/{post_sub} is excluded by rule"

        if rule_subs and post_sub not in rule_subs and "all" not in rule_subs:
            return False, f"Subreddit r/{post_sub} is not in rule's target subreddits"

        # 2. Score filter
        if rule.min_score and post.score < rule.min_score:
            return False, f"Post score ({post.score}) is below rule minimum ({rule.min_score})"

        # 3. Comments filter
        if rule.min_comments and post.num_comments < rule.min_comments:
            return False, f"Post comments ({post.num_comments}) is below rule minimum ({rule.min_comments})"

        # 4. Age filter
        if rule.max_age_hours and post.posted_at:
            cutoff = datetime.utcnow() - timedelta(hours=rule.max_age_hours)
            if post.posted_at < cutoff:
                return False, f"Post is older than maximum age ({rule.max_age_hours}h)"

        # 5. Author exclusions
        author_exclusions = [e.pattern.lower() for e in (rule.exclusions or []) if e.exclusion_type == "author"]
        if post.author and post.author.lower() in author_exclusions:
            return False, f"Author u/{post.author} is excluded"

        return True, None
