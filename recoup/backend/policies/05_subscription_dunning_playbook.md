# Subscription Dunning Playbook

## Scope & Grace Period Framework
Defines the multi-stage dunning lifecycle for recurring subscription billing failures (`subscription_renewal`). Enforces a 14-day soft grace period where account features remain active.

## Retry Schedule & Communication Cadence
- **Smart Retries**: Automatic background transaction retries on Day 1, Day 3, Day 7, and Day 14 (timed with bank batch processing hours).
- **Communication Schedule (Max 3 touches)**:
  - **Day 1**: Gentle billing notification explaining failure reason and offering 1-click retry link.
  - **Day 6**: Mid-grace reminder summarizing current account status and upcoming downgrade date.
  - **Day 13**: Final warning notice 24 hours before account transition to restricted/free tier.

## Channels & Escalation
- Primary: Email with detailed billing invoice and payment portal link.
- Secondary: In-app banner and WhatsApp notification for active users.

## Final Action & Tone Guidance
- At Day 14 expiry, gracefully downgrade account to Free Tier or pause subscription without deleting user data.
- Tone should remain professional, transparent, and value-focused, emphasizing continuous subscription benefits.
