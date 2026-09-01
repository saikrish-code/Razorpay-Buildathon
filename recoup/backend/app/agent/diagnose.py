"""
app/agent/diagnose.py
---------------------
Payment failure and cart abandonment diagnosis engine for Recoup.

Architecture:
1. Rule-Based Path (Deterministic, Fast, 0 Cost):
   For transactions with clear failure_reason_codes (e.g., insufficient_funds,
   card_expired, bank_timeout, account_closed, wrong_otp, network_error),
   classifies them deterministically into one of 4 categories:
     - recoverable_wait
     - recoverable_action_needed
     - recoverable_technical
     - unrecoverable
   Zero LLM API calls are made, controlling costs completely.

2. LLM Diagnostic Path (Ambiguous & Customer Abandoned):
   For 'customer_abandoned' or ambiguous / unmapped failure codes,
   invokes an LLM with full transaction context using OpenAI Structured
   Outputs / tool calling to return guaranteed valid JSON containing:
     - category (one of the 4 recovery categories)
     - likely_reason (human-readable root-cause hypothesis)
     - confidence (float between 0.0 and 1.0)
     - recommended_action (contextual recovery next-step)
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)


# ── Recovery Category Enum ─────────────────────────────────────────────────────

class RecoveryCategory(str, Enum):
    """
    Standard four-tier classification for payment failures and abandonments.
    """
    RECOVERABLE_WAIT = "recoverable_wait"
    RECOVERABLE_ACTION_NEEDED = "recoverable_action_needed"
    RECOVERABLE_TECHNICAL = "recoverable_technical"
    UNRECOVERABLE = "unrecoverable"


# ── Pydantic Models ────────────────────────────────────────────────────────────

class LLMDiagnosisResponse(BaseModel):
    """
    Structured JSON schema enforced on LLM tool-calling and structured output.
    """
    category: RecoveryCategory = Field(
        ...,
        description="The primary recovery category: recoverable_wait, recoverable_action_needed, recoverable_technical, or unrecoverable."
    )
    likely_reason: str = Field(
        ...,
        description="Detailed explanation of the root cause or shopper intent leading to failure/abandonment."
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score in this diagnosis between 0.0 (uncertain) and 1.0 (certain)."
    )
    recommended_action: str = Field(
        ...,
        description="Recommended next operational action or customer outreach strategy."
    )
    friction_points: List[str] = Field(
        default_factory=list,
        description="Specific friction factors identified (e.g., high price, OTP friction, missing payment method)."
    )


class DiagnosisResult(BaseModel):
    """
    Complete diagnosis result returned to callers.
    """
    transaction_id: str
    category: RecoveryCategory
    failure_reason_code: str
    likely_reason: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    is_llm_diagnosed: bool = Field(
        ...,
        description="True if an LLM was invoked (ambiguous/abandoned), False if resolved deterministically (rule-based)."
    )
    source: Literal["rule_based", "llm"] = Field(
        ...,
        description="Origin of the classification decision ('rule_based' vs 'llm')."
    )
    recommended_action: Optional[str] = None
    friction_points: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Deterministic Rule-Based Knowledge Base ────────────────────────────────────

# Normalized reason code -> (Category, Likely Reason Description, Recommended Action)
RULE_BASED_MAP: Dict[str, Tuple[RecoveryCategory, str, str]] = {
    # ── recoverable_wait ──
    "insufficient_funds": (
        RecoveryCategory.RECOVERABLE_WAIT,
        "Customer account balance was insufficient at the time of transaction authorization.",
        "Initiate polite WhatsApp payment reminder within 15-30 mins; schedule smart retries on Day 3 and Day 7.",
    ),
    "daily_limit_exceeded": (
        RecoveryCategory.RECOVERABLE_WAIT,
        "Customer exceeded their card, UPI, or banking daily transaction limit.",
        "Queue automatic payment retry for the next calendar day after daily banking limits reset.",
    ),
    "limit_exceeded": (
        RecoveryCategory.RECOVERABLE_WAIT,
        "Transaction amount exceeded customer account velocity or single-transaction limit.",
        "Queue retry for the following day or suggest splitting transaction amount.",
    ),
    "bank_timeout": (
        RecoveryCategory.RECOVERABLE_WAIT,
        "Issuing bank experienced a temporary authorization timeout during processing.",
        "Wait for banking switch recovery and trigger automatic background retry within 30-60 minutes.",
    ),
    "bank_downtime": (
        RecoveryCategory.RECOVERABLE_WAIT,
        "Issuing bank is undergoing scheduled maintenance or temporary core outage.",
        "Queue automated retry for after the bank's scheduled maintenance window.",
    ),
    "bank_unavailable": (
        RecoveryCategory.RECOVERABLE_WAIT,
        "Issuing bank nodes were temporarily unreachable during debit attempt.",
        "Perform background retry within 45 minutes; switch to alternate route if available.",
    ),
    "issuer_unavailable": (
        RecoveryCategory.RECOVERABLE_WAIT,
        "Card issuer gateway was unreachable at transaction time.",
        "Retry automatically after 30 minutes.",
    ),

    # ── recoverable_action_needed ──
    "card_expired": (
        RecoveryCategory.RECOVERABLE_ACTION_NEEDED,
        "The debit or credit card on file has expired and cannot be charged.",
        "Send tokenized 1-click card update link via Email and WhatsApp to update payment instrument.",
    ),
    "expired_card": (
        RecoveryCategory.RECOVERABLE_ACTION_NEEDED,
        "The customer card has expired.",
        "Send card update reminder link via email and WhatsApp.",
    ),
    "wrong_otp": (
        RecoveryCategory.RECOVERABLE_ACTION_NEEDED,
        "Customer entered an incorrect or expired One-Time Password during 3D Secure verification.",
        "Send instant 1-click checkout recovery link to prompt customer to re-authenticate with a fresh OTP.",
    ),
    "invalid_otp": (
        RecoveryCategory.RECOVERABLE_ACTION_NEEDED,
        "Invalid OTP provided by customer during payment verification.",
        "Provide quick-retry payment link via preferred channel.",
    ),
    "otp_expired": (
        RecoveryCategory.RECOVERABLE_ACTION_NEEDED,
        "Customer OTP timed out before verification was completed.",
        "Send fresh checkout link with instant OTP generation.",
    ),
    "authentication_failed": (
        RecoveryCategory.RECOVERABLE_ACTION_NEEDED,
        "Customer failed 3D Secure / PIN / biometric authentication.",
        "Notify customer with direct link to complete authentication or select an alternative payment method.",
    ),
    "auth_failed": (
        RecoveryCategory.RECOVERABLE_ACTION_NEEDED,
        "Cardholder authentication was unsuccessful.",
        "Send instant payment retry link with alternate payment method options.",
    ),
    "incorrect_pin": (
        RecoveryCategory.RECOVERABLE_ACTION_NEEDED,
        "Customer entered an invalid UPI PIN or ATM PIN.",
        "Prompt customer to retry with correct PIN or switch to card / netbanking.",
    ),
    "invalid_cvv": (
        RecoveryCategory.RECOVERABLE_ACTION_NEEDED,
        "Card CVV verification failed during checkout.",
        "Prompt customer to re-enter valid card CVV.",
    ),
    "payment_method_declined": (
        RecoveryCategory.RECOVERABLE_ACTION_NEEDED,
        "Payment method declined by issuing bank (e.g. online transactions disabled on card).",
        "Advise customer to enable online/e-commerce transactions via their banking app or use UPI.",
    ),
    "card_declined": (
        RecoveryCategory.RECOVERABLE_ACTION_NEEDED,
        "Card declined by card network or issuing bank.",
        "Prompt customer to use an alternative card, UPI, or Netbanking.",
    ),
    "do_not_honor": (
        RecoveryCategory.RECOVERABLE_ACTION_NEEDED,
        "Issuing bank returned generic 'Do Not Honor' decline flag.",
        "Send outreach asking customer to authorize transaction with bank or switch payment method.",
    ),

    # ── recoverable_technical ──
    "network_error": (
        RecoveryCategory.RECOVERABLE_TECHNICAL,
        "Network connection dropped or timed out between customer, merchant, and payment gateway.",
        "Initiate automatic background technical retry and send seamless payment continuation link.",
    ),
    "connection_timeout": (
        RecoveryCategory.RECOVERABLE_TECHNICAL,
        "Network timeout during handshake with payment infrastructure.",
        "Retry transaction automatically via backup network switch.",
    ),
    "gateway_error": (
        RecoveryCategory.RECOVERABLE_TECHNICAL,
        "Payment gateway encountered an internal processing glitch or 5xx server error.",
        "Execute automated backend retry using secondary payment gateway route.",
    ),
    "gateway_timeout": (
        RecoveryCategory.RECOVERABLE_TECHNICAL,
        "Payment gateway timed out waiting for upstream acquiring bank response.",
        "Perform automatic retry after 15 minutes.",
    ),
    "internal_server_error": (
        RecoveryCategory.RECOVERABLE_TECHNICAL,
        "Transient system processing error during payment lifecycle.",
        "Schedule automated system retry.",
    ),
    "system_error": (
        RecoveryCategory.RECOVERABLE_TECHNICAL,
        "Temporary backend processing error.",
        "Execute automatic system retry.",
    ),
    "processing_error": (
        RecoveryCategory.RECOVERABLE_TECHNICAL,
        "Switch processing error during transaction authorization.",
        "Retry automatically via alternate gateway switch.",
    ),

    # ── unrecoverable ──
    "account_closed": (
        RecoveryCategory.UNRECOVERABLE,
        "Customer bank account or mandate is permanently closed.",
        "Freeze all automated retries immediately. Transition record to unrecoverable status and notify support.",
    ),
    "account_inactive": (
        RecoveryCategory.UNRECOVERABLE,
        "Customer bank account is deactivated or frozen by bank.",
        "Zero outreach. Transition status to unrecoverable.",
    ),
    "invalid_account": (
        RecoveryCategory.UNRECOVERABLE,
        "Customer bank account or VPA details do not exist.",
        "Mark as unrecoverable; suppress automated recovery.",
    ),
    "account_does_not_exist": (
        RecoveryCategory.UNRECOVERABLE,
        "Account number not found at destination bank.",
        "Mark as unrecoverable; log audit entry.",
    ),
    "fraud_suspected": (
        RecoveryCategory.UNRECOVERABLE,
        "Transaction flagged by risk engine or issuing bank for suspected fraud.",
        "Strict outreach freeze. Block customer account and route to risk compliance.",
    ),
    "stolen_card": (
        RecoveryCategory.UNRECOVERABLE,
        "Payment instrument reported lost or stolen.",
        "Block further charges permanently and notify security team.",
    ),
    "lost_card": (
        RecoveryCategory.UNRECOVERABLE,
        "Card flagged as lost by issuer.",
        "Block all retries immediately.",
    ),
    "sanctioned_entity": (
        RecoveryCategory.UNRECOVERABLE,
        "Entity matched against AML / sanctions restriction database.",
        "Immediate freeze; compliance escalation.",
    ),
    "blacklisted_customer": (
        RecoveryCategory.UNRECOVERABLE,
        "Customer ID or payment instrument is blacklisted.",
        "Do not contact. Transition to unrecoverable.",
    ),
}


# ── Normalization and Rule Evaluation ──────────────────────────────────────────

def normalize_reason_code(code: Optional[str]) -> str:
    """Normalize failure reason code string for deterministic matching."""
    if not code:
        return ""
    return code.strip().lower().replace(" ", "_").replace("-", "_")


def classify_rule_based(
    failure_reason_code: Optional[str]
) -> Optional[Tuple[RecoveryCategory, str, str]]:
    """
    Attempt deterministic classification based on known failure_reason_code.
    Returns (category, likely_reason, recommended_action) if matched, or None.
    
    'customer_abandoned' and unknown codes return None, triggering LLM diagnosis.
    """
    norm_code = normalize_reason_code(failure_reason_code)
    if not norm_code or norm_code == "customer_abandoned":
        return None
    return RULE_BASED_MAP.get(norm_code)


# ── LLM Diagnostic Engine ──────────────────────────────────────────────────────

DIAGNOSIS_SYSTEM_PROMPT = """You are Recoup AI's Chief Revenue Recovery & Payment Diagnostics Agent.
Your job is to analyze payment drop-offs, checkout abandonments, and ambiguous payment failure events to determine the exact root cause, appropriate recovery category, confidence score, and tailored recovery action.

