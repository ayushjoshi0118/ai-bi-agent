# Production Deployment Guide

This guide details instructions for provisioning and operating the AI Business Intelligence Agent SaaS platform across staging and production environments.

---

## 1. Prerequisites

- **Host OS**: Ubuntu 22.04 LTS / Debian 12 / RHEL 9
- **Docker**: Engine version >= 24.0
- **Docker Compose**: Version >= 2.20
- **Managed Database (Recommended for Production)**: AWS RDS PostgreSQL / Google Cloud SQL PostgreSQL (v15+)
- **Managed Redis**: AWS ElastiCache / Redis Enterprise (v7+)
- **Domain & SSL**: Valid FQDN with Let's Encrypt or Cloudflare TLS

---

## 2. Environment Configuration

Copy the example production environment template:

```bash
cp .env.example .env.production
chmod 600 .env.production
```

Configure required variables:

```ini
# Application Secrets (Generate with: openssl rand -hex 32)
SECRET_KEY=e839a7c3902f43...
JWT_SECRET_KEY=94b8e21a88b19...

# Fernet Key for DB Credential Encryption (Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
ENCRYPTION_KEY=s8uVb...=

# PostgreSQL (App Metadata)
DATABASE_URL=postgresql+asyncpg://biagent_user:strong_password@db-host:5432/biagent_prod
DATABASE_URL_SYNC=postgresql://biagent_user:strong_password@db-host:5432/biagent_prod

# Redis (Task Queue & Caching)
REDIS_URL=rediss://:strong_redis_password@redis-host:6379/0
CELERY_BROKER_URL=rediss://:strong_redis_password@redis-host:6379/1
CELERY_RESULT_BACKEND=rediss://:strong_redis_password@redis-host:6379/2

# AI LLM Provider
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-prod-...
```

---

## 3. Database Migrations

Apply Alembic migrations to initialize or upgrade the database schema:

```bash
# Run migrations via Docker
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head

# Or locally with Python:
cd backend
alembic upgrade head
```

---

## 4. Starting the Services

Launch all services in detached production mode:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Verify status and health checks:

```bash
docker compose -f docker-compose.prod.yml ps
```

---

## 5. Reverse Proxy & HTTPS Setup

Configure NGINX as the front-facing reverse proxy with automatic TLS termination:

```nginx
server {
    listen 80;
    server_name bi.yourcompany.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name bi.yourcompany.com;

    ssl_certificate /etc/letsencrypt/live/bi.yourcompany.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bi.yourcompany.com/privkey.pem;

    client_max_body_size 50M;

    # API Backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend Next.js
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 6. Backup and Restore Procedures

### Database Backup
```bash
pg_dump -U biagent_user -h db-host -Fc biagent_prod > backup_$(date +%Y%m%d_%H%M%S).dump
```

### Database Restore
```bash
pg_restore -U biagent_user -h db-host -d biagent_prod -c backup_20261025.dump
```
