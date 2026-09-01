"""
models/transaction.py
---------------------
Pydantic v2 schemas for Transaction request / response payloads.
These are separate from the SQLAlchemy ORM models in db/base.py.
"""

from __future__ import annotations

import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.audit_log import AuditLogRead


class TransactionBase(BaseModel):
    transaction_id: str = Field(..., description="Unique transaction ID (e.g. txn_xxx or pay_xxx)")
    razorpay_payment_id: str | None = Field(None, description="Razorpay payment ID (e.g. pay_xxx)")
    customer_id: str = Field(..., description="Customer identifier (e.g. cust_xxx)")
    type: str = Field(..., description="Failure category: one_time_checkout, subscription_renewal, checkout_abandonment")
    amount: float = Field(..., gt=0, description="Amount in INR")
    currency: str = Field("INR", max_length=8)
    event_type: str = Field("payment.failed", description="Event type string")
    failure_reason_code: str = Field(..., description="Failure reason code")
    contact_attempts_so_far: int = Field(0, description="Number of recovery outreach attempts")
    customer_channel_pref: str = Field("whatsapp", description="Preferred contact channel (whatsapp, sms, email)")
    status: str = Field("open", description="Recovery status: open, pending, recovered, unrecoverable")
    
    customer_email: EmailStr | None = None
    customer_phone: str | None = None
    description: str | None = None
    timestamp: datetime.datetime | None = None


class TransactionCreate(TransactionBase):
    """Used when creating a new transaction via POST."""
    pass


class TransactionUpdate(BaseModel):
    """Used when partially updating a transaction via PATCH."""
    status: str | None = None
    contact_attempts_so_far: int | None = None
    customer_email: EmailStr | None = None
    customer_phone: str | None = None
    description: str | None = None


class TransactionRead(TransactionBase):
    """Returned by GET endpoints — includes DB-generated fields."""
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionDetailRead(TransactionRead):
    """Returned by GET /transactions/{id} — includes complete ordered audit trail."""
    audit_logs: List[AuditLogRead] = Field(
        default_factory=list, description="Ordered audit trail entries for this transaction"
    )

    model_config = ConfigDict(from_attributes=True)
