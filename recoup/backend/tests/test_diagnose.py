"""
tests/test_diagnose.py
----------------------
Unit and integration tests for the payment failure & cart abandonment diagnosis engine.

Confirms:
1. Rule-based path NEVER calls the LLM (cost is zero for deterministic codes).
2. Ambiguous / 'customer_abandoned' path ALWAYS calls the LLM.
3. All four categories (recoverable_wait, recoverable_action_needed, recoverable_technical, unrecoverable)
   are correctly classified.
4. Structured outputs and tool-calling modes return valid JSON schemas.
5. Mixed batch execution adheres to strict cost control.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

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
from app.models.transaction import TransactionBase


# ── Mock LLM Fixture ───────────────────────────────────────────────────────────

@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client supporting structured parse and tool-calls."""
    client = MagicMock()

    # Mock beta.chat.completions.parse
    mock_parsed_response = MagicMock()
    mock_parsed_response.choices = [
        MagicMock(
            message=MagicMock(
                parsed=LLMDiagnosisResponse(
                    category=RecoveryCategory.RECOVERABLE_ACTION_NEEDED,
                    likely_reason="Customer dropped off due to high cart value hesitation on luxury earbuds.",
                    confidence=0.88,
                    recommended_action="Send WhatsApp reminder with 5% promo code within 30 minutes.",
                    friction_points=["price_hesitation", "luxury_goods"]
                )
            )
        )
    ]
    client.beta.chat.completions.parse.return_value = mock_parsed_response

    # Mock standard chat.completions.create with tool call
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "record_payment_diagnosis"
    mock_tool_call.function.arguments = json.dumps({
        "category": "recoverable_action_needed",
        "likely_reason": "Tool call diagnosed customer abandonment.",
        "confidence": 0.85,
        "recommended_action": "Trigger SMS recovery link.",
        "friction_points": ["checkout_friction"]
    })

    mock_chat_response = MagicMock()
    mock_chat_response.choices = [
        MagicMock(
            message=MagicMock(
                tool_calls=[mock_tool_call],
                content=None
            )
        )
    ]
    client.chat.completions.create.return_value = mock_chat_response

    return client


# ── 1. Deterministic Rule-Based Tests (Zero LLM Calls Guaranteed) ──────────────

