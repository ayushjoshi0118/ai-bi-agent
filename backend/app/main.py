"""
FastAPI Application Entrypoint.
Initializes middleware, routing, structured logging, database engine, and graceful lifespans.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import structlog

from app.api.router import api_v1_router
from app.config import get_settings
from app.database import async_engine
from app.middleware.cors import setup_cors
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.models.base import Base
from app.schemas.common import ErrorDetail, ErrorResponse
from app.utils.logging import configure_logging

settings = get_settings()
configure_logging(log_level=settings.log_level)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing database connections and graceful shutdown."""
    logger.info("application_startup", app=settings.app_name, env=settings.app_env)

    # In development/local mode, automatically create tables if they do not exist
    if settings.app_env == "development" or settings.debug:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("database_tables_initialized")

    yield

    logger.info("application_shutdown")
    await async_engine.dispose()


app = FastAPI(
    title="AI Business Intelligence Agent API",
    description="Production-grade AI Business Intelligence Agent SaaS platform with SQL-safe analytics and workflows.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 1. Setup CORS
setup_cors(app)

# 2. Add Request Logging & Correlation ID Middleware
app.add_middleware(RequestLoggingMiddleware)

# 3. Add Rate Limiting Middleware
app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit_requests_per_minute)

# 4. Include API v1 Router
app.include_router(api_v1_router)


# Global Exception Handlers returning consistent ErrorResponse schema
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=True,
            message=str(exc.detail),
            request_id=request_id,
        ).model_dump(mode="json"),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    details = [
        ErrorDetail(
            field=" -> ".join(str(loc) for loc in err["loc"]),
            message=err["msg"],
            code=err["type"],
        )
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error=True,
            message="Request input validation failed",
            details=details,
            request_id=request_id,
        ).model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.error("unhandled_server_exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error=True,
            message="An unexpected internal server error occurred. Please contact support.",
            request_id=request_id,
        ).model_dump(mode="json"),
    )
