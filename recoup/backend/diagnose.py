#!/usr/bin/env python3
"""
diagnose.py
-----------
Standalone entrypoint and direct import module for Recoup Payment Diagnostics Engine.

Usage as CLI:
    python diagnose.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agent.diagnose import (
    DiagnosisResult,
    LLMDiagnosisResponse,
    RecoveryCategory,
    RULE_BASED_MAP,
    async_diagnose_transaction,
    classify_rule_based,
    diagnose_batch,
    diagnose_transaction,
    diagnose_with_llm,
    normalize_reason_code,
)


def main() -> None:
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 80)
    print("  RECOUP PAYMENT FAILURE & CART ABANDONMENT DIAGNOSIS ENGINE")
    print("=" * 80)
    print(f"  Deterministic Rule Mappings Indexed: {len(RULE_BASED_MAP)}")
    print("=" * 80 + "\n")

    sample_txns = [
        {
            "transaction_id": "txn_rule_001",
            "type": "one_time_checkout",
            "amount": 2499.00,
            "failure_reason_code": "insufficient_funds",
            "description": "Python & AI System Design Masterclass",
            "customer_channel_pref": "whatsapp",
        },
        {
            "transaction_id": "txn_rule_002",
            "type": "subscription_renewal",
            "amount": 4999.00,
            "failure_reason_code": "card_expired",
            "description": "Annual Developer Plan Renewal",
            "customer_channel_pref": "email",
        },
        {
            "transaction_id": "txn_rule_003",
            "type": "one_time_checkout",
            "amount": 6995.00,
            "failure_reason_code": "network_error",
            "description": "Logitech MX Master 3S Wireless Mouse",
            "customer_channel_pref": "sms",
        },
        {
            "transaction_id": "txn_rule_004",
            "type": "subscription_renewal",
            "amount": 12500.00,
            "failure_reason_code": "account_closed",
            "description": "Enterprise SaaS Workspace License",
            "customer_channel_pref": "email",
        },
        {
            "transaction_id": "txn_ambig_005",
            "type": "checkout_abandonment",
            "amount": 12900.00,
            "failure_reason_code": "customer_abandoned",
            "description": "Cart Recovery - Bose QuietComfort Earbuds",
            "customer_channel_pref": "whatsapp",
        },
    ]

    for txn in sample_txns:
        res = diagnose_transaction(txn)
        print(f"Transaction ID : {res.transaction_id}")
        print(f"Failure Code   : {res.failure_reason_code}")
        print(f"Diagnosis Path : {'[LLM INFERRED]' if res.is_llm_diagnosed else '[RULE DETERMINISTIC (0 COST)]'}")
        print(f"Category       : {res.category.value}")
        print(f"Confidence     : {res.confidence * 100:.1f}%")
        print(f"Likely Reason  : {res.likely_reason}")
        print(f"Action Policy  : {res.recommended_action}")
        print("-" * 80)


if __name__ == "__main__":
    main()
