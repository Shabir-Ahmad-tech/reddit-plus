"""
Settings & System Configuration Router.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from src.config import settings
from src.api.schemas.models import AlertSettingsUpdate, LLMSettingsUpdate
from src.intelligence.router import get_ai_router

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("")
def get_current_settings():
    """Get active system configuration."""
    return {
        "app": {
            "name": settings.app.app_name,
            "version": settings.app.version,
            "environment": settings.app.app_env,
        },
        "reddit": {
            "has_credentials": bool(settings.reddit.client_id and settings.reddit.client_secret),
            "client_id": settings.reddit.client_id or "Public mode",
            "user_agent": settings.reddit.user_agent,
            "subreddits": settings.reddit.subreddits,
        },
        "llm": {
            "provider": settings.llm.provider,
            "model": settings.llm.model,
            "has_api_key": bool(settings.llm.opencode_zen.api_key),
            "ollama_host": settings.llm.ollama.host,
            "ollama_model": settings.llm.ollama.model,
        },
        "alerts": {
            "ntfy_topic": settings.alerts.ntfy_topic,
            "ntfy_server": settings.alerts.ntfy_server,
            "email": settings.alerts.email,
            "webhook_url": settings.alerts.webhook_url,
            "min_opportunity_score": settings.alerts.min_opportunity_score,
            "min_intent_confidence": settings.alerts.min_intent_confidence,
            "tags_to_alert": settings.alerts.tags_to_alert,
            "frequency": settings.alerts.frequency,
        },
    }


@router.put("/alerts")
def update_alert_settings(req: AlertSettingsUpdate):
    """Update alert preferences."""
    if req.ntfy_topic is not None:
        settings.alerts.ntfy_topic = req.ntfy_topic
    if req.email is not None:
        settings.alerts.email = req.email
    if req.webhook_url is not None:
        settings.alerts.webhook_url = req.webhook_url
    if req.min_opportunity_score is not None:
        settings.alerts.min_opportunity_score = req.min_opportunity_score
    if req.min_intent_confidence is not None:
        settings.alerts.min_intent_confidence = req.min_intent_confidence
    if req.tags_to_alert is not None:
        settings.alerts.tags_to_alert = req.tags_to_alert
    if req.frequency is not None:
        settings.alerts.frequency = req.frequency

    return {"success": True, "alerts": settings.alerts.model_dump()}


@router.put("/llm")
def update_llm_settings(req: LLMSettingsUpdate):
    """Update LLM provider and model."""
    settings.llm.provider = req.provider
    if req.model:
        settings.llm.model = req.model
        settings.llm.opencode_zen.model = req.model
    if req.api_key:
        settings.llm.opencode_zen.api_key = req.api_key
    if req.ollama_host:
        settings.llm.ollama.host = req.ollama_host

    return {"success": True, "llm": settings.llm.model_dump(exclude={"opencode_zen": {"api_key"}})}


@router.post("/test-llm")
async def test_llm_connection():
    """Test AI connectivity."""
    router_ai = get_ai_router()
    try:
        resp = await router_ai.generate(
            prompt="Reply with exact text: 'Reddit Plus AI operational.'",
            temperature=0.1,
            max_tokens=30,
        )
        return {
            "healthy": True,
            "provider": router_ai.provider,
            "model": router_ai.active_model,
            "sample_response": resp,
        }
    except Exception as e:
        return {
            "healthy": False,
            "provider": router_ai.provider,
            "model": router_ai.active_model,
            "error": str(e),
        }
