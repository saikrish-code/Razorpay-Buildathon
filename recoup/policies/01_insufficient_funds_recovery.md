# Insufficient Funds Recovery Policy

## Scope & Applicability
Applies to all payment failures flagged with failure reason code `insufficient_funds` across one-time checkouts and subscription billing.

## Contact Limits & Timing Windows
- **Maximum Outreach Limit**: Exactly 3 recovery attempts over a 7-day rolling cycle.
- **Touchpoint 1 (Immediate)**: Send automated recovery notification within 15–30 minutes of failure, capturing high customer awareness.
- **Touchpoint 2 (Follow-up)**: Trigger morning notification on Day 3 between 09:30 AM and 11:00 AM IST (aligning with banking deposit cycles).
- **Touchpoint 3 (Final Notice)**: Send final grace-period warning on Day 7 at 10:00 AM IST before pausing service.

## Preferred Channels & Routing
- Primary: WhatsApp Interactive Message with instant UPI/Netbanking payment link.
- Secondary: SMS fallback if WhatsApp delivery receipt fails within 5 minutes.

## Tone & Communication Guidance
- Tone must be empathetic, discreet, and solution-oriented.
- Strictly avoid accusatory phrasing, overdraft mentions, or urgent debt-collection language.
- Clearly present alternative payment methods (e.g., UPI, alternate debit/credit card, Netbanking) via secure Razorpay checkout links.