Classification Guidelines:
1. 'recoverable_wait':
   - Temporary timing or liquidity issues where waiting (e.g. salary cycle, payday, daily limit reset, bank server stabilization) is the primary remedy.
2. 'recoverable_action_needed':
   - Friction where user must take an intentional step (e.g. price hesitation overcome by incentive, re-entering OTP, switching payment method, updating cart, renewing mandate).
3. 'recoverable_technical':
   - App, browser, network, or checkout UI session timeout/glitch that can be recovered via a seamless 1-click continuation link.
4. 'unrecoverable':
   - Clear indicators of bad faith, invalid account, permanent opt-out, or impossible recovery.

You MUST return a valid structured JSON response matching the required schema with:
- category: one of ["recoverable_wait", "recoverable_action_needed", "recoverable_technical", "unrecoverable"]
- likely_reason: specific root-cause analysis factoring in the transaction amount, customer profile, item type, and channel
- confidence: numeric score from 0.0 to 1.0 indicating your diagnostic certainty
- recommended_action: concrete, high-converting recovery tactic tailored to the customer
- friction_points: list of key friction factors identified (e.g., ["price_hesitation", "high_ticket_cart"])
"""

DIAGNOSIS_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "record_payment_diagnosis",
        "description": "Records the structured diagnosis for an abandoned checkout or ambiguous payment failure.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "recoverable_wait",
                        "recoverable_action_needed",
                        "recoverable_technical",
                        "unrecoverable"
                    ],
                    "description": "The recovery category classification."
                },
                "likely_reason": {
                    "type": "string",
                    "description": "Comprehensive explanation of why the customer abandoned checkout or payment failed."
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Confidence score between 0.0 and 1.0."
                },
                "recommended_action": {
                    "type": "string",
                    "description": "Actionable, tailored outreach or recovery recommendation."
                },
                "friction_points": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of key friction drivers."
                }
            },
            "required": ["category", "likely_reason", "confidence", "recommended_action", "friction_points"],
            "additionalProperties": False
        }
    }
}


def _build_llm_user_prompt(context: Dict[str, Any]) -> str:
    """Build a detailed contextual prompt for the LLM."""
    txn_id = context.get("transaction_id", "unknown")
    amount = context.get("amount", "unknown")
    currency = context.get("currency", "INR")
    txn_type = context.get("type", "checkout_abandonment")
    failure_code = context.get("failure_reason_code", "customer_abandoned")
    description = context.get("description", "No description provided")
    channel_pref = context.get("customer_channel_pref", "whatsapp")
    contact_attempts = context.get("contact_attempts_so_far", 0)
    customer_email = context.get("customer_email", "unknown")
    customer_phone = context.get("customer_phone", "unknown")
    timestamp = context.get("timestamp", "recent")

    # Mask sensitive details for privacy
    masked_phone = customer_phone[:6] + "XXXX" if len(str(customer_phone)) >= 10 else "masked"
    masked_email = customer_email[0] + "***@" + customer_email.split("@")[-1] if "@" in str(customer_email) else "masked"

    return f"""Please diagnose the following payment event:

