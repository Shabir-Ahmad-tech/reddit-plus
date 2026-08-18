import os
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import create_engine, select, func, or_, and_, desc
from sqlalchemy.orm import Session, sessionmaker, joinedload
from sqlalchemy.exc import IntegrityError

from .models import Base, Mention, IntentTag, Reply, Keyword, AlertConfig
from src.config import settings


# Ensure data directory exists
db_path = Path(settings.app.database_path)
if not db_path.is_absolute():
    db_path = Path(os.getcwd()) / db_path
db_path.parent.mkdir(parents=True, exist_ok=True)

# Engine and session factory
engine = create_engine(
    f"sqlite:///{db_path.as_posix()}",
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    """Create all tables and initialize schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    # SQLite schema migration for new and legacy columns
    _new_cols = [
        ("ai_analysis", "JSON"),
        ("num_comments", "INTEGER DEFAULT 0"),
        ("upvote_ratio", "REAL DEFAULT 0.0"),
        ("post_flair", "TEXT"),
        ("post_type", "TEXT"),
        ("thumbnail_url", "TEXT"),
        ("awards_count", "INTEGER DEFAULT 0"),
    ]
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            cols = [row[1] for row in conn.execute(text("PRAGMA table_info(mentions)")).fetchall()]
            for col_name, col_def in _new_cols:
                if col_name not in cols:
                    conn.execute(text(f"ALTER TABLE mentions ADD COLUMN {col_name} {col_def}"))
            conn.commit()
    except Exception:
        pass


@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# --- Mention CRUD ---

def upsert_mention(
    session: Session,
    source: str,
    source_id: str,
    url: str,
    title: Optional[str],
    content: str,
    author: Optional[str],
    subreddit: Optional[str],
    score: int,
    posted_at: datetime,
    num_comments: int = 0,
    upvote_ratio: float = 0.0,
    post_flair: Optional[str] = None,
    post_type: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    awards_count: int = 0,
) -> Tuple[Mention, bool]:
    """Insert or update a mention. Returns (mention, is_new)."""
    # Ensure posted_at has no tzinfo if SQLite requires naive datetimes or normalize
    if posted_at and posted_at.tzinfo is not None:
        posted_at = posted_at.astimezone(timezone.utc).replace(tzinfo=None)

    mention = session.execute(
        select(Mention).where(Mention.source == source, Mention.source_id == source_id)
    ).scalar_one_or_none()

    if mention:
        # Update existing with latest data
        if title:
            mention.title = title
        if content:
            mention.content = content
        if author:
            mention.author = author
        if subreddit:
            mention.subreddit = subreddit
        mention.score = score
        mention.url = url
        # Always update Reddit-native signals
        mention.num_comments = num_comments
        mention.upvote_ratio = upvote_ratio
        if post_flair:
            mention.post_flair = post_flair
        if post_type:
            mention.post_type = post_type
        if thumbnail_url:
            mention.thumbnail_url = thumbnail_url
        mention.awards_count = awards_count
        return mention, False
    else:
        # Create new
        mention = Mention(
            source=source,
            source_id=source_id,
            url=url,
            title=title,
            content=content,
            author=author,
            subreddit=subreddit,
            score=score,
            posted_at=posted_at or datetime.utcnow(),
            fetched_at=datetime.utcnow(),
            num_comments=num_comments,
            upvote_ratio=upvote_ratio,
            post_flair=post_flair,
            post_type=post_type,
            thumbnail_url=thumbnail_url,
            awards_count=awards_count,
        )
        session.add(mention)
        session.flush()
        return mention, True


def get_mention_by_id(session: Session, mention_id: int) -> Optional[Mention]:
    """Fetch single mention with relations preloaded."""
    return session.execute(
        select(Mention)
        .options(joinedload(Mention.intent_tags), joinedload(Mention.replies))
        .where(Mention.id == mention_id)
    ).unique().scalar_one_or_none()


def update_mention_analysis(session: Session, mention_id: int, analysis: Dict[str, Any]) -> Optional[Mention]:
    """Save or update structured AI analysis for a mention."""
    mention = session.execute(select(Mention).where(Mention.id == mention_id)).scalar_one_or_none()
    if mention:
        mention.ai_analysis = analysis
        session.flush()
    return mention


def get_unprocessed_mentions(session: Session, limit: int = 50) -> List[Mention]:
    """Get mentions that don't have intent tags yet."""
    subquery = select(IntentTag.mention_id).distinct()
    return session.execute(
        select(Mention)
        .where(~Mention.id.in_(subquery))
        .order_by(Mention.posted_at.desc())
        .limit(limit)
    ).scalars().all()


def get_all_mentions_for_reclassify(session: Session, limit: int = 200) -> List[Mention]:
    """Get ALL mentions for forced re-classification (including already-classified).
    Prioritises posts with low-confidence fallback tags (confidence == 60) first.
    """
    return session.execute(
        select(Mention)
        .options(joinedload(Mention.intent_tags))
        .order_by(Mention.posted_at.desc())
        .limit(limit)
    ).unique().scalars().all()




def get_mentions_filtered(
    session: Session,
    source: Optional[str] = None,
    tag: Optional[str] = None,
    query: Optional[str] = None,
    min_confidence: Optional[float] = None,
    has_reply: Optional[bool] = None,
    is_sent: Optional[bool] = None,
    hours: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Mention], int]:
    """Get filtered and paginated mentions with total count."""
    stmt = select(Mention).options(
        joinedload(Mention.intent_tags),
        joinedload(Mention.replies)
    )

    filters = []

    if source and source != "all":
        filters.append(Mention.source == source)

    if query and query.strip():
        q = f"%{query.strip()}%"
        filters.append(or_(Mention.title.ilike(q), Mention.content.ilike(q), Mention.author.ilike(q)))

    if hours:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        filters.append(Mention.posted_at >= cutoff)

    if tag and tag != "all":
        sub_tag = select(IntentTag.mention_id).where(IntentTag.tag == tag)
        if min_confidence is not None:
            sub_tag = sub_tag.where(IntentTag.confidence >= int(min_confidence * 100))
        filters.append(Mention.id.in_(sub_tag))
    elif min_confidence is not None and min_confidence > 0:
        sub_conf = select(IntentTag.mention_id).where(IntentTag.confidence >= int(min_confidence * 100))
        filters.append(Mention.id.in_(sub_conf))

    if has_reply is not None:
        sub_rep = select(Reply.mention_id).distinct()
        if has_reply:
            filters.append(Mention.id.in_(sub_rep))
        else:
            filters.append(~Mention.id.in_(sub_rep))

    if is_sent is not None:
        sub_sent = select(Reply.mention_id).where(Reply.sent == (1 if is_sent else 0))
        filters.append(Mention.id.in_(sub_sent))

    if filters:
        stmt = stmt.where(and_(*filters))

    # Count total
    count_stmt = select(func.count(Mention.id))
    if filters:
        count_stmt = count_stmt.where(and_(*filters))
    total_count = session.execute(count_stmt).scalar() or 0

    # Paginate and sort
    stmt = stmt.order_by(Mention.posted_at.desc()).offset(offset).limit(limit)
    mentions = session.execute(stmt).unique().scalars().all()

    return mentions, total_count