class TestDeterministicRuleBasedPath:
    """
    Ensure clear failure_reason_codes classify into the correct categories
    and NEVER invoke the LLM.
    """

    @pytest.mark.parametrize("code,expected_category", [
        ("insufficient_funds", RecoveryCategory.RECOVERABLE_WAIT),
        ("daily_limit_exceeded", RecoveryCategory.RECOVERABLE_WAIT),
        ("limit_exceeded", RecoveryCategory.RECOVERABLE_WAIT),
        ("bank_timeout", RecoveryCategory.RECOVERABLE_WAIT),
        ("bank_downtime", RecoveryCategory.RECOVERABLE_WAIT),
        ("bank_unavailable", RecoveryCategory.RECOVERABLE_WAIT),
        ("issuer_unavailable", RecoveryCategory.RECOVERABLE_WAIT),
    ])
    def test_recoverable_wait_codes(self, code, expected_category, mock_openai_client):
        txn = {
            "transaction_id": f"txn_{code}",
            "amount": 2500.0,
            "failure_reason_code": code,
            "type": "one_time_checkout"
        }
        res = diagnose_transaction(txn, llm_client=mock_openai_client)

        assert res.category == expected_category
        assert res.is_llm_diagnosed is False
        assert res.source == "rule_based"
        assert res.confidence == 1.0
        assert res.likely_reason != ""
        assert res.recommended_action is not None

        # Verify LLM was NOT called
        mock_openai_client.beta.chat.completions.parse.assert_not_called()
        mock_openai_client.chat.completions.create.assert_not_called()

    @pytest.mark.parametrize("code,expected_category", [
        ("card_expired", RecoveryCategory.RECOVERABLE_ACTION_NEEDED),
        ("expired_card", RecoveryCategory.RECOVERABLE_ACTION_NEEDED),
        ("wrong_otp", RecoveryCategory.RECOVERABLE_ACTION_NEEDED),
        ("invalid_otp", RecoveryCategory.RECOVERABLE_ACTION_NEEDED),
        ("otp_expired", RecoveryCategory.RECOVERABLE_ACTION_NEEDED),
        ("authentication_failed", RecoveryCategory.RECOVERABLE_ACTION_NEEDED),
        ("auth_failed", RecoveryCategory.RECOVERABLE_ACTION_NEEDED),
        ("incorrect_pin", RecoveryCategory.RECOVERABLE_ACTION_NEEDED),
        ("invalid_cvv", RecoveryCategory.RECOVERABLE_ACTION_NEEDED),
        ("payment_method_declined", RecoveryCategory.RECOVERABLE_ACTION_NEEDED),
        ("card_declined", RecoveryCategory.RECOVERABLE_ACTION_NEEDED),
        ("do_not_honor", RecoveryCategory.RECOVERABLE_ACTION_NEEDED),
    ])
    def test_recoverable_action_needed_codes(self, code, expected_category, mock_openai_client):
        txn = {
            "transaction_id": f"txn_{code}",
            "amount": 3499.0,
            "failure_reason_code": code,
            "type": "subscription_renewal"
        }
        res = diagnose_transaction(txn, llm_client=mock_openai_client)

        assert res.category == expected_category
        assert res.is_llm_diagnosed is False
        assert res.source == "rule_based"
        assert res.confidence == 1.0

        # Verify LLM was NOT called
        mock_openai_client.beta.chat.completions.parse.assert_not_called()
        mock_openai_client.chat.completions.create.assert_not_called()

    @pytest.mark.parametrize("code,expected_category", [
        ("network_error", RecoveryCategory.RECOVERABLE_TECHNICAL),
        ("connection_timeout", RecoveryCategory.RECOVERABLE_TECHNICAL),
        ("gateway_error", RecoveryCategory.RECOVERABLE_TECHNICAL),
        ("gateway_timeout", RecoveryCategory.RECOVERABLE_TECHNICAL),
        ("internal_server_error", RecoveryCategory.RECOVERABLE_TECHNICAL),
        ("system_error", RecoveryCategory.RECOVERABLE_TECHNICAL),
        ("processing_error", RecoveryCategory.RECOVERABLE_TECHNICAL),
    ])
    def test_recoverable_technical_codes(self, code, expected_category, mock_openai_client):
        txn = {
            "transaction_id": f"txn_{code}",
            "amount": 1899.0,
            "failure_reason_code": code,
            "type": "one_time_checkout"
        }
        res = diagnose_transaction(txn, llm_client=mock_openai_client)

        assert res.category == expected_category
        assert res.is_llm_diagnosed is False
        assert res.source == "rule_based"
        assert res.confidence == 1.0

        # Verify LLM was NOT called
        mock_openai_client.beta.chat.completions.parse.assert_not_called()
        mock_openai_client.chat.completions.create.assert_not_called()

    @pytest.mark.parametrize("code,expected_category", [
        ("account_closed", RecoveryCategory.UNRECOVERABLE),
        ("account_inactive", RecoveryCategory.UNRECOVERABLE),
        ("invalid_account", RecoveryCategory.UNRECOVERABLE),
        ("account_does_not_exist", RecoveryCategory.UNRECOVERABLE),
        ("fraud_suspected", RecoveryCategory.UNRECOVERABLE),
        ("stolen_card", RecoveryCategory.UNRECOVERABLE),
        ("lost_card", RecoveryCategory.UNRECOVERABLE),
        ("sanctioned_entity", RecoveryCategory.UNRECOVERABLE),
        ("blacklisted_customer", RecoveryCategory.UNRECOVERABLE),
    ])
    def test_unrecoverable_codes(self, code, expected_category, mock_openai_client):
        txn = {
            "transaction_id": f"txn_{code}",
            "amount": 9999.0,
            "failure_reason_code": code,
            "type": "subscription_renewal"
        }
        res = diagnose_transaction(txn, llm_client=mock_openai_client)

        assert res.category == expected_category
        assert res.is_llm_diagnosed is False
        assert res.source == "rule_based"
        assert res.confidence == 1.0

        # Verify LLM was NOT called
        mock_openai_client.beta.chat.completions.parse.assert_not_called()
        mock_openai_client.chat.completions.create.assert_not_called()

    def test_case_and_formatting_insensitivity(self, mock_openai_client):
        """Verify uppercase, spaces, and hyphens match the deterministic rule map."""
        variants = ["INSUFFICIENT_FUNDS", " Card-Expired ", "NETWORK_ERROR", "Account Closed"]
        for var in variants:
            txn = {"transaction_id": "txn_var", "failure_reason_code": var, "amount": 500}
            res = diagnose_transaction(txn, llm_client=mock_openai_client)
            assert res.is_llm_diagnosed is False
            assert res.confidence == 1.0

        mock_openai_client.beta.chat.completions.parse.assert_not_called()