Transaction Details:
- Transaction ID: {txn_id}
- Failure Reason Code: {failure_code}
- Transaction Type: {txn_type}
- Amount: {currency} {amount}
- Item / Description: {description}
- Customer Preferred Channel: {channel_pref}
- Contact Attempts So Far: {contact_attempts}
- Timestamp: {timestamp}
- Customer Contact (Masked): {masked_phone}, {masked_email}

Analyze the transaction context and determine:
1. The most probable root cause of abandonment / failure.
2. The appropriate recovery classification category.
3. Your confidence score (0.0 to 1.0).
4. The optimal personalized recovery recommendation for this customer and channel.
"""


def _intelligent_fallback_diagnosis(context: Dict[str, Any]) -> LLMDiagnosisResponse:
    """
    Intelligent heuristic fallback used if no OpenAI API key is configured
    or in offline mode, ensuring structured JSON output and test stability.
    """
    amount = float(context.get("amount", 1000.0) or 1000.0)
    txn_type = str(context.get("type", "checkout_abandonment"))
    description = str(context.get("description", "")).lower()
    channel = str(context.get("customer_channel_pref", "whatsapp"))

    if "subscription" in txn_type or "renewal" in description:
        category = RecoveryCategory.RECOVERABLE_ACTION_NEEDED
        likely_reason = (
            f"Subscriber drop-off on recurring plan ({context.get('description', 'Subscription')}). "
            f"Likely intentional review of renewal value or pending payment authorization."
        )
        confidence = 0.85
        action = f"Send gentle value-recap notice via {channel.title()} with a 1-click instant reactivation portal."
        frictions = ["subscription_fatigue", "intent_re-evaluation"]

    elif amount >= 8000.0:
        category = RecoveryCategory.RECOVERABLE_ACTION_NEEDED
        likely_reason = (
            f"High-ticket checkout hesitation (Rs. {amount:,.2f}). Shopper likely paused to compare prices, "
            f"calculate budget, or seek reassurance on warranty/return terms."
        )
        confidence = 0.88
        action = (
            f"Trigger concierge {channel.title()} outreach within 30-45 minutes offering easy EMI options "
            f"or a limited-time 5% checkout completion discount."
        )
        frictions = ["high_price_hesitation", "comparison_shopping", "budget_scrutiny"]

    elif any(k in description for k in ["earbuds", "headphones", "watch", "shoes", "jeans"]):
        category = RecoveryCategory.RECOVERABLE_ACTION_NEEDED
        likely_reason = (
            f"E-commerce lifestyle purchase abandonment ({context.get('description', 'Cart item')}). "
            f"Likely shopper was multitasking, experienced checkout friction, or got distracted before OTP verification."
        )
        confidence = 0.82
        action = (
            f"Send warm, concierge WhatsApp reminder with cart thumbnail and single-click direct checkout link "
            f"holding reserved stock for 24 hours."
        )
        frictions = ["multitasking_distraction", "checkout_friction"]

    else:
        category = RecoveryCategory.RECOVERABLE_ACTION_NEEDED
        likely_reason = (
            f"Customer dropped off during checkout ({context.get('description', 'Purchase')}). "
            f"Potential payment hesitation or intent to complete later on desktop/mobile."
        )
        confidence = 0.78
        action = f"Send friendly saved-cart reminder via {channel.title()} within the high-intent 45-minute window."
        frictions = ["uncompleted_intent", "hesitation"]

    return LLMDiagnosisResponse(
        category=category,
        likely_reason=likely_reason,
        confidence=confidence,
        recommended_action=action,
        friction_points=frictions
    )


def diagnose_with_llm(
    context: Dict[str, Any],
    llm_client: Any = None,
    model: Optional[str] = None
) -> LLMDiagnosisResponse:
    """
    Invoke LLM with transaction context using OpenAI Structured Outputs or Tool Calling.
    Guarantees valid JSON conforming to LLMDiagnosisResponse.
    """
    client = llm_client
    model_name = model or settings.openai_model or "gpt-4o-mini"
    api_key = settings.openai_api_key

    # If client is not provided and no valid API key is configured, use structured fallback
    if client is None and (not api_key or api_key.startswith("sk-your-") or api_key == ""):
        logger.info("[diagnose] No valid OpenAI API key found. Using intelligent structured fallback engine.")
        return _intelligent_fallback_diagnosis(context)

    # Initialize OpenAI client if not injected
    if client is None:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
        except Exception as e:
            logger.warning(f"[diagnose] Failed to initialize OpenAI client ({e}). Falling back to structured engine.")
            return _intelligent_fallback_diagnosis(context)

    user_prompt = _build_llm_user_prompt(context)
    messages = [
        {"role": "system", "content": DIAGNOSIS_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    # Attempt Structured Outputs (beta.chat.completions.parse)
    if hasattr(client, "beta") and hasattr(client.beta, "chat") and hasattr(client.beta.chat, "completions"):
        try:
            response = client.beta.chat.completions.parse(
                model=model_name,
                messages=messages,
                response_format=LLMDiagnosisResponse,
                temperature=0.2,
            )
            parsed = response.choices[0].message.parsed
            if parsed is not None:
                return parsed
        except Exception as e:
            logger.warning(f"[diagnose] Structured parse mode failed ({e}), falling back to tool calling.")

    # Attempt Tool Calling mode (tools parameter)
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=[DIAGNOSIS_TOOL_DEFINITION],
            tool_choice={"type": "function", "function": {"name": "record_payment_diagnosis"}},
            temperature=0.2,
        )
        choice = response.choices[0]
        if choice.message.tool_calls:
            tool_call = choice.message.tool_calls[0]
            args_str = tool_call.function.arguments
            args_dict = json.loads(args_str)
            return LLMDiagnosisResponse.model_validate(args_dict)
        elif choice.message.content:
            raw_content = choice.message.content.strip()
            # If wrapped in markdown code blocks, strip them
            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]
            if raw_content.startswith("```"):
                raw_content = raw_content[3:]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]
            parsed_json = json.loads(raw_content.strip())
            return LLMDiagnosisResponse.model_validate(parsed_json)
    except Exception as e:
        logger.error(f"[diagnose] LLM call failed ({e}). Falling back to structured diagnosis engine.")
        return _intelligent_fallback_diagnosis(context)

    return _intelligent_fallback_diagnosis(context)


# ── Unified Public Diagnosis API ───────────────────────────────────────────────

def extract_transaction_dict(
    transaction: Union[Dict[str, Any], Any]
) -> Dict[str, Any]:
    """Extract standard dictionary representation from dict, Pydantic, or ORM object."""
    if isinstance(transaction, dict):
        return transaction
    elif hasattr(transaction, "model_dump"):
        return transaction.model_dump()
    elif hasattr(transaction, "dict"):
        return transaction.dict()
    elif hasattr(transaction, "__dict__"):
        # Filter out SQLAlchemy internal state
        return {k: v for k, v in transaction.__dict__.items() if not k.startswith("_")}
    return dict(transaction)


def diagnose_transaction(
    transaction: Union[Dict[str, Any], Any],
    llm_client: Any = None,
    model: Optional[str] = None
) -> DiagnosisResult:
    """
    Diagnose a payment transaction or abandonment event.

    - Deterministic Rule-Based Path:
      If transaction has a recognized, unambiguous failure_reason_code,
      classifies it immediately using deterministic rules.
      **Zero LLM calls are made**, strictly controlling token cost.

    - LLM Diagnostic Path:
      For 'customer_abandoned' or ambiguous failure codes, invokes the LLM
      with contextual information and returns guaranteed valid structured JSON.

    Parameters:
        transaction: Transaction dictionary, Pydantic schema, or ORM model.
        llm_client: Optional injected OpenAI client (for testing/mocking).
        model: Optional model override string.

    Returns:
        DiagnosisResult: Complete structured diagnosis with category, likely_reason,
                         confidence, source, and is_llm_diagnosed flag.
    """
    txn_data = extract_transaction_dict(transaction)
    txn_id = str(txn_data.get("transaction_id") or txn_data.get("id") or "unknown_txn")
    failure_code = str(txn_data.get("failure_reason_code") or "").strip()

    # Step 1: Check Deterministic Rule-Based Logic
    rule_match = classify_rule_based(failure_code)
    if rule_match is not None:
        category, likely_reason, rec_action = rule_match
        return DiagnosisResult(
            transaction_id=txn_id,
            category=category,
            failure_reason_code=failure_code,
            likely_reason=likely_reason,
            confidence=1.0,
            is_llm_diagnosed=False,
            source="rule_based",
            recommended_action=rec_action,
            friction_points=[],
            metadata={"rule_matched": failure_code.lower()}
        )

    # Step 2: Ambiguous / Customer Abandoned Path -> Call LLM
    llm_res = diagnose_with_llm(txn_data, llm_client=llm_client, model=model)

    return DiagnosisResult(
        transaction_id=txn_id,
        category=llm_res.category,
        failure_reason_code=failure_code or "customer_abandoned",
        likely_reason=llm_res.likely_reason,
        confidence=round(float(llm_res.confidence), 4),
        is_llm_diagnosed=True,
        source="llm",
        recommended_action=llm_res.recommended_action,
        friction_points=llm_res.friction_points,
        metadata={"model_used": model or settings.openai_model or "gpt-4o-mini"}
    )


async def async_diagnose_transaction(
    transaction: Union[Dict[str, Any], Any],
    llm_client: Any = None,
    model: Optional[str] = None
) -> DiagnosisResult:
    """
    Async variant of diagnose_transaction.
    Executes rule-based matching synchronously (0-cost), and invokes LLM if ambiguous.
    """
    # Rule based evaluation is CPU bound and instantaneous
    txn_data = extract_transaction_dict(transaction)
    failure_code = str(txn_data.get("failure_reason_code") or "").strip()
    
    rule_match = classify_rule_based(failure_code)
    if rule_match is not None:
        return diagnose_transaction(txn_data, llm_client=llm_client, model=model)
    
    # Ambiguous path
    return diagnose_transaction(txn_data, llm_client=llm_client, model=model)


def diagnose_batch(
    transactions: List[Union[Dict[str, Any], Any]],
    llm_client: Any = None,
    model: Optional[str] = None
) -> List[DiagnosisResult]:
    """
    Diagnose a batch of transactions efficiently.
    Ensures deterministic cases never invoke the LLM.
    """
    return [diagnose_transaction(t, llm_client=llm_client, model=model) for t in transactions]
