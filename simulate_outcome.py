#!/usr/bin/env python3
"""
simulate_outcome.py
-------------------
Root entrypoint for Recoup AI recovery outcome simulator.
Delegates to backend/simulate_outcome.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent / "recoup" / "backend"
if not backend_dir.exists():
    backend_dir = Path(__file__).resolve().parent / "backend"

if backend_dir.exists() and str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from simulate_outcome import (
    BASE_RECOVERY_PROBABILITIES,
    CHANNEL_ENGAGEMENT_MULTIPLIERS,
    SimulationOutcome,
    calculate_effective_probability,
    main,
    simulate_outcome,
    simulate_recovery_outcome,
)

if __name__ == "__main__":
    main()
