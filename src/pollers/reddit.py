"""
Reddit poller compatibility wrapper pointing to src.reddit.
"""

from src.reddit import RedditClient, SubmissionFetcher, CommentFetcher, RedditSearchService, normalize_submission

RedditPoller = SubmissionFetcher

__all__ = ["RedditPoller", "RedditClient", "SubmissionFetcher", "CommentFetcher", "RedditSearchService"]