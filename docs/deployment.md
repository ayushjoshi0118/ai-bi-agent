# Enterprise Production Deployment & Release Engineering Guide

This guide details the complete operational specifications, multi-stage container architecture, environment configuration reference, database migration safety protocols, reverse proxy security parameters, load capacity models, and disaster recovery procedures for the AI Business Intelligence Agent SaaS platform.

---

## 1. Production Architecture Overview

The system runs as an isolated, containerized topology with distinct security boundaries, least-privilege network segmentation, and non-root container users:

```
                              [ HTTPS Traffic: Port 443 ]
                                           │
                                           ▼
                 ┌──────────────────────────────────────────────────┐
                 │       Nginx Reverse Proxy (TLS 1.2/1.3)          │
                 │   - HSTS, CSP, X-Frame-Options, Rate Limiting    │
                 │   - 50MB Upload Limit, 120s Streaming Timeouts   │
                 └──────────────┬────────────────────┬──────────────┘
                                │                    │
             /api/* (REST/SSE)  │                    │ /* (HTML/Static/SSR)
                                ▼                    ▼
                 ┌──────────────────────┐   ┌──────────────────────┐
                 │  FastAPI Backend     │   │ Next.js Standalone   │
                 │  - Gunicorn (4 wkrs) │   │ - Node 20 Runner     │
                 │  - Non-root UID 10001│   │ - Non-root UID 1001  │
                 │  - AsyncPG + Pool 20 │   │ - Next Standalone    │
                 └──────────┬───────────┘   └──────────────────────┘
                            │
               ┌────────────┴────────────┐
               │  Internal Docker Net    │
               ▼                         ▼
   ┌──────────────────────┐  ┌───────────────────────────────────┐
   │ PostgreSQL 16 (Prod) │  │ Redis 7 (AppendOnly, Password)    │
   │ - App Metadata       │  │ - DB 0: Telemetry Cache / Limits  │
   │ - RLS Isolation      │  │ - DB 1: Celery Broker Queue       │
   │ - 30-Day WAL Archive │  │ - DB 2: Celery Result Backend     │
   └──────────────────────┘  └─────────────────┬─────────────────┘
                                               │
                                 ┌─────────────┴─────────────┐
                                 ▼                           ▼
                     ┌──────────────────────┐   ┌──────────────────────┐
                     │ Celery Worker        │   │ Celery Beat          │
                     │ - 4 Concurrent Wkrs  │   │ - Cron Scheduler     │
                     │ - Non-root UID 10001 │   │ - Timezone (zoneinfo)│
                     └──────────────────────┘   └──────────────────────┘
```

---

## 2. Hardened Multi-Stage Containerization

Both services utilize multi-stage builds to ensure minimal image footprint, eliminate build tools and compilers from the runtime image, and enforce unprivileged user execution:

### 2.1 Backend Container (`backend/Dockerfile`)
- **Stage 1 (`builder`)**: Uses `python:3.11-slim-bookworm` to install build dependencies (`build-essential`, `libpq-dev`), create an isolated virtualenv (`/opt/venv`), and compile wheels.
- **Stage 2 (`runner`)**: Minimal runtime with shared libraries (`libpq5`, `curl`, `ca-certificates`).
- **User Security**: System user `appuser` with UID `10001` and GID `10001`. The container never executes as `root`.
- **Readiness Entrypoint**: `backend/docker-entrypoint.sh` executes `app.wait_for_deps` to ensure PostgreSQL and Redis are healthy before running migrations or starting Gunicorn.
- **Healthcheck**: `curl -f http://localhost:8000/api/v1/health/live` (30s interval, 5s timeout, 3 retries).

### 2.2 Frontend Container (`frontend/Dockerfile`)
- **Stage 1 (`deps`)**: Uses `node:20-alpine` with `libc6-compat` to execute `npm ci` against pinned `package-lock.json`.
- **Stage 2 (`builder`)**: Compiles optimized Next.js standalone bundle with `output: "standalone"`.
- **Stage 3 (`runner`)**: Copies only `.next/standalone`, `.next/static`, and `public`. Image size is reduced from >1GB to ~120MB.
- **User Security**: Non-root system user `nextjs` with UID `1001` and GID `1001`.
- **Healthcheck**: `wget --spider http://localhost:3000` (30s interval, 5s timeout, 3 retries).

