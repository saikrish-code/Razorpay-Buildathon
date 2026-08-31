#!/usr/bin/env python3
"""
generate_data.py
----------------
Forwarder script in recoup/ directory.
Delegates directly to backend/generate_data.py.
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent / "backend"
if backend_dir.exists() and str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from generate_data import main

if __name__ == "__main__":
    main()
