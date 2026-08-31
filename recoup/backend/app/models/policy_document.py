"""
models/policy_document.py
--------------------------
Pydantic v2 schemas for PolicyDocument request / response payloads.
"""

import datetime

from pydantic import BaseModel, ConfigDict, Field


class PolicyDocumentBase(BaseModel):
    title: str = Field(..., max_length=256)
    content: str
    version: str = Field("1.0", max_length=32)
    is_active: bool = True


class PolicyDocumentCreate(PolicyDocumentBase):
    pass


class PolicyDocumentUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    version: str | None = None
    is_active: bool | None = None


class PolicyDocumentRead(PolicyDocumentBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
