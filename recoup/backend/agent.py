#!/usr/bin/env python3
"""
agent.py
--------
Standalone CLI and module entrypoint for Recoup AI Core Recovery Agent.

Demonstrates:
- Autonomous reasoning loop over sample open transactions.
- Policy retrieval with RAG semantic search.
- Historical case lookup.
- 6 LLM tools with deterministic guardrails checking contact limits, quiet hours, and opt-outs.
- Automatic block logging and immutable audit trails.

Usage:
    python agent.py
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agent.agent import RecoupAgent, AgentExecutionResult
from app.guardrails.guardrail import DeterministicGuardrail, IST_TIMEZONE, get_dnc_registry


def main() -> None:
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 80)
    print("  RECOUP AI AUTONOMOUS REVENUE RECOVERY AGENT & DETERMINISTIC GUARDRAILS")
    print("=" * 80)
    print("  Engine: Policy Retrieval RAG + 6 LLM Tools + Pre-Execution Safety Checks")
    print("=" * 80 + "\n")

    # Setup DNC Registry with sample opted-out customer
    dnc = get_dnc_registry()
    dnc.add("cust_opted_out_888")

    agent = RecoupAgent()

    # Create realistic open transaction scenarios to exercise all tools and guardrails
    sample_open_transactions = [
        # 1. Standard Insufficient Funds during operational daytime (Expected: Allowed outreach)
        {
            "transaction_id": "txn_agent_001",
            "customer_id": "cust_active_101",
            "type": "one_time_checkout",
            "amount": 2499.00,
            "failure_reason_code": "insufficient_funds",
            "description": "Python & AI System Design Masterclass",
            "customer_channel_pref": "whatsapp",
            "contact_attempts_so_far": 0,
            "status": "open",
        },
        # 2. Card Expired on Subscription Renewal (Expected: Allowed card update link)
        {
            "transaction_id": "txn_agent_002",
            "customer_id": "cust_sub_202",
            "type": "subscription_renewal",
            "amount": 4999.00,
            "failure_reason_code": "card_expired",
            "description": "Annual Developer Plan Renewal",
            "customer_channel_pref": "email",
            "contact_attempts_so_far": 1,
            "status": "open",
        },
        # 3. Network Error / Gateway Timeout (Expected: Technical Retry executed)
        {
            "transaction_id": "txn_agent_003",
            "customer_id": "cust_tech_303",
            "type": "one_time_checkout",
            "amount": 6995.00,
            "failure_reason_code": "network_error",
            "description": "Logitech MX Master 3S Wireless Mouse",
            "customer_channel_pref": "sms",
            "contact_attempts_so_far": 0,
            "status": "open",
        },
        # 4. Account Closed / Fraud (Expected: Outreach frozen & Escalated to Human)
        {
            "transaction_id": "txn_agent_004",
            "customer_id": "cust_fraud_404",
            "type": "subscription_renewal",
            "amount": 12500.00,
            "failure_reason_code": "account_closed",
            "description": "Enterprise SaaS Workspace License",
            "customer_channel_pref": "email",
            "contact_attempts_so_far": 0,
            "status": "open",
        },
        # 5. Guardrail Test: Max Attempts Exceeded (Attempts = 3, Expected: BLOCKED)
        {
            "transaction_id": "txn_agent_005_max_attempts",
            "customer_id": "cust_spammed_505",
            "type": "one_time_checkout",
            "amount": 1899.00,
            "failure_reason_code": "insufficient_funds",
            "description": "Apple 20W USB-C Power Adapter",
            "customer_channel_pref": "whatsapp",
            "contact_attempts_so_far": 3,
            "status": "open",
        },
        # 6. Guardrail Test: Opted-Out Customer (Expected: BLOCKED by DNC Registry)
        {
            "transaction_id": "txn_agent_006_opted_out",
            "customer_id": "cust_opted_out_888",
            "type": "checkout_abandonment",
            "amount": 14999.00,
            "failure_reason_code": "customer_abandoned",
            "description": "Sony WH-1000XM5 Noise Cancelling Headphones",
            "customer_channel_pref": "whatsapp",
            "contact_attempts_so_far": 0,
            "status": "open",
        },
    ]

    # Evaluate during operational hours (14:30 IST)
    daytime_eval = datetime.datetime(2026, 9, 2, 14, 30, 0, tzinfo=IST_TIMEZONE)

    print(f"Executing Recovery Cycle for {len(sample_open_transactions)} transactions at {daytime_eval.strftime('%Y-%m-%d %H:%M:%S %Z')}...\n")
    results = agent.run_recovery_cycle(sample_open_transactions, current_time=daytime_eval)

    for i, res in enumerate(results, 1):
        print(f"[{i:02d}] Transaction ID : {res.transaction_id} (Customer: {res.customer_id})")
        print(f"     Policy Match   : {res.policy_chunks_retrieved[0]['policy_title'] if res.policy_chunks_retrieved else 'None'}")
        print(f"     Reasoning      : {res.llm_reasoning}")
        print(f"     Tools Executed : {[t.tool_name for t in res.tools_executed]}")

        for tool_rec in res.tools_executed:
            if tool_rec.was_blocked_by_guardrail:
                print(f"     -> [GUARDRAIL BLOCKED] Tool: {tool_rec.tool_name} | Rule: {tool_rec.guardrail_rule}")
                print(f"        Reason: {tool_rec.guardrail_reason}")
            else:
                print(f"     -> [TOOL SUCCESS] Tool: {tool_rec.tool_name} | Status: {tool_rec.result.get('status', 'ok')}")

        print(f"     Final Status   : {res.final_transaction_status}")
        print("-" * 80)

    # Demonstrate Quiet Hours Evaluation (22:30 IST)
    print("\n" + "=" * 80)
    print("  DEMONSTRATING QUIET HOURS GUARDRAIL INTERCEPTION (22:30 IST)")
    print("=" * 80)
    night_time = datetime.datetime(2026, 9, 2, 22, 30, 0, tzinfo=IST_TIMEZONE)
    night_txn = {
        "transaction_id": "txn_night_007",
        "customer_id": "cust_night_707",
        "type": "one_time_checkout",
        "amount": 3499.00,
        "failure_reason_code": "insufficient_funds",
        "description": "Ergonomic Mesh Keyboard",
        "customer_channel_pref": "whatsapp",
        "contact_attempts_so_far": 0,
        "status": "open",
    }
    night_res = agent.process_transaction(night_txn, current_time=night_time)
    print(f"Transaction ID : {night_res.transaction_id}")
    print(f"Evaluated At   : {night_time.strftime('%H:%M:%S %Z')}")
    print(f"Tools Executed : {[t.tool_name for t in night_res.tools_executed]}")
    for tool_rec in night_res.tools_executed:
        if tool_rec.was_blocked_by_guardrail:
            print(f"-> [GUARDRAIL BLOCKED] {tool_rec.guardrail_reason}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
