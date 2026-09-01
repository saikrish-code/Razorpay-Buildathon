"""
routes/transactions.py
-----------------------
REST endpoints for Transactions, Batch Pipeline Execution, and Analytics Reports.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import db as crud
from app.database import get_db
from app.models.audit_log import AuditLogRead
from app.models.report import ReportResponse, RunBatchRequest, RunBatchResponse
from app.models.transaction import (
    TransactionCreate,
    TransactionDetailRead,
    TransactionRead,
    TransactionUpdate,
)
from run_batch import resolve_db_path, run_recovery_batch

router = APIRouter(tags=["Transactions"])


# ── GET /transactions (with multi-field filters) ──────────────────────────────

@router.get(
    "/transactions",
    response_model=List[TransactionRead],
    summary="List transactions with filters",
    description="Retrieve a paginated, filtered list of recovery transactions.",
)
@router.get(
    "/api/transactions",
    response_model=List[TransactionRead],
    include_in_schema=False,
)
async def list_transactions(
    status: Optional[str] = Query(None, description="Filter by status (open, pending, recovered, unrecoverable)"),
    failure_reason_code: Optional[str] = Query(None, description="Filter by failure reason code (insufficient_funds, card_expired, etc.)"),
    type: Optional[str] = Query(None, description="Filter by transaction type (one_time_checkout, subscription_renewal, checkout_abandonment)"),
    channel: Optional[str] = Query(None, description="Filter by customer channel (whatsapp, sms, email)"),
    min_amount: Optional[float] = Query(None, ge=0, description="Minimum amount in INR"),
    max_amount: Optional[float] = Query(None, ge=0, description="Maximum amount in INR"),
    search: Optional[str] = Query(None, description="Free-text search across transaction_id, customer_id, email, phone, or description"),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    db: AsyncSession = Depends(get_db),
) -> List[TransactionRead]:
    """Return a filtered, paginated list of transactions."""
    return await crud.transactions.get_all(
        db=db,
        skip=skip,
        limit=limit,
        status=status,
        failure_reason_code=failure_reason_code,
        type=type,
        channel=channel,
        min_amount=min_amount,
        max_amount=max_amount,
        search=search,
    )


# ── GET /transactions/{id} (with full audit trail) ─────────────────────────────

@router.get(
    "/transactions/{transaction_id}",
    response_model=TransactionDetailRead,
    summary="Get transaction with full audit trail",
    description="Retrieve a single transaction by primary key ID or transaction_id (e.g. txn_xxx) including complete ordered audit logs.",
)
@router.get(
    "/api/transactions/{transaction_id}",
    response_model=TransactionDetailRead,
    include_in_schema=False,
)
async def get_transaction(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
) -> TransactionDetailRead:
    """Return a single transaction along with its complete audit trail."""
    obj = await crud.transactions.get_by_id_or_code(
        db=db,
        identifier=transaction_id,
        load_audit_trail=True,
    )
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with identifier '{transaction_id}' not found.",
        )
    return obj


# ── GET /transactions/{id}/audit-logs ──────────────────────────────────────────

@router.get(
    "/transactions/{transaction_id}/audit-logs",
    response_model=List[AuditLogRead],
    summary="Get audit trail for a transaction",
)
@router.get(
    "/api/transactions/{transaction_id}/audit-logs",
    response_model=List[AuditLogRead],
    include_in_schema=False,
)
async def get_audit_trail(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[AuditLogRead]:
    """Return the ordered audit trail for a single transaction."""
    obj = await crud.transactions.get_by_id_or_code(db=db, identifier=transaction_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found.",
        )
    return await crud.audit_logs.get_by_transaction(db, obj.id)


# ── POST /transactions (Create) ────────────────────────────────────────────────

@router.post(
    "/transactions",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a transaction",
)
@router.post(
    "/api/transactions",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_transaction(
    data: TransactionCreate,
    db: AsyncSession = Depends(get_db),
) -> TransactionRead:
    return await crud.transactions.create(db, data)


# ── PATCH /transactions/{id} (Update) ──────────────────────────────────────────

@router.patch(
    "/transactions/{transaction_id}",
    response_model=TransactionRead,
    summary="Update a transaction",
)
@router.patch(
    "/api/transactions/{transaction_id}",
    response_model=TransactionRead,
    include_in_schema=False,
)
async def update_transaction(
    transaction_id: str,
    data: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
) -> TransactionRead:
    obj = await crud.transactions.get_by_id_or_code(db=db, identifier=transaction_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with identifier '{transaction_id}' not found.",
        )
    updated = await crud.transactions.update(db, obj.id, data)
    return updated


# ── POST /run-batch (Trigger full recovery batch pipeline) ─────────────────────

@router.post(
    "/run-batch",
    response_model=RunBatchResponse,
    summary="Execute full batch recovery pipeline",
    description="Runs the 6-step recovery pipeline (diagnose -> retrieve policy -> agent acts -> simulate outcome -> log & update DB) across all transactions.",
)
@router.post(
    "/api/run-batch",
    response_model=RunBatchResponse,
    include_in_schema=False,
)
async def run_batch_endpoint(
    payload: Optional[RunBatchRequest] = None,
) -> RunBatchResponse:
    """Triggers the full recovery batch pipeline and updates database records."""
    req = payload or RunBatchRequest()
    try:
        db_file = resolve_db_path()
        results, report = run_recovery_batch(
            db_path=db_file,
            limit=req.limit,
            random_seed=req.random_seed,
        )
        return RunBatchResponse(
            status="completed",
            message=f"Batch recovery pipeline successfully processed {len(results)} transaction(s). Total Recovered: INR {report.total_recovered_amount:,.2f} ({report.amount_recovery_rate:.1f}%).",
            processed_count=len(results),
            report=ReportResponse(
                total_transactions=report.total_transactions,
                total_at_risk_amount=report.total_at_risk_amount,
                total_recovered_amount=report.total_recovered_amount,
                amount_recovery_rate=report.amount_recovery_rate,
                count_recovered=report.count_recovered,
                count_unrecoverable=report.count_unrecoverable,
                count_pending=report.count_pending,
                count_blocked_by_guardrail=report.count_blocked_by_guardrail,
                volume_recovery_rate=report.volume_recovery_rate,
                by_failure_reason=report.by_failure_reason,
                by_category=report.by_category,
                by_channel=report.by_channel,
            ),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute batch recovery pipeline: {str(e)}",
        )


# ── GET /report (Executive Recovery Metrics & Breakdown) ───────────────────────

@router.get(
    "/report",
    response_model=ReportResponse,
    summary="Get revenue recovery analytics report",
    description="Returns aggregate KPI metrics, total revenue at risk, total recovered, recovery rate, and breakdown by failure reason, category, and channel.",
)
@router.get(
    "/api/report",
    response_model=ReportResponse,
    include_in_schema=False,
)
async def get_recovery_report(
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """Calculates live recovery metrics from the transactions database."""
    all_txns = await crud.transactions.get_all(db=db, skip=0, limit=10000)

    total_at_risk = 0.0
    total_recovered = 0.0
    count_recovered = 0
    count_unrecoverable = 0
    count_pending = 0
    count_blocked = 0

    reason_stats: Dict[str, Dict[str, Any]] = {}
    category_stats: Dict[str, Dict[str, Any]] = {}
    channel_stats: Dict[str, Dict[str, Any]] = {}

    for txn in all_txns:
        amount = float(txn.amount or 0.0)
        code = str(txn.failure_reason_code or "unknown").lower()
        channel = str(txn.customer_channel_pref or "whatsapp").lower()
        stat = str(txn.status or "open").lower()

        # Map category if known
        cat_str = "recoverable_wait"
        if code in {"account_closed", "fraud_suspected", "blacklisted_customer"}:
            cat_str = "unrecoverable"
        elif code in {"network_error", "gateway_error", "system_error", "bank_timeout"}:
            cat_str = "recoverable_technical"
        elif code in {"card_expired", "wrong_otp", "customer_abandoned"}:
            cat_str = "recoverable_action_needed"

        is_recovered = (stat == "recovered" or stat == "success")
        is_unrecoverable = (stat == "unrecoverable")
        is_blocked = (stat == "pending_compliance_review")

        recovered_amt = amount if is_recovered else 0.0

        total_at_risk += amount
        total_recovered += recovered_amt

        if is_recovered:
            count_recovered += 1
        elif is_unrecoverable:
            count_unrecoverable += 1
        elif is_blocked:
            count_blocked += 1
        else:
            count_pending += 1

        # Reason breakdown
        if code not in reason_stats:
            reason_stats[code] = {
                "count": 0,
                "at_risk": 0.0,
                "recovered_count": 0,
                "recovered_amt": 0.0,
                "category": cat_str,
            }
        reason_stats[code]["count"] += 1
        reason_stats[code]["at_risk"] += amount
        if is_recovered:
            reason_stats[code]["recovered_count"] += 1
            reason_stats[code]["recovered_amt"] += amount

        # Category breakdown
        if cat_str not in category_stats:
            category_stats[cat_str] = {
                "count": 0,
                "at_risk": 0.0,
                "recovered_count": 0,
                "recovered_amt": 0.0,
            }
        category_stats[cat_str]["count"] += 1
        category_stats[cat_str]["at_risk"] += amount
        if is_recovered:
            category_stats[cat_str]["recovered_count"] += 1
            category_stats[cat_str]["recovered_amt"] += amount

        # Channel breakdown
        if channel not in channel_stats:
            channel_stats[channel] = {
                "count": 0,
                "at_risk": 0.0,
                "recovered_count": 0,
                "recovered_amt": 0.0,
            }
        channel_stats[channel]["count"] += 1
        channel_stats[channel]["at_risk"] += amount
        if is_recovered:
            channel_stats[channel]["recovered_count"] += 1
            channel_stats[channel]["recovered_amt"] += amount

    amount_rate = (total_recovered / total_at_risk * 100.0) if total_at_risk > 0 else 0.0
    volume_rate = (count_recovered / len(all_txns) * 100.0) if all_txns else 0.0

    return ReportResponse(
        total_transactions=len(all_txns),
        total_at_risk_amount=total_at_risk,
        total_recovered_amount=total_recovered,
        amount_recovery_rate=amount_rate,
        count_recovered=count_recovered,
        count_unrecoverable=count_unrecoverable,
        count_pending=count_pending,
        count_blocked_by_guardrail=count_blocked,
        volume_recovery_rate=volume_rate,
        by_failure_reason=reason_stats,
        by_category=category_stats,
        by_channel=channel_stats,
    )
