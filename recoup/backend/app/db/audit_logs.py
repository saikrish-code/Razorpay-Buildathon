"""
db/audit_logs.py
----------------
CRUD / repository functions for the AuditLog table.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import AuditLog
from app.models.audit_log import AuditLogCreate


async def get_by_transaction(db: AsyncSession, transaction_id: int) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.transaction_id == transaction_id)
        .order_by(AuditLog.created_at)
    )
    return list(result.scalars().all())


async def create(db: AsyncSession, data: AuditLogCreate) -> AuditLog:
    obj = AuditLog(**data.model_dump())
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return obj
