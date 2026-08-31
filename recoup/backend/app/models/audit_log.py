"""
models/audit_log.py
-------------------
Pydantic v2 schemas for AuditLog request / response payloads.
"""

import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.base import AuditAction


class AuditLogBase(BaseModel):
    transaction_id: int = Field(..., description="FK → transactions.id")
    action: AuditAction
    actor: str | None = Field(None, description="User email or 'system'")
    notes: str | None = None


class AuditLogCreate(AuditLogBase):
    pass


class AuditLogRead(AuditLogBase):
    id: int
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
