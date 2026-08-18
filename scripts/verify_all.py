#!/usr/bin/env python3
"""
Reddit Plus v2 End-to-End System Verification.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.run_tests import run_all_tests
from src.database import init_db
from src.matching import MatchingEngine
from src.intelligence import OpportunityScorer

def main():
    print("🚀 Verifying Reddit Plus v2...")
    init_db()
    run_all_tests()
    print("🎉 All systems operational!")

if __name__ == "__main__":
    main()
