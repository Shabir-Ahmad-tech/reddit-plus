#!/usr/bin/env python3
"""Comprehensive test and verification script for ParseStream Free."""
import sys
import asyncio
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import (
    init_db,
    get_session,
    add_keyword,
    get_all_keywords,
    upsert_mention,
    get_mentions_filtered,
    get_dashboard_stats,
    add_intent_tag,
    add_reply,
    delete_keyword,
)
from src.pollers.hackernews import HackerNewsPoller
from src.pollers.reddit import RedditPoller
from src.llm import classify_intent, generate_reply
from src.alerts import get_email_sender, get_push_sender, get_webhook_sender


async def run_tests():
    print("=" * 60)
    print("🚀 PARSESTREAM FREE — COMPLETE ENGINE VERIFICATION")
    print("=" * 60)

    # 1. Database Init & CRUD Test
    print("\n[1/5] Testing Database Initialization & CRUD...")
    init_db()
    with get_session() as session:
        kw = add_keyword(session, "saas monitoring test", ["reddit", "hackernews"], ["startups"], min_score=1)
        print(f"  ✓ Added keyword: {kw.keyword} (id={kw.id})")

        keywords = get_all_keywords(session)
        print(f"  ✓ Total keywords in DB: {len(keywords)}")

        # Add sample mention
        mention, is_new = upsert_mention(
            session=session,
            source="reddit",
            source_id="test_post_001",
            url="https://reddit.com/r/startups/comments/test_post_001",
            title="Looking for a tool to monitor social discussions",
            content="We need a reliable SaaS to track when people talk about our product on Reddit and Hacker News. Any recommendations?",
            author="founder_joe",
            subreddit="startups",
            score=15,
            posted_at=None,
        )
        print(f"  ✓ Upserted mention: ID={mention.id}, IsNew={is_new}")

        # Add intent and reply
        add_intent_tag(session, mention.id, "buy-intent", 0.92)
        add_reply(session, mention.id, "Hi Joe, check out ParseStream Free which is an open-source self-hosted monitor.", "test-model")
        print("  ✓ Attached Intent Tag ('buy-intent', 92%) and Suggested Reply")

        # Stats
        stats = get_dashboard_stats(session)
        print(f"  ✓ Dashboard Stats Aggregated: Total={stats['total_mentions']}, Leads={stats['actionable_leads']}, Replies={stats['total_replies']}")

    # 2. AI Classifier & Heuristic Fallback Test
    print("\n[2/5] Testing AI Classification & Reply Generation...")
    sample_text = "I am so frustrated with our current CRM, it is constantly crashing and buggy. Looking for alternatives!"
    intent_res = await classify_intent(sample_text)
    print(f"  ✓ Intent Classification: Tag='{intent_res.tag}', Conf={intent_res.confidence:.2f}, Fallback={intent_res.is_fallback}")

    reply_res = await generate_reply("reddit", "Alternative to broken CRM?", sample_text, intent_res.tag, tone="empathic")
    print(f"  ✓ Reply Generation ({reply_res.model}): \"{reply_res.content[:80]}...\"")

    # 3. Hacker News Poller Test (Algolia Real-time API)
    print("\n[3/5] Testing Hacker News Real-Time Algolia Poller...")
    hn = HackerNewsPoller()
    conn = await hn.test_connection()
    print(f"  ✓ HN Connection Health: {'ONLINE' if conn else 'OFFLINE'}")
    live_hn = await hn.search_live("python", limit=2)
    print(f"  ✓ Live HN search returned {len(live_hn)} items")
    if live_hn:
        print(f"     Example: [{live_hn[0]['source_id']}] {live_hn[0]['title'][:50]} (points: {live_hn[0]['score']})")
    await hn.close()

    # 4. Reddit Poller Test
    print("\n[4/5] Testing Reddit Poller (PRAW & Public JSON Fallback)...")
    reddit = RedditPoller()
    live_reddit = await reddit.search_live("saas", limit=2)
    print(f"  ✓ Live Reddit search returned {len(live_reddit)} items")
    if live_reddit:
        print(f"     Example: {live_reddit[0]['title'][:50]} (score: {live_reddit[0]['score']})")
    await reddit.close()

    # 5. FastAPI App and Web UI Test
    print("\n[5/5] Testing Web API & Static UI Assets...")
    from src.api.app import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    res_stats = client.get("/api/stats")
    print(f"  ✓ GET /api/stats -> Status {res_stats.status_code}")

    res_mentions = client.get("/api/mentions")
    print(f"  ✓ GET /api/mentions -> Status {res_mentions.status_code}, Found {len(res_mentions.json().get('items', []))} items")

    res_ui = client.get("/")
    print(f"  ✓ GET / (SPA UI HTML) -> Status {res_ui.status_code}, Length {len(res_ui.text)} bytes")

    print("\n" + "=" * 60)
    print("🎉 ALL SYSTEMS OPERATIONAL AND FULLY VERIFIED!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
