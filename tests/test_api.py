"""
API Endpoint Integration Tests.
"""

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_dashboard_metrics_endpoint():
    resp = client.get("/api/v1/dashboard/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_posts" in data
    assert "high_opportunities" in data
    assert "job_runner" in data


def test_monitoring_rules_crud():
    # 1. Create rule
    create_payload = {
        "name": "Test Python Web Dev",
        "keywords": ["fastapi", "django"],
        "subreddits": ["python", "webdev"],
        "min_score": 5,
        "min_opportunity_score": 70,
    }
    resp = client.post("/api/v1/monitoring-rules", json=create_payload)
    assert resp.status_code == 200
    rule = resp.json()
    rule_id = rule["id"]
    assert rule["name"] == "Test Python Web Dev"

    # 2. List rules
    list_resp = client.get("/api/v1/monitoring-rules")
    assert list_resp.status_code == 200
    rules = list_resp.json()
    assert any(r["id"] == rule_id for r in rules)

    # 3. Delete rule
    del_resp = client.delete(f"/api/v1/monitoring-rules/{rule_id}")
    assert del_resp.status_code == 200


def test_opportunities_list_endpoint():
    resp = client.get("/api/v1/opportunities")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


def test_settings_endpoint():
    resp = client.get("/api/v1/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "app" in data
    assert "llm" in data
    assert "alerts" in data


def test_saas_trends_leaderboard_endpoint():
    resp = client.get("/api/v1/trends/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "leaderboard" in data
    assert len(data["leaderboard"]) > 0
    first = data["leaderboard"][0]
    assert "name" in first
    assert "mentions" in first
    assert "positive_pct" in first


def test_saas_market_gaps_endpoint():
    resp = client.get("/api/v1/trends/market-gaps")
    assert resp.status_code == 200
    data = resp.json()
    assert "gaps" in data
    assert len(data["gaps"]) > 0
    first = data["gaps"][0]
    assert "problem" in first
    assert "opportunity" in first
