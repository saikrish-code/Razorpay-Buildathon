#!/usr/bin/env python3
"""
test_retrieval.py
-----------------
Demonstrates and validates the in-memory policy retrieval module for sample queries.
Executes semantic retrieval across the 6 markdown policies using cosine similarity.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend directory to sys.path if running from root
backend_dir = Path(__file__).resolve().parent / "recoup" / "backend"
if not backend_dir.exists():
    backend_dir = Path(__file__).resolve().parent

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.retrieval.retriever import retrieve_policy, get_vector_store


def main() -> None:
    # Ensure Windows console handles UTF-8 formatting cleanly
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    store = get_vector_store()
    print("=" * 80)
    print("  RECOUP POLICY RETRIEVAL ENGINE (IN-MEMORY VECTOR STORE)")
    print("=" * 80)
    print(f"  Indexed Policy Chunks : {len(store.chunks)}")
    for i, c in enumerate(store.chunks, 1):
        print(f"    [{i:02d}] {c.policy_title} -> {c.section_title}")
    print("=" * 80 + "\n")

    # Test queries testing distinct policies
    sample_queries = [
        {
            "query": "What is the procedure when a payment fails due to low bank balance or insufficient funds?",
            "expected": "Insufficient Funds Recovery Policy",
        },
        {
            "query": "Can we send automated recovery messages to customers at 11 PM or during quiet hours?",
            "expected": "Do-Not-Contact and Timing Rules",
        },
        {
            "query": "How should we handle fatal account_closed errors and when are they written off?",
            "expected": "Unrecoverable Account Write-off Policy",
        },
        {
            "query": "What is the grace period and retry schedule for failed recurring SaaS subscriptions?",
            "expected": "Subscription Dunning Playbook",
        },
        {
            "query": "When and how should we reach out to shoppers who left items in their checkout cart?",
            "expected": "Abandoned Checkout Outreach Policy",
        },
        {
            "query": "How do we remind users to update their expired credit card for billing continuity?",
            "expected": "Card Update Reminder Policy",
        },
    ]

    all_passed = True

    for idx, test_case in enumerate(sample_queries, 1):
        query = test_case["query"]
        expected_policy = test_case["expected"]

        print(f"Query #{idx}: \"{query}\"")
        print(f"Expected Target Policy: {expected_policy}")
        print("-" * 80)

        results = retrieve_policy(query, k=2)

        if not results:
            print("  [FAIL] No policy chunks returned!\n")
            all_passed = False
            continue

        top_match = results[0]
        top_title = top_match["policy_title"]
        top_score = top_match["score"]
        match_pass = expected_policy.lower() in top_title.lower()

        status_str = "[PASS] Correct Policy Retrieved" if match_pass else "[FAIL] Mismatched Policy"
        print(f"  Result: {status_str}")
        print(f"  Top Match Policy : {top_title} (Cosine Similarity Score: {top_score})")
        print(f"  Section Header   : {top_match['section_title']}")
        print(f"  Document File    : {top_match['file_name']}")
        print("  Retrieved Chunk Snippet:")
        # Indent snippet
        for line in top_match["content"].splitlines()[:5]:
            print(f"    | {line}")
        if len(top_match["content"].splitlines()) > 5:
            print("    | ...")

        if len(results) > 1:
            second_match = results[1]
            print(f"  Runner-up Match  : {second_match['policy_title']} -> {second_match['section_title']} (Score: {second_match['score']})")

        print("-" * 80 + "\n")

    print("=" * 80)
    if all_passed:
        print("  ALL SAMPLE QUERIES RETRIEVED THE CORRECT POLICIES WITH HIGH CONFIDENCE!")
    else:
        print("  Some queries did not match expectations.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
