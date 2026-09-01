#!/usr/bin/env python3
"""
test_diagnose.py
----------------
Demonstration and validation suite for the payment failure & cart abandonment diagnosis engine.

Validates:
1. Deterministic Rule-Based Path: Tests failure codes for all 4 categories and confirms 0 LLM calls.
2. Ambiguous & Cart Abandonment Path: Tests LLM invocation with structured JSON output.
3. Cost Control / Batch Spy: Confirms LLM is only called for ambiguous cases.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add backend directory to sys.path if running from root
backend_dir = Path(__file__).resolve().parent / "recoup" / "backend"
if not backend_dir.exists():
    backend_dir = Path(__file__).resolve().parent

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agent.diagnose import (
    DiagnosisResult,
    LLMDiagnosisResponse,
    RecoveryCategory,
    RULE_BASED_MAP,
    classify_rule_based,
    diagnose_batch,
    diagnose_transaction,
)


def run_diagnose_tests() -> bool:
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 80)
    print("  RECOUP PAYMENT DIAGNOSTICS VALIDATION SUITE")
    print("=" * 80)
    print(f"  Indexed Deterministic Rule Mappings: {len(RULE_BASED_MAP)}")
    print("=" * 80 + "\n")

    all_passed = True

    # ── Test 1: Rule-Based Deterministic Categorization (0 Cost) ─────────────
    print("[TEST 1] Deterministic Rule-Based Classification (Verifying ZERO LLM Calls)...")

    # Mock client spy
    mock_llm_client = MagicMock()

    rule_test_cases = [
        ("insufficient_funds", RecoveryCategory.RECOVERABLE_WAIT),
        ("daily_limit_exceeded", RecoveryCategory.RECOVERABLE_WAIT),
        ("bank_timeout", RecoveryCategory.RECOVERABLE_WAIT),
        ("card_expired", RecoveryCategory.RECOVERABLE_ACTION_NEEDED),
        ("wrong_otp", RecoveryCategory.RECOVERABLE_ACTION_NEEDED),
        ("authentication_failed", RecoveryCategory.RECOVERABLE_ACTION_NEEDED),
        ("network_error", RecoveryCategory.RECOVERABLE_TECHNICAL),
        ("gateway_error", RecoveryCategory.RECOVERABLE_TECHNICAL),
        ("account_closed", RecoveryCategory.UNRECOVERABLE),
        ("fraud_suspected", RecoveryCategory.UNRECOVERABLE),
    ]

    for code, expected_cat in rule_test_cases:
        txn = {
            "transaction_id": f"txn_{code}",
            "amount": 2999.0,
            "failure_reason_code": code,
            "description": f"Test item for {code}"
        }
        res = diagnose_transaction(txn, llm_client=mock_llm_client)

        passed = (
            res.category == expected_cat
            and res.is_llm_diagnosed is False
            and res.confidence == 1.0
            and res.source == "rule_based"
        )
        if not passed:
            all_passed = False
            print(f"  [FAIL] Code: '{code}' -> Expected {expected_cat.value}, Got {res.category.value}")
        else:
            print(f"  [PASS] '{code:22s}' -> {res.category.value:26s} | LLM Called: {res.is_llm_diagnosed}")

    # Verify LLM was called 0 times across all deterministic cases
    llm_call_count = (
        mock_llm_client.beta.chat.completions.parse.call_count
        + mock_llm_client.chat.completions.create.call_count
    )
    if llm_call_count == 0:
        print(f"\n  >> ZERO LLM Calls Confirmed for deterministic rules (Calls: {llm_call_count})\n")
    else:
        print(f"\n  >> [FAIL] LLM was called {llm_call_count} times for deterministic rules!\n")
        all_passed = False

    # ── Test 2: Ambiguous & customer_abandoned Path (Always Calls LLM) ────────
    print("[TEST 2] Ambiguous & Customer Abandoned Path (Verifying LLM Invocation & Structured Output)...")

    mock_llm_spy = MagicMock()
    mock_parsed = MagicMock()
    mock_parsed.choices = [
        MagicMock(
            message=MagicMock(
                parsed=LLMDiagnosisResponse(
                    category=RecoveryCategory.RECOVERABLE_ACTION_NEEDED,
                    likely_reason="High cart value hesitation on luxury earbuds (Rs 12,900); customer paused to reconsider budget.",
                    confidence=0.88,
                    recommended_action="Send concierge WhatsApp cart reminder with 1-click checkout and 5% limited discount.",
                    friction_points=["price_hesitation", "luxury_purchase"]
                )
            )
        )
    ]
    mock_llm_spy.beta.chat.completions.parse.return_value = mock_parsed

    abandoned_txn = {
        "transaction_id": "txn_abn_demo",
        "type": "checkout_abandonment",
        "amount": 12900.0,
        "failure_reason_code": "customer_abandoned",
        "description": "Cart Recovery - Bose QuietComfort Earbuds",
        "customer_channel_pref": "whatsapp"
    }

    res_abn = diagnose_transaction(abandoned_txn, llm_client=mock_llm_spy)

    if (
        res_abn.is_llm_diagnosed is True
        and res_abn.source == "llm"
        and mock_llm_spy.beta.chat.completions.parse.call_count == 1
        and res_abn.confidence == 0.88
        and "hesitation" in res_abn.likely_reason.lower()
    ):
        print(f"  [PASS] 'customer_abandoned' -> LLM successfully invoked (Calls: 1)")
        print(f"         Category       : {res_abn.category.value}")
        print(f"         Confidence     : {res_abn.confidence * 100:.1f}%")
        print(f"         Likely Reason  : {res_abn.likely_reason}")
        print(f"         Action Policy  : {res_abn.recommended_action}\n")
    else:
        print(f"  [FAIL] customer_abandoned did not invoke LLM as expected!\n")
        all_passed = False

    # ── Test 3: Batch Cost Control Spy Verification ───────────────────────────
    print("[TEST 3] Batch Cost Control (10 Deterministic + 2 Abandoned Transactions)...")

    batch_mock = MagicMock()
    batch_mock.beta.chat.completions.parse.return_value = mock_parsed

    batch_txns = [
        {"transaction_id": f"txn_d_{i}", "failure_reason_code": code, "amount": 1000}
        for i, (code, _) in enumerate(rule_test_cases)
    ] + [
        {"transaction_id": "txn_a_1", "failure_reason_code": "customer_abandoned", "amount": 5000},
        {"transaction_id": "txn_a_2", "failure_reason_code": "customer_abandoned", "amount": 8000},
    ]

    batch_results = diagnose_batch(batch_txns, llm_client=batch_mock)

    batch_llm_calls = batch_mock.beta.chat.completions.parse.call_count
    if len(batch_results) == 12 and batch_llm_calls == 2:
        print(f"  [PASS] Batch of 12 items processed: exactly 2 LLM calls made for 2 abandoned transactions.")
        print(f"         10 Rule-based transactions: 0 LLM calls (100% cost-controlled).\n")
    else:
        print(f"  [FAIL] Batch LLM calls mismatch: Expected 2, got {batch_llm_calls}\n")
        all_passed = False

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=" * 80)
    if all_passed:
        print("  ALL DIAGNOSTICS & COST-CONTROL TESTS PASSED SUCCESSFULLY! (100%)")
    else:
        print("  SOME TESTS FAILED.")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = run_diagnose_tests()
    sys.exit(0 if success else 1)
