"""
Reddit Plus v2 — Database Engine & Session Factory
Supports SQLite (local standalone) & PostgreSQL.
"""

import os
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from src.config import settings, PROJECT_ROOT
from .models import Base, Workspace, User

logger = logging.getLogger(__name__)

# Ensure data directory exists
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Normalise database URL for SQLite if relative path
db_url = settings.database.url
if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
    # Windows relative path support
    raw_path = db_url.replace("sqlite:///", "")
    if not Path(raw_path).is_absolute():
        abs_path = str((PROJECT_ROOT / raw_path).resolve()).replace("\\", "/")
        db_url = f"sqlite:///{abs_path}"

connect_args = {"check_same_thread": False} if "sqlite" in db_url else {}
engine = create_engine(
    db_url,
    echo=settings.database.echo,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional database session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    with get_session() as session:
        yield session


def init_db():
    """Create all tables and bootstrap default workspace."""
    logger.info("Initializing Reddit Plus v2 database schema...")
    Base.metadata.create_all(bind=engine)

    # Seed default workspace if none exists
    with get_session() as session:
        default_ws = session.query(Workspace).filter(Workspace.slug == "default").first()
        if not default_ws:
            default_ws = Workspace(
                name="Default Workspace",
                slug="default",
            )
            session.add(default_ws)
            session.flush()
            logger.info(f"Created default workspace (id={default_ws.id})")

        # Ensure default admin user
        default_user = session.query(User).filter(User.email == "admin@redditplus.local").first()
        if not default_user:
            default_user = User(
                email="admin@redditplus.local",
                full_name="Admin",
                is_admin=True,
            )
            session.add(default_user)
            session.flush()

    logger.info("Database initialized successfully.")
