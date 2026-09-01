#!/usr/bin/env python3
"""
run_batch.py
------------
End-to-End Batch Pipeline Runner for Recoup AI.

Executes the complete revenue recovery pipeline across all transactions:
1. Diagnose: Identifies root cause and assigns recovery category (rule-based deterministic or LLM).
2. Retrieve Policy: Queries company recovery policies via RAG vector search.
3. Agent Decides & Acts: Autonomous agent reasons, selects optimal recovery tools, and executes them.
   - send_message and escalate_to_human are verified by deterministic guardrails before execution.
4. Simulate Outcome: Evaluates calibrated recovery probabilities and determines recovery success.
5. Log & Update: Inserts audit log records and updates transaction statuses in the database.
6. Analytics Report: Computes and prints Total At Risk, Total Recovered, Recovery Rate, and
   breakdowns by Failure Reason Code and Recovery Category.

Usage:
    python run_batch.py
"""

from __future__ import annotations

import datetime
import json
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agent.agent import RecoupAgent
from app.agent.diagnose import RecoveryCategory, diagnose_transaction
from app.guardrails.guardrail import DeterministicGuardrail, IST_TIMEZONE, get_dnc_registry
from app.retrieval.retriever import retrieve_policy
from simulate_outcome import SimulationOutcome, simulate_recovery_outcome


# ── Database Resolution ────────────────────────────────────────────────────────

