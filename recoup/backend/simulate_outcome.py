"""
simulate_outcome.py
-------------------
Outcome simulation engine for Recoup AI revenue recovery actions.

Simulates whether an attempted recovery action (e.g., technical retry, WhatsApp/SMS/Email
outreach, card update reminder) succeeds or fails based on realistic empirical recovery
probabilities calibrated to payment failure categories.

Empirical Recovery Probabilities:
- recoverable_technical      : ~85% base probability (automated retry, network switch, gateway routing)
- recoverable_wait           : ~70% base probability (funds deposited, bank server restored, salary cycle)
- recoverable_action_needed  : ~40% base probability (customer re-enters OTP, updates card, switches payment)
- unrecoverable              : 0% probability (permanently closed bank accounts, confirmed fraud)

Safety & Guardrail Integration:
- If an outreach action was blocked by a safety guardrail (e.g. quiet hours, opted-out, max attempts),
  recovery success is strictly 0.0% because the message never reached the customer.
"""

from __future__ import annotations

import datetime
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Union

from app.agent.diagnose import RecoveryCategory


# ── Base Probabilities Config ──────────────────────────────────────────────────

BASE_RECOVERY_PROBABILITIES: Dict[str, float] = {
    RecoveryCategory.RECOVERABLE_TECHNICAL.value: 0.85,
    RecoveryCategory.RECOVERABLE_WAIT.value: 0.70,
    RecoveryCategory.RECOVERABLE_ACTION_NEEDED.value: 0.40,
    RecoveryCategory.UNRECOVERABLE.value: 0.00,
}

# Channel Effectiveness Multipliers
CHANNEL_ENGAGEMENT_MULTIPLIERS: Dict[str, float] = {
    "whatsapp": 1.08,  # +8% higher engagement for interactive WhatsApp checkout links
    "sms": 0.96,       # Standard SMS CTR
    "email": 0.92,     # Standard Email open/CTR
}


# ── Data Models ────────────────────────────────────────────────────────────────

@dataclass
class SimulationOutcome:
    """
    Structured outcome of a simulated recovery attempt.
    """
    is_recovered: bool
    recovery_category: str
    action_attempted: str
    base_probability: float
    effective_probability: float
    recovery_method: str
    details: str
    amount: float
    recovered_amount: float
    transaction_id: str
    customer_id: str
    was_blocked_by_guardrail: bool = False
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now().isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "customer_id": self.customer_id,
            "is_recovered": self.is_recovered,
            "recovery_category": self.recovery_category,
            "action_attempted": self.action_attempted,
            "base_probability": round(self.base_probability, 4),
            "effective_probability": round(self.effective_probability, 4),
            "recovery_method": self.recovery_method,
            "details": self.details,
            "amount": self.amount,
            "recovered_amount": self.recovered_amount,
            "was_blocked_by_guardrail": self.was_blocked_by_guardrail,
            "timestamp": self.timestamp,
        }


# ── Simulation Engine ──────────────────────────────────────────────────────────

def calculate_effective_probability(
    category: Union[RecoveryCategory, str],
    action: str,
    channel: str = "whatsapp",
    contact_attempts: int = 0,
    is_blocked: bool = False,
) -> float:
    """
    Computes calibrated recovery probability for a given category, action, and channel.
    """
    if is_blocked:
        return 0.0

    cat_str = category.value if isinstance(category, RecoveryCategory) else str(category).lower().strip()
    base_prob = BASE_RECOVERY_PROBABILITIES.get(cat_str, 0.35)

    if base_prob == 0.0:
        return 0.0

    # Apply channel multiplier for customer outreach
    ch_key = str(channel).lower().strip()
    multiplier = CHANNEL_ENGAGEMENT_MULTIPLIERS.get(ch_key, 1.0)

    # Attempt factor: First touchpoint has highest awareness; slight decay on repeat touches
    attempt_decay = max(0.85, 1.0 - (contact_attempts * 0.05))

    effective = base_prob * multiplier * attempt_decay
    return max(0.0, min(0.98, effective))


