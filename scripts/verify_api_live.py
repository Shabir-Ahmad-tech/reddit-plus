#!/usr/bin/env python3
"""Test all FastAPI endpoints in detail."""
import sys
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.app import app
from fastapi.testclient import TestClient

def test_api():
    client = TestClient(app)

    print("Testing GET / ...")
    r = client.get("/")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert "ParseStream" in r.text
    print("  ✓ Web UI HTML served successfully")

    print("Testing GET /static/app.js ...")
    r = client.get("/static/app.js")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    print("  ✓ Static JS assets served successfully")

    print("Testing GET /api/stats ...")
    r = client.get("/api/stats")
    assert r.status_code == 200
    stats = r.json()
    assert "total_mentions" in stats
    print(f"  ✓ /api/stats: {stats['total_mentions']} total mentions")

    print("Testing GET /api/mentions ...")
    r = client.get("/api/mentions")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    print(f"  ✓ /api/mentions: {len(data['items'])} items returned")

    print("Testing GET /api/keywords ...")
    r = client.get("/api/keywords")
    assert r.status_code == 200
    kws = r.json()
    print(f"  ✓ /api/keywords: {len(kws)} keywords configured")

    print("Testing GET /api/config ...")
    r = client.get("/api/config")
    assert r.status_code == 200
    cfg = r.json()
    assert "ollama" in cfg and "alerts" in cfg
    print("  ✓ /api/config loaded correctly")

    print("Testing POST /api/ai/test-intent (Heuristic fallback test) ...")
    r = client.post("/api/ai/test-intent", json={"text": "Any alternatives to HubSpot? We are looking to switch to a cheaper CRM."})
    assert r.status_code == 200
    intent_data = r.json()
    assert "tag" in intent_data
    print(f"  ✓ Intent Classified: {intent_data['tag']} ({intent_data['confidence_percent']}%)")

    print("Testing POST /api/ai/test-reply ...")
    r = client.post("/api/ai/test-reply", json={
        "content": "Looking for a tool to monitor Reddit and HN comments automatically.",
        "tone": "casual",
        "intent_tag": "buy-intent",
        "source": "reddit"
    })
    assert r.status_code == 200
    reply_data = r.json()
    assert "reply" in reply_data
    print(f"  ✓ Reply Generated: {reply_data['reply'][:60]}...")

    print("Testing POST /api/ai/test-analyze (Deep Post Intelligence) ...")
    r = client.post("/api/ai/test-analyze", json={
        "title": "Need a self hosted social monitor",
        "content": "We need to track mentions of our brand across Reddit and HN with AI intent tags.",
        "source": "reddit"
    })
    assert r.status_code == 200
    analysis = r.json()
    assert "summary" in analysis and "what_it_means" in analysis and "requirements" in analysis
    print(f"  ✓ Deep Post Analysis: Summary, What It Means, Requirements ({len(analysis['requirements'])} reqs)")

    print("Testing GET /api/export?format=csv ...")
    r = client.get("/api/export?format=csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    print("  ✓ CSV Export functional")

    print("Testing GET /api/export?format=json ...")
    r = client.get("/api/export?format=json")
    assert r.status_code == 200
    assert "application/json" in r.headers["content-type"]
    print("  ✓ JSON Export functional")

    print("Testing GET /api/logs ...")
    r = client.get("/api/logs")
    assert r.status_code == 200
    logs = r.json()
    print(f"  ✓ Activity Logs functional ({len(logs)} entries in buffer)")

    print("\n🎉 ALL API ENDPOINTS AND STATIC UI VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    test_api()
