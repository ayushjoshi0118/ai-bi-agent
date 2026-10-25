"""
Main API Router configuration aggregating all v1 sub-routers.
"""

from fastapi import APIRouter

from app.api.v1.anomalies import router as anomalies_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.data_sources import router as data_sources_router
from app.api.v1.datasets import router as datasets_router
from app.api.v1.health import router as health_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.queries import router as queries_router
from app.api.v1.reports import router as reports_router
from app.api.v1.scheduled_jobs import router as scheduled_jobs_router
from app.api.v1.users import router as users_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(organizations_router)
api_v1_router.include_router(data_sources_router)
api_v1_router.include_router(datasets_router)
api_v1_router.include_router(conversations_router)
api_v1_router.include_router(queries_router)
api_v1_router.include_router(reports_router)
api_v1_router.include_router(anomalies_router)
api_v1_router.include_router(scheduled_jobs_router)
api_v1_router.include_router(audit_router)
