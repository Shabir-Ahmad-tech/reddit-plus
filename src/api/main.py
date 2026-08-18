"""
Reddit Plus v2 — FastAPI Application Entrypoint.
Hardened with enterprise security headers and middleware.
"""

from contextlib import asynccontextmanager
from pathlib import Path
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.config import settings, PROJECT_ROOT
from src.database.session import init_db
from src.jobs.runner import job_runner, log_event
from src.api.v1 import v1_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Reddit Plus v2...")
    init_db()
    await job_runner.start()
    log_event("Application startup complete. Monitoring active.", "info")
    yield
    # Shutdown
    logger.info("Shutting down Reddit Plus v2...")
    await job_runner.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Reddit Plus API",
        version=settings.app.version,
        description="Reddit-Native Social Intelligence & Lead Opportunity Platform",
        lifespan=lifespan,
    )

    # Security Headers Middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: https://*.redditstatic.com https://*.redditmedia.com https://reddit.com; "
            "connect-src 'self'; "
            "manifest-src 'self';"
        )
        return response

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.allowed_origins or ["*"],
        allow_credentials=True if settings.app.allowed_origins != ["*"] else False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API v1 routes
    app.include_router(v1_router)

    # Legacy routes compatibility
    from .legacy_compat import legacy_router
    app.include_router(legacy_router)

    # Static assets and SPA mounting
    static_dir = PROJECT_ROOT / "src" / "api" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_index():
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            return {"message": "Reddit Plus v2 API operational"}

        @app.get("/manifest.json", include_in_schema=False)
        async def serve_manifest():
            return FileResponse(str(static_dir / "manifest.json"), media_type="application/manifest+json")

        @app.get("/sw.js", include_in_schema=False)
        async def serve_sw():
            return FileResponse(str(static_dir / "sw.js"), media_type="application/javascript")

    return app


app = create_app()