---

## 3. Environment Variable Reference

| Variable Name | Required | Default / Example | Type | Description & Security Policy |
| :--- | :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | Yes | `production` | String | Environment tier (`development`, `staging`, `production`). Disables debug endpoints in prod. |
| `DEBUG` | No | `false` | Boolean | Must be strictly `false` in staging and production. |
| `LOG_LEVEL` | No | `INFO` | String | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `DOMAIN_NAME` | Yes | `biagent.yourdomain.com` | String | Primary public domain used for CORS and reverse proxy headers. |
| `CORS_ORIGINS` | Yes | `https://biagent.yourdomain.com` | CSV String | Permitted cross-origin origins. Never use `*` in production. |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://...` | Connection URL | Primary async database URL for application metadata. **Secret**. |
| `DATABASE_URL_SYNC` | Yes | `postgresql://...` | Connection URL | Synchronous database URL for Alembic migrations and Celery workers. **Secret**. |
| `DATABASE_POOL_SIZE` | No | `20` | Integer | Connection pool size per backend process. |
| `DATABASE_MAX_OVERFLOW`| No | `10` | Integer | Max connections allowed above pool size during traffic bursts. |
| `REDIS_PASSWORD` | Yes | `[min 32 chars]` | Secret String | Authentication password for Redis 7. **Secret**. |
| `REDIS_URL` | Yes | `redis://:pass@redis:6379/0` | Connection URL | Redis instance for rate limiting, sliding windows, and caching. |
| `CELERY_BROKER_URL` | Yes | `redis://:pass@redis:6379/1` | Connection URL | Redis database index 1 for background job queue. |
| `CELERY_RESULT_BACKEND`| Yes | `redis://:pass@redis:6379/2` | Connection URL | Redis database index 2 for task result persistence. |
| `JWT_SECRET_KEY` | Yes | `[64 hex chars]` | Secret String | HMAC-SHA256 signature key for user JWTs. Rotate every 90 days. **Secret**. |
| `ENCRYPTION_KEY` | Yes | `[Fernet Base64]` | Secret String | AES-128-CBC / HMAC-SHA256 Fernet key for customer database credentials. **Secret**. |
| `LLM_PROVIDER` | Yes | `openai` | String | LLM integration provider (`openai`, `google`, `anthropic`). |
| `LLM_MODEL` | Yes | `gpt-4o` | String | Target LLM model name. |
| `LLM_API_KEY` | Yes | `sk-proj-...` | Secret String | Upstream provider API credential. Redacted in all logs. **Secret**. |
| `LLM_REQUEST_TIMEOUT` | No | `60` | Integer | Maximum duration in seconds for LLM generation before timeout. |
| `MAX_UPLOAD_SIZE_MB` | No | `50` | Integer | Maximum permitted file upload size for CSV / Excel datasets. |
| `UPLOAD_DIR` | No | `/app/uploads` | Filepath | Persistent tenant-partitioned directory for raw datasets. |
| `RATE_LIMIT_PER_MINUTE`| No | `120` | Integer | Maximum API requests per minute per authenticated user. |
| `QUERY_MAX_ROWS` | No | `10000` | Integer | Strict limit on rows returned by user analytical queries. |
| `QUERY_TIMEOUT_SECONDS`| No | `30` | Integer | Strict database statement timeout for analytics queries. |
| `SENTRY_DSN` | No | `""` | URL | Optional Sentry crash reporting DSN. |

---

## 4. Database Migration & Release Management

### 4.1 Backward-Compatible Migration Protocol
All database changes must adhere to the **Expand / Contract (Parallel Run)** pattern to allow zero-downtime rolling deployments and safe instant rollback:

1. **Pre-Deployment (Expand Phase)**:
   - Additive schema updates only: add new nullable columns, create new tables, add non-blocking indexes (`CREATE INDEX CONCURRENTLY`).
   - Run before new application containers are deployed:
     ```bash
     python -c "from alembic.config import CommandLine; CommandLine().main(argv=['upgrade', 'head'])"
     ```
