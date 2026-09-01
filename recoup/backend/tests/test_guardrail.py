"""
tests/test_guardrail.py
-----------------------
Unit and integration tests for the deterministic guardrail and Recoup AI recovery agent.

Test Coverage:
1. Max contact attempts exceeded (contact count limits).
2. Contact during blocked hours (quiet hours vs operational hours).
3. Opted-out customer (Do-Not-Contact registry, opt-out flags).
4. Minimum time between contacts (cooldown window / 24h rolling limit).
5. Unrecoverable account outreach freeze (account_closed / fraud).
6. Block logging (immutable audit logs generated upon guardrail rejection).
7. Permitted outreach happy paths (normal daytime flow).
8. Agent integration: Guardrail intercepting LLM tool execution before dispatch.
9. All 6 LLM tools unit testing.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from app.agent.agent import RecoupAgent, ToolExecutionRecord
from app.guardrails.guardrail import (
    DEFAULT_MAX_CONTACT_ATTEMPTS,
    DNCRegistry,
    DeterministicGuardrail,
    GuardrailResult,
    GuardrailRule,
    GuardrailViolation,
    IST_TIMEZONE,
    guardrail_check,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def clean_dnc_registry():
    """Provides an isolated DNC registry for testing."""
    return DNCRegistry(initial_opt_outs={"cust_opted_out_001", "cust_dnc_test"})


@pytest.fixture
def custom_guardrail(clean_dnc_registry):
    """Provides a DeterministicGuardrail instance with custom test registry."""
    return DeterministicGuardrail(
        max_contact_attempts=3,
        min_time_between_contacts_hours=24.0,
        dnc_registry=clean_dnc_registry,
    )


@pytest.fixture
def daytime_ist():
    """A datetime strictly within operational hours (14:30 IST / 2:30 PM)."""
    return datetime.datetime(2026, 9, 2, 14, 30, 0, tzinfo=IST_TIMEZONE)


@pytest.fixture
def quiet_hours_night_ist():
    """A datetime strictly within quiet hours blackout (22:30 IST / 10:30 PM)."""
    return datetime.datetime(2026, 9, 2, 22, 30, 0, tzinfo=IST_TIMEZONE)


@pytest.fixture
def quiet_hours_morning_ist():
    """A datetime strictly within quiet hours blackout (05:00 IST / 5:00 AM)."""
    return datetime.datetime(2026, 9, 2, 5, 0, 0, tzinfo=IST_TIMEZONE)


# ── 1. Max Contact Attempts Exceeded Tests ─────────────────────────────────────

class TestMaxContactAttempts:
    def test_max_attempts_exact_threshold_blocked(self, custom_guardrail, daytime_ist):
        """When contact_attempts_so_far equals max_contact_attempts (3), outreach must be blocked."""
        context = {
            "transaction_id": "txn_001",
            "customer_id": "cust_100",
            "contact_attempts_so_far": 3,
            "status": "open",
        }
        res: GuardrailResult = custom_guardrail.check_action(
            action="send_message",
            context=context,
            current_time=daytime_ist,
        )
        assert res.is_allowed is False
        assert res.rule_violated == GuardrailRule.MAX_CONTACT_ATTEMPTS_EXCEEDED
        assert "reached or exceeded the maximum" in res.reason
        assert len(custom_guardrail.blocked_history) == 1

    def test_max_attempts_exceeded_value_blocked(self, custom_guardrail, daytime_ist):
        """When contact_attempts_so_far is greater than max_contact_attempts (e.g. 5), outreach must be blocked."""
        context = {
            "transaction_id": "txn_002",
            "customer_id": "cust_101",
            "contact_attempts_so_far": 5,
            "status": "open",
        }
        res = custom_guardrail.check_action(
            action="send_message",
            context=context,
            current_time=daytime_ist,
        )
        assert res.is_allowed is False
        assert res.rule_violated == GuardrailRule.MAX_CONTACT_ATTEMPTS_EXCEEDED

    def test_custom_max_attempts_context_override(self, custom_guardrail, daytime_ist):
        """Context-specific max_contact_attempts overrides default limit."""
        context = {
            "transaction_id": "txn_003",
            "customer_id": "cust_102",
            "contact_attempts_so_far": 1,
            "max_contact_attempts": 1,
            "status": "open",
        }
        res = custom_guardrail.check_action(
            action="send_message",
            context=context,
            current_time=daytime_ist,
        )
        assert res.is_allowed is False
        assert res.rule_violated == GuardrailRule.MAX_CONTACT_ATTEMPTS_EXCEEDED

    def test_below_max_attempts_permitted(self, custom_guardrail, daytime_ist):
        """When contact_attempts_so_far < max_contact_attempts, check passes."""
        context = {
            "transaction_id": "txn_004",
            "customer_id": "cust_103",
            "contact_attempts_so_far": 2,
            "status": "open",
        }
        res = custom_guardrail.check_action(
            action="send_message",
            context=context,
            current_time=daytime_ist,
        )
        assert res.is_allowed is True
        assert res.rule_violated is None
        assert "Outreach approved" in res.reason


# ── 2. Contact During Blocked Hours (Quiet Hours) Tests ────────────────────────

class TestAllowedContactHours:
    def test_night_quiet_hours_blocked(self, custom_guardrail, quiet_hours_night_ist):
        """Outreach at 22:30 IST must be blocked under quiet hours policy."""
        context = {
            "transaction_id": "txn_005",
            "customer_id": "cust_200",
            "contact_attempts_so_far": 0,
        }
        res = custom_guardrail.check_action(
            action="send_message",
            context=context,
            current_time=quiet_hours_night_ist,
        )
        assert res.is_allowed is False
        assert res.rule_violated == GuardrailRule.QUIET_HOURS_BLOCKED
        assert "quiet hours blackout window" in res.reason

    def test_early_morning_quiet_hours_blocked(self, custom_guardrail, quiet_hours_morning_ist):
        """Outreach at 05:00 IST must be blocked."""
        context = {
            "transaction_id": "txn_006",
            "customer_id": "cust_201",
            "contact_attempts_so_far": 0,
        }
        res = custom_guardrail.check_action(
            action="send_message",
            context=context,
            current_time=quiet_hours_morning_ist,
        )
        assert res.is_allowed is False
        assert res.rule_violated == GuardrailRule.QUIET_HOURS_BLOCKED

    def test_boundary_quiet_hours_8_59_blocked(self, custom_guardrail):
        """Outreach at 08:59:59 IST is outside 09:00 operational start and must be blocked."""
        t_8_59 = datetime.datetime(2026, 9, 2, 8, 59, 59, tzinfo=IST_TIMEZONE)
        res = custom_guardrail.check_action(
            action="send_message",
            context={"customer_id": "cust_202", "contact_attempts_so_far": 0},
            current_time=t_8_59,
        )
        assert res.is_allowed is False
        assert res.rule_violated == GuardrailRule.QUIET_HOURS_BLOCKED

    def test_boundary_operational_start_9_00_allowed(self, custom_guardrail):
        """Outreach at 09:00:00 IST is within operational hours and allowed."""
        t_9_00 = datetime.datetime(2026, 9, 2, 9, 0, 0, tzinfo=IST_TIMEZONE)
        res = custom_guardrail.check_action(
            action="send_message",
            context={"customer_id": "cust_203", "contact_attempts_so_far": 0},
            current_time=t_9_00,
        )
        assert res.is_allowed is True
        assert res.rule_violated is None

    def test_boundary_operational_end_20_00_allowed(self, custom_guardrail):
        """Outreach at 20:00:00 IST is within operational window and allowed."""
        t_20_00 = datetime.datetime(2026, 9, 2, 20, 0, 0, tzinfo=IST_TIMEZONE)
        res = custom_guardrail.check_action(
            action="send_message",
            context={"customer_id": "cust_204", "contact_attempts_so_far": 0},
            current_time=t_20_00,
        )
        assert res.is_allowed is True
        assert res.rule_violated is None

    def test_boundary_quiet_hours_20_01_blocked(self, custom_guardrail):
        """Outreach at 20:01:00 IST is in quiet hours and blocked."""
        t_20_01 = datetime.datetime(2026, 9, 2, 20, 1, 0, tzinfo=IST_TIMEZONE)
        res = custom_guardrail.check_action(
            action="send_message",
            context={"customer_id": "cust_205", "contact_attempts_so_far": 0},
            current_time=t_20_01,
        )
        assert res.is_allowed is False
        assert res.rule_violated == GuardrailRule.QUIET_HOURS_BLOCKED


# ── 3. Opted-Out Customer / DNC Tests ──────────────────────────────────────────

class TestOptedOutCustomer:
    def test_customer_in_dnc_registry_blocked(self, custom_guardrail, daytime_ist):
        """Customer present in DNC registry must be blocked immediately."""
        context = {
            "transaction_id": "txn_007",
            "customer_id": "cust_opted_out_001",
            "contact_attempts_so_far": 0,
        }
        res = custom_guardrail.check_action(
            action="send_message",
            context=context,
            current_time=daytime_ist,
        )
        assert res.is_allowed is False
        assert res.rule_violated == GuardrailRule.OPTED_OUT_CUSTOMER
        assert "Do-Not-Contact registry" in res.reason

    def test_customer_context_opt_out_flag_blocked(self, custom_guardrail, daytime_ist):
        """Transaction context marked with is_opted_out=True must be blocked."""
        context = {
            "transaction_id": "txn_008",
            "customer_id": "cust_fresh_user_999",
            "is_opted_out": True,
            "contact_attempts_so_far": 0,
        }
        res = custom_guardrail.check_action(
            action="send_message",
            context=context,
            current_time=daytime_ist,
        )
        assert res.is_allowed is False
        assert res.rule_violated == GuardrailRule.OPTED_OUT_CUSTOMER

    def test_dnc_registry_dynamic_addition(self, custom_guardrail, daytime_ist, clean_dnc_registry):
        """Adding a new user to DNC registry immediately blocks outreach."""
        clean_dnc_registry.add("cust_newly_unsubscribed")
        context = {
            "transaction_id": "txn_009",
            "customer_id": "cust_newly_unsubscribed",
            "contact_attempts_so_far": 0,
        }
        res = custom_guardrail.check_action(
            action="send_message",
            context=context,
            current_time=daytime_ist,
        )
        assert res.is_allowed is False
        assert res.rule_violated == GuardrailRule.OPTED_OUT_CUSTOMER

    def test_dnc_registry_phone_or_email_blocked(self, custom_guardrail, daytime_ist, clean_dnc_registry):
        """Matching by phone or email in DNC registry blocks outreach."""
        clean_dnc_registry.add("+919876543210")
        clean_dnc_registry.add("optout@example.com")

        res_phone = custom_guardrail.check_action(
            action="send_message",
            context={"customer_id": "cust_abc", "customer_phone": "+919876543210"},
            current_time=daytime_ist,
        )
        assert res_phone.is_allowed is False
        assert res_phone.rule_violated == GuardrailRule.OPTED_OUT_CUSTOMER

        res_email = custom_guardrail.check_action(
            action="send_message",
            context={"customer_id": "cust_def", "customer_email": "optout@example.com"},
            current_time=daytime_ist,
        )
        assert res_email.is_allowed is False
        assert res_email.rule_violated == GuardrailRule.OPTED_OUT_CUSTOMER


# ── 4. Minimum Time Between Contacts (Cooldown) Tests ──────────────────────────

class TestMinimumTimeBetweenContacts:
    def test_cooldown_violation_blocked(self, custom_guardrail, daytime_ist):
        """Outreach attempted 3 hours after previous contact (min 24h) must be blocked."""
        last_contact = daytime_ist - datetime.timedelta(hours=3)
        context = {
            "transaction_id": "txn_010",
            "customer_id": "cust_300",
            "contact_attempts_so_far": 1,
            "last_contacted_at": last_contact.isoformat(),
        }
        res = custom_guardrail.check_action(
            action="send_message",
            context=context,
            current_time=daytime_ist,
        )
        assert res.is_allowed is False
        assert res.rule_violated == GuardrailRule.MIN_TIME_BETWEEN_CONTACTS_VIOLATION
        assert "Minimum cooldown is 24.0 hours" in res.reason

    def test_cooldown_satisfied_allowed(self, custom_guardrail, daytime_ist):
        """Outreach attempted 25 hours after previous contact is allowed."""
        last_contact = daytime_ist - datetime.timedelta(hours=25)
        context = {
            "transaction_id": "txn_011",
            "customer_id": "cust_301",
            "contact_attempts_so_far": 1,
            "last_contacted_at": last_contact.isoformat(),
        }
        res = custom_guardrail.check_action(
            action="send_message",
            context=context,
            current_time=daytime_ist,
        )
        assert res.is_allowed is True
        assert res.rule_violated is None


# ── 5. Unrecoverable Outreach Freeze Tests ──────────────────────────────────────

class TestUnrecoverableFreeze:
    def test_account_closed_outreach_frozen(self, custom_guardrail, daytime_ist):
        """Policy 06: account_closed transactions must have zero automated outreach."""
        context = {
            "transaction_id": "txn_012",
            "customer_id": "cust_400",
            "failure_reason_code": "account_closed",
            "status": "unrecoverable",
            "contact_attempts_so_far": 0,
        }
        res = custom_guardrail.check_action(
            action="send_message",
            context=context,
            current_time=daytime_ist,
        )
        assert res.is_allowed is False
        assert res.rule_violated == GuardrailRule.UNRECOVERABLE_OUTREACH_FROZEN


# ── 6. Block Logging & Audit Trail Tests ───────────────────────────────────────

class TestBlockLogging:
    def test_blocked_action_logged_in_audit(self, daytime_ist):
        """Blocked actions must generate structured audit logs."""
        logged_events = []
        guardrail = DeterministicGuardrail(
            audit_logger=lambda entry: logged_events.append(entry)
        )
        context = {
            "transaction_id": "txn_audit_001",
            "customer_id": "cust_audit_1",
            "contact_attempts_so_far": 3,
        }
        res = guardrail.check_action("send_message", context=context, current_time=daytime_ist)
        assert res.is_allowed is False
        assert len(logged_events) == 1
        assert logged_events[0]["event"] == "guardrail_blocked"
        assert logged_events[0]["rule"] == GuardrailRule.MAX_CONTACT_ATTEMPTS_EXCEEDED.value
        assert "[GUARDRAIL BLOCKED]" in res.format_audit_note()


# ── 7. Agent & LLM Tools Integration Tests ────────────────────────────────────

class TestAgentAndGuardrailIntegration:
    @pytest.fixture
    def agent_with_guardrail(self, custom_guardrail):
        return RecoupAgent(guardrail=custom_guardrail)

    def test_agent_tool_send_message_blocked_on_opt_out(self, agent_with_guardrail, daytime_ist):
        """Direct call to agent's send_message tool is intercepted and blocked for opted-out user."""
        res = agent_with_guardrail.send_message(
            customer_id="cust_opted_out_001",
            channel="whatsapp",
            content="Your payment failed. Please click here to retry.",
            transaction_id="txn_agent_optout",
            current_time=daytime_ist,
        )
        assert res["status"] == "blocked"
        assert res["is_allowed"] is False
        assert res["rule_violated"] == GuardrailRule.OPTED_OUT_CUSTOMER.value

        # Check audit log was generated
        logs = agent_with_guardrail.audit_history
        assert any(l["action"] == "guardrail_blocked" and l["transaction_id"] == "txn_agent_optout" for l in logs)

    def test_agent_tool_send_message_blocked_on_quiet_hours(self, agent_with_guardrail, quiet_hours_night_ist):
        """Direct call to agent's send_message tool is blocked during quiet hours."""
        res = agent_with_guardrail.send_message(
            customer_id="cust_active_001",
            channel="whatsapp",
            content="Your payment failed.",
            transaction_id="txn_agent_night",
            current_time=quiet_hours_night_ist,
        )
        assert res["status"] == "blocked"
        assert res["rule_violated"] == GuardrailRule.QUIET_HOURS_BLOCKED.value

    def test_agent_tool_send_message_blocked_on_max_attempts(self, agent_with_guardrail, daytime_ist):
        """Direct call to send_message is blocked when contact count >= 3."""
        res = agent_with_guardrail.send_message(
            customer_id="cust_active_002",
            channel="whatsapp",
            content="Final reminder.",
            transaction_id="txn_agent_max",
            context={"contact_attempts_so_far": 3},
            current_time=daytime_ist,
        )
        assert res["status"] == "blocked"
        assert res["rule_violated"] == GuardrailRule.MAX_CONTACT_ATTEMPTS_EXCEEDED.value

    def test_agent_tool_send_message_delivered_when_allowed(self, agent_with_guardrail, daytime_ist):
        """When guardrail passes, send_message successfully delivers outreach."""
        res = agent_with_guardrail.send_message(
            customer_id="cust_clean_001",
            channel="whatsapp",
            content="Hello from Recoup! Your cart is waiting.",
            transaction_id="txn_agent_ok",
            context={"contact_attempts_so_far": 0},
            current_time=daytime_ist,
        )
        assert res["status"] == "delivered"
        assert res["is_allowed"] is True
        assert res["channel"] == "whatsapp"

    def test_agent_tools_retrieve_policy(self, agent_with_guardrail):
        """Tool 1: retrieve_policy queries policy chunks successfully."""
        chunks = agent_with_guardrail.retrieve_policy("insufficient funds recovery", k=2)
        assert len(chunks) > 0
        assert "Insufficient Funds Recovery Policy" in chunks[0]["policy_title"]

    def test_agent_tools_retrieve_similar_cases(self, agent_with_guardrail):
        """Tool 2: retrieve_similar_cases matches historical patterns."""
        cases = agent_with_guardrail.retrieve_similar_cases("insufficient_funds")
        assert len(cases) > 0
        assert cases[0]["failure_reason_code"] == "insufficient_funds"

    def test_agent_tools_simulate_retry_payment(self, agent_with_guardrail):
        """Tool 3: simulate_retry_payment succeeds on technical network error."""
        res = agent_with_guardrail.simulate_retry_payment(
            transaction_id="txn_tech_99",
            context={"failure_reason_code": "network_error"},
        )
        assert res["status"] == "success"
        assert "pay_retry_" in res["retry_payment_id"]

    def test_agent_tools_escalate_to_human(self, agent_with_guardrail, daytime_ist):
        """Tool 5: escalate_to_human routes unrecoverable cases to support."""
        res = agent_with_guardrail.escalate_to_human(
            transaction_id="txn_esc_01",
            reason="Account permanently closed.",
            current_time=daytime_ist,
        )
        assert res["status"] == "escalated"
        assert "ESC_txn_esc_01" in res["ticket_id"]

    def test_agent_tools_log_action(self, agent_with_guardrail, daytime_ist):
        """Tool 6: log_action records immutable audit log."""
        res = agent_with_guardrail.log_action(
            transaction_id="txn_log_01",
            action="reviewed",
            reasoning="Agent verified transaction status.",
            actor="agent",
            current_time=daytime_ist,
        )
        assert res["status"] == "logged"
        assert res["entry"]["notes"] == "Agent verified transaction status."

    def test_agent_process_open_transaction_loop(self, agent_with_guardrail, daytime_ist):
        """Tests the full agent reasoning loop over open transactions."""
        open_txns = [
            {
                "transaction_id": "txn_loop_1",
                "customer_id": "cust_loop_1",
                "failure_reason_code": "insufficient_funds",
                "type": "one_time_checkout",
                "amount": 1999.00,
                "contact_attempts_so_far": 0,
                "status": "open",
            },
            {
                "transaction_id": "txn_loop_2",
                "customer_id": "cust_opted_out_001",  # Opted out -> Should be blocked!
                "failure_reason_code": "insufficient_funds",
                "type": "one_time_checkout",
                "amount": 2999.00,
                "contact_attempts_so_far": 0,
                "status": "open",
            },
            {
                "transaction_id": "txn_loop_3",
                "customer_id": "cust_loop_3",
                "failure_reason_code": "account_closed",  # Unrecoverable -> Should escalate!
                "type": "subscription_renewal",
                "amount": 8999.00,
                "contact_attempts_so_far": 0,
                "status": "open",
            },
        ]

        results = agent_with_guardrail.run_recovery_cycle(open_txns, current_time=daytime_ist)
        assert len(results) == 3

        # Txn 1: Insufficient funds allowed outreach
        assert results[0].transaction_id == "txn_loop_1"
        assert results[0].final_transaction_status == "pending"
        assert len(results[0].actions_blocked) == 0

        # Txn 2: Opted out blocked
        assert results[1].transaction_id == "txn_loop_2"
        assert len(results[1].actions_blocked) == 1
        assert results[1].actions_blocked[0]["rule_violated"] == GuardrailRule.OPTED_OUT_CUSTOMER.value

        # Txn 3: Unrecoverable escalated
        assert results[2].transaction_id == "txn_loop_3"
        assert results[2].final_transaction_status == "unrecoverable"
        assert any(t.tool_name == "escalate_to_human" for t in results[2].tools_executed)
