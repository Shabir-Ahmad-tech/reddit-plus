"""
Reddit Plus v2 — Domain-Driven Database Models
Comprehensive multi-user, opportunity-first data architecture.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import json

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    Float,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    """User account model for multi-user / team access."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    workspace_memberships = relationship("WorkspaceMember", back_populates="user", cascade="all, delete-orphan")


class Workspace(Base):
    """Multi-tenant organization/workspace."""
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")
    monitoring_rules = relationship("MonitoringRule", back_populates="workspace", cascade="all, delete-orphan")
    matches = relationship("Match", back_populates="workspace", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="workspace", cascade="all, delete-orphan")
    competitors = relationship("Competitor", back_populates="workspace", cascade="all, delete-orphan")


class WorkspaceMember(Base):
    """Workspace membership with roles."""
    __tablename__ = "workspace_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), default="member")  # admin, member, viewer
    created_at = Column(DateTime, default=datetime.utcnow)

    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User", back_populates="workspace_memberships")

    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),)


class Subreddit(Base):
    """Subreddit directory and metadata."""
    __tablename__ = "subreddits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(150), nullable=True)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    subscribers = Column(BigInteger, default=0)
    over18 = Column(Boolean, default=False)
    is_monitored = Column(Boolean, default=True)
    last_crawled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    profile = relationship("SubredditProfile", back_populates="subreddit", uselist=False, cascade="all, delete-orphan")
    posts = relationship("RedditPost", back_populates="subreddit_rel")


class SubredditProfile(Base):
    """Community intelligence profile for a subreddit."""
    __tablename__ = "subreddit_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subreddit_id = Column(Integer, ForeignKey("subreddits.id", ondelete="CASCADE"), unique=True, nullable=False)
    promotion_tolerance = Column(Float, default=0.5)  # 0.0 (zero tolerance) to 1.0 (free promotion)
    technical_depth = Column(Float, default=0.5)  # 0.0 (casual) to 1.0 (hardcore technical)
    average_post_length = Column(Integer, default=500)
    common_topics = Column(JSON, default=list)  # ["SaaS", "marketing", "pricing"]
    common_intents = Column(JSON, default=list)  # ["pain-point", "seeking-alternatives"]
    reply_style = Column(String(100), default="casual_value")  # direct, technical, storytelling
    self_promotion_risk = Column(Float, default=0.6)  # 0.0 to 1.0
    rules_summary = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subreddit = relationship("Subreddit", back_populates="profile")


class MonitoringRule(Base):
    """Rich monitoring rules defining what conversations to detect."""
    __tablename__ = "monitoring_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    # Threshold filters
    min_score = Column(Integer, default=1)
    min_comments = Column(Integer, default=0)
    min_opportunity_score = Column(Integer, default=60)
    max_age_hours = Column(Integer, default=72)
    target_intents = Column(JSON, default=list)  # ["buy-intent", "seeking-alternatives"]

    # Notification preferences per rule
    notify_ntfy = Column(Boolean, default=True)
    notify_email = Column(Boolean, default=False)
    notify_webhook = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    workspace = relationship("Workspace", back_populates="monitoring_rules")
    keywords = relationship("RuleKeyword", back_populates="rule", cascade="all, delete-orphan")
    rule_subreddits = relationship("RuleSubreddit", back_populates="rule", cascade="all, delete-orphan")
    exclusions = relationship("RuleExclusion", back_populates="rule", cascade="all, delete-orphan")
    matches = relationship("Match", back_populates="rule", cascade="all, delete-orphan")


class RuleKeyword(Base):
    """Target keywords or phrases associated with a monitoring rule."""
    __tablename__ = "rule_keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey("monitoring_rules.id", ondelete="CASCADE"), nullable=False)
    keyword = Column(String(255), nullable=False)
    match_type = Column(String(50), default="phrase")  # exact, phrase, broad
    weight = Column(Float, default=1.0)
    is_negative = Column(Boolean, default=False)

    rule = relationship("MonitoringRule", back_populates="keywords")


