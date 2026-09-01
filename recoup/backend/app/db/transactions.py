"""
db/transactions.py
------------------
CRUD / repository functions for the Transaction table with advanced filtering,
eager audit-log loading, and aggregated KPI analytics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import AuditLog, Transaction
from app.models.transaction import TransactionCreate, TransactionUpdate


async def get_all(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    failure_reason_code: Optional[str] = None,
    type: Optional[str] = None,
    channel: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    search: Optional[str] = None,
) -> list[Transaction]:
    """
    Return a paginated list of transactions filtered by any combination of criteria.
    """
    query = select(Transaction)

    if status:
        query = query.where(Transaction.status == status.strip().lower())

    if failure_reason_code:
        query = query.where(Transaction.failure_reason_code == failure_reason_code.strip().lower())

    if type:
        query = query.where(Transaction.type == type.strip().lower())

    if channel:
        query = query.where(Transaction.customer_channel_pref == channel.strip().lower())

    if min_amount is not None:
        query = query.where(Transaction.amount >= min_amount)

    if max_amount is not None:
        query = query.where(Transaction.amount <= max_amount)

    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Transaction.transaction_id.ilike(search_pattern),
                Transaction.customer_id.ilike(search_pattern),
                Transaction.customer_email.ilike(search_pattern),
                Transaction.customer_phone.ilike(search_pattern),
                Transaction.description.ilike(search_pattern),
            )
        )

    query = query.order_by(Transaction.id.asc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, transaction_id: int) -> Transaction | None:
    """Find a single transaction by primary key integer id."""
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    return result.scalar_one_or_none()


async def get_by_id_or_code(
    db: AsyncSession,
    identifier: Union[int, str],
    load_audit_trail: bool = False,
) -> Transaction | None:
    """
    Find a transaction by primary key int ID or unique string transaction_id (e.g. 'txn_xxx').
    Optionally eager-loads the full audit trail.
    """
    query = select(Transaction)
    if load_audit_trail:
        query = query.options(selectinload(Transaction.audit_logs))

    if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
        int_id = int(identifier)
        query = query.where(or_(Transaction.id == int_id, Transaction.transaction_id == str(identifier)))
    else:
        query = query.where(Transaction.transaction_id == str(identifier))

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create(db: AsyncSession, data: TransactionCreate) -> Transaction:
    obj = Transaction(**data.model_dump())
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return obj


async def update(
    db: AsyncSession, transaction_id: int, data: TransactionUpdate
) -> Transaction | None:
    obj = await get_by_id(db, transaction_id)
    if obj is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await db.flush()
    await db.refresh(obj)
    return obj


async def delete(db: AsyncSession, transaction_id: int) -> bool:
    obj = await get_by_id(db, transaction_id)
    if obj is None:
        return False
    await db.delete(obj)
    return True
