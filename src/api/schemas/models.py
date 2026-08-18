"""
Pydantic Schemas for Reddit Plus v2 API.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# --- Monitoring Rules ---
class RuleKeywordCreate(BaseModel):
    keyword: str
    match_type: str = "phrase"  # exact, phrase, broad
    weight: float = 1.0
    is_negative: bool = False


class MonitoringRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    subreddits: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)
    min_score: int = 1
    min_comments: int = 0
    min_opportunity_score: int = 60
    max_age_hours: int = 72
    target_intents: List[str] = Field(
        default_factory=lambda: ["buy-intent", "seeking-alternatives", "pain-point", "question"]
    )
    notify_ntfy: bool = True
    notify_email: bool = False
    notify_webhook: bool = False


class MonitoringRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    min_score: Optional[int] = None
    min_comments: Optional[int] = None
    min_opportunity_score: Optional[int] = None
    max_age_hours: Optional[int] = None


class KeywordExpandRequest(BaseModel):
    seed: str


# --- Replies & Critic ---
class ReplyGenerateRequest(BaseModel):
    post_id: Optional[int] = None
    match_id: Optional[int] = None
    title: Optional[str] = None
    content: Optional[str] = None
    subreddit: Optional[str] = "all"
    intent_tag: Optional[str] = "question"
    strategy: str = "DIRECT_ANSWER"
    recommended_angle: Optional[str] = None
    product_context: Optional[str] = None


class ReplyRegenerateRequest(BaseModel):
    strategy: str = "DIRECT_ANSWER"
    recommended_angle: Optional[str] = None
    product_context: Optional[str] = None


class ReplyUpdateRequest(BaseModel):
    content: Optional[str] = None
    status: Optional[str] = None  # approved, sent, discarded


class ReplyCriticRequest(BaseModel):
    reply: str
    title: str
    content: str
    subreddit: str = "all"


# --- Competitors ---
class CompetitorCreate(BaseModel):
    name: str
    website: Optional[str] = None
    tracked_keywords: Optional[List[str]] = None


# --- Settings ---
class AlertSettingsUpdate(BaseModel):
    ntfy_topic: Optional[str] = None
    email: Optional[str] = None
    webhook_url: Optional[str] = None
    min_opportunity_score: Optional[int] = None
    min_intent_confidence: Optional[float] = None
    tags_to_alert: Optional[List[str]] = None
    frequency: Optional[str] = None


class LLMSettingsUpdate(BaseModel):
    provider: str  # opencode_zen, ollama, auto
    model: Optional[str] = None
    api_key: Optional[str] = None
    ollama_host: Optional[str] = None


# --- Subreddits ---
class SubredditCreate(BaseModel):
    name: str


class SubredditProfileUpdate(BaseModel):
    promotion_tolerance: Optional[float] = None
    technical_depth: Optional[float] = None
    reply_style: Optional[str] = None
    common_topics: Optional[List[str]] = None
    notes: Optional[str] = None


# --- Live Search ---
class LiveSearchRequest(BaseModel):
    query: str
    subreddit: Optional[str] = "all"
    sort: str = "new"
    time_filter: str = "all"
    limit: int = 15
