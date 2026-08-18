"""
API v1 Router module.
"""

from fastapi import APIRouter

from .dashboard import router as dashboard_router
from .opportunities import router as opportunities_router
from .posts import router as posts_router
from .monitoring import router as monitoring_router
from .replies import router as replies_router
from .subreddits import router as subreddits_router
from .competitors import router as competitors_router
from .notifications import router as notifications_router
from .settings import router as settings_router

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(dashboard_router)
v1_router.include_router(opportunities_router)
v1_router.include_router(posts_router)
v1_router.include_router(monitoring_router)
v1_router.include_router(replies_router)
v1_router.include_router(subreddits_router)
v1_router.include_router(competitors_router)
v1_router.include_router(notifications_router)
v1_router.include_router(settings_router)

__all__ = ["v1_router"]