def simulate_recovery_outcome(
    action: str,
    category: Union[RecoveryCategory, str],
    transaction: Optional[Dict[str, Any]] = None,
    was_blocked_by_guardrail: bool = False,
    random_seed: Optional[int] = None,
) -> SimulationOutcome:
    """
    Simulates recovery success or failure for a given action and diagnosis category.

    Args:
        action: Decided action/tool ('simulate_retry_payment', 'send_message', 'escalate_to_human', 'log_action')
        category: Diagnosis category (recoverable_technical, recoverable_wait, recoverable_action_needed, unrecoverable)
        transaction: Transaction metadata dictionary (id, amount, channel, contact_attempts, etc.)
        was_blocked_by_guardrail: True if guardrail rejected the proposed action
        random_seed: Optional seed for 100% deterministic test reproducibility

    Returns:
        SimulationOutcome with boolean is_recovered and recovery telemetry.
    """
    txn = transaction or {}
    tx_id = str(txn.get("transaction_id", "unknown"))
    cust_id = str(txn.get("customer_id", "unknown"))
    amount = float(txn.get("amount", 0.0) or 0.0)
    channel = str(txn.get("customer_channel_pref", "whatsapp")).lower()
    contact_attempts = int(txn.get("contact_attempts_so_far", 0) or 0)
    code = str(txn.get("failure_reason_code", "")).lower()

    cat_str = category.value if isinstance(category, RecoveryCategory) else str(category).lower().strip()
    base_prob = BASE_RECOVERY_PROBABILITIES.get(cat_str, 0.0)

    rng = random.Random(random_seed) if random_seed is not None else random.Random()

    # Case 1: Action Blocked by Guardrails
    if was_blocked_by_guardrail:
        return SimulationOutcome(
            is_recovered=False,
            recovery_category=cat_str,
            action_attempted=action,
            base_probability=base_prob,
            effective_probability=0.0,
            recovery_method="Blocked by Safety Guardrail",
            details="Action was blocked by safety guardrails before execution. Zero customer contact made.",
            amount=amount,
            recovered_amount=0.0,
            transaction_id=tx_id,
            customer_id=cust_id,
            was_blocked_by_guardrail=True,
        )

    # Case 2: Unrecoverable / Fatal Error
    if cat_str == RecoveryCategory.UNRECOVERABLE.value or code in {"account_closed", "fraud_detected", "sanctioned"}:
        return SimulationOutcome(
            is_recovered=False,
            recovery_category=cat_str,
            action_attempted=action,
            base_probability=0.0,
            effective_probability=0.0,
            recovery_method="Human Operations Escalation / Write-Off",
            details="Account is permanently closed or fraudulent. Queued for operations manual review and tax write-off.",
            amount=amount,
            recovered_amount=0.0,
            transaction_id=tx_id,
            customer_id=cust_id,
            was_blocked_by_guardrail=False,
        )

    # Case 3: Action is Escalate to Human (Not an automated recovery action)
    if action in {"escalate_to_human", "escalate"}:
        return SimulationOutcome(
            is_recovered=False,
            recovery_category=cat_str,
            action_attempted=action,
            base_probability=base_prob,
            effective_probability=0.0,
            recovery_method="Customer Support Escalation Queue",
            details="Escalated to human support agents for manual concierge outreach.",
            amount=amount,
            recovered_amount=0.0,
            transaction_id=tx_id,
            customer_id=cust_id,
            was_blocked_by_guardrail=False,
        )

    # Case 4: Recoverable Action (simulate_retry_payment or send_message)
    effective_prob = calculate_effective_probability(
        category=cat_str,
        action=action,
        channel=channel,
        contact_attempts=contact_attempts,
        is_blocked=False,
    )

    roll = rng.random()
    is_recovered = roll < effective_prob

    if is_recovered:
        if action in {"simulate_retry_payment", "retry_payment"}:
            method = "Automated Gateway Retry (Secondary Route)"
            details = f"Payment switch retry succeeded on {code}. Gateway authorization captured INR {amount:,.2f}."
        elif cat_str == RecoveryCategory.RECOVERABLE_WAIT.value:
            method = f"Alternative Payment Link via {channel.upper()}"
            details = f"Customer replenished balance and completed payment via instant UPI link ({channel.title()})."
        elif "card" in code or cat_str == RecoveryCategory.RECOVERABLE_ACTION_NEEDED.value:
            method = f"Interactive Card Update / Checkout via {channel.upper()}"
            details = f"Customer completed authentication / card update via {channel.title()} 1-click portal."
        else:
            method = f"Concierge Recovery Link via {channel.upper()}"
            details = f"Shopper returned to saved cart and completed payment of INR {amount:,.2f}."

        recovered_amt = amount
    else:
        method = f"Pending Follow-Up ({action})"
        details = f"Simulated outreach / retry did not convert on attempt #{contact_attempts + 1} (Roll: {roll:.2f} >= Prob: {effective_prob:.2f})."
        recovered_amt = 0.0

    return SimulationOutcome(
        is_recovered=is_recovered,
        recovery_category=cat_str,
        action_attempted=action,
        base_probability=base_prob,
        effective_probability=effective_prob,
        recovery_method=method,
        details=details,
        amount=amount,
        recovered_amount=recovered_amt,
        transaction_id=tx_id,
        customer_id=cust_id,
        was_blocked_by_guardrail=False,
    )


