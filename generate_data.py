#!/usr/bin/env python3
"""
generate_data.py
----------------
Root forwarder / standalone entrypoint for synthetic data generation.
Delegates to backend/generate_data.py or executes directly.
"""

import sys
from pathlib import Path

# Add backend directory to python path
backend_dir = Path(__file__).resolve().parent / "recoup" / "backend"
if not backend_dir.exists():
    backend_dir = Path(__file__).resolve().parent / "backend"

if backend_dir.exists() and str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from generate_data import main

if __name__ == "__main__":
    main()
