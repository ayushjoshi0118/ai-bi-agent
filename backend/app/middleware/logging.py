"""
Request logging and correlation ID middleware.
"""

from __future__ import annotations

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that assigns a correlation ID (X-Request-ID) to every request
    and logs duration, status code, and client IP.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Bind context variable for structlog
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            client_ip=request.client.host if request.client else "unknown",
        )

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000
            response.headers["X-Request-ID"] = request_id
            
            # Avoid logging excessive noise for static or health checks
            if not request.url.path.endswith("/health"):
                logger.info(
                    "http_request_completed",
                    status_code=response.status_code,
                    duration_ms=round(duration_ms, 2),
                )
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "http_request_failed",
                error=str(exc),
                duration_ms=round(duration_ms, 2),
                exc_info=True,
            )
            raise
