"""
guardrails/guardrail.py
-----------------------
Policy enforcement and safety checks before LLM actions are executed.

TODO: Implement rule-based and/or LLM-based guardrails.
      Examples: PII redaction, spend-limit checks, action allow-lists.
"""


class GuardrailViolation(Exception):
    """Raised when an action fails a guardrail check."""

    def __init__(self, rule: str, detail: str = "") -> None:
        self.rule = rule
        self.detail = detail
        super().__init__(f"Guardrail '{rule}' violated: {detail}")


class Guardrail:
    """
    Stub guardrail.  Add concrete checks as the business logic matures.

    Usage (future):
        guardrail = Guardrail()
        guardrail.check(action="retry_payment", context={"amount": 50000})
    """

    def check(self, action: str, context: dict | None = None) -> None:
        """
        Validate *action* against configured policies.
        Raises GuardrailViolation if the action is not permitted.
        Not yet implemented — passes all actions by default.
        """
        # TODO: Implement policy checks (e.g., max retry amount, PII masking)
        pass
