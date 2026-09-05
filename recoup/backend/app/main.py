"""
main.py
-------
FastAPI application entry point.
Run locally with:  uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routes import audit_logs, health, policy_documents, transactions

# Path to built React frontend
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


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

# ── Mount Frontend Static Assets (if built) ───────────────────────────────────
assets_dir = FRONTEND_DIST / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(transactions.router)
app.include_router(audit_logs.router)
app.include_router(policy_documents.router)


# ── Root & Navigation Endpoints ────────────────────────────────────────────────
@app.get("/", tags=["root"], summary="API Root Overview")
async def root(request: Request):
    """Returns frontend SPA if requested by browser, or API status if JSON requested."""
    accept = request.headers.get("accept", "")
    index_html = FRONTEND_DIST / "index.html"
    if "text/html" in accept and index_html.exists():
        return FileResponse(str(index_html))

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


@app.get("/favicon.svg", include_in_schema=False)
async def favicon():
    fav = FRONTEND_DIST / "favicon.svg"
    if fav.exists():
        return FileResponse(str(fav))
    return Response(status_code=404)


@app.get("/icons.svg", include_in_schema=False)
async def icons():
    ic = FRONTEND_DIST / "icons.svg"
    if ic.exists():
        return FileResponse(str(ic))
    return Response(status_code=404)


@app.get("/docs", include_in_schema=False)
async def redirect_docs():
    """Redirect /docs to /api/docs for convenience."""
    return RedirectResponse(url="/api/docs")


@app.get("/api", include_in_schema=False)
async def api_root():
    """Redirect /api to /api/docs."""
    return RedirectResponse(url="/api/docs")


# ── Catch-All SPA Fallback ────────────────────────────────────────────────────
@app.get("/{full_path:path}", include_in_schema=False)
async def catch_all(full_path: str):
    """Catch-all route to serve the SPA on direct navigation or refresh."""
    if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("redoc"):
        raise HTTPException(status_code=404, detail="API endpoint not found")

    file_path = FRONTEND_DIST / full_path
    if file_path.is_file():
        return FileResponse(str(file_path))

    index_html = FRONTEND_DIST / "index.html"
    if index_html.exists():
        return FileResponse(str(index_html))

    raise HTTPException(status_code=404, detail="Resource not found")