class RuleSubreddit(Base):
    """Subreddits scoped to a monitoring rule."""
    __tablename__ = "rule_subreddits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey("monitoring_rules.id", ondelete="CASCADE"), nullable=False)
    subreddit_name = Column(String(100), nullable=False)
    is_excluded = Column(Boolean, default=False)

    rule = relationship("MonitoringRule", back_populates="rule_subreddits")


class RuleExclusion(Base):
    """Negative patterns or author exclusions for a rule."""
    __tablename__ = "rule_exclusions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey("monitoring_rules.id", ondelete="CASCADE"), nullable=False)
    exclusion_type = Column(String(50), default="keyword")  # keyword, author, flair
    pattern = Column(String(255), nullable=False)

    rule = relationship("MonitoringRule", back_populates="exclusions")


class RedditPost(Base):
    """Reddit post entity with complete native Reddit signals."""
    __tablename__ = "reddit_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reddit_id = Column(String(50), unique=True, nullable=False, index=True)
    subreddit = Column(String(100), nullable=False, index=True)
    subreddit_id = Column(Integer, ForeignKey("subreddits.id", ondelete="SET NULL"), nullable=True)

    title = Column(Text, nullable=False)
    body = Column(Text, nullable=True)
    author = Column(String(100), nullable=True, index=True)
    url = Column(Text, nullable=True)
    permalink = Column(Text, nullable=True)

    score = Column(Integer, default=0, index=True)
    num_comments = Column(Integer, default=0)
    upvote_ratio = Column(Float, default=0.0)
    post_flair = Column(String(200), nullable=True)
    post_type = Column(String(50), default="text")  # text, link, image, video, gallery
    thumbnail_url = Column(Text, nullable=True)
    awards_count = Column(Integer, default=0)
    is_locked = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)

    posted_at = Column(DateTime, nullable=False, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    subreddit_rel = relationship("Subreddit", back_populates="posts")
    comments = relationship("RedditComment", back_populates="post", cascade="all, delete-orphan")
    matches = relationship("Match", back_populates="post", cascade="all, delete-orphan")
    analysis = relationship("Analysis", back_populates="post", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_reddit_posts_sub_posted", "subreddit", "posted_at"),
    )


class RedditComment(Base):
    """Reddit comments with hierarchical threading and top-comment tracking."""
    __tablename__ = "reddit_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reddit_id = Column(String(50), unique=True, nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("reddit_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_reddit_id = Column(String(50), nullable=True)

    body = Column(Text, nullable=False)
    author = Column(String(100), nullable=True)
    score = Column(Integer, default=0)
    is_submitter = Column(Boolean, default=False)
    depth = Column(Integer, default=0)
    permalink = Column(Text, nullable=True)
    posted_at = Column(DateTime, nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    post = relationship("RedditPost", back_populates="comments")
    matches = relationship("Match", back_populates="comment", cascade="all, delete-orphan")


class Match(Base):
    """Decoupled match entity connecting a Reddit post/comment with a monitoring rule."""
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey("monitoring_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("reddit_posts.id", ondelete="CASCADE"), nullable=True, index=True)
    comment_id = Column(Integer, ForeignKey("reddit_comments.id", ondelete="CASCADE"), nullable=True, index=True)

    match_score = Column(Float, default=0.0)  # 0 to 100
    match_reasons = Column(JSON, default=list)  # ["Exact keyword: AI automation", "Buying intent: high", ...]
    status = Column(String(50), default="new", index=True)  # new, saved, ignored, replied, archived

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="matches")
    rule = relationship("MonitoringRule", back_populates="matches")
    post = relationship("RedditPost", back_populates="matches")
    comment = relationship("RedditComment", back_populates="matches")
    opportunity = relationship("OpportunityScore", back_populates="match", uselist=False, cascade="all, delete-orphan")
    reply_drafts = relationship("ReplyDraft", back_populates="match", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="match", cascade="all, delete-orphan")


class Analysis(Base):
    """Deep AI intelligence analysis for a post."""
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("reddit_posts.id", ondelete="CASCADE"), unique=True, nullable=False)

    summary = Column(Text, nullable=True)
    what_it_means = Column(Text, nullable=True)
    what_it_requires = Column(Text, nullable=True)
    urgency = Column(String(50), default="Medium")  # High, Medium, Low
    sentiment = Column(String(50), default="Inquiring")
    intent_tag = Column(String(100), default="question", index=True)
    intent_confidence = Column(Float, default=0.0)

    # Signals
    buy_signal_strength = Column(Integer, default=0)
    pain_strength = Column(Integer, default=0)
    engagement_potential = Column(Integer, default=50)

    # Structured extractions
    mentioned_products = Column(JSON, default=list)
    pain_keywords = Column(JSON, default=list)
    requirements = Column(JSON, default=list)
    goals = Column(JSON, default=list)
    competitors = Column(JSON, default=list)

    recommended_angle = Column(Text, nullable=True)
    reddit_context = Column(Text, nullable=True)
    community_signals = Column(Text, nullable=True)

    is_fallback = Column(Boolean, default=False)
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("RedditPost", back_populates="analysis")


class OpportunityScore(Base):
    """Deterministic opportunity score calculated by the scoring formula."""
    __tablename__ = "opportunity_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), unique=True, nullable=False)

    total_score = Column(Integer, default=0, index=True)  # 0 to 100
    relevance_score = Column(Float, default=0.0)
    buying_signal_score = Column(Float, default=0.0)
    pain_score = Column(Float, default=0.0)
    urgency_score = Column(Float, default=0.0)
    engagement_score = Column(Float, default=0.0)
    freshness_score = Column(Float, default=0.0)
    community_fit_score = Column(Float, default=0.0)

    recommended_action = Column(String(100), default="Monitor")  # Reply Now, Monitor, Bookmark, Skip
    calculated_at = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match", back_populates="opportunity")


class ReplyDraft(Base):
    """Generated reply draft with strategy and critic evaluation."""
    __tablename__ = "reply_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("reddit_posts.id", ondelete="CASCADE"), nullable=True)
    comment_id = Column(Integer, ForeignKey("reddit_comments.id", ondelete="CASCADE"), nullable=True)

    strategy = Column(String(100), default="DIRECT_ANSWER")  # DIRECT_ANSWER, VALUE_FIRST, TECHNICAL, PERSONAL_EXPERIENCE, COMPARISON, QUESTION_BACK, SOFT_MENTION, NO_PROMOTION
    content = Column(Text, nullable=False)
    model_used = Column(String(100), default="AI")
    status = Column(String(50), default="draft")  # draft, approved, sent, rejected

    # Critic evaluation
    critic_scorecard = Column(JSON, default=dict)  # {"authenticity": 92, "relevance": 95, "helpfulness": 88, "promotion_risk": 12, ...}
    promotion_risk = Column(Integer, default=0)
    is_safe = Column(Boolean, default=True)

    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    match = relationship("Match", back_populates="reply_drafts")


class Notification(Base):
    """Alert event record."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=True)

    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    channel = Column(String(50), default="ntfy")  # ntfy, email, webhook
    status = Column(String(50), default="sent")  # sent, failed, pending
    error_message = Column(Text, nullable=True)
    delivered_at = Column(DateTime, default=datetime.utcnow)

    workspace = relationship("Workspace", back_populates="notifications")
    match = relationship("Match", back_populates="notifications")


class Competitor(Base):
    """Competitor tracking entity."""
    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(150), nullable=False)
    website = Column(String(255), nullable=True)
    tracked_keywords = Column(JSON, default=list)  # ["Zapier alternative", "switch from Zapier"]
    auto_rule_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    workspace = relationship("Workspace", back_populates="competitors")