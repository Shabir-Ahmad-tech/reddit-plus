#!/usr/bin/env python3
"""Initialize database tables."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import init_db
from src.config import settings

def main():
    print(f"Initializing database at: {settings.app.database_path}")
    init_db()
    print("✅ Database tables created successfully")

if __name__ == "__main__":
    main()