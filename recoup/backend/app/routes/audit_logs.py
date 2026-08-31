"""
routes/audit_logs.py
---------------------
REST endpoints for direct AuditLog access (cross-transaction queries).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import db as crud
from app.database import get_db
from app.models.audit_log import AuditLogCreate, AuditLogRead

router = APIRouter(prefix="/api/audit-logs", tags=["Audit Logs"])


@router.post(
    "",
    response_model=AuditLogRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an audit log entry",
)
async def create_audit_log(
    data: AuditLogCreate,
    db: AsyncSession = Depends(get_db),
) -> AuditLogRead:
    return await crud.audit_logs.create(db, data)
