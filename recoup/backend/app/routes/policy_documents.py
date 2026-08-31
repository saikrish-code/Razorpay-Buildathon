"""
routes/policy_documents.py
---------------------------
REST endpoints for PolicyDocument CRUD.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import db as crud
from app.database import get_db
from app.models.policy_document import (
    PolicyDocumentCreate,
    PolicyDocumentRead,
    PolicyDocumentUpdate,
)

from app.retrieval import retrieve_policy

router = APIRouter(prefix="/api/policy-documents", tags=["Policy Documents"])


@router.get("/search", summary="Search policy documents via in-memory vector retriever")
async def search_policies(q: str, k: int = 2) -> list[dict]:
    """Retrieve top-k relevant policy chunks using cosine similarity."""
    return retrieve_policy(query=q, k=k)


@router.get("", response_model=list[PolicyDocumentRead], summary="List policy documents")
async def list_policy_documents(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[PolicyDocumentRead]:
    return await crud.policy_documents.get_all(db, active_only=active_only)


@router.get("/{doc_id}", response_model=PolicyDocumentRead, summary="Get a policy document")
async def get_policy_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
) -> PolicyDocumentRead:
    obj = await crud.policy_documents.get_by_id(db, doc_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return obj


@router.post(
    "",
    response_model=PolicyDocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a policy document",
)
async def create_policy_document(
    data: PolicyDocumentCreate,
    db: AsyncSession = Depends(get_db),
) -> PolicyDocumentRead:
    return await crud.policy_documents.create(db, data)


@router.patch("/{doc_id}", response_model=PolicyDocumentRead, summary="Update a policy document")
async def update_policy_document(
    doc_id: int,
    data: PolicyDocumentUpdate,
    db: AsyncSession = Depends(get_db),
) -> PolicyDocumentRead:
    obj = await crud.policy_documents.update(db, doc_id, data)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return obj
