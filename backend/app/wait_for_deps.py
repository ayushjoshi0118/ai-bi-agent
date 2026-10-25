"""
Readiness probe and dependency waiter.

Verifies PostgreSQL and Redis availability before starting application processes or Celery workers.
"""

from __future__ import annotations

import os
import sys
import time
import structlog
from urllib.parse import urlparse

logger = structlog.get_logger("app.wait_for_deps")


def wait_for_postgres(timeout_seconds: int = 45) -> bool:
    """Check PostgreSQL connectivity with retries."""
    import psycopg2

    db_url = os.getenv(
        "DATABASE_URL_SYNC",
        os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/bi_agent")
    )
    # Strip asyncpg driver if present
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "")
    if "+psycopg2" in db_url:
        db_url = db_url.replace("+psycopg2", "")

    start_time = time.time()
    attempt = 1
    while time.time() - start_time < timeout_seconds:
        try:
            conn = psycopg2.connect(db_url, connect_timeout=3)
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
            conn.close()
            logger.info("postgres_ready", attempts=attempt, elapsed_s=round(time.time() - start_time, 2))
            return True
        except Exception as e:
            logger.warning("postgres_waiting", attempt=attempt, error=str(e), elapsed_s=round(time.time() - start_time, 2))
            time.sleep(2)
            attempt += 1

    logger.error("postgres_timeout", timeout=timeout_seconds)
    return False


def wait_for_redis(timeout_seconds: int = 30) -> bool:
    """Check Redis connectivity with retries."""
    import redis

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    start_time = time.time()
    attempt = 1
    while time.time() - start_time < timeout_seconds:
        try:
            client = redis.Redis.from_url(redis_url, socket_timeout=3)
            if client.ping():
                client.close()
                logger.info("redis_ready", attempts=attempt, elapsed_s=round(time.time() - start_time, 2))
                return True
        except Exception as e:
            logger.warning("redis_waiting", attempt=attempt, error=str(e), elapsed_s=round(time.time() - start_time, 2))
            time.sleep(2)
            attempt += 1

    logger.error("redis_timeout", timeout=timeout_seconds)
    return False


def main() -> None:
    logger.info("checking_dependencies")
    pg_ok = wait_for_postgres()
    if not pg_ok:
        sys.exit(1)

    redis_ok = wait_for_redis()
    if not redis_ok:
        sys.exit(1)

    logger.info("all_dependencies_ready")
    sys.exit(0)


if __name__ == "__main__":
    main()
