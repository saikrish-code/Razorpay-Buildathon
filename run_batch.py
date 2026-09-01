#!/usr/bin/env python3
"""
run_batch.py
------------
Root entrypoint for Recoup AI batch recovery runner.
Delegates to backend/run_batch.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent / "recoup" / "backend"
if not backend_dir.exists():
    backend_dir = Path(__file__).resolve().parent / "backend"

if backend_dir.exists() and str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from run_batch import (
    BatchSummaryReport,
    BatchTransactionResult,
    main,
    print_batch_report,
    resolve_db_path,
    run_recovery_batch,
)

if __name__ == "__main__":
    main()
