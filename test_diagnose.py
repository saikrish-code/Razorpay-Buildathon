#!/usr/bin/env python3
"""
test_diagnose.py
----------------
Root runner for diagnose tests. Delegates to backend/test_diagnose.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent / "recoup" / "backend"
if not backend_dir.exists():
    backend_dir = Path(__file__).resolve().parent / "backend"

if backend_dir.exists() and str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from test_diagnose import run_diagnose_tests

if __name__ == "__main__":
    success = run_diagnose_tests()
    sys.exit(0 if success else 1)