def resolve_db_path() -> Path:
    """Finds the active SQLite database path."""
    cwd = Path.cwd()
    script_dir = Path(__file__).resolve().parent

    candidates = [
        script_dir / "recoup.db",
        cwd / "recoup.db",
        cwd / "backend" / "recoup.db",
        cwd / "recoup" / "backend" / "recoup.db",
        script_dir.parent / "recoup.db",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return script_dir / "recoup.db"


# ── Batch Result Data Structures ───────────────────────────────────────────────

@dataclass
class BatchTransactionResult:
    id: int
    transaction_id: str
    customer_id: str
    failure_reason_code: str
    type: str
    amount: float
    category: str
    action_decided: str
    was_blocked_by_guardrail: bool
    guardrail_rule: Optional[str]
    is_recovered: bool
    recovered_amount: float
    final_status: str
    simulated_outcome: SimulationOutcome


@dataclass
class BatchSummaryReport:
    total_transactions: int
    total_at_risk_amount: float
    total_recovered_amount: float
    amount_recovery_rate: float
    count_recovered: int
    count_unrecoverable: int
    count_pending: int
    count_blocked_by_guardrail: int
    volume_recovery_rate: float
    by_failure_reason: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_category: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_channel: Dict[str, Dict[str, Any]] = field(default_factory=dict)


# ── Core Pipeline Execution ───────────────────────────────────────────────────

def run_recovery_batch(
    db_path: Optional[Path | str] = None,
    limit: Optional[int] = None,
    random_seed: Optional[int] = 42,
    evaluation_time: Optional[datetime.datetime] = None,
) -> Tuple[List[BatchTransactionResult], BatchSummaryReport]:
    """
    Executes the full pipeline across all transactions in SQLite database:
    diagnose → retrieve policy → agent decides and acts → simulate outcome → log & update.
    """
    target_db = Path(db_path) if db_path else resolve_db_path()
    if not target_db.exists():
        raise FileNotFoundError(f"SQLite database not found at {target_db}. Run generate_data.py first.")

    eval_dt = evaluation_time or datetime.datetime(2026, 9, 2, 14, 30, 0, tzinfo=IST_TIMEZONE)

    conn = sqlite3.connect(str(target_db))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM transactions ORDER BY id ASC"
    if limit is not None:
        query += f" LIMIT {int(limit)}"

    rows = cursor.execute(query).fetchall()
    transactions = [dict(row) for row in rows]

    agent = RecoupAgent()
    results: List[BatchTransactionResult] = []

    # Aggregation Buckets
    total_at_risk = 0.0
    total_recovered = 0.0
    count_recovered = 0
    count_unrecoverable = 0
    count_pending = 0
    count_blocked = 0

    reason_stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "at_risk": 0.0, "recovered_count": 0, "recovered_amt": 0.0, "category": "unknown"}
    )
    category_stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "at_risk": 0.0, "recovered_count": 0, "recovered_amt": 0.0}
    )
    channel_stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "at_risk": 0.0, "recovered_count": 0, "recovered_amt": 0.0}
    )

    db_updates: List[Tuple[str, int, int]] = []
    audit_log_inserts: List[Tuple[int, str, str, str, str]] = []

    now_iso = eval_dt.isoformat()

    for idx, txn in enumerate(transactions):
        tx_row_id = txn["id"]
        tx_id = txn["transaction_id"]
        cust_id = txn["customer_id"]
        code = str(txn.get("failure_reason_code", "unknown")).lower().strip()
        txn_type = str(txn.get("type", "one_time_checkout"))
        amount = float(txn.get("amount", 0.0) or 0.0)
        channel = str(txn.get("customer_channel_pref", "whatsapp")).lower()
        contact_attempts = int(txn.get("contact_attempts_so_far", 0) or 0)

        # ── Step 1: Diagnose ──
        diagnosis = diagnose_transaction(txn)
        cat_val = diagnosis.category.value

        # ── Step 2: Retrieve Policy (RAG Vector Store) ──
        policy_query = f"{code} {txn_type} recovery policy and contact limits"
        policy_chunks = retrieve_policy(query=policy_query, k=2)

        # ── Step 3: Agent Decides & Acts (Guarded) ──
        agent_res = agent.process_transaction(txn, current_time=eval_dt)

        # Determine the primary action decided by agent
        if agent_res.tools_executed:
            primary_tool_rec = agent_res.tools_executed[0]
            action_decided = primary_tool_rec.tool_name
            was_blocked = primary_tool_rec.was_blocked_by_guardrail
            guardrail_rule = primary_tool_rec.guardrail_rule
        else:
            action_decided = "log_action"
            was_blocked = False
            guardrail_rule = None

        # ── Step 4: Simulate Outcome ──
        # Use deterministic seed tied to transaction id + base seed for reproducible runs
        seed_val = (hash(tx_id) + (random_seed or 0)) % (2**31 - 1) if random_seed is not None else None

        sim_outcome = simulate_recovery_outcome(
            action=action_decided,
            category=diagnosis.category,
            transaction=txn,
            was_blocked_by_guardrail=was_blocked,
            random_seed=seed_val,
        )

        # ── Step 5: Determine Final Status & DB Updates ──
        if sim_outcome.is_recovered:
            final_status = "recovered"
            recovered_amt = amount
            count_recovered += 1
            new_attempts = contact_attempts + (1 if action_decided == "send_message" else 0)
        elif cat_val == RecoveryCategory.UNRECOVERABLE.value or code in {"account_closed", "fraud_detected"}:
            final_status = "unrecoverable"
            recovered_amt = 0.0
            count_unrecoverable += 1
            new_attempts = contact_attempts
        elif was_blocked:
            final_status = "pending_compliance_review"
            recovered_amt = 0.0
            count_blocked += 1
            new_attempts = contact_attempts
        else:
            final_status = "pending"
            recovered_amt = 0.0
            count_pending += 1
            new_attempts = contact_attempts + (1 if action_decided == "send_message" else 0)

        total_at_risk += amount
        total_recovered += recovered_amt

        # Record DB updates
        db_updates.append((final_status, new_attempts, tx_row_id))

        # Build Audit Log Entry
        audit_note = (
            f"Pipeline Execution | Diagnosis: {cat_val} ({diagnosis.confidence*100:.0f}% conf) | "
            f"Action: {action_decided} | Guardrail: {'BLOCKED (' + str(guardrail_rule) + ')' if was_blocked else 'PASSED'} | "
            f"Outcome: {'RECOVERED (INR ' + f'{amount:,.2f}' + ')' if sim_outcome.is_recovered else 'UNRECOVERED'} | "
            f"Method: {sim_outcome.recovery_method}"
        )
        action_verb = "resolved" if sim_outcome.is_recovered else ("flagged" if (was_blocked or final_status == "unrecoverable") else "contact_attempted")
        audit_log_inserts.append((tx_row_id, action_verb, "recoup_pipeline", audit_note, now_iso))

        # Update Aggregations
        reason_stats[code]["count"] += 1
        reason_stats[code]["at_risk"] += amount
        reason_stats[code]["category"] = cat_val
        if sim_outcome.is_recovered:
            reason_stats[code]["recovered_count"] += 1
            reason_stats[code]["recovered_amt"] += amount

        category_stats[cat_val]["count"] += 1
        category_stats[cat_val]["at_risk"] += amount
        if sim_outcome.is_recovered:
            category_stats[cat_val]["recovered_count"] += 1
            category_stats[cat_val]["recovered_amt"] += amount

        channel_stats[channel]["count"] += 1
        channel_stats[channel]["at_risk"] += amount
        if sim_outcome.is_recovered:
            channel_stats[channel]["recovered_count"] += 1
            channel_stats[channel]["recovered_amt"] += amount

        results.append(
            BatchTransactionResult(
                id=tx_row_id,
                transaction_id=tx_id,
                customer_id=cust_id,
                failure_reason_code=code,
                type=txn_type,
                amount=amount,
                category=cat_val,
                action_decided=action_decided,
                was_blocked_by_guardrail=was_blocked,
                guardrail_rule=guardrail_rule,
                is_recovered=sim_outcome.is_recovered,
                recovered_amount=recovered_amt,
                final_status=final_status,
                simulated_outcome=sim_outcome,
            )
        )

    # ── Commit Database Updates & Audit Logs ──
    cursor.executemany(
        "UPDATE transactions SET status = ?, contact_attempts_so_far = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        db_updates,
    )
    cursor.executemany(
        "INSERT INTO audit_logs (transaction_id, action, actor, notes, created_at) VALUES (?, ?, ?, ?, ?)",
        audit_log_inserts,
    )
    conn.commit()
    conn.close()

    # Calculate overall metrics
    amount_rate = (total_recovered / total_at_risk * 100.0) if total_at_risk > 0 else 0.0
    volume_rate = (count_recovered / len(transactions) * 100.0) if transactions else 0.0

    report = BatchSummaryReport(
        total_transactions=len(transactions),
        total_at_risk_amount=total_at_risk,
        total_recovered_amount=total_recovered,
        amount_recovery_rate=amount_rate,
        count_recovered=count_recovered,
        count_unrecoverable=count_unrecoverable,
        count_pending=count_pending,
        count_blocked_by_guardrail=count_blocked,
        volume_recovery_rate=volume_rate,
        by_failure_reason=dict(reason_stats),
        by_category=dict(category_stats),
        by_channel=dict(channel_stats),
    )

    return results, report


