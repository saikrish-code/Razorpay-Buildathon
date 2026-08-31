"""
db/__init__.py
--------------
Re-exports CRUD sub-modules so routes can write:

    from app import db as crud
    await crud.transactions.get_all(db)
"""

from app.db import audit_logs, policy_documents, transactions

__all__ = ["transactions", "audit_logs", "policy_documents"]
