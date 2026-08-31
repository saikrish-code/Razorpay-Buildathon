"""
models/transaction.py
---------------------
Pydantic v2 schemas for Transaction request / response payloads.
These are separate from the SQLAlchemy ORM models in db/base.py.
"""

import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.base import TransactionStatus


class TransactionBase(BaseModel):
    razorpay_payment_id: str = Field(..., description="Razorpay payment ID (e.g. pay_xxx)")
    amount: float = Field(..., gt=0, description="Amount in smallest currency unit (paise)")
    currency: str = Field("INR", max_length=8)
    status: TransactionStatus = TransactionStatus.pending
    customer_email: EmailStr | None = None
    customer_phone: str | None = None
    description: str | None = None


class TransactionCreate(TransactionBase):
    """Used when creating a new transaction via POST."""
    pass


class TransactionUpdate(BaseModel):
    """Used when partially updating a transaction via PATCH."""
    status: TransactionStatus | None = None
    customer_email: EmailStr | None = None
    customer_phone: str | None = None
    description: str | None = None


class TransactionRead(TransactionBase):
    """Returned by GET endpoints — includes DB-generated fields."""
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
