#!/usr/bin/env python3
"""
test_guardrail.py
-----------------
Root test runner for Deterministic Guardrails & Recoup Agent.
Runs pytest on tests/test_guardrail.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent / "recoup" / "backend"
if not backend_dir.exists():
    backend_dir = Path(__file__).resolve().parent / "backend"

if backend_dir.exists() and str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest


def main() -> int:
    test_path = backend_dir / "tests" / "test_guardrail.py"
    if not test_path.exists():
        test_path = Path(__file__).resolve().parent / "recoup" / "backend" / "tests" / "test_guardrail.py"

    print("=" * 80)
    print("  RUNNING RECOUP DETERMINISTIC GUARDRAIL & AGENT UNIT TESTS")
    print("=" * 80)
    ret_code = pytest.main(["-v", str(test_path)])
    return int(ret_code)


if __name__ == "__main__":
    sys.exit(main())
