# Production Launch Checklist

Before deploying the AI Business Intelligence Agent SaaS into production, verify all items:

---

## 1. Secrets & Encryption
- [ ] `SECRET_KEY` rotated from defaults to 64-character random string.
- [ ] `JWT_SECRET_KEY` generated with cryptographically secure PRNG.
- [ ] `ENCRYPTION_KEY` configured using a valid 32-byte URL-safe base64-encoded Fernet key.
- [ ] Database credentials and secrets excluded from git commits and docker image layers.
- [ ] PostgreSQL production passwords set with minimum 24 alphanumeric characters.

---

## 2. Infrastructure & Networking
- [ ] Host firewall (UFW/AWS Security Group) only exposes ports 80/443 to the public internet.
- [ ] PostgreSQL port 5432 and Redis port 6379 bound to private VPC/localhost only.
- [ ] HTTPS enforced with valid TLS 1.3 certificates and HSTS headers.
- [ ] Reverse proxy client upload limit configured to match `MAX_UPLOAD_SIZE_MB` (50MB).

---

## 3. Database & Storage
- [ ] Managed PostgreSQL instance provisioned with multi-AZ replication.
- [ ] Automated point-in-time recovery (PITR) enabled with 30-day retention.
- [ ] Database migrations executed: `alembic upgrade head`.
- [ ] Dedicated upload volume provisioned with persistent block storage (EBS / GCE PD).

---

## 4. Background Workers & Queue
- [ ] Redis cluster configured with persistent AOF (`appendonly yes`).
- [ ] Celery worker concurrency sized appropriately for CPU resources (`--concurrency=4`).
- [ ] Celery Beat scheduler running exactly one instance to prevent duplicate cron runs.

---

## 5. Security & Isolation Testing
- [ ] Full automated test suite passes: `pytest tests -v`.
- [ ] Cross-tenant isolation verified with zero cross-organization data leakage.
- [ ] Untrusted SQL parser rejects modifying operations (`DROP`, `INSERT`, `UPDATE`, `ALTER`).
- [ ] Rate limiting verified on sensitive auth endpoints.
