"""
agent/agent.py
--------------
Core Autonomous Revenue Recovery Agent for Recoup AI.

Architecture:
1. LLM Tool Ecosystem (6 Tools):
   - retrieve_policy(query): RAG semantic retrieval over policy markdown files.
   - retrieve_similar_cases(transaction): Historical case matcher for recovery patterns.
   - simulate_retry_payment(transaction_id): Simulates / triggers technical payment retry.
   - send_message(customer_id, channel, content): Customer outreach across WhatsApp/SMS/Email.
     [WRAPPED BY DETERMINISTIC GUARDRAIL]
   - escalate_to_human(transaction_id, reason): Human operations routing.
     [WRAPPED BY DETERMINISTIC GUARDRAIL]
   - log_action(transaction_id, action, reasoning): Immutable audit logging.

2. Deterministic Guardrail Interception:
   Before `send_message` or `escalate_to_human` are executed, the deterministic guardrail
   verifies: contact count limits, minimum time between contacts (cooldown), operational
   hours (09:00–20:00 IST), opt-out status, and unrecoverable freezes.
   Any blocked action is strictly prevented from executing and immediately logged.

3. Recovery Loop:
   Iterates through open transactions, retrieves policy & similar cases, reasons about the
   optimal recovery action using LLM tool calling (with offline fallback), executes tools,
   and logs audit entries.
"""

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

from app.config import settings
from app.guardrails.guardrail import (
    DEFAULT_MAX_CONTACT_ATTEMPTS,
    DEFAULT_MIN_TIME_BETWEEN_CONTACTS_HOURS,
    DeterministicGuardrail,
    GuardrailResult,
    GuardrailRule,
    IST_TIMEZONE,
    get_guardrail,
)
from app.retrieval.retriever import retrieve_policy as rag_retrieve_policy

logger = logging.getLogger("recoup.agent")


# ── Similar Cases In-Memory Historical Knowledge Base ──────────────────────────

HISTORICAL_CASES: List[Dict[str, Any]] = [
    {
        "case_id": "hist_001",
        "failure_reason_code": "insufficient_funds",
        "type": "one_time_checkout",
        "amount_range": "low_to_mid",
        "channel": "whatsapp",
        "resolution_tactic": "Delayed WhatsApp reminder sent on Day 3 morning during banking deposit hours with 1-click UPI pay link.",
        "outcome": "recovered_day_3",
    },
    {
        "case_id": "hist_002",
        "failure_reason_code": "card_expired",
        "type": "subscription_renewal",
        "amount_range": "mid_to_high",
        "channel": "email",
        "resolution_tactic": "Dual Email + WhatsApp card update portal reminder sent 24h post failure.",
        "outcome": "card_updated_and_charged",
    },
    {
        "case_id": "hist_003",
        "failure_reason_code": "network_error",
        "type": "one_time_checkout",
        "amount_range": "all",
        "channel": "sms",
        "resolution_tactic": "Automated technical retry executed within 15 minutes; payment succeeded without customer interruption.",
        "outcome": "recovered_instant_retry",
    },
    {
        "case_id": "hist_004",
        "failure_reason_code": "account_closed",
        "type": "subscription_renewal",
        "amount_range": "high",
        "channel": "none",
        "resolution_tactic": "Outreach frozen immediately; case escalated to customer operations team for account review.",
        "outcome": "unrecoverable_escalated",
    },
    {
        "case_id": "hist_005",
        "failure_reason_code": "customer_abandoned",
        "type": "checkout_abandonment",
        "amount_range": "high",
        "channel": "whatsapp",
        "resolution_tactic": "Sent conversational WhatsApp cart reminder with reserved stock assurance and optional 5% checkout incentive.",
        "outcome": "recovered_cart",
    },
    {
        "case_id": "hist_006",
        "failure_reason_code": "wrong_otp",
        "type": "one_time_checkout",
        "amount_range": "low_to_mid",
        "channel": "whatsapp",
        "resolution_tactic": "Instant 1-click retry payment link sent within 15 minutes while customer was still active.",
        "outcome": "recovered_otp_retry",
    },
]


# ── OpenAI Tool Schemas ────────────────────────────────────────────────────────

