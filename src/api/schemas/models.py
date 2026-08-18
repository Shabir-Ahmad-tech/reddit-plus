"""
Pydantic Schemas for Reddit Plus v2 API.
Hardened with input bounds and validation constraints.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# --- Monitoring Rules ---
class RuleKeywordCreate(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=150)
    match_type: str = Field(default="phrase", pattern="^(exact|phrase|broad)$")
    weight: float = Field(default=1.0, ge=0.1, le=5.0)
    is_negative: bool = False


class MonitoringRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(default=None, max_length=500)
    keywords: List[str] = Field(default_factory=list, max_length=100)
    subreddits: List[str] = Field(default_factory=list, max_length=50)
    exclusions: List[str] = Field(default_factory=list, max_length=50)
    min_score: int = Field(default=1, ge=0, le=100000)
    min_comments: int = Field(default=0, ge=0, le=100000)
    min_opportunity_score: int = Field(default=60, ge=0, le=100)
    max_age_hours: int = Field(default=72, ge=1, le=720)
    target_intents: List[str] = Field(
        default_factory=lambda: ["buy-intent", "seeking-alternatives", "pain-point", "question"]
    )
    notify_ntfy: bool = True
    notify_email: bool = False
    notify_webhook: bool = False


class MonitoringRuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=150)
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None
    min_score: Optional[int] = Field(default=None, ge=0, le=100000)
    min_comments: Optional[int] = Field(default=None, ge=0, le=100000)
    min_opportunity_score: Optional[int] = Field(default=None, ge=0, le=100)
    max_age_hours: Optional[int] = Field(default=None, ge=1, le=720)


class KeywordExpandRequest(BaseModel):
    seed: str = Field(..., min_length=1, max_length=100)


# --- Replies & Critic ---
class ReplyGenerateRequest(BaseModel):
    post_id: Optional[int] = None
    match_id: Optional[int] = None
    title: Optional[str] = Field(default=None, max_length=500)
    content: Optional[str] = Field(default=None, max_length=10000)
    subreddit: Optional[str] = Field(default="all", max_length=50)
    intent_tag: Optional[str] = Field(default="question", max_length=50)
    strategy: str = Field(default="DIRECT_ANSWER", max_length=50)
    recommended_angle: Optional[str] = Field(default=None, max_length=500)
    product_context: Optional[str] = Field(default=None, max_length=1000)


class ReplyRegenerateRequest(BaseModel):
    strategy: str = Field(default="DIRECT_ANSWER", max_length=50)
    recommended_angle: Optional[str] = Field(default=None, max_length=500)
    product_context: Optional[str] = Field(default=None, max_length=1000)


class ReplyUpdateRequest(BaseModel):
    content: Optional[str] = Field(default=None, max_length=5000)
    status: Optional[str] = Field(default=None, pattern="^(draft|approved|sent|discarded|ignored)$")


class ReplyCriticRequest(BaseModel):
    reply: str = Field(..., min_length=1, max_length=5000)
    title: str = Field(default="Discussion", max_length=500)
    content: str = Field(default="", max_length=10000)
    subreddit: str = Field(default="all", max_length=50)


# --- Competitors ---
class CompetitorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    website: Optional[str] = Field(default=None, max_length=200)
    tracked_keywords: Optional[List[str]] = Field(default=None, max_length=50)


# --- Settings ---
class AlertSettingsUpdate(BaseModel):
    ntfy_topic: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=150)
    webhook_url: Optional[str] = Field(default=None, max_length=500)
    min_opportunity_score: Optional[int] = Field(default=None, ge=0, le=100)
    min_intent_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    tags_to_alert: Optional[List[str]] = None
    frequency: Optional[str] = Field(default=None, max_length=50)


class LLMSettingsUpdate(BaseModel):
    provider: str = Field(..., max_length=50)  # opencode_zen, ollama, auto
    model: Optional[str] = Field(default=None, max_length=100)
    api_key: Optional[str] = Field(default=None, max_length=200)
    ollama_host: Optional[str] = Field(default=None, max_length=200)


class RedditSettingsUpdate(BaseModel):
    client_id: Optional[str] = Field(default=None, max_length=100)
    client_secret: Optional[str] = Field(default=None, max_length=200)
    user_agent: Optional[str] = Field(default=None, max_length=200)
    subreddits: Optional[List[str]] = Field(default=None, max_length=100)


# --- Subreddits ---
class SubredditCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


class SubredditProfileUpdate(BaseModel):
    promotion_tolerance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    technical_depth: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    reply_style: Optional[str] = Field(default=None, max_length=50)
    common_topics: Optional[List[str]] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


# --- Live Search ---
class LiveSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    subreddit: Optional[str] = Field(default="all", max_length=50)
    sort: str = Field(default="new", pattern="^(new|relevance|top)$")
    time_filter: str = Field(default="all", pattern="^(hour|day|week|month|year|all)$")
    limit: int = Field(default=15, ge=1, le=50)
