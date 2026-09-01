"""
models/report.py
----------------
Pydantic v2 schemas for recovery metrics reports and batch execution payloads.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class FailureReasonMetric(BaseModel):
    failure_reason_code: str
    category: str
    count: int
    at_risk_amount: float
    recovered_count: int
    recovered_amount: float
    recovery_rate: float


class CategoryMetric(BaseModel):
    category: str
    count: int
    at_risk_amount: float
    recovered_count: int
    recovered_amount: float
    recovery_rate: float


class ChannelMetric(BaseModel):
    channel: str
    count: int
    at_risk_amount: float
    recovered_count: int
    recovered_amount: float
    recovery_rate: float


class ReportResponse(BaseModel):
    total_transactions: int = Field(..., description="Total transactions in the report")
    total_at_risk_amount: float = Field(..., description="Total INR amount at risk")
    total_recovered_amount: float = Field(..., description="Total INR amount recovered")
    amount_recovery_rate: float = Field(..., description="Percentage of revenue recovered")
    count_recovered: int = Field(..., description="Number of recovered transactions")
    count_unrecoverable: int = Field(..., description="Number of permanently unrecoverable records")
    count_pending: int = Field(..., description="Number of pending/follow-up transactions")
    count_blocked_by_guardrail: int = Field(..., description="Number of actions blocked by guardrails")
    volume_recovery_rate: float = Field(..., description="Percentage of transaction count recovered")
    by_failure_reason: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Metrics grouped by failure reason code"
    )
    by_category: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Metrics grouped by recovery category"
    )
    by_channel: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Metrics grouped by preferred contact channel"
    )
    generated_at: str = Field(
        default_factory=lambda: datetime.datetime.now().isoformat(),
        description="Timestamp when this report was generated",
    )

    model_config = ConfigDict(from_attributes=True)


class RunBatchRequest(BaseModel):
    limit: Optional[int] = Field(None, ge=1, description="Optional limit of transactions to process")
    random_seed: Optional[int] = Field(42, description="Random seed for deterministic outcome simulation")


class RunBatchResponse(BaseModel):
    status: str = Field("completed", description="Execution status")
    message: str = Field(..., description="Summary message")
    processed_count: int = Field(..., description="Total transactions processed")
    report: ReportResponse = Field(..., description="Full recovery metrics report")
