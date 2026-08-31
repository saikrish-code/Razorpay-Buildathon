# Unrecoverable Account Write-off Policy

## Scope & Classification
Applies immediately to transactions failing with fatal error codes including `account_closed`, invalid account numbers, sanctioned entities, or confirmed fraud.

## Operational Rules & Outreach Prohibition
- **Strict Outreach Freeze**: Zero automated contact attempts are permitted. All automated retries, SMS, and WhatsApp triggers must be blocked instantly.
- **Status Transition**: Automatically mark transaction status as `unrecoverable` and set contact attempts to 0.
- **Audit Logging**: Write an immutable audit log entry documenting permanent failure code, timestamp, and automated workflow termination.

## Escalation & Financial Write-Off
- For transaction amounts >= Rs. 10,000, automatically route ticket to the Customer Operations team for manual account review.
- For standard transaction amounts (< Rs. 10,000), queue record for monthly financial write-off and tax reconciliation after 30 days of inactivity.

## Tone & Protocol
- Internal handling must be strictly objective, compliance-focused, and auditable.
- Any direct communication must originate from human support agents handling account closure inquiries.