# Convenience Alias
simulate_outcome = simulate_recovery_outcome


# ── Standalone CLI Demo ────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 80)
    print("  RECOUP AI RECOVERY OUTCOME SIMULATOR")
    print("=" * 80)
    print("  Empirical Base Probabilities:")
    for cat, prob in BASE_RECOVERY_PROBABILITIES.items():
        print(f"    - {cat:28s}: {prob * 100:.0f}%")
    print("=" * 80 + "\n")

    test_scenarios = [
        ("simulate_retry_payment", "recoverable_technical", {"transaction_id": "txn_t1", "amount": 5840.0, "failure_reason_code": "network_error"}),
        ("send_message", "recoverable_wait", {"transaction_id": "txn_w1", "amount": 2499.0, "failure_reason_code": "insufficient_funds", "customer_channel_pref": "whatsapp"}),
        ("send_message", "recoverable_action_needed", {"transaction_id": "txn_a1", "amount": 4999.0, "failure_reason_code": "card_expired", "customer_channel_pref": "email"}),
        ("escalate_to_human", "unrecoverable", {"transaction_id": "txn_u1", "amount": 12500.0, "failure_reason_code": "account_closed"}),
        ("send_message", "recoverable_wait", {"transaction_id": "txn_g1", "amount": 1899.0, "failure_reason_code": "insufficient_funds"}, True),
    ]

    for item in test_scenarios:
        action = item[0]
        category = item[1]
        txn = item[2]
        is_blocked = item[3] if len(item) > 3 else False

        res = simulate_recovery_outcome(
            action=action,
            category=category,
            transaction=txn,
            was_blocked_by_guardrail=is_blocked,
            random_seed=42,
        )
        print(f"Transaction ID : {res.transaction_id}")
        print(f"Category       : {res.recovery_category}")
        print(f"Action         : {res.action_attempted}")
        print(f"Probability    : {res.effective_probability * 100:.1f}%")
        print(f"Outcome        : {'[RECOVERED]' if res.is_recovered else '[FAILED / UNRECOVERED]'}")
        print(f"Method         : {res.recovery_method}")
        print(f"Details        : {res.details}")
        print("-" * 80)


if __name__ == "__main__":
    main()
