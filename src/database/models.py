from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Float, Index, UniqueConstraint, JSON
)
from sqlalchemy.orm import relationship, declarative_base

try:
    from pgvector.sqlalchemy import Vector
    EmbeddingType = JSON
except ImportError:
    EmbeddingType = JSON

Base = declarative_base()


class Mention(Base):
    __tablename__ = "mentions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False, index=True)  # always 'reddit'
    source_id = Column(String(100), nullable=False, index=True)
    url = Column(Text, nullable=False, unique=True)
    title = Column(Text)
    content = Column(Text)
    author = Column(String(200))
    subreddit = Column(String(100), nullable=True, index=True)

    # Reddit-native signals
    score = Column(Integer, default=0)
    num_comments = Column(Integer, default=0)
    upvote_ratio = Column(Float, default=0.0)
    post_flair = Column(String(200), nullable=True)
    post_type = Column(String(50), nullable=True)       # text | link | image | video | gallery
    thumbnail_url = Column(Text, nullable=True)
    awards_count = Column(Integer, default=0)

    posted_at = Column(DateTime, nullable=False, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    embedding = Column(EmbeddingType, nullable=True)
    ai_analysis = Column(JSON, nullable=True)

    # Relationships
    intent_tags = relationship("IntentTag", back_populates="mention", cascade="all, delete-orphan")
    replies = relationship("Reply", back_populates="mention", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_source_source_id"),
        Index("ix_mentions_source_posted", "source", "posted_at"),
    )


class IntentTag(Base):
    __tablename__ = "intent_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mention_id = Column(Integer, ForeignKey("mentions.id", ondelete="CASCADE"), nullable=False, index=True)
    tag = Column(String(50), nullable=False, index=True)
    confidence = Column(Integer, default=0)  # 0-100
    created_at = Column(DateTime, default=datetime.utcnow)

    mention = relationship("Mention", back_populates="intent_tags")


class Reply(Base):
    __tablename__ = "replies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mention_id = Column(Integer, ForeignKey("mentions.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    model = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    sent = Column(Integer, default=0)  # 0 = false, 1 = true

    mention = relationship("Mention", back_populates="replies")


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(200), nullable=False, unique=True, index=True)
    sources = Column(JSON, nullable=False)           # always ["reddit"]
    subreddits = Column(JSON, nullable=True)         # ["python", "startups"] or null
    min_score = Column(Integer, default=1)
    active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class AlertConfig(Base):
    __tablename__ = "alert_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=True)
    ntfy_topic = Column(String(200), nullable=True)
    min_intent_confidence = Column(Integer, default=70)  # 0-100
    tags_to_alert = Column(JSON, nullable=True)
    frequency = Column(String(20), default="immediate")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)