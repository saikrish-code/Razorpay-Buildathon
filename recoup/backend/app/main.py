"""
main.py
-------
FastAPI application entry point.
Run locally with:  uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routes import audit_logs, health, policy_documents, transactions


# ── Lifespan (startup / shutdown) ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create DB tables on startup."""
    await init_db()
    yield
    # (add shutdown logic here if needed)


# ── App factory ────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Revenue recovery API powered by AI agents.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
# When wildcard '*' is used for origins, allow_credentials must be False
allow_creds = "*" not in settings.cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(transactions.router)
app.include_router(audit_logs.router)
app.include_router(policy_documents.router)


# ── Root & Navigation Endpoints ────────────────────────────────────────────────
@app.get("/", tags=["root"], summary="API Root Overview")
async def root():
    """Returns application status and available API route links."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "online",
        "message": "Welcome to Recoup AI Revenue Recovery API",
        "docs_url": "/api/docs",
        "endpoints": {
            "health": "/api/health",
            "transactions": "/api/transactions",
            "audit_logs": "/api/audit-logs",
            "policy_documents": "/api/policy-documents",
        },
    }


@app.get("/docs", include_in_schema=False)
async def redirect_docs():
    """Redirect /docs to /api/docs for convenience."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/docs")


@app.get("/api", include_in_schema=False)
async def api_root():
    """Redirect /api to /api/docs."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/docs")
