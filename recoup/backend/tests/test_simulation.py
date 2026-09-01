"""
tests/test_simulation.py
-------------------------
Unit and statistical tests for the outcome simulation engine and batch execution pipeline.

Test Coverage:
1. Verification of base empirical recovery probabilities:
   - recoverable_technical (~85%)
   - recoverable_wait (~70%)
   - recoverable_action_needed (~40%)
   - unrecoverable (0%)
2. Guardrail blocked outreach strictly yielding 0% recovery.
3. Unrecoverable / account_closed cases strictly yielding 0% automated recovery.
4. Escalate to human handling.
5. Monte Carlo statistical validation across 1,000 iterations per category.
6. Full batch pipeline integration test with SQLite database updates and audit log verification.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

from app.agent.diagnose import RecoveryCategory
from run_batch import run_recovery_batch
from simulate_outcome import (
    BASE_RECOVERY_PROBABILITIES,
    calculate_effective_probability,
    simulate_recovery_outcome,
)


# ── 1. Base Probabilities & Calibration Tests ──────────────────────────────────

class TestSimulationProbabilities:
    def test_base_probabilities_configuration(self):
        """Verify empirical base probabilities match the specified architecture."""
        assert BASE_RECOVERY_PROBABILITIES[RecoveryCategory.RECOVERABLE_TECHNICAL.value] == 0.85
        assert BASE_RECOVERY_PROBABILITIES[RecoveryCategory.RECOVERABLE_WAIT.value] == 0.70
        assert BASE_RECOVERY_PROBABILITIES[RecoveryCategory.RECOVERABLE_ACTION_NEEDED.value] == 0.40
        assert BASE_RECOVERY_PROBABILITIES[RecoveryCategory.UNRECOVERABLE.value] == 0.00

    def test_unrecoverable_strictly_zero_probability(self):
        """Unrecoverable category must always have 0% recovery probability and never recover."""
        outcome = simulate_recovery_outcome(
            action="send_message",
            category=RecoveryCategory.UNRECOVERABLE,
            transaction={"transaction_id": "txn_u1", "amount": 10000.0, "failure_reason_code": "account_closed"},
        )
        assert outcome.is_recovered is False
        assert outcome.recovered_amount == 0.0
        assert outcome.effective_probability == 0.0

    def test_guardrail_blocked_action_strictly_zero_probability(self):
        """Actions blocked by safety guardrails must have 0% recovery."""
        outcome = simulate_recovery_outcome(
            action="send_message",
            category=RecoveryCategory.RECOVERABLE_WAIT,
            transaction={"transaction_id": "txn_g1", "amount": 2500.0, "failure_reason_code": "insufficient_funds"},
            was_blocked_by_guardrail=True,
        )
        assert outcome.is_recovered is False
        assert outcome.was_blocked_by_guardrail is True
        assert outcome.effective_probability == 0.0
        assert outcome.recovered_amount == 0.0
        assert "Blocked by Safety Guardrail" in outcome.recovery_method

    def test_escalate_to_human_outcome(self):
        """Escalate to human does not automatically recover on the spot."""
        outcome = simulate_recovery_outcome(
            action="escalate_to_human",
            category=RecoveryCategory.UNRECOVERABLE,
            transaction={"transaction_id": "txn_e1", "amount": 15000.0, "failure_reason_code": "account_closed"},
        )
        assert outcome.is_recovered is False
        assert "Escalation" in outcome.recovery_method


# ── 2. Monte Carlo Statistical Distribution Validation ─────────────────────────

class TestMonteCarloProbabilities:
    def test_technical_recovery_distribution(self):
        """1,000 simulations of recoverable_technical should center closely around ~85%."""
        iterations = 1000
        recovered_count = 0
        txn = {"transaction_id": "txn_t", "amount": 5000.0, "failure_reason_code": "network_error"}

        for i in range(iterations):
            res = simulate_recovery_outcome(
                action="simulate_retry_payment",
                category=RecoveryCategory.RECOVERABLE_TECHNICAL,
                transaction=txn,
                random_seed=i,
            )
            if res.is_recovered:
                recovered_count += 1

        empirical_rate = recovered_count / iterations
        # Allow +/- 4% margin of error for 1,000 trials at 85%
        assert 0.81 <= empirical_rate <= 0.89, f"Expected ~0.85, got {empirical_rate:.4f}"

    def test_wait_recovery_distribution(self):
        """1,000 simulations of recoverable_wait should center around ~70%."""
        iterations = 1000
        recovered_count = 0
        txn = {"transaction_id": "txn_w", "amount": 3000.0, "failure_reason_code": "insufficient_funds", "customer_channel_pref": "whatsapp"}

        for i in range(iterations):
            res = simulate_recovery_outcome(
                action="send_message",
                category=RecoveryCategory.RECOVERABLE_WAIT,
                transaction=txn,
                random_seed=i,
            )
            if res.is_recovered:
                recovered_count += 1

        empirical_rate = recovered_count / iterations
        # Channel multiplier for WhatsApp gives ~75.6%
        assert 0.70 <= empirical_rate <= 0.80, f"Expected ~0.75, got {empirical_rate:.4f}"

    def test_action_needed_recovery_distribution(self):
        """1,000 simulations of recoverable_action_needed should center around ~40%."""
        iterations = 1000
        recovered_count = 0
        txn = {"transaction_id": "txn_a", "amount": 4000.0, "failure_reason_code": "card_expired", "customer_channel_pref": "email"}

        for i in range(iterations):
            res = simulate_recovery_outcome(
                action="send_message",
                category=RecoveryCategory.RECOVERABLE_ACTION_NEEDED,
                transaction=txn,
                random_seed=i,
            )
            if res.is_recovered:
                recovered_count += 1

        empirical_rate = recovered_count / iterations
        assert 0.33 <= empirical_rate <= 0.43, f"Expected ~0.37, got {empirical_rate:.4f}"


# ── 3. Full Batch Pipeline Integration Test ────────────────────────────────────

class TestBatchPipeline:
    @pytest.fixture
    def test_database(self, tmp_path):
        """Creates a temporary SQLite database with a sample dataset for batch testing."""
        db_file = tmp_path / "test_recoup.db"
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id VARCHAR(64) UNIQUE NOT NULL,
            razorpay_payment_id VARCHAR(64),
            customer_id VARCHAR(64) NOT NULL,
            type VARCHAR(64) NOT NULL,
            amount FLOAT NOT NULL,
            currency VARCHAR(8) DEFAULT 'INR',
            event_type VARCHAR(64) DEFAULT 'payment.failed',
            failure_reason_code VARCHAR(64) NOT NULL,
            contact_attempts_so_far INTEGER DEFAULT 0,
            customer_channel_pref VARCHAR(32) DEFAULT 'whatsapp',
            status VARCHAR(32) DEFAULT 'open',
            customer_email VARCHAR(256),
            customer_phone VARCHAR(32),
            description TEXT,
            timestamp DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL,
            action VARCHAR(32) NOT NULL,
            actor VARCHAR(128),
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(transaction_id) REFERENCES transactions (id) ON DELETE CASCADE
        )
        """)

        sample_rows = [
            ("txn_pipe_001", "cust_101", "one_time_checkout", 2500.0, "insufficient_funds", 0, "whatsapp", "open", "Course Purchase"),
            ("txn_pipe_002", "cust_102", "subscription_renewal", 5000.0, "card_expired", 0, "email", "open", "Plan Renewal"),
            ("txn_pipe_003", "cust_103", "one_time_checkout", 7500.0, "network_error", 0, "sms", "open", "Headphones"),
            ("txn_pipe_004", "cust_104", "subscription_renewal", 12000.0, "account_closed", 0, "email", "open", "Enterprise License"),
        ]

        cursor.executemany(
            """
            INSERT INTO transactions (transaction_id, customer_id, type, amount, failure_reason_code, contact_attempts_so_far, customer_channel_pref, status, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            sample_rows,
        )
        conn.commit()
        conn.close()
        return db_file

    def test_run_recovery_batch_pipeline(self, test_database):
        """Runs the entire pipeline against test database and validates state mutations & report."""
        results, report = run_recovery_batch(db_path=test_database, random_seed=42)

        assert len(results) == 4
        assert report.total_transactions == 4
        assert report.total_at_risk_amount == 27000.0
        assert report.total_recovered_amount > 0.0
        assert 0.0 < report.amount_recovery_rate <= 100.0

        # Verify failure reason breakdown exists
        assert "insufficient_funds" in report.by_failure_reason
        assert "card_expired" in report.by_failure_reason
        assert "network_error" in report.by_failure_reason
        assert "account_closed" in report.by_failure_reason

        # Verify account_closed was marked unrecoverable
        assert report.by_failure_reason["account_closed"]["category"] == "unrecoverable"
        assert report.by_failure_reason["account_closed"]["recovered_amt"] == 0.0

        # Verify database was updated
        conn = sqlite3.connect(str(test_database))
        cursor = conn.cursor()

        db_txns = cursor.execute("SELECT transaction_id, status, contact_attempts_so_far FROM transactions").fetchall()
        assert len(db_txns) == 4
        # None of the transactions should remain 'open'
        for _, status, _ in db_txns:
            assert status in {"recovered", "unrecoverable", "pending", "pending_compliance_review"}

        # Verify audit logs were written
        audit_count = cursor.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
        assert audit_count == 4

        conn.close()
