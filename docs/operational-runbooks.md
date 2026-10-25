# Operational Runbooks, Disaster Recovery & Monitoring Guide

## 1. Executive Summary

This document specifies the operational runbooks, disaster recovery (DR) procedures, monitoring definitions, alerting thresholds, and backup retention policies for the production AI Business Intelligence Agent platform.

---

## 2. Disaster Recovery & Backup Retention

### 2.1 Backup Retention Policy
| Tier | Backup Type | Frequency | Retention Window | Storage Target |
| :--- | :--- | :--- | :--- | :--- |
| **Active DB** | Continuous WAL Archiving | Continuous (every 60s) | 30 Days | Geo-redundant Object Storage (S3 / GCS) |
| **Snapshots** | PostgreSQL Full BaseBackup | Daily at 02:00 UTC | 90 Days | KMS-encrypted cold storage |
| **Uploaded Files** | S3 / GCS Object Versioning | Real-time on upload | 365 Days | Multi-region bucket with Object Lock |

### 2.2 Point-in-Time Recovery (PITR) Procedure
In the event of accidental data corruption or disaster:
```bash
# 1. Stop web and worker containers
docker compose stop api celery_worker celery_beat

# 2. Prepare clean data directory
pg_ctl stop -D /var/lib/postgresql/data
rm -rf /var/lib/postgresql/data/*

# 3. Restore latest base backup
pg_basebackup -h backup-storage -D /var/lib/postgresql/data -Ft -z -P

# 4. Configure recovery target time in postgresql.conf
cat <<EOF >> /var/lib/postgresql/data/postgresql.auto.conf
restore_command = 'cp /mnt/wal_archive/%f %p'
recovery_target_time = '2026-03-01 14:30:00 UTC'
recovery_target_action = 'promote'
EOF

# 5. Start PostgreSQL in recovery mode and monitor recovery
pg_ctl start -D /var/lib/postgresql/data
tail -f /var/lib/postgresql/data/log/postgresql.log
# Look for: "redo done at ... archive recovery complete ... database system was not properly shut down"
```

---

## 3. Worker Crash & Stale Job Recovery Runbook

### 3.1 Detection
The platform automatically identifies background workers that terminated unexpectedly (OOM kill, node preemption, or network partition).

- **Automated Sweep**: `AutonomousJobManager.recover_all_stale_runs(db, stale_timeout_minutes=15)` scans all runs stuck in `RUNNING` status $> 15$ minutes and marks them as `FAILED` with `failure_classification = "worker_crashed"`.
- **Manual Trigger**:
```bash
python -c "import asyncio; from app.database import AsyncSessionLocal; from app.workflows.job_manager import AutonomousJobManager; asyncio.run(AutonomousJobManager.recover_all_stale_runs(AsyncSessionLocal()))"
```

### 3.2 Overlap Prevention
If a job is currently executing, subsequent scheduled triggers automatically detect the active `RUNNING` lease and yield with `skipped_overlap`, preventing duplicate calculations.

---

## 4. Monitoring Telemetry & Alerting Thresholds

The platform exposes Prometheus metrics at `GET /api/v1/health/metrics` (Header: `Accept: text/plain`):

### 4.1 Prometheus Metric Catalog
- `bi_llm_requests_total`: Total count of LLM completions.
- `bi_llm_input_tokens_total` / `bi_llm_output_tokens_total`: Input and output token volume.
- `bi_llm_cost_usd_total`: Cumulative estimated token expenditure.
- `bi_llm_latency_p50_ms` / `bi_llm_latency_p95_ms`: LLM response time percentiles.
- `bi_query_duration_p50_ms` / `bi_query_duration_p95_ms`: Database query execution latency.
- `bi_queue_depth`: Number of pending background tasks.
- `bi_report_outcomes_total{outcome="completed|failed|dead_lettered"}`: Job run outcomes.
- `bi_security_failures_total{type="cross_tenant_attempt|membership_revoked|rate_limit_exceeded"}`: Security incidents.

### 4.2 Critical Alerting Rules
| Alert Name | Metric Condition | Window | Severity | Action |
| :--- | :--- | :--- | :--- | :--- |
| **CrossTenantProbeAlert** | `rate(bi_security_failures_total{type="cross_tenant_attempt"}[5m]) > 0` | 1m | P1 - Critical | Notify Security Operations; review IP / user for malicious scanning. |
| **WorkerCrashRateHigh** | `rate(bi_report_outcomes_total{outcome="worker_crashed"}[15m]) > 3` | 5m | P2 - High | Check worker node memory (OOMKilled) and Redis connectivity. |
| **QueueBackpressureSaturation** | `bi_queue_depth > 500` | 5m | P2 - High | Scale Celery worker replicas; inspect long-running queries. |
| **LLMLatencyDegraded** | `bi_llm_latency_p95_ms > 15000` | 10m | P3 - Medium | Check upstream model API status; failover to secondary provider. |
| **DatabasePoolExhausted** | `rate(bi_security_failures_total{type="db_pool_timeout"}[5m]) > 5` | 3m | P1 - Critical | Increase `pool_size` and check for unclosed connection leaks. |

---

## 5. Security Incident Response: Cross-Tenant Isolation Breach Attempt

If `security.cross_tenant_attempt` is recorded in audit logs:
1. Locate actor and client context:
   ```sql
   SELECT * FROM audit_events WHERE action = 'security.cross_tenant_attempt' ORDER BY created_at DESC LIMIT 10;
   ```
2. Verify that the response code was HTTP 404 (Resource not found). Confirm that no resource data, schema names, or metadata were leaked to the client.
3. Check actor's active sessions in Redis:
   ```bash
   redis-cli KEYS "rate_limit:user:*"
   ```
4. If malicious intent is established, suspend the user:
   ```sql
   UPDATE users SET is_active = FALSE WHERE id = '<actor_user_id>';
   ```