# ── 2. Ambiguous and Customer Abandoned LLM Path Tests ─────────────────────────

class TestAmbiguousAndAbandonedLLMPath:
    """
    Ensure customer_abandoned cases and ambiguous/unknown codes ALWAYS call the LLM
    and return structured JSON matching the schema.
    """

    def test_customer_abandoned_calls_llm_structured_parse(self, mock_openai_client):
        txn = {
            "transaction_id": "txn_abn_001",
            "type": "checkout_abandonment",
            "amount": 12900.0,
            "currency": "INR",
            "failure_reason_code": "customer_abandoned",
            "description": "Cart Recovery - Bose QuietComfort Earbuds",
            "customer_channel_pref": "whatsapp",
            "contact_attempts_so_far": 0
        }

        res = diagnose_transaction(txn, llm_client=mock_openai_client)

        # Confirm LLM was called
        assert mock_openai_client.beta.chat.completions.parse.call_count == 1
        assert res.is_llm_diagnosed is True
        assert res.source == "llm"
        assert res.category == RecoveryCategory.RECOVERABLE_ACTION_NEEDED
        assert "earbuds" in res.likely_reason.lower()
        assert 0.0 <= res.confidence <= 1.0
        assert res.recommended_action is not None
        assert "price_hesitation" in res.friction_points

    def test_customer_abandoned_tool_calling_fallback(self):
        """Verify tool calling fallback mode parses JSON correctly when parse is unavailable."""
        client = MagicMock(spec=["chat"])
        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "record_payment_diagnosis"
        mock_tool_call.function.arguments = json.dumps({
            "category": "recoverable_wait",
            "likely_reason": "Customer waiting for salary deposit before completing purchase.",
            "confidence": 0.75,
            "recommended_action": "Queue reminder for 1st of month.",
            "friction_points": ["liquidity_timing"]
        })

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(tool_calls=[mock_tool_call], content=None))
        ]
        client.chat.completions.create.return_value = mock_response

        txn = {
            "transaction_id": "txn_tool_001",
            "failure_reason_code": "customer_abandoned",
            "amount": 4500.0
        }

        res = diagnose_transaction(txn, llm_client=client)

        assert client.chat.completions.create.call_count == 1
        assert res.is_llm_diagnosed is True
        assert res.category == RecoveryCategory.RECOVERABLE_WAIT
        assert res.confidence == 0.75
        assert "salary deposit" in res.likely_reason

    def test_unknown_ambiguous_failure_code_calls_llm(self, mock_openai_client):
        """Any unmapped ambiguous code must trigger LLM reasoning."""
        txn = {
            "transaction_id": "txn_unknown_code",
            "failure_reason_code": "unrecognized_custom_bank_dropoff",
            "amount": 8500.0
        }

        res = diagnose_transaction(txn, llm_client=mock_openai_client)

        assert mock_openai_client.beta.chat.completions.parse.call_count == 1
        assert res.is_llm_diagnosed is True
        assert res.source == "llm"

    def test_offline_structured_fallback_when_no_api_key(self):
        """When no API key is provided and client is None, fallback produces valid structured schema."""
        txn = {
            "transaction_id": "txn_offline",
            "failure_reason_code": "customer_abandoned",
            "amount": 14999.0,
            "description": "Sony WH-1000XM5 Noise Cancelling Headphones",
            "customer_channel_pref": "whatsapp"
        }

        with patch("app.agent.diagnose.settings.openai_api_key", ""):
            res = diagnose_transaction(txn, llm_client=None)

            assert res.is_llm_diagnosed is True
            assert res.category in list(RecoveryCategory)
            assert res.confidence > 0.0
            assert "hesitation" in res.likely_reason.lower() or "sony" in res.likely_reason.lower()
            assert res.recommended_action is not None


