"""
Database module for Reddit Plus v2.
"""

from .models import (
    Base,
    User,
    Workspace,
    WorkspaceMember,
    Subreddit,
    SubredditProfile,
    MonitoringRule,
    RuleKeyword,
    RuleSubreddit,
    RuleExclusion,
    RedditPost,
    RedditComment,
    Match,
    Analysis,
    OpportunityScore,
    ReplyDraft,
    Notification,
    Competitor,
)
from .session import get_session, get_db, init_db, engine, SessionLocal
from .repositories.post_repository import PostRepository
from .repositories.comment_repository import CommentRepository
from .repositories.rule_repository import RuleRepository
from .repositories.match_repository import MatchRepository
from .repositories.analysis_repository import AnalysisRepository
from .repositories.reply_repository import ReplyRepository
from .repositories.subreddit_repository import SubredditRepository
from .repositories.notification_repository import NotificationRepository
from .repositories.competitor_repository import CompetitorRepository

__all__ = [
    "Base",
    "User",
    "Workspace",
    "WorkspaceMember",
    "Subreddit",
    "SubredditProfile",
    "MonitoringRule",
    "RuleKeyword",
    "RuleSubreddit",
    "RuleExclusion",
    "RedditPost",
    "RedditComment",
    "Match",
    "Analysis",
    "OpportunityScore",
    "ReplyDraft",
    "Notification",
    "Competitor",
    "get_session",
    "get_db",
    "init_db",
    "engine",
    "SessionLocal",
    "PostRepository",
    "CommentRepository",
    "RuleRepository",
    "MatchRepository",
    "AnalysisRepository",
    "ReplyRepository",
    "SubredditRepository",
    "NotificationRepository",
    "CompetitorRepository",
]