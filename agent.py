#!/usr/bin/env python3
"""
agent.py
--------
Root entrypoint for Recoup AI Core Recovery Agent.
Delegates to backend/agent.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent / "recoup" / "backend"
if not backend_dir.exists():
    backend_dir = Path(__file__).resolve().parent / "backend"

if backend_dir.exists() and str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from agent import main

if __name__ == "__main__":
    main()
