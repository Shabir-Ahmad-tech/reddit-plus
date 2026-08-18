#!/usr/bin/env python3
"""Initialize database tables for Reddit Plus v2."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import init_db
from src.config import settings

def main():
    print(f"Initializing database at: {settings.database.url}")
    init_db()
    print("✅ Reddit Plus v2 database initialized successfully.")

if __name__ == "__main__":
    main()