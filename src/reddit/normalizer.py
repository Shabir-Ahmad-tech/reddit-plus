"""
Reddit Data Normalizer.
Standardizes raw Reddit JSON or PRAW responses into NormalizedSubmission / NormalizedComment.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from .models import NormalizedSubmission, NormalizedComment


def detect_post_type(data: Dict[str, Any]) -> str:
    """Determine the post type from raw Reddit JSON."""
    if data.get("is_video"):
        return "video"
    if data.get("is_gallery"):
        return "gallery"
    post_hint = data.get("post_hint", "")
    if post_hint == "image" or any((data.get("url") or "").lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
        return "image"
    if data.get("is_self", True):
        return "text"
    if data.get("url") and "reddit.com" not in data.get("url", ""):
        return "link"
    return "text"


def extract_thumbnail(data: Dict[str, Any]) -> Optional[str]:
    """Extract a safe thumbnail URL if present."""
    thumb = data.get("thumbnail", "")
    if thumb and thumb.startswith("http") and thumb not in ("self", "default", "nsfw", "spoiler"):
        return thumb
    return None


def normalize_submission(data: Dict[str, Any]) -> NormalizedSubmission:
    """Convert raw Reddit submission dict into NormalizedSubmission."""
    created_utc = data.get("created_utc", 0)
    try:
        posted_at = datetime.fromtimestamp(created_utc, tz=timezone.utc).replace(tzinfo=None) if created_utc else datetime.utcnow()
    except Exception:
        posted_at = datetime.utcnow()

    sub_name = (data.get("subreddit") or "all").replace("r/", "").lower()
    reddit_id = str(data.get("id", "") or "")

    permalink = data.get("permalink", "")
    if permalink and not permalink.startswith("http"):
        full_permalink = f"https://reddit.com{permalink}"
    elif permalink and permalink.startswith("http"):
        full_permalink = permalink
    elif reddit_id and sub_name:
        full_permalink = f"https://reddit.com/r/{sub_name}/comments/{reddit_id}"
    else:
        full_permalink = f"https://reddit.com/r/{sub_name}"

    author = data.get("author") or "[deleted]"
    body = data.get("selftext") or data.get("body") or ""

    return NormalizedSubmission(
        reddit_id=reddit_id,
        subreddit=sub_name,
        title=data.get("title", ""),
        body=body,
        author=str(author),
        url=data.get("url") or full_permalink,
        permalink=full_permalink,
        score=int(data.get("score", 0) or 0),
        num_comments=int(data.get("num_comments", 0) or 0),
        upvote_ratio=float(data.get("upvote_ratio", 0.0) or 0.0),
        post_flair=data.get("link_flair_text") or None,
        post_type=detect_post_type(data),
        thumbnail_url=extract_thumbnail(data),
        awards_count=int(data.get("total_awards_received", 0) or 0),
        posted_at=posted_at,
        raw_data=data,
    )


def normalize_comment(data: Dict[str, Any], post_reddit_id: str) -> NormalizedComment:
    """Convert raw Reddit comment dict into NormalizedComment."""
    created_utc = data.get("created_utc", 0)
    try:
        posted_at = datetime.fromtimestamp(created_utc, tz=timezone.utc).replace(tzinfo=None) if created_utc else datetime.utcnow()
    except Exception:
        posted_at = datetime.utcnow()

    permalink = data.get("permalink", "")
    if permalink and not permalink.startswith("http"):
        full_permalink = f"https://reddit.com{permalink}"
    elif permalink and permalink.startswith("http"):
        full_permalink = permalink
    else:
        full_permalink = None

    return NormalizedComment(
        reddit_id=str(data.get("id", "") or ""),
        post_reddit_id=post_reddit_id,
        parent_reddit_id=data.get("parent_id"),
        body=data.get("body", ""),
        author=str(data.get("author") or "[deleted]"),
        score=int(data.get("score", 0) or 0),
        is_submitter=bool(data.get("is_submitter", False)),
        depth=int(data.get("depth", 0) or 0),
        permalink=full_permalink,
        posted_at=posted_at,
        raw_data=data,
    )