# ── Formatted Console Output ───────────────────────────────────────────────────

def print_batch_report(report: BatchSummaryReport) -> None:
    """Prints a beautiful, comprehensive terminal report of the batch pipeline execution."""
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("\n" + "=" * 92)
    print("      RECOUP AI REVENUE RECOVERY ENGINE — FULL PIPELINE BATCH EXECUTION REPORT")
    print("=" * 92)
    print(f"  Pipeline Flow: Ingest -> Diagnose -> Retrieve Policy -> Agent Acts -> Simulate -> Log & Update")
    print("=" * 92 + "\n")

    # ── Executive KPI Dashboard ───────────────────────────────────────────────
    print("┌" + "─" * 90 + "┐")
    print("│                              EXECUTIVE RECOVERY SUMMARY                                  │")
    print("├" + "─" * 90 + "┤")
    print(f"│  Total Transactions Processed : {report.total_transactions:<15}                                      │")
    print(f"│  Total Revenue at Risk        : INR {report.total_at_risk_amount:>14,.2f}                                      │")
    print(f"│  Total Revenue Recovered      : INR {report.total_recovered_amount:>14,.2f}  [SUCCESS]                             │")
    print(f"│  Amount Recovery Rate         : {report.amount_recovery_rate:>13.2f}%                                       │")
    print(f"│  Transactions Recovered Count : {report.count_recovered:<15} ({report.volume_recovery_rate:.1f}% volume recovery)                │")
    print(f"│  Permanently Unrecoverable    : {report.count_unrecoverable:<15} (Frozen & Escalate to Operations)        │")
    print(f"│  Pending / Active Follow-up   : {report.count_pending:<15}                                      │")
    print(f"│  Guardrail Interceptions      : {report.count_blocked_by_guardrail:<15} (Safety & Quiet Hours Protected)         │")
    print("└" + "─" * 90 + "┘\n")

    # ── Breakdown by Failure Reason Code ──────────────────────────────────────
    print("=" * 92)
    print("  BREAKDOWN BY PAYMENT FAILURE REASON CODE")
    print("=" * 92)
    print(
        f"{'Failure Reason Code':<24} | {'Category':<22} | {'Count':<6} | {'At Risk (INR)':<14} | {'Recovered':<14} | {'Rate':<7}"
    )
    print("-" * 92)

    sorted_reasons = sorted(
        report.by_failure_reason.items(),
        key=lambda x: x[1]["at_risk"],
        reverse=True,
    )

    for code, data in sorted_reasons:
        rate = (data["recovered_amt"] / data["at_risk"] * 100.0) if data["at_risk"] > 0 else 0.0
        print(
            f"{code:<24} | {data['category']:<22} | {data['count']:<6} | "
            f"{data['at_risk']:>14,.2f} | {data['recovered_amt']:>14,.2f} | {rate:>6.1f}%"
        )
    print("-" * 92)
    print(
        f"{'TOTAL':<24} | {'':<22} | {report.total_transactions:<6} | "
        f"{report.total_at_risk_amount:>14,.2f} | {report.total_recovered_amount:>14,.2f} | {report.amount_recovery_rate:>6.1f}%"
    )
    print("=" * 92 + "\n")

    # ── Breakdown by Recovery Category ────────────────────────────────────────
    print("=" * 92)
    print("  BREAKDOWN BY RECOVERY CATEGORY")
    print("=" * 92)
    print(f"{'Category':<28} | {'Count':<6} | {'At Risk (INR)':<14} | {'Recovered (INR)':<15} | {'Recovery Rate':<13}")
    print("-" * 92)
    for cat, data in sorted(report.by_category.items(), key=lambda x: x[1]["at_risk"], reverse=True):
        rate = (data["recovered_amt"] / data["at_risk"] * 100.0) if data["at_risk"] > 0 else 0.0
        print(
            f"{cat:<28} | {data['count']:<6} | {data['at_risk']:>14,.2f} | "
            f"{data['recovered_amt']:>15,.2f} | {rate:>12.1f}%"
        )
    print("=" * 92 + "\n")

    # ── Breakdown by Channel Preference ───────────────────────────────────────
    print("=" * 92)
    print("  BREAKDOWN BY CUSTOMER CHANNEL PREFERENCE")
    print("=" * 92)
    print(f"{'Channel':<20} | {'Count':<6} | {'At Risk (INR)':<14} | {'Recovered (INR)':<15} | {'Conversion Rate':<15}")
    print("-" * 92)
    for ch, data in sorted(report.by_channel.items(), key=lambda x: x[1]["recovered_amt"], reverse=True):
        rate = (data["recovered_amt"] / data["at_risk"] * 100.0) if data["at_risk"] > 0 else 0.0
        print(
            f"{ch.title():<20} | {data['count']:<6} | {data['at_risk']:>14,.2f} | "
            f"{data['recovered_amt']:>15,.2f} | {rate:>14.1f}%"
        )
    print("=" * 92 + "\n")


def main() -> None:
    db = resolve_db_path()
    print(f"Loading transactions from database: {db}...")
    results, report = run_recovery_batch(db_path=db, random_seed=42)
    print_batch_report(report)


if __name__ == "__main__":
    main()
