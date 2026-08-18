"""
Reddit Plus v2 Test Runner.
Executes all unit and integration tests.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import inspect
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests import test_matching, test_scoring, test_reddit_normalizer, test_critic, test_api


def run_all_tests():
    modules = [
        test_matching,
        test_scoring,
        test_reddit_normalizer,
        test_critic,
        test_api,
    ]

    total_run = 0
    passed = 0
    failed = 0

    print("=" * 60)
    print("[TEST SUITE] Running Reddit Plus v2 Test Suite")
    print("=" * 60)

    for mod in modules:
        mod_name = mod.__name__.split(".")[-1]
        print(f"\n[SUITE] {mod_name}")
        for name, func in inspect.getmembers(mod, inspect.isfunction):
            if name.startswith("test_"):
                total_run += 1
                try:
                    func()
                    print(f"  [PASS] {name}")
                    passed += 1
                except Exception as e:
                    print(f"  [FAIL] {name} -> FAILED: {e}")
                    failed += 1

    print("\n" + "=" * 60)
    print(f"Test Summary: {passed}/{total_run} PASSED ({failed} failed)")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
