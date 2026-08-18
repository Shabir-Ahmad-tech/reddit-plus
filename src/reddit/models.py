"""
Reddit Ingestion Data Models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class NormalizedComment:
    reddit_id: str
    post_reddit_id: str
    parent_reddit_id: Optional[str]
    body: str
    author: str
    score: int = 0
    is_submitter: bool = False
    depth: int = 0
    permalink: Optional[str] = None
    posted_at: Optional[datetime] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedSubmission:
    reddit_id: str
    subreddit: str
    title: str
    body: str
    author: str
    url: Optional[str] = None
    permalink: Optional[str] = None
    score: int = 0
    num_comments: int = 0
    upvote_ratio: float = 0.0
    post_flair: Optional[str] = None
    post_type: str = "text"  # text, link, image, video, gallery
    thumbnail_url: Optional[str] = None
    awards_count: int = 0
    posted_at: Optional[datetime] = None
    top_comments: List[NormalizedComment] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)