AGENT_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "retrieve_policy",
            "description": "Retrieves company recovery policies and operational rules from the policy knowledge base using semantic search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language question or policy topic (e.g., 'insufficient funds retry schedule', 'quiet hours rules').",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_similar_cases",
            "description": "Finds historical recovery cases and resolution tactics for transactions with matching failure codes and characteristics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {
                        "type": "string",
                        "description": "The transaction ID being evaluated.",
                    },
                    "failure_reason_code": {
                        "type": "string",
                        "description": "The failure reason code (e.g. 'insufficient_funds', 'card_expired', 'customer_abandoned').",
                    },
                },
                "required": ["failure_reason_code"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_retry_payment",
            "description": "Simulates an automated technical payment retry via Razorpay / payment switch for network or transient errors.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {
                        "type": "string",
                        "description": "The unique transaction identifier.",
                    },
                },
                "required": ["transaction_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Sends customer outreach message via preferred channel (WhatsApp, SMS, Email). Subject to strict guardrail verification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The unique customer identifier (e.g. cust_xxx).",
                    },
                    "channel": {
                        "type": "string",
                        "enum": ["whatsapp", "sms", "email"],
                        "description": "The communication channel to dispatch message to.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The personalized recovery message content containing clear call-to-action and payment link.",
                    },
                },
                "required": ["customer_id", "channel", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": "Escalates unrecoverable, fraudulent, high-value, or compliance-restricted transactions to human customer operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {
                        "type": "string",
                        "description": "The unique transaction identifier.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Detailed explanation of why human intervention is required.",
                    },
                },
                "required": ["transaction_id", "reason"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_action",
            "description": "Records an immutable audit log entry documenting an action taken, actor, and reasoning.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {
                        "type": "string",
                        "description": "The unique transaction identifier.",
                    },
                    "action": {
                        "type": "string",
                        "description": "Action performed (e.g. 'contact_attempted', 'retried', 'escalated', 'flagged', 'resolved').",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Comprehensive explanation of why this action was decided.",
                    },
                },
                "required": ["transaction_id", "action", "reasoning"],
                "additionalProperties": False,
            },
        },
    },
]


# ── Data Models ────────────────────────────────────────────────────────────────

@dataclass
class ToolExecutionRecord:
    tool_name: str
    arguments: Dict[str, Any]
    result: Dict[str, Any]
    was_blocked_by_guardrail: bool = False
    guardrail_rule: Optional[str] = None
    guardrail_reason: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(IST_TIMEZONE).isoformat()
    )


@dataclass
class AgentDecision:
    transaction_id: str
    action_type: str  # e.g. "send_message", "retry_payment", "escalate_to_human", "none"
    reasoning: str
    policy_reference: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentExecutionResult:
    transaction_id: str
    customer_id: str
    status: str
    policy_chunks_retrieved: List[Dict[str, Any]] = field(default_factory=list)
    similar_cases: List[Dict[str, Any]] = field(default_factory=list)
    llm_reasoning: str = ""
    tools_executed: List[ToolExecutionRecord] = field(default_factory=list)
    actions_blocked: List[Dict[str, Any]] = field(default_factory=list)
    audit_logs: List[Dict[str, Any]] = field(default_factory=list)
    final_transaction_status: str = "open"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "customer_id": self.customer_id,
            "status": self.status,
            "policy_chunks_retrieved": self.policy_chunks_retrieved,
            "similar_cases": self.similar_cases,
            "llm_reasoning": self.llm_reasoning,
            "tools_executed": [asdict(t) for t in self.tools_executed],
            "actions_blocked": self.actions_blocked,
            "audit_logs": self.audit_logs,
            "final_transaction_status": self.final_transaction_status,
        }


# ── Recoup Agent Class ─────────────────────────────────────────────────────────