def get_mentions_by_keyword(
    session: Session,
    keyword: str,
    source: Optional[str] = None,
    limit: int = 20,
) -> List[Mention]:
    """Search mentions by keyword in title or content."""
    query = select(Mention).options(
        joinedload(Mention.intent_tags),
        joinedload(Mention.replies)
    ).where(
        or_(
            Mention.title.ilike(f"%{keyword}%"),
            Mention.content.ilike(f"%{keyword}%"),
        )
    )
    if source and source != "all":
        query = query.where(Mention.source == source)
    query = query.order_by(Mention.posted_at.desc()).limit(limit)
    return session.execute(query).unique().scalars().all()


def get_recent_mentions(session: Session, hours: int = 24, limit: int = 100) -> List[Mention]:
    """Get mentions from the last N hours."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    return session.execute(
        select(Mention)
        .options(joinedload(Mention.intent_tags), joinedload(Mention.replies))
        .where(Mention.posted_at >= cutoff)
        .order_by(Mention.posted_at.desc())
        .limit(limit)
    ).unique().scalars().all()


def delete_mention(session: Session, mention_id: int) -> bool:
    """Delete a mention by ID."""
    mention = session.get(Mention, mention_id)
    if mention:
        session.delete(mention)
        return True
    return False


# --- Dashboard Stats ---

def get_dashboard_stats(session: Session) -> Dict[str, Any]:
    """Aggregate statistics for the dashboard."""
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)

    total_mentions = session.execute(select(func.count(Mention.id))).scalar() or 0
    mentions_24h = session.execute(
        select(func.count(Mention.id)).where(Mention.posted_at >= last_24h)
    ).scalar() or 0

    # Source breakdown
    source_rows = session.execute(
        select(Mention.source, func.count(Mention.id)).group_by(Mention.source)
    ).all()
    source_counts = {row[0]: row[1] for row in source_rows}

    # Intent tag breakdown
    tag_rows = session.execute(
        select(IntentTag.tag, func.count(IntentTag.id)).group_by(IntentTag.tag)
    ).all()
    tag_counts = {row[0]: row[1] for row in tag_rows}

    actionable_tags = ["buy-intent", "pain-point", "competitor-complaint"]
    actionable_leads = sum(tag_counts.get(t, 0) for t in actionable_tags)

    # Replies
    total_replies = session.execute(select(func.count(Reply.id))).scalar() or 0
    sent_replies = session.execute(select(func.count(Reply.id)).where(Reply.sent == 1)).scalar() or 0
    pending_replies = total_replies - sent_replies

    # Active keywords
    active_keywords_count = session.execute(
        select(func.count(Keyword.id)).where(Keyword.active == 1)
    ).scalar() or 0

    # Mentions over last 24h (by 4-hour buckets)
    timeline_labels = []
    timeline_counts = []
    for i in range(6, -1, -1):
        bucket_start = now - timedelta(hours=(i + 1) * 4)
        bucket_end = now - timedelta(hours=i * 4)
        count = session.execute(
            select(func.count(Mention.id)).where(
                and_(Mention.posted_at >= bucket_start, Mention.posted_at < bucket_end)
            )
        ).scalar() or 0
        timeline_labels.append(bucket_end.strftime("%H:%M"))
        timeline_counts.append(count)

    return {
        "total_mentions": total_mentions,
        "mentions_24h": mentions_24h,
        "actionable_leads": actionable_leads,
        "total_replies": total_replies,
        "sent_replies": sent_replies,
        "pending_replies": pending_replies,
        "active_keywords": active_keywords_count,
        "source_counts": source_counts,
        "tag_counts": tag_counts,
        "timeline": {
            "labels": timeline_labels,
            "counts": timeline_counts,
        },
    }


# --- Intent Tag CRUD ---

def add_intent_tag(session: Session, mention_id: int, tag: str, confidence: float) -> IntentTag:
    """Add an intent tag to a mention. Confidence stored as 0-100 int."""
    # Check if tag already exists for this mention
    existing = session.execute(
        select(IntentTag).where(IntentTag.mention_id == mention_id, IntentTag.tag == tag)
    ).scalar_one_or_none()
    if existing:
        existing.confidence = int(confidence * 100)
        return existing

    intent_tag = IntentTag(
        mention_id=mention_id,
        tag=tag,
        confidence=int(confidence * 100),
    )
    session.add(intent_tag)
    session.flush()
    return intent_tag


def get_intent_tags(session: Session, mention_id: int) -> List[IntentTag]:
    return session.execute(
        select(IntentTag).where(IntentTag.mention_id == mention_id)
    ).scalars().all()


# --- Reply CRUD ---

def add_reply(session: Session, mention_id: int, content: str, model: str) -> Reply:
    """Add or replace suggested reply."""
    existing = session.execute(
        select(Reply).where(Reply.mention_id == mention_id)
    ).scalar_one_or_none()
    if existing:
        existing.content = content
        existing.model = model
        existing.created_at = datetime.utcnow()
        return existing

    reply = Reply(mention_id=mention_id, content=content, model=model)
    session.add(reply)
    session.flush()
    return reply


def update_reply_content(session: Session, reply_id: int, content: str) -> Optional[Reply]:
    reply = session.get(Reply, reply_id)
    if reply:
        reply.content = content
        session.flush()
    return reply


def get_unsent_replies(session: Session) -> List[Reply]:
    return session.execute(
        select(Reply).where(Reply.sent == 0)
    ).scalars().all()


def mark_reply_sent(session: Session, reply_id: int, sent: bool = True):
    reply = session.get(Reply, reply_id)
    if reply:
        reply.sent = 1 if sent else 0
        session.flush()


# --- Keyword CRUD ---

def add_keyword(
    session: Session,
    keyword: str,
    sources: List[str],
    subreddits: Optional[List[str]] = None,
    min_score: int = 1,
) -> Keyword:
    kw_str = keyword.strip().lower()
    kw = session.execute(
        select(Keyword).where(Keyword.keyword == kw_str)
    ).scalar_one_or_none()

    if kw:
        kw.sources = sources
        kw.subreddits = subreddits
        kw.min_score = min_score
        kw.active = 1
        return kw

    kw = Keyword(
        keyword=kw_str,
        sources=sources,
        subreddits=subreddits,
        min_score=min_score,
        active=1,
    )
    session.add(kw)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return session.execute(
            select(Keyword).where(Keyword.keyword == kw_str)
        ).scalar_one()
    return kw


def get_all_keywords(session: Session) -> List[Keyword]:
    return session.execute(
        select(Keyword).order_by(Keyword.created_at.desc())
    ).scalars().all()


def get_active_keywords(session: Session) -> List[Keyword]:
    return session.execute(
        select(Keyword).where(Keyword.active == 1)
    ).scalars().all()


def update_keyword_active(session: Session, keyword_id: int, active: bool) -> Optional[Keyword]:
    kw = session.get(Keyword, keyword_id)
    if kw:
        kw.active = 1 if active else 0
        session.flush()
    return kw


def delete_keyword(session: Session, keyword: str) -> bool:
    kw = session.execute(
        select(Keyword).where(Keyword.keyword == keyword.lower())
    ).scalar_one_or_none()
    if kw:
        session.delete(kw)
        return True
    return False


def delete_keyword_by_id(session: Session, keyword_id: int) -> bool:
    kw = session.get(Keyword, keyword_id)
    if kw:
        session.delete(kw)
        return True
    return False


# --- Alert Config CRUD ---

def get_alert_config(session: Session) -> Optional[AlertConfig]:
    return session.execute(select(AlertConfig).limit(1)).scalar_one_or_none()


def upsert_alert_config(
    session: Session,
    email: Optional[str] = None,
    ntfy_topic: Optional[str] = None,
    min_intent_confidence: float = 0.7,
    tags_to_alert: Optional[List[str]] = None,
    frequency: str = "hourly",
) -> AlertConfig:
    config = get_alert_config(session)
    if config:
        config.email = email
        config.ntfy_topic = ntfy_topic
        config.min_intent_confidence = int(min_intent_confidence * 100)
        config.tags_to_alert = tags_to_alert or ["buy-intent", "pain-point", "competitor-complaint"]
        config.frequency = frequency
        config.updated_at = datetime.utcnow()
    else:
        config = AlertConfig(
            email=email,
            ntfy_topic=ntfy_topic,
            min_intent_confidence=int(min_intent_confidence * 100),
            tags_to_alert=tags_to_alert or ["buy-intent", "pain-point", "competitor-complaint"],
            frequency=frequency,
        )
        session.add(config)
    session.flush()
    return config