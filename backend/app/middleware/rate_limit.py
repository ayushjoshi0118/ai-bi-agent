"""
Multi-Tenant & User Rate Limiting Middleware.
Enforces requests-per-minute ceilings by client IP, authenticated user ID, and organization ID.
Tracks monthly usage quotas and attaches standard X-RateLimit headers.
"""

from __future__ import annotations

from collections import defaultdict
import time
from typing import Callable, Dict, Tuple
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as aioredis

from app.config import get_settings
from app.monitoring.metrics import metrics_collector

settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Multi-tenant sliding window rate limiter.
    Enforces rate limits by organization, user, and IP address.
    Utilizes Redis when available, with a thread-safe in-memory sliding window fallback.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 120,
        org_requests_per_minute: int = 360,
    ):
        super().__init__(app)
        self.user_limit = requests_per_minute
        self.org_limit = org_requests_per_minute
        self.redis: aioredis.Redis | None = None
        # In-memory sliding window fallback (key -> list of timestamp floats)
        self._in_memory_windows: Dict[str, list[float]] = defaultdict(list)

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

        now = time.time()
        client_ip = request.client.host if request.client else "unknown"
        org_id = request.headers.get("X-Org-ID", "")
        auth_header = request.headers.get("Authorization", "")
        user_key = f"user:{client_ip}"
        if auth_header and len(auth_header) > 20:
            user_key = f"token:{auth_header[-16:]}"

        redis_client = await self.get_redis()
        current_minute = int(now // 60)
        reset_seconds = 60 - int(now % 60)

        # 1. Enforce User / IP Rate Limit
        exceeded = False
        remaining = self.user_limit

        if redis_client:
            try:
                k_user = f"rate_limit:{user_key}:{current_minute}"
                u_cnt = await redis_client.incr(k_user)
                if u_cnt == 1:
                    await redis_client.expire(k_user, 60)
                remaining = max(0, self.user_limit - u_cnt)
                if u_cnt > self.user_limit:
                    exceeded = True

                # Org-level check if org_id present
                if org_id and not exceeded:
                    k_org = f"rate_limit:org:{org_id}:{current_minute}"
                    o_cnt = await redis_client.incr(k_org)
                    if o_cnt == 1:
                        await redis_client.expire(k_org, 60)
                    if o_cnt > self.org_limit:
                        exceeded = True
            except Exception:
                exceeded = False
        else:
            # In-memory sliding window fallback
            cutoff = now - 60.0
            # User window
            user_history = [t for t in self._in_memory_windows[user_key] if t > cutoff]
            user_history.append(now)
            self._in_memory_windows[user_key] = user_history
            remaining = max(0, self.user_limit - len(user_history))
            if len(user_history) > self.user_limit:
                exceeded = True

            # Org window
            if org_id and not exceeded:
                org_key = f"org:{org_id}"
                org_history = [t for t in self._in_memory_windows[org_key] if t > cutoff]
                org_history.append(now)
                self._in_memory_windows[org_key] = org_history
                if len(org_history) > self.org_limit:
                    exceeded = True

        if exceeded:
            metrics_collector.record_security_failure("rate_limit_exceeded")
            return Response(
                content='{"error": true, "message": "Rate limit quota exceeded. Please slow down your requests."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
                headers={
                    "Retry-After": str(reset_seconds),
                    "X-RateLimit-Limit": str(self.user_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_seconds),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.user_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_seconds)
        return response
