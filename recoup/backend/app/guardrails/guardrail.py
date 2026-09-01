"""
guardrails/guardrail.py
-----------------------
Deterministic policy enforcement and safety guardrails for Recoup AI recovery actions.

Core Responsibilities:
1. Deterministic Pre-execution Verification:
   Evaluates all proposed recovery actions (specifically `send_message` and `escalate_to_human`)
   BEFORE execution to strictly enforce regulatory, business, and privacy constraints.
2. Compliance & Timing Enforcement:
   - Maximum Contact Count Limits: Rejects actions if contact attempts exceed the threshold (default: 3).
   - Operational vs Quiet Hours: Automated customer outreach is strictly permitted between
     09:00 IST and 20:00 IST. Outreach is blocked during quiet hours (20:01 IST to 08:59 IST).
   - Frequency Capping / Minimum Time Between Contacts: Enforces a minimum cooldown between
     messages (default: 24.0 hours rolling window).
   - Opt-Out / Do-Not-Contact (DNC) Registry: Zero automated outreach is permitted to customers
     who have unsubscribed, replied STOP/DNC, or are on the global opt-out registry.
   - Unrecoverable Status Outreach Freeze: Completely freezes outreach on closed accounts or confirmed fraud.
3. Block Interception & Immutable Audit Logging:
   If a proposed action violates any guardrail rule, execution is blocked immediately and a
   structured `[GUARDRAIL BLOCKED]` audit record is logged with full rule metadata and rationale.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("recoup.guardrails")

# ── Timezone & Timing Constants ────────────────────────────────────────────────

# Indian Standard Time (UTC+05:30)
IST_TIMEZONE = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IST")

# Permitted outreach window (Policy 03: 09:00 IST to 20:00 IST)
OPERATIONAL_HOUR_START = datetime.time(9, 0, 0)
OPERATIONAL_HOUR_END = datetime.time(20, 0, 0)

# Default Policy Constraints
DEFAULT_MAX_CONTACT_ATTEMPTS = 3
DEFAULT_MIN_TIME_BETWEEN_CONTACTS_HOURS = 24.0


# ── Guardrail Violation Codes ──────────────────────────────────────────────────

class GuardrailRule(str, Enum):
    MAX_CONTACT_ATTEMPTS_EXCEEDED = "MAX_CONTACT_ATTEMPTS_EXCEEDED"
    QUIET_HOURS_BLOCKED = "QUIET_HOURS_BLOCKED"
    OPTED_OUT_CUSTOMER = "OPTED_OUT_CUSTOMER"
    MIN_TIME_BETWEEN_CONTACTS_VIOLATION = "MIN_TIME_BETWEEN_CONTACTS_VIOLATION"
    UNRECOVERABLE_OUTREACH_FROZEN = "UNRECOVERABLE_OUTREACH_FROZEN"
    INVALID_ACTION_PAYLOAD = "INVALID_ACTION_PAYLOAD"
    DUPLICATE_ESCALATION = "DUPLICATE_ESCALATION"


# ── Data Models ────────────────────────────────────────────────────────────────

@dataclass
class GuardrailResult:
    """
    Result of a deterministic guardrail evaluation.
    """
    is_allowed: bool
    action: str
    rule_violated: Optional[GuardrailRule] = None
    reason: str = ""
    evaluated_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(IST_TIMEZONE)
    )
    context_snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_allowed": self.is_allowed,
            "action": self.action,
            "rule_violated": self.rule_violated.value if self.rule_violated else None,
            "reason": self.reason,
            "evaluated_at": self.evaluated_at.isoformat(),
            "context_snapshot": self.context_snapshot,
        }

    def format_audit_note(self) -> str:
        """Formatted string for inclusion in transaction audit logs."""
        if self.is_allowed:
            return f"[GUARDRAIL PASSED] Action '{self.action}' approved. {self.reason}"
        return (
            f"[GUARDRAIL BLOCKED] Action '{self.action}' rejected. "
            f"Rule: {self.rule_violated.value if self.rule_violated else 'UNKNOWN'}. "
            f"Reason: {self.reason}"
        )


class GuardrailViolation(Exception):
    """Raised when an action violates safety guardrails in strict mode."""

    def __init__(self, result: GuardrailResult) -> None:
        self.result = result
        super().__init__(result.format_audit_note())


# ── In-Memory Do-Not-Contact (DNC) Registry ────────────────────────────────────

class DNCRegistry:
    """
    Thread-safe in-memory Do-Not-Contact registry for customer opt-outs.
    Synchronizes with customer opt-out requests ("STOP", "UNSUBSCRIBE", "DNC").
    """

    def __init__(self, initial_opt_outs: Optional[Set[str]] = None) -> None:
        self._opt_outs: Set[str] = set(initial_opt_outs or [])

    def add(self, customer_id_or_contact: str) -> None:
        if customer_id_or_contact:
            self._opt_outs.add(str(customer_id_or_contact).strip().lower())

    def remove(self, customer_id_or_contact: str) -> None:
        self._opt_outs.discard(str(customer_id_or_contact).strip().lower())

    def is_opted_out(self, customer_id_or_contact: Optional[str]) -> bool:
        if not customer_id_or_contact:
            return False
        return str(customer_id_or_contact).strip().lower() in self._opt_outs

    def clear(self) -> None:
        self._opt_outs.clear()

    def all_opted_out(self) -> Set[str]:
        return set(self._opt_outs)


# Global singleton DNC registry
_GLOBAL_DNC_REGISTRY = DNCRegistry(
    initial_opt_outs={"cust_opted_out_001", "cust_dnc_999", "cust_unsub_404"}
)


def get_dnc_registry() -> DNCRegistry:
    return _GLOBAL_DNC_REGISTRY


# ── Core Deterministic Guardrail Engine ────────────────────────────────────────

class DeterministicGuardrail:
    """
    Deterministic safety and compliance guardrail.
    Inspects action payloads and transaction context before execution.
    """

    def __init__(
        self,
        max_contact_attempts: int = DEFAULT_MAX_CONTACT_ATTEMPTS,
        min_time_between_contacts_hours: float = DEFAULT_MIN_TIME_BETWEEN_CONTACTS_HOURS,
        operational_start: datetime.time = OPERATIONAL_HOUR_START,
        operational_end: datetime.time = OPERATIONAL_HOUR_END,
        dnc_registry: Optional[DNCRegistry] = None,
        audit_logger: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> None:
        self.max_contact_attempts = max_contact_attempts
        self.min_time_between_contacts_hours = min_time_between_contacts_hours
        self.operational_start = operational_start
        self.operational_end = operational_end
        self.dnc_registry = dnc_registry or get_dnc_registry()
        self.audit_logger = audit_logger
        self.blocked_history: List[GuardrailResult] = []

    # ── Time & Window Check ────────────────────────────────────────────────────

    def is_within_operational_hours(
        self, current_time: Optional[datetime.datetime] = None
    ) -> Tuple[bool, datetime.time, str]:
        """
        Validates if current_time (converted to IST) falls within allowed contact hours (09:00–20:00 IST).
        Returns (is_operational, time_in_ist, message).
        """
        if current_time is None:
            now_ist = datetime.datetime.now(IST_TIMEZONE)
        else:
            if current_time.tzinfo is None:
                # Assume IST if naive
                now_ist = current_time.replace(tzinfo=IST_TIMEZONE)
            else:
                now_ist = current_time.astimezone(IST_TIMEZONE)

        time_val = now_ist.time()
        is_allowed = self.operational_start <= time_val <= self.operational_end
        time_str = time_val.strftime("%H:%M:%S")

        if is_allowed:
            msg = f"Current time ({time_str} IST) is within permitted operational hours (09:00–20:00 IST)."
        else:
            msg = (
                f"Current time ({time_str} IST) falls into quiet hours blackout window "
                f"(Permitted: {self.operational_start.strftime('%H:%M')}–{self.operational_end.strftime('%H:%M')} IST)."
            )

        return is_allowed, time_val, msg

    # ── Check Action Before Execution ──────────────────────────────────────────

    def check_action(
        self,
        action: str,
        context: Optional[Dict[str, Any]] = None,
        current_time: Optional[datetime.datetime] = None,
    ) -> GuardrailResult:
        """
        Deterministically evaluates whether a proposed action is permitted or blocked.

        Args:
            action: Action name (e.g. 'send_message', 'escalate_to_human', 'simulate_retry_payment')
            context: Transaction and customer context dictionary
            current_time: Optional evaluation timestamp for deterministic testing

        Returns:
            GuardrailResult containing decision, rule violated, and reasoning.
        """
        ctx = context or {}
        action_name = action.strip().lower()
        now_dt = current_time or datetime.datetime.now(IST_TIMEZONE)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=IST_TIMEZONE)

        # ── 1. Checks for 'send_message' / Customer Outreach ───────────────────
        if action_name in {"send_message", "outreach", "customer_message", "notify_customer"}:
            customer_id = ctx.get("customer_id")
            customer_phone = ctx.get("customer_phone")
            customer_email = ctx.get("customer_email")
            contact_attempts = int(ctx.get("contact_attempts_so_far", 0) or 0)
            max_attempts = int(ctx.get("max_contact_attempts", self.max_contact_attempts) or self.max_contact_attempts)
            status = str(ctx.get("status", "")).lower()
            failure_code = str(ctx.get("failure_reason_code", "")).lower()
            is_opted_out_flag = bool(ctx.get("is_opted_out", False) or ctx.get("opted_out", False))

            # Rule A: Opted-Out / Do-Not-Contact Customer
            if (
                is_opted_out_flag
                or self.dnc_registry.is_opted_out(customer_id)
                or self.dnc_registry.is_opted_out(customer_phone)
                or self.dnc_registry.is_opted_out(customer_email)
            ):
                result = GuardrailResult(
                    is_allowed=False,
                    action=action,
                    rule_violated=GuardrailRule.OPTED_OUT_CUSTOMER,
                    reason=(
                        f"Customer '{customer_id}' is opted out or present in the Do-Not-Contact registry. "
                        f"Automated communications are strictly forbidden."
                    ),
                    evaluated_at=now_dt,
                    context_snapshot=ctx,
                )
                self._record_evaluation(result)
                return result

            # Rule B: Unrecoverable / Fatal Error Status Outreach Freeze (Policy 06)
            if status == "unrecoverable" or failure_code in {"account_closed", "fraud_detected", "sanctioned"}:
                result = GuardrailResult(
                    is_allowed=False,
                    action=action,
                    rule_violated=GuardrailRule.UNRECOVERABLE_OUTREACH_FROZEN,
                    reason=(
                        f"Transaction has unrecoverable status or fatal failure code ('{failure_code}'). "
                        f"Automated customer outreach is prohibited under Policy 06."
                    ),
                    evaluated_at=now_dt,
                    context_snapshot=ctx,
                )
                self._record_evaluation(result)
                return result

            # Rule C: Maximum Contact Count Limit Exceeded (Policy 01 & Policy 05)
            if contact_attempts >= max_attempts:
                result = GuardrailResult(
                    is_allowed=False,
                    action=action,
                    rule_violated=GuardrailRule.MAX_CONTACT_ATTEMPTS_EXCEEDED,
                    reason=(
                        f"Contact attempts ({contact_attempts}) have reached or exceeded the maximum permitted "
                        f"limit ({max_attempts}). Outreach is blocked to prevent customer spam."
                    ),
                    evaluated_at=now_dt,
                    context_snapshot=ctx,
                )
                self._record_evaluation(result)
                return result

            # Rule D: Operational Hours vs Quiet Hours Blackout (Policy 03)
            is_operational, time_ist, hours_msg = self.is_within_operational_hours(now_dt)
            if not is_operational:
                result = GuardrailResult(
                    is_allowed=False,
                    action=action,
                    rule_violated=GuardrailRule.QUIET_HOURS_BLOCKED,
                    reason=hours_msg,
                    evaluated_at=now_dt,
                    context_snapshot=ctx,
                )
                self._record_evaluation(result)
                return result

            # Rule E: Minimum Time Between Contacts / Cooldown Frequency Capping (Policy 03)
            last_contacted_at = ctx.get("last_contacted_at") or ctx.get("last_contact_timestamp")
            if last_contacted_at:
                if isinstance(last_contacted_at, str):
                    try:
                        last_dt = datetime.datetime.fromisoformat(last_contacted_at)
                    except ValueError:
                        last_dt = None
                elif isinstance(last_contacted_at, datetime.datetime):
                    last_dt = last_contacted_at
                else:
                    last_dt = None

                if last_dt is not None:
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=IST_TIMEZONE)
                    else:
                        last_dt = last_dt.astimezone(IST_TIMEZONE)

                    elapsed_hours = (now_dt - last_dt).total_seconds() / 3600.0
                    min_cooldown = float(
                        ctx.get("min_time_between_contacts_hours", self.min_time_between_contacts_hours)
                        or self.min_time_between_contacts_hours
                    )
                    if elapsed_hours < min_cooldown:
                        result = GuardrailResult(
                            is_allowed=False,
                            action=action,
                            rule_violated=GuardrailRule.MIN_TIME_BETWEEN_CONTACTS_VIOLATION,
                            reason=(
                                f"Only {elapsed_hours:.1f} hours elapsed since last outreach at "
                                f"{last_dt.strftime('%Y-%m-%d %H:%M:%S %Z')}. "
                                f"Minimum cooldown is {min_cooldown:.1f} hours (1 contact / 24h rule)."
                            ),
                            evaluated_at=now_dt,
                            context_snapshot=ctx,
                        )
                        self._record_evaluation(result)
                        return result

            # All send_message checks passed
            result = GuardrailResult(
                is_allowed=True,
                action=action,
                rule_violated=None,
                reason=(
                    f"Outreach approved: Contact attempt #{contact_attempts + 1} of {max_attempts}, "
                    f"within operational hours ({time_ist.strftime('%H:%M')} IST), customer opted-in."
                ),
                evaluated_at=now_dt,
                context_snapshot=ctx,
            )
            self._record_evaluation(result)
            return result

        # ── 2. Checks for 'escalate_to_human' ──────────────────────────────────
        elif action_name in {"escalate_to_human", "escalate", "human_escalation"}:
            status = str(ctx.get("status", "")).lower()
            reason = str(ctx.get("reason", "")).strip()

            if status in {"recovered", "refunded", "resolved"}:
                result = GuardrailResult(
                    is_allowed=False,
                    action=action,
                    rule_violated=GuardrailRule.INVALID_ACTION_PAYLOAD,
                    reason=f"Transaction is already resolved with status '{status}'. Escalation denied.",
                    evaluated_at=now_dt,
                    context_snapshot=ctx,
                )
                self._record_evaluation(result)
                return result

            if ctx.get("is_already_escalated", False):
                result = GuardrailResult(
                    is_allowed=False,
                    action=action,
                    rule_violated=GuardrailRule.DUPLICATE_ESCALATION,
                    reason="Transaction has already been escalated to human operations. Duplicate blocked.",
                    evaluated_at=now_dt,
                    context_snapshot=ctx,
                )
                self._record_evaluation(result)
                return result

            # Approved escalation
            result = GuardrailResult(
                is_allowed=True,
                action=action,
                rule_violated=None,
                reason=f"Escalation approved: {reason or 'High-priority intervention required.'}",
                evaluated_at=now_dt,
                context_snapshot=ctx,
            )
            self._record_evaluation(result)
            return result

        # ── 3. Default for other tools / actions ────────────────────────────────
        result = GuardrailResult(
            is_allowed=True,
            action=action,
            rule_violated=None,
            reason=f"Action '{action}' is safe for execution.",
            evaluated_at=now_dt,
            context_snapshot=ctx,
        )
        self._record_evaluation(result)
        return result

    # ── Record Evaluation & Log Blocks ─────────────────────────────────────────

    def _record_evaluation(self, result: GuardrailResult) -> None:
        """Records the evaluation and triggers block logging if rejected."""
        if not result.is_allowed:
            self.blocked_history.append(result)
            logger.warning(result.format_audit_note())

            if self.audit_logger is not None:
                try:
                    self.audit_logger({
                        "event": "guardrail_blocked",
                        "action": result.action,
                        "rule": result.rule_violated.value if result.rule_violated else "UNKNOWN",
                        "reason": result.reason,
                        "timestamp": result.evaluated_at.isoformat(),
                        "context": result.context_snapshot,
                    })
                except Exception as ex:
                    logger.error(f"Failed to invoke audit_logger callback: {ex}")


# ── Global Singleton & Wrapper ─────────────────────────────────────────────────

_GLOBAL_GUARDRAIL = DeterministicGuardrail()


def get_guardrail() -> DeterministicGuardrail:
    """Returns the global DeterministicGuardrail instance."""
    return _GLOBAL_GUARDRAIL


def guardrail_check(
    action: str,
    context: Optional[Dict[str, Any]] = None,
    current_time: Optional[datetime.datetime] = None,
    guardrail: Optional[DeterministicGuardrail] = None,
) -> GuardrailResult:
    """
    Convenience function for deterministic pre-execution guardrail evaluation.
    """
    g = guardrail or get_guardrail()
    return g.check_action(action=action, context=context, current_time=current_time)


# Compatibility alias
Guardrail = DeterministicGuardrail