class RecoupAgent:
    """
    Autonomous AI Revenue Recovery Agent.

    Orchestrates policy retrieval, historical case lookup, LLM reasoning,
    tool execution, deterministic guardrails, and audit trail generation.
    """

    def __init__(
        self,
        guardrail: Optional[DeterministicGuardrail] = None,
        llm_client: Any = None,
        model: Optional[str] = None,
        audit_log_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.guardrail = guardrail or get_guardrail()
        self.client = llm_client
        self.model = model or settings.openai_model or "gpt-4o-mini"
        self.audit_log_sink = audit_log_sink
        self.audit_history: List[Dict[str, Any]] = []

    # ── Tool 1: retrieve_policy ────────────────────────────────────────────────

    def retrieve_policy(self, query: str, k: int = 2) -> List[Dict[str, Any]]:
        """
        Tool: Searches the policy knowledge base using semantic vector search.
        """
        try:
            results = rag_retrieve_policy(query=query, k=k)
            logger.info(f"[tool:retrieve_policy] Query '{query}' retrieved {len(results)} chunks.")
            return results
        except Exception as e:
            logger.error(f"[tool:retrieve_policy] Retrieval error: {e}")
            return []

    # ── Tool 2: retrieve_similar_cases ─────────────────────────────────────────

    def retrieve_similar_cases(
        self,
        transaction: Union[Dict[str, Any], str, Any],
        limit: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Tool: Retrieves matching historical recovery cases based on failure reason and type.
        """
        if isinstance(transaction, str):
            code = transaction.lower().strip()
            txn_type = ""
        elif isinstance(transaction, dict):
            code = str(transaction.get("failure_reason_code", "")).lower().strip()
            txn_type = str(transaction.get("type", "")).lower().strip()
        elif hasattr(transaction, "failure_reason_code"):
            code = str(getattr(transaction, "failure_reason_code", "")).lower().strip()
            txn_type = str(getattr(transaction, "type", "")).lower().strip()
        else:
            code = ""
            txn_type = ""

        matched: List[Dict[str, Any]] = []
        for case in HISTORICAL_CASES:
            case_code = case["failure_reason_code"].lower()
            if code == case_code:
                matched.append(case)
            elif code in case_code or case_code in code:
                matched.append(case)

        # Fallback to general matches if none specific
        if not matched:
            for case in HISTORICAL_CASES:
                if txn_type and case["type"] == txn_type:
                    matched.append(case)

        if not matched:
            matched = HISTORICAL_CASES[:limit]

        return matched[:limit]

    # ── Tool 3: simulate_retry_payment ─────────────────────────────────────────

    def simulate_retry_payment(
        self,
        transaction_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Tool: Simulates a payment retry via Razorpay API / banking network.
        """
        ctx = context or {}
        code = str(ctx.get("failure_reason_code", "")).lower()

        # Technical/transient errors have high retry success probability
        if code in {"network_error", "bank_timeout", "connection_timeout", "gateway_error", "internal_server_error"}:
            status = "success"
            retry_id = f"pay_retry_{transaction_id.replace('txn_', '')}"
            message = "Payment retry succeeded via secondary gateway switch."
        elif code in {"account_closed", "fraud_detected"}:
            status = "failed_permanent"
            retry_id = None
            message = "Retry rejected: Account is permanently closed or flagged."
        else:
            # Insufficient funds or expired card cannot be retried without customer action
            status = "failed_action_required"
            retry_id = None
            message = f"Payment retry failed: Customer action required ({code})."

        result = {
            "status": status,
            "transaction_id": transaction_id,
            "retry_payment_id": retry_id,
            "message": message,
            "timestamp": datetime.datetime.now(IST_TIMEZONE).isoformat(),
        }
        logger.info(f"[tool:simulate_retry_payment] {result}")
        return result

    # ── Tool 4: send_message (Guarded) ─────────────────────────────────────────

    def send_message(
        self,
        customer_id: str,
        channel: str,
        content: str,
        transaction_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        current_time: Optional[datetime.datetime] = None,
    ) -> Dict[str, Any]:
        """
        Tool: Dispatches customer outreach message.
        CRITICALLY WRAPPED by DeterministicGuardrail: checks contact count, cooldown,
        quiet hours, and opt-outs BEFORE sending. Blocks and logs if violated.
        """
        ctx = dict(context or {})
        ctx.setdefault("customer_id", customer_id)
        ctx.setdefault("channel", channel)
        if transaction_id:
            ctx.setdefault("transaction_id", transaction_id)

        # ── Deterministic Guardrail Verification ───────────────────────────────
        guardrail_result: GuardrailResult = self.guardrail.check_action(
            action="send_message",
            context=ctx,
            current_time=current_time,
        )

        # ── Blocked by Guardrail ───────────────────────────────────────────────
        if not guardrail_result.is_allowed:
            block_entry = {
                "transaction_id": transaction_id or ctx.get("transaction_id", "unknown"),
                "action": "send_message",
                "blocked": True,
                "rule_violated": guardrail_result.rule_violated.value if guardrail_result.rule_violated else "UNKNOWN",
                "reason": guardrail_result.reason,
                "attempted_payload": {
                    "customer_id": customer_id,
                    "channel": channel,
                    "content": content,
                },
                "timestamp": guardrail_result.evaluated_at.isoformat(),
            }

            # Immutable Block Logging
            self.log_action(
                transaction_id=block_entry["transaction_id"],
                action="guardrail_blocked",
                reasoning=guardrail_result.format_audit_note(),
                actor="guardrail",
                current_time=current_time,
            )

            logger.warning(f"[tool:send_message:BLOCKED] {guardrail_result.format_audit_note()}")
            return {
                "status": "blocked",
                "is_allowed": False,
                "rule_violated": guardrail_result.rule_violated.value if guardrail_result.rule_violated else "UNKNOWN",
                "reason": guardrail_result.reason,
                "message": "Outreach blocked by deterministic safety guardrail.",
                "guardrail_result": guardrail_result.to_dict(),
            }

        # ── Permitted Outreach Execution ──────────────────────────────────────
        dispatched_message = {
            "status": "delivered",
            "is_allowed": True,
            "customer_id": customer_id,
            "channel": channel,
            "content": content,
            "delivery_timestamp": datetime.datetime.now(IST_TIMEZONE).isoformat(),
            "guardrail_note": guardrail_result.reason,
        }

        # Log successful contact attempt
        tx_id = transaction_id or ctx.get("transaction_id", "unknown")
        attempts_count = int(ctx.get("contact_attempts_so_far", 0)) + 1
        self.log_action(
            transaction_id=tx_id,
            action="contact_attempted",
            reasoning=(
                f"Customer outreach dispatched via {channel.upper()} (Attempt #{attempts_count}). "
                f"Content preview: '{content[:60]}...'"
            ),
            actor="agent",
            current_time=current_time,
        )

        logger.info(f"[tool:send_message:DELIVERED] {dispatched_message}")
        return dispatched_message

    # ── Tool 5: escalate_to_human (Guarded) ────────────────────────────────────

    def escalate_to_human(
        self,
        transaction_id: str,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
        current_time: Optional[datetime.datetime] = None,
    ) -> Dict[str, Any]:
        """
        Tool: Escalates unrecoverable, fatal, or high-value cases to human support.
        Wrapped by DeterministicGuardrail.
        """
        ctx = dict(context or {})
        ctx.setdefault("transaction_id", transaction_id)
        ctx.setdefault("reason", reason)

        # ── Deterministic Guardrail Check ──────────────────────────────────────
        guardrail_result: GuardrailResult = self.guardrail.check_action(
            action="escalate_to_human",
            context=ctx,
            current_time=current_time,
        )

        if not guardrail_result.is_allowed:
            self.log_action(
                transaction_id=transaction_id,
                action="guardrail_blocked",
                reasoning=guardrail_result.format_audit_note(),
                actor="guardrail",
                current_time=current_time,
            )
            return {
                "status": "blocked",
                "is_allowed": False,
                "rule_violated": guardrail_result.rule_violated.value if guardrail_result.rule_violated else "UNKNOWN",
                "reason": guardrail_result.reason,
            }

        # ── Permitted Escalation Execution ────────────────────────────────────
        ticket_id = f"ESC_{transaction_id}_{datetime.datetime.now().strftime('%H%M%S')}"
        escalation_payload = {
            "status": "escalated",
            "is_allowed": True,
            "ticket_id": ticket_id,
            "transaction_id": transaction_id,
            "reason": reason,
            "queue": "Customer Operations & Fraud Team",
            "timestamp": datetime.datetime.now(IST_TIMEZONE).isoformat(),
        }

        self.log_action(
            transaction_id=transaction_id,
            action="flagged",
            reasoning=f"Escalated to human operations: {reason} (Ticket: {ticket_id})",
            actor="agent",
            current_time=current_time,
        )

        logger.info(f"[tool:escalate_to_human] {escalation_payload}")
        return escalation_payload

    # ── Tool 6: log_action ─────────────────────────────────────────────────────

    def log_action(
        self,
        transaction_id: str,
        action: str,
        reasoning: str,
        actor: str = "agent",
        current_time: Optional[datetime.datetime] = None,
    ) -> Dict[str, Any]:
        """
        Tool: Creates an immutable audit log entry.
        """
        now_str = (
            current_time.isoformat()
            if current_time
            else datetime.datetime.now(IST_TIMEZONE).isoformat()
        )
        log_entry = {
            "transaction_id": transaction_id,
            "action": action,
            "actor": actor,
            "notes": reasoning,
            "timestamp": now_str,
        }
        self.audit_history.append(log_entry)

        if self.audit_log_sink is not None:
            try:
                self.audit_log_sink(log_entry)
            except Exception as ex:
                logger.error(f"[log_action] Failed to notify audit_log_sink: {ex}")

        logger.info(f"[tool:log_action] [{actor.upper()}] {action} on {transaction_id}: {reasoning}")
        return {"status": "logged", "entry": log_entry}

    # ── Intelligent Decision Engine (LLM + Structured Heuristic Fallback) ───────

    def _decide_action_offline(
        self,
        transaction: Dict[str, Any],
        policies: List[Dict[str, Any]],
        similar_cases: List[Dict[str, Any]],
    ) -> AgentDecision:
        """
        Structured offline reasoning engine used when OpenAI API key is unavailable.
        Reasons deterministically based on policy guidelines and transaction attributes.
        """
        tx_id = transaction.get("transaction_id", "unknown")
        cust_id = transaction.get("customer_id", "unknown")
        code = str(transaction.get("failure_reason_code", "")).lower()
        amount = float(transaction.get("amount", 0) or 0)
        channel = str(transaction.get("customer_channel_pref", "whatsapp")).lower()
        status = str(transaction.get("status", "open")).lower()
        contact_attempts = int(transaction.get("contact_attempts_so_far", 0) or 0)
        item = transaction.get("description", "your purchase")

        # 1. Unrecoverable / Fatal Code
        if code in {"account_closed", "fraud_detected", "sanctioned"}:
            reasoning = (
                f"Transaction failed with permanent error '{code}'. Under Policy 06 (Unrecoverable Write-Off), "
                f"automated outreach is prohibited. Escalating to Operations team for account review."
            )
            tool_calls = [
                {
                    "tool": "escalate_to_human",
                    "arguments": {
                        "transaction_id": tx_id,
                        "reason": f"Permanent failure ({code}) on amount Rs. {amount:,.2f}.",
                    },
                }
            ]
            return AgentDecision(
                transaction_id=tx_id,
                action_type="escalate_to_human",
                reasoning=reasoning,
                policy_reference="06_unrecoverable_account_write_off",
                tool_calls=tool_calls,
            )

        # 2. Technical / Network Timeout Error
        if code in {"network_error", "bank_timeout", "connection_timeout", "gateway_error"}:
            reasoning = (
                f"Transient technical error '{code}'. Policy recommends immediate automatic backend retry. "
                f"If retry succeeds, transaction is recovered with zero customer friction."
            )
            tool_calls = [
                {
                    "tool": "simulate_retry_payment",
                    "arguments": {"transaction_id": tx_id},
                }
            ]
            return AgentDecision(
                transaction_id=tx_id,
                action_type="simulate_retry_payment",
                reasoning=reasoning,
                policy_reference="05_subscription_dunning_playbook",
                tool_calls=tool_calls,
            )

        # 3. Card Expired
        if code in {"card_expired", "expired_card"}:
            content = (
                f"Hi! Your card on file has expired for {item} (Rs. {amount:,.2f}). "
                f"Please update your card details securely here: https://pay.recoup.ai/card-update/{tx_id} "
                f"to ensure uninterrupted service."
            )
            reasoning = (
                f"Card expired for customer {cust_id}. Under Policy 02 (Card Update Reminder), "
                f"dispatching secure 1-click payment update link via {channel.upper()}."
            )
            tool_calls = [
                {
                    "tool": "send_message",
                    "arguments": {
                        "customer_id": cust_id,
                        "channel": channel,
                        "content": content,
                    },
                }
            ]
            return AgentDecision(
                transaction_id=tx_id,
                action_type="send_message",
                reasoning=reasoning,
                policy_reference="02_card_update_reminder",
                tool_calls=tool_calls,
            )

        # 4. Insufficient Funds / Low Balance
        if code in {"insufficient_funds", "low_balance"}:
            content = (
                f"Hello! We noticed a temporary payment issue for {item} (Rs. {amount:,.2f}). "
                f"You can quickly complete payment using UPI, Netbanking, or another card here: "
                f"https://pay.recoup.ai/checkout/{tx_id}"
            )
            reasoning = (
                f"Payment failed due to low balance/insufficient funds. Under Policy 01 (Insufficient Funds Recovery), "
                f"dispatching empathetic recovery message with instant alternative payment options (Attempt #{contact_attempts + 1})."
            )
            tool_calls = [
                {
                    "tool": "send_message",
                    "arguments": {
                        "customer_id": cust_id,
                        "channel": channel,
                        "content": content,
                    },
                }
            ]
            return AgentDecision(
                transaction_id=tx_id,
                action_type="send_message",
                reasoning=reasoning,
                policy_reference="01_insufficient_funds_recovery",
                tool_calls=tool_calls,
            )

        # 5. Checkout Abandonment / Other
        content = (
            f"Hi! You left {item} in your cart. "
            f"We've reserved your order! Complete your checkout seamlessly here: "
            f"https://pay.recoup.ai/cart/{tx_id}"
        )
        reasoning = (
            f"Customer dropped off during checkout for {item}. Under Policy 04 (Abandoned Checkout Outreach), "
            f"sending personalized cart continuation message via {channel.upper()}."
        )
        tool_calls = [
            {
                "tool": "send_message",
                "arguments": {
                    "customer_id": cust_id,
                    "channel": channel,
                    "content": content,
                },
            }
        ]
        return AgentDecision(
            transaction_id=tx_id,
            action_type="send_message",
            reasoning=reasoning,
            policy_reference="04_abandoned_checkout_outreach",
            tool_calls=tool_calls,
        )

    def _reason_with_llm(
        self,
        transaction: Dict[str, Any],
        policies: List[Dict[str, Any]],
        similar_cases: List[Dict[str, Any]],
    ) -> AgentDecision:
        """
        Uses OpenAI Tool Calling to reason over the transaction and decide tools to invoke.
        Falls back seamlessly to deterministic engine if OpenAI is not available.
        """
        api_key = settings.openai_api_key
        if not api_key or api_key.startswith("sk-your-") or api_key == "":
            return self._decide_action_offline(transaction, policies, similar_cases)

        try:
            if self.client is None:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)

            policy_summary = "\n\n".join(
                f"Policy [{p.get('policy_title', '')} - {p.get('section_title', '')}]:\n{p.get('content', '')}"
                for p in policies
            )
            cases_summary = "\n".join(
                f"- Case {c.get('case_id')}: Failure code '{c.get('failure_reason_code')}', tactic: {c.get('resolution_tactic')}"
                for c in similar_cases
            )

            system_prompt = (
                "You are Recoup AI's Autonomous Revenue Recovery Agent. "
                "Your objective is to inspect failed payment transactions and checkout abandonments, "
                "retrieve company policy constraints, reason about the compliant next action, and invoke "
                "the appropriate tool (e.g. simulate_retry_payment, send_message, escalate_to_human, log_action). "
                "CRITICAL: Adhere strictly to quiet hours, contact limits (max 3), and unrecoverable account freezes."
            )

            user_prompt = f"""Transaction Context:
- Transaction ID: {transaction.get('transaction_id')}
- Customer ID: {transaction.get('customer_id')}
- Failure Reason Code: {transaction.get('failure_reason_code')}
- Type: {transaction.get('type')}
- Amount: {transaction.get('currency', 'INR')} {transaction.get('amount')}
- Description: {transaction.get('description')}
- Preferred Channel: {transaction.get('customer_channel_pref')}
- Contact Attempts So Far: {transaction.get('contact_attempts_so_far', 0)}
- Current Status: {transaction.get('status')}

Relevant Company Policies:
{policy_summary}

Similar Historical Cases:
{cases_summary}

Determine the best recovery action and invoke the required tool."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=AGENT_TOOLS_SCHEMA,
                tool_choice="auto",
                temperature=0.2,
            )

            choice = response.choices[0]
            tool_calls = []
            reasoning = choice.message.content or "LLM selected recovery tool."

            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments)
                    except Exception:
                        fn_args = {}
                    tool_calls.append({"tool": fn_name, "arguments": fn_args})

            if not tool_calls:
                return self._decide_action_offline(transaction, policies, similar_cases)

            return AgentDecision(
                transaction_id=str(transaction.get("transaction_id")),
                action_type=tool_calls[0]["tool"],
                reasoning=reasoning,
                policy_reference=policies[0].get("policy_title", "Retrieved Policy") if policies else "Standard Policy",
                tool_calls=tool_calls,
            )

        except Exception as e:
            logger.warning(f"[agent:reason] OpenAI tool call failed ({e}). Using offline reasoning engine.")
            return self._decide_action_offline(transaction, policies, similar_cases)

    # ── Core Transaction Processor ─────────────────────────────────────────────

    def process_transaction(
        self,
        transaction: Union[Dict[str, Any], Any],
        current_time: Optional[datetime.datetime] = None,
    ) -> AgentExecutionResult:
        """
        Processes a single open transaction through the complete agentic pipeline:
        1. Normalizes transaction payload.
        2. Retrieves relevant policy via semantic search.
        3. Retrieves matching similar historical cases.
        4. Reasons about optimal action (LLM / intelligent fallback).
        5. Executes tools, with `send_message` and `escalate_to_human` strictly guarded
           by deterministic guardrails before execution.
        6. Logs all decisions and outputs immutable audit trail.
        """
        # 1. Normalize transaction dict
        if hasattr(transaction, "__dict__") and not isinstance(transaction, dict):
            if hasattr(transaction, "model_dump"):
                txn_data = transaction.model_dump()
            else:
                txn_data = {
                    k: v
                    for k, v in transaction.__dict__.items()
                    if not k.startswith("_")
                }
        else:
            txn_data = dict(transaction)

        tx_id = str(txn_data.get("transaction_id", "unknown"))
        cust_id = str(txn_data.get("customer_id", "unknown"))
        code = str(txn_data.get("failure_reason_code", "unknown"))
        txn_type = str(txn_data.get("type", "one_time_checkout"))

        logger.info(f"========== Processing Transaction: {tx_id} ({code}) ==========")

        # 2. Retrieve Relevant Policy
        policy_query = f"{code} {txn_type} recovery policy and contact rules"
        retrieved_policies = self.retrieve_policy(query=policy_query, k=2)

        # 3. Retrieve Similar Cases
        similar_cases = self.retrieve_similar_cases(transaction=txn_data, limit=2)

        # 4. Reason about the action
        decision = self._reason_with_llm(
            transaction=txn_data,
            policies=retrieved_policies,
            similar_cases=similar_cases,
        )

        # 5. Execute Decided Tools with Pre-Execution Guardrail Safety
        executed_records: List[ToolExecutionRecord] = []
        blocked_actions: List[Dict[str, Any]] = []
        final_status = str(txn_data.get("status", "open"))

        for tool_call in decision.tool_calls:
            tool_name = tool_call.get("tool", "")
            args = tool_call.get("arguments", {})

            if tool_name == "retrieve_policy":
                res = self.retrieve_policy(query=args.get("query", policy_query))
                executed_records.append(
                    ToolExecutionRecord(tool_name=tool_name, arguments=args, result={"results": res})
                )

            elif tool_name == "retrieve_similar_cases":
                res = self.retrieve_similar_cases(transaction_or_code=args.get("failure_reason_code", code))
                executed_records.append(
                    ToolExecutionRecord(tool_name=tool_name, arguments=args, result={"cases": res})
                )

            elif tool_name == "simulate_retry_payment":
                res = self.simulate_retry_payment(
                    transaction_id=args.get("transaction_id", tx_id),
                    context=txn_data,
                )
                if res.get("status") == "success":
                    final_status = "recovered"
                    self.log_action(
                        transaction_id=tx_id,
                        action="resolved",
                        reasoning="Payment recovered automatically via technical retry switch.",
                        actor="agent",
                        current_time=current_time,
                    )
                executed_records.append(
                    ToolExecutionRecord(tool_name=tool_name, arguments=args, result=res)
                )

            elif tool_name == "send_message":
                res = self.send_message(
                    customer_id=args.get("customer_id", cust_id),
                    channel=args.get("channel", txn_data.get("customer_channel_pref", "whatsapp")),
                    content=args.get("content", ""),
                    transaction_id=tx_id,
                    context=txn_data,
                    current_time=current_time,
                )
                is_blocked = (res.get("status") == "blocked")
                if is_blocked:
                    blocked_actions.append(res)
                    final_status = "pending_compliance_review"
                else:
                    final_status = "pending"
                    txn_data["contact_attempts_so_far"] = int(txn_data.get("contact_attempts_so_far", 0)) + 1

                executed_records.append(
                    ToolExecutionRecord(
                        tool_name=tool_name,
                        arguments=args,
                        result=res,
                        was_blocked_by_guardrail=is_blocked,
                        guardrail_rule=res.get("rule_violated"),
                        guardrail_reason=res.get("reason"),
                    )
                )

            elif tool_name == "escalate_to_human":
                res = self.escalate_to_human(
                    transaction_id=args.get("transaction_id", tx_id),
                    reason=args.get("reason", decision.reasoning),
                    context=txn_data,
                    current_time=current_time,
                )
                is_blocked = (res.get("status") == "blocked")
                if is_blocked:
                    blocked_actions.append(res)
                else:
                    final_status = "unrecoverable" if code in {"account_closed", "fraud_detected"} else "flagged"

                executed_records.append(
                    ToolExecutionRecord(
                        tool_name=tool_name,
                        arguments=args,
                        result=res,
                        was_blocked_by_guardrail=is_blocked,
                        guardrail_rule=res.get("rule_violated"),
                        guardrail_reason=res.get("reason"),
                    )
                )

            elif tool_name == "log_action":
                res = self.log_action(
                    transaction_id=args.get("transaction_id", tx_id),
                    action=args.get("action", "reviewed"),
                    reasoning=args.get("reasoning", decision.reasoning),
                    actor="agent",
                    current_time=current_time,
                )
                executed_records.append(
                    ToolExecutionRecord(tool_name=tool_name, arguments=args, result=res)
                )

        # 6. Audit Trail for this transaction
        tx_logs = [log for log in self.audit_history if log.get("transaction_id") == tx_id]

        return AgentExecutionResult(
            transaction_id=tx_id,
            customer_id=cust_id,
            status="processed",
            policy_chunks_retrieved=retrieved_policies,
            similar_cases=similar_cases,
            llm_reasoning=decision.reasoning,
            tools_executed=executed_records,
            actions_blocked=blocked_actions,
            audit_logs=tx_logs,
            final_transaction_status=final_status,
        )

    # ── Recovery Cycle Loop ────────────────────────────────────────────────────

    def run_recovery_cycle(
        self,
        transactions: Optional[List[Union[Dict[str, Any], Any]]] = None,
        current_time: Optional[datetime.datetime] = None,
    ) -> List[AgentExecutionResult]:
        """
        Executes the recovery loop over all provided open transactions:
        For each open transaction:
          - Retrieves relevant policy
          - Reasons about the right action
          - Executes tools with guardrail pre-execution verification
          - Logs outcomes
        """
        tx_list = transactions or []
        results: List[AgentExecutionResult] = []

        logger.info(f"Starting recovery cycle over {len(tx_list)} open transaction(s)...")

        for txn in tx_list:
            res = self.process_transaction(txn, current_time=current_time)
            results.append(res)

        logger.info(f"Completed recovery cycle: {len(results)} processed, {sum(len(r.actions_blocked) for r in results)} guardrail blocks.")
        return results

    async def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Async single-task invocation for API routers and background tasks.
        """
        ctx = context or {}
        if "transaction_id" in ctx or "failure_reason_code" in ctx:
            result = self.process_transaction(ctx)
            return json.dumps(result.to_dict(), indent=2)
        else:
            # General question -> retrieve policy and answer
            policies = self.retrieve_policy(task, k=2)
            if policies:
                return f"Top Policy: {policies[0]['policy_title']}\n{policies[0]['content']}"
            return f"Processed task: {task}"
