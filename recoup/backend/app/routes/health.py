"""
routes/health.py
----------------
Health-check endpoint — confirms the API is reachable and returns
the application version.
"""

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health", summary="Health check")
async def health() -> dict:
    """Returns `{"status": "ok"}` — used by the frontend to verify connectivity."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }
