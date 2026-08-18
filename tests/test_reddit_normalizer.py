"""
Unit Tests for Reddit Data Normalizer.
"""

from src.reddit.normalizer import normalize_submission, normalize_comment, detect_post_type


def test_submission_normalization():
    raw = {
        "id": "abc123z",
        "subreddit": "SaaS",
        "title": "Looking for a HubSpot alternative",
        "selftext": "We need something more affordable with good API support.",
        "author": "dev_founder",
        "score": 42,
        "num_comments": 15,
        "upvote_ratio": 0.91,
        "link_flair_text": "Question",
        "is_self": True,
        "created_utc": 1700000000,
        "permalink": "/r/SaaS/comments/abc123z/looking_for_a_hubspot_alternative/",
    }

    norm = normalize_submission(raw)
    assert norm.reddit_id == "abc123z"
    assert norm.subreddit == "saas"
    assert norm.title == "Looking for a HubSpot alternative"
    assert norm.score == 42
    assert norm.num_comments == 15
    assert norm.post_type == "text"
    assert "https://reddit.com" in norm.permalink


def test_comment_normalization():
    raw = {
        "id": "c_987",
        "parent_id": "t3_abc123z",
        "body": "Check out Twenty CRM or Brevo, both have great APIs.",
        "author": "helpful_engineer",
        "score": 18,
        "is_submitter": False,
        "created_utc": 1700001000,
    }

    norm = normalize_comment(raw, post_reddit_id="abc123z")
    assert norm.reddit_id == "c_987"
    assert norm.post_reddit_id == "abc123z"
    assert norm.score == 18
    assert "Twenty CRM" in norm.body
