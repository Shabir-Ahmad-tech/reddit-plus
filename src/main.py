"""
Reddit Plus v2 — CLI & Application Launcher.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import os
from pathlib import Path
import typer
import uvicorn

from src.config import settings
from src.database.session import init_db

cli = typer.Typer(
    name="reddit-plus",
    help="Reddit Plus v2 — Reddit Intelligence & Lead Generation Platform",
    no_args_is_help=True,
)


@cli.command("ui")
def start_ui(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind server to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind server to"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload for development"),
):
    """Launch the Reddit Plus Web Dashboard & Background Ingestion API."""
    print("=" * 60)
    print(">> Starting Reddit Plus v2 Intelligence Platform")
    print(f">> Web Dashboard: http://{host}:{port}")
    print(">> Opportunity Inbox & Reddit Monitoring Active")
    print("=" * 60)
    uvicorn.run("src.api.main:app", host=host, port=port, reload=reload)


@cli.command("init")
def initialize_database():
    """Initialize database tables and default workspace."""
    init_db()
    print(">> Database schema initialized successfully.")


@cli.command("run-cycle")
def run_cycle():
    """Execute a single ingestion, matching, AI analysis, and alert cycle."""
    import asyncio
    from src.jobs.runner import job_runner

    init_db()
    print(">> Running single Reddit Plus intelligence cycle...")
    results = asyncio.run(job_runner.run_full_cycle())
    print(f">> Cycle completed: {results}")


if __name__ == "__main__":
    cli()