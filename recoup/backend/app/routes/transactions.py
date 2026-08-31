"""
routes/transactions.py
-----------------------
REST endpoints for the Transaction resource.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import db as crud
from app.database import get_db
from app.models.audit_log import AuditLogRead
from app.models.transaction import TransactionCreate, TransactionRead, TransactionUpdate

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


@router.get("", response_model=list[TransactionRead], summary="List transactions")
async def list_transactions(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[TransactionRead]:
    """Return a paginated list of all transactions."""
    return await crud.transactions.get_all(db, skip=skip, limit=limit)


@router.get(
    "/{transaction_id}",
    response_model=TransactionRead,
    summary="Get a single transaction",
)
async def get_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
) -> TransactionRead:
    obj = await crud.transactions.get_by_id(db, transaction_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return obj


@router.get(
    "/{transaction_id}/audit-logs",
    response_model=list[AuditLogRead],
    summary="Get audit trail for a transaction",
)
async def get_audit_trail(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogRead]:
    """Return the ordered audit trail for a single transaction."""
    return await crud.audit_logs.get_by_transaction(db, transaction_id)


@router.post(
    "",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a transaction",
)
async def create_transaction(
    data: TransactionCreate,
    db: AsyncSession = Depends(get_db),
) -> TransactionRead:
    return await crud.transactions.create(db, data)


@router.patch(
    "/{transaction_id}",
    response_model=TransactionRead,
    summary="Update a transaction",
)
async def update_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
) -> TransactionRead:
    obj = await crud.transactions.update(db, transaction_id, data)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return obj
