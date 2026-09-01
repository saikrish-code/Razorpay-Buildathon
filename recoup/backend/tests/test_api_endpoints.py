"""
tests/test_api_endpoints.py
----------------------------
Integration and endpoint tests for FastAPI routes:
- GET /transactions (with multi-field filters, search, pagination)
- GET /transactions/{id} (with full audit trail and 404 error handling for missing records)
- POST /run-batch (triggers batch pipeline execution)
- GET /report (summary metrics and breakdown by reason)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as c:
        yield c


# ── 1. GET /transactions Tests ─────────────────────────────────────────────────

class TestTransactionsEndpoint:
    def test_list_transactions_default(self, client):
        """GET /transactions returns a non-empty list of transactions."""
        response = client.get("/transactions?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 10
        if data:
            item = data[0]
            assert "transaction_id" in item
            assert "amount" in item
            assert "status" in item

    def test_filter_by_status(self, client):
        """GET /transactions?status=recovered returns only recovered items."""
        response = client.get("/transactions?status=recovered&limit=10")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["status"] == "recovered"

    def test_filter_by_failure_reason_code(self, client):
        """GET /transactions?failure_reason_code=insufficient_funds filters correctly."""
        response = client.get("/transactions?failure_reason_code=insufficient_funds&limit=10")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["failure_reason_code"] == "insufficient_funds"

    def test_filter_by_channel(self, client):
        """GET /transactions?channel=whatsapp filters by preferred channel."""
        response = client.get("/transactions?channel=whatsapp&limit=10")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["customer_channel_pref"] == "whatsapp"

    def test_filter_by_amount_range(self, client):
        """GET /transactions?min_amount=2000&max_amount=5000 filters by amount bounds."""
        response = client.get("/transactions?min_amount=2000&max_amount=5000&limit=10")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert 2000 <= item["amount"] <= 5000

    def test_search_filter(self, client):
        """GET /transactions?search=cust_ filters matching records."""
        response = client.get("/transactions?search=cust_&limit=5")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert "cust_" in item["customer_id"] or "cust_" in str(item.get("description", ""))


# ── 2. GET /transactions/{id} Tests ───────────────────────────────────────────

class TestTransactionDetailEndpoint:
    def test_get_transaction_by_id_with_audit_trail(self, client):
        """GET /transactions/{id} returns transaction with audit_logs list."""
        list_res = client.get("/transactions?limit=1")
        assert list_res.status_code == 200
        items = list_res.json()
        if not items:
            pytest.skip("No transactions in database to test.")

        tx_id = items[0]["id"]
        response = client.get(f"/transactions/{tx_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == tx_id
        assert "audit_logs" in data
        assert isinstance(data["audit_logs"], list)

    def test_get_transaction_by_string_code(self, client):
        """GET /transactions/{txn_xxx} finds transaction by string identifier."""
        list_res = client.get("/transactions?limit=1")
        items = list_res.json()
        if not items:
            pytest.skip("No transactions in database to test.")

        txn_code = items[0]["transaction_id"]
        response = client.get(f"/transactions/{txn_code}")
        assert response.status_code == 200
        data = response.json()
        assert data["transaction_id"] == txn_code

    def test_get_transaction_not_found_404(self, client):
        """GET /transactions/non_existent_id returns 404 with structured error."""
        response = client.get("/transactions/txn_non_existent_999999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()


# ── 3. POST /run-batch Tests ──────────────────────────────────────────────────

class TestRunBatchEndpoint:
    def test_trigger_batch_pipeline(self, client):
        """POST /run-batch executes recovery pipeline and returns updated metrics."""
        response = client.post("/run-batch", json={"limit": 5, "random_seed": 42})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["processed_count"] == 5
        assert "report" in data
        assert data["report"]["total_transactions"] == 5
        assert data["report"]["total_at_risk_amount"] > 0
        assert "by_failure_reason" in data["report"]


# ── 4. GET /report Tests ──────────────────────────────────────────────────────

class TestReportEndpoint:
    def test_get_recovery_report(self, client):
        """GET /report returns KPI metrics and breakdown by reason."""
        response = client.get("/report")
        assert response.status_code == 200
        data = response.json()
        assert "total_transactions" in data
        assert "total_at_risk_amount" in data
        assert "total_recovered_amount" in data
        assert "amount_recovery_rate" in data
        assert "by_failure_reason" in data
        assert "by_category" in data
        assert "by_channel" in data
        assert isinstance(data["by_failure_reason"], dict)
        assert len(data["by_failure_reason"]) > 0
