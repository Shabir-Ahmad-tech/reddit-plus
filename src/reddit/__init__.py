"""
Reddit Ingestion Engine for Reddit Plus v2.
"""

from .client import RedditClient
from .auth import RedditAuthManager
from .submissions import SubmissionFetcher
from .comments import CommentFetcher
from .search import RedditSearchService
from .normalizer import normalize_submission, normalize_comment, detect_post_type
from .models import NormalizedSubmission, NormalizedComment
from .rate_limits import AsyncRateLimiter

__all__ = [
    "RedditClient",
    "RedditAuthManager",
    "SubmissionFetcher",
    "CommentFetcher",
    "RedditSearchService",
    "normalize_submission",
    "normalize_comment",
    "detect_post_type",
    "NormalizedSubmission",
    "NormalizedComment",
    "AsyncRateLimiter",
]