# ── 3. Cost Control & Batch Execution Tests ────────────────────────────────────

class TestCostControlAndBatchDiagnosis:
    """
    Validates that in large mixed batches, deterministic cases never call LLM,
    strictly capping LLM consumption only to ambiguous instances.
    """

    def test_mixed_batch_exact_llm_call_count(self, mock_openai_client):
        # 16 clear deterministic transactions
        rule_codes = [
            "insufficient_funds", "card_expired", "bank_timeout", "account_closed",
            "wrong_otp", "network_error", "daily_limit_exceeded", "gateway_error",
            "invalid_cvv", "authentication_failed", "account_inactive", "processing_error",
            "stolen_card", "do_not_honor", "limit_exceeded", "bank_downtime"
        ]
        deterministic_txns = [
            {"transaction_id": f"txn_det_{i}", "failure_reason_code": code, "amount": 1000 + i * 100}
            for i, code in enumerate(rule_codes)
        ]

        # 4 customer_abandoned transactions
        abandoned_txns = [
            {"transaction_id": f"txn_abn_{i}", "failure_reason_code": "customer_abandoned", "amount": 5000 + i * 500}
            for i in range(4)
        ]

        # Combine (total 20 transactions)
        all_txns = deterministic_txns + abandoned_txns

        results = diagnose_batch(all_txns, llm_client=mock_openai_client)

        assert len(results) == 20

        # Exact cost verification: LLM must be called EXACTLY 4 times (only for the abandoned items)
        assert mock_openai_client.beta.chat.completions.parse.call_count == 4

        # Verify the 16 rule-based transactions have is_llm_diagnosed == False
        for res in results[:16]:
            assert res.is_llm_diagnosed is False
            assert res.source == "rule_based"
            assert res.confidence == 1.0

        # Verify the 4 abandoned transactions have is_llm_diagnosed == True
        for res in results[16:]:
            assert res.is_llm_diagnosed is True
            assert res.source == "llm"


# ── 4. Async and Pydantic Model Compatibility Tests ────────────────────────────

class TestModelCompatibilityAndAsync:
    """
    Validates integration with Pydantic schemas and async diagnosis.
    """

    def test_async_diagnose_rule_path(self, mock_openai_client):
        import asyncio

        txn = {
            "transaction_id": "txn_async_001",
            "failure_reason_code": "insufficient_funds",
            "amount": 2500.0
        }
        res = asyncio.run(async_diagnose_transaction(txn, llm_client=mock_openai_client))

        assert res.category == RecoveryCategory.RECOVERABLE_WAIT
        assert res.is_llm_diagnosed is False
        mock_openai_client.beta.chat.completions.parse.assert_not_called()

    def test_async_diagnose_abandoned_path(self, mock_openai_client):
        import asyncio

        txn = {
            "transaction_id": "txn_async_002",
            "failure_reason_code": "customer_abandoned",
            "amount": 9800.0
        }
        res = asyncio.run(async_diagnose_transaction(txn, llm_client=mock_openai_client))

        assert res.is_llm_diagnosed is True
        assert mock_openai_client.beta.chat.completions.parse.call_count == 1

    def test_pydantic_transaction_model_input(self, mock_openai_client):
        """Verify passing a Pydantic TransactionBase model instance works seamlessly."""
        txn_model = TransactionBase(
            transaction_id="txn_pydantic_001",
            customer_id="cust_12345",
            type="one_time_checkout",
            amount=4499.0,
            failure_reason_code="wrong_otp",
            customer_channel_pref="whatsapp",
            status="open"
        )

        res = diagnose_transaction(txn_model, llm_client=mock_openai_client)

        assert res.transaction_id == "txn_pydantic_001"
        assert res.category == RecoveryCategory.RECOVERABLE_ACTION_NEEDED
        assert res.is_llm_diagnosed is False
        mock_openai_client.beta.chat.completions.parse.assert_not_called()