2. **Application Rolling Rollout**:
   - Deploy new backend containers running version `N+1`.
   - Both version `N` and version `N+1` continue functioning simultaneously because the schema changes were purely additive.
3. **Post-Deployment (Contract Phase)**:
   - After version `N+1` is 100% verified and version `N` is fully retired:
   - Run cleanup migrations to backfill default values, add `NOT NULL` constraints, or deprecate/drop obsolete columns.

### 4.2 Rollback Procedure
If a release fails smoke checks:
1. Re-route traffic to prior container image tags (`bi-agent-backend:prev`, `bi-agent-frontend:prev`).
2. Because pre-deployment migrations were strictly backward-compatible, older application code continues to operate seamlessly without rolling back the database.
3. If database rollback is mandatory:
   ```bash
   python -c "from alembic.config import CommandLine; CommandLine().main(argv=['downgrade', '-1'])"
   ```

---

## 5. Reverse Proxy & Network Hardening

The Nginx configuration (`nginx/nginx.conf`) enforces strict transport security and proxy buffers:
- **TLS 1.2 & TLS 1.3**: Strong cipher suites with Perfect Forward Secrecy (`ECDHE-ECDSA-AES128-GCM-SHA256`, `ECDHE-RSA-AES256-GCM-SHA384`).
- **HSTS**: `max-age=63072000; includeSubDomains; preload` prevents protocol downgrade attacks.
- **Framing & Clickjacking Defense**: `X-Frame-Options: DENY` and `Content-Security-Policy: frame-ancestors 'none'`.
- **Upload Limit**: `client_max_body_size 50M` strictly synchronized with backend `MAX_UPLOAD_SIZE_MB`.
- **Timeout Management**: `proxy_read_timeout 120s` accommodates deep AI reasoning without terminating long-lived server-sent events.

---

## 6. Performance, Bottlenecks & Capacity Planning

### 6.1 Resource Budgets & Container Limits
Configured in `docker-compose.prod.yml`:
- **Nginx Proxy**: 1.0 CPU, 256MB RAM
- **Backend API (Gunicorn)**: 2.0 CPU, 1536MB RAM
- **Background Worker**: 2.0 CPU, 1536MB RAM
- **Scheduler (Beat)**: 0.5 CPU, 256MB RAM
- **PostgreSQL Database**: 2.0 CPU, 2048MB RAM (Buffer pool 512MB)
- **Redis Cache/Queue**: 1.0 CPU, 512MB RAM
- **Frontend Standalone**: 1.0 CPU, 1024MB RAM

### 6.2 Database Bottlenecks & N+1 Prevention
1. **Connection Pooling**: `DATABASE_POOL_SIZE=20` with `DATABASE_MAX_OVERFLOW=10`. Total maximum connections across 4 Gunicorn workers + Celery is bounded to 120 connections, comfortably under PostgreSQL's default limit of 200.
2. **Eager Loading on Relationships**: Query services use SQLAlchemy `.options(selectinload(...))` or explicit joins on `Organization.memberships`, `Report.versions`, and `DataSource.datasets` to eliminate N+1 select cascades.
3. **Composite Foreign Key Indexes**: All tenant-isolated tables (`reports`, `datasets`, `data_sources`, `scheduled_jobs`, `audit_events`) have B-tree indexes on `(org_id, created_at)` and `(org_id, id)`.

---

## 7. Disaster Recovery & Backup Drills

- **Automated Backup**: `python scripts/db_backup_restore.py --db-url $DATABASE_URL_SYNC` generates custom-format pg_dump archives verified with SHA-256 checksums.
- **Automated Restore Drill**: `python scripts/db_backup_restore.py --drill` spins up a temporary shadow verification database (`biagent_restore_drill_*`), tests restore integrity, verifies tables, and safely purges the test database.
- **RPO (Recovery Point Objective)**: < 15 minutes via continuous PostgreSQL WAL archiving.
- **RTO (Recovery Time Objective)**: < 30 minutes via automated shadow restore automation.
