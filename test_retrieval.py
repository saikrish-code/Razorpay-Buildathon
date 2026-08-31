#!/usr/bin/env python3
"""
test_retrieval.py
-----------------
Root forwarder for test_retrieval.py.
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent / "recoup" / "backend"
if not backend_dir.exists():
    backend_dir = Path(__file__).resolve().parent / "backend"

if backend_dir.exists() and str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from test_retrieval import main

if __name__ == "__main__":
    main()
