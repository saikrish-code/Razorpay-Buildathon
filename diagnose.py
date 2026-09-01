#!/usr/bin/env python3
"""
diagnose.py
-----------
Root entrypoint for Recoup payment diagnosis engine.
Delegates to backend/diagnose.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent / "recoup" / "backend"
if not backend_dir.exists():
    backend_dir = Path(__file__).resolve().parent / "backend"

if backend_dir.exists() and str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from diagnose import (
    DiagnosisResult,
    LLMDiagnosisResponse,
    RecoveryCategory,
    RULE_BASED_MAP,
    async_diagnose_transaction,
    classify_rule_based,
    diagnose_batch,
    diagnose_transaction,
    diagnose_with_llm,
    main,
    normalize_reason_code,
)

if __name__ == "__main__":
    main()
