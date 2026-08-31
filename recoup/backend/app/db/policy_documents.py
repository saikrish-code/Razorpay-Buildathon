"""
db/policy_documents.py
-----------------------
CRUD / repository functions for the PolicyDocument table.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import PolicyDocument
from app.models.policy_document import PolicyDocumentCreate, PolicyDocumentUpdate


async def get_all(db: AsyncSession, active_only: bool = False) -> list[PolicyDocument]:
    stmt = select(PolicyDocument)
    if active_only:
        stmt = stmt.where(PolicyDocument.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, doc_id: int) -> PolicyDocument | None:
    result = await db.execute(select(PolicyDocument).where(PolicyDocument.id == doc_id))
    return result.scalar_one_or_none()


async def create(db: AsyncSession, data: PolicyDocumentCreate) -> PolicyDocument:
    obj = PolicyDocument(**data.model_dump())
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return obj


async def update(
    db: AsyncSession, doc_id: int, data: PolicyDocumentUpdate
) -> PolicyDocument | None:
    obj = await get_by_id(db, doc_id)
    if obj is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await db.flush()
    await db.refresh(obj)
    return obj
