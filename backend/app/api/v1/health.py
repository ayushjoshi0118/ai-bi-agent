"""
Health and readiness endpoints for Docker, Kubernetes, and monitoring.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.config import get_settings
from app.dependencies import get_db

router = APIRouter(prefix="/health", tags=["Health"])
settings = get_settings()


@router.get("", summary="Liveness Probe")
async def health_check():
    """Returns 200 OK if service is alive."""
    return {"status": "ok", "app": settings.app_name, "environment": settings.app_env}


@router.get("/ready", summary="Readiness Probe")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Verifies database and redis connections."""
    checks = {"database": False, "redis": False}

    # DB check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        checks["database_error"] = str(e)

    # Redis check
    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = True
    except Exception as e:
        checks["redis_error"] = str(e)

    all_ready = checks["database"]  # Redis is optional in development
    return {
        "ready": all_ready,
        "services": checks,
    }
