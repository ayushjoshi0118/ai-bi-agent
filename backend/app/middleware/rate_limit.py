"""
Redis-backed rate limiting middleware.
"""

from __future__ import annotations

import time
from typing import Callable
from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as aioredis
from app.config import get_settings

settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter using Redis.
    Falls back gracefully if Redis is unavailable in local dev.
    """

    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.limit = requests_per_minute
        self.redis: aioredis.Redis | None = None

    async def get_redis(self) -> aioredis.Redis | None:
        if self.redis is None:
            try:
                self.redis = aioredis.from_url(
                    settings.redis_url, encoding="utf-8", decode_responses=True
                )
                await self.redis.ping()
            except Exception:
                self.redis = None
        return self.redis

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting on health checks or documentation
        if request.url.path.startswith(("/docs", "/openapi.json", "/redoc", "/api/v1/health")):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        redis_client = await self.get_redis()

        if redis_client:
            try:
                current_minute = int(time.time() // 60)
                key = f"rate_limit:{client_ip}:{current_minute}"
                count = await redis_client.incr(key)
                if count == 1:
                    await redis_client.expire(key, 60)

                if count > self.limit:
                    return Response(
                        content='{"error": true, "message": "Rate limit exceeded. Please try again shortly."}',
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        media_type="application/json",
                        headers={"Retry-After": "60"},
                    )
            except Exception:
                # If Redis is temporarily unreachable, do not fail the request
                pass

        return await call_next(request)
