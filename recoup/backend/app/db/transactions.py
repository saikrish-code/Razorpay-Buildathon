"""
db/transactions.py
------------------
CRUD / repository functions for the Transaction table.
Business logic belongs in the routes or services layer — not here.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Transaction
from app.models.transaction import TransactionCreate, TransactionUpdate


async def get_all(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[Transaction]:
    result = await db.execute(select(Transaction).offset(skip).limit(limit))
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, transaction_id: int) -> Transaction | None:
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
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
