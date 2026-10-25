# API Reference & Contracts

All endpoints are hosted under `/api/v1` and return standardized JSON responses.

---

## Standard Error Response Format

```json
{
  "error": true,
  "message": "Human-readable summary of the error",
  "details": [
    {
      "field": "body -> email",
      "message": "Invalid email address format",
      "code": "value_error"
    }
  ],
  "request_id": "a8f7c9e1-23b4-4c5d-9f8e-123456789abc",
  "timestamp": "2026-10-25T14:00:00Z"
}
```

---

## Authentication & Headers

Protected endpoints require a valid JWT Bearer token:
```
Authorization: Bearer <access_token>
```

To switch workspaces in multi-tenant environments, pass the target organization ID:
```
X-Org-ID: <uuid>
```

---

## Key Endpoints Summary

### Auth (`/api/v1/auth`)
- `POST /auth/signup`: Register new account and auto-provision isolated personal workspace.
- `POST /auth/login`: Authenticate and receive access + refresh token pair.
- `POST /auth/refresh`: Rotate refresh token for a new access token.
- `POST /auth/logout`: Invalidate session.

### Organizations (`/api/v1/organizations`)
- `GET /organizations`: List user's workspaces.
- `POST /organizations`: Create a new team workspace.
- `GET /organizations/current/members`: List active workspace members.
- `POST /organizations/current/members`: Invite user with role (Admin, Analyst, Viewer).

### Data Sources & Ingestion (`/api/v1/data-sources`)
- `GET /data-sources`: List connected data sources for active organization.
- `POST /data-sources/upload`: Ingest CSV/XLSX file with automated schema profiling.
- `POST /data-sources/postgres`: Connect customer PostgreSQL database with encrypted credentials.
- `POST /data-sources/{id}/test`: Perform liveness check and schema reachability test.
- `DELETE /data-sources/{id}`: Soft-delete data source.

### Datasets (`/api/v1/datasets`)
- `GET /datasets`: List all tables available to active workspace.
- `GET /datasets/{id}`: Retrieve column types, keys, and row counts.
- `GET /datasets/{id}/preview`: Inspect sample rows for verification.

### AI Agent Conversations (`/api/v1/conversations`)
- `GET /conversations`: Retrieve user's chat history.
- `POST /conversations/analyze`: Submit natural language question for orchestrated query plan, SQL execution, chart recommendation, and evidence-backed answer.
- `POST /conversations/{id}/messages`: Continue multi-turn conversation.

### Anomaly Alerts (`/api/v1/anomalies`)
- `GET /anomalies`: List statistical anomalies detected in metrics.
- `POST /anomalies/scan`: Trigger Z-Score or IQR detection on a numeric column.
- `PUT /anomalies/{id}/status`: Acknowledge or resolve an alert.

### Scheduled Jobs (`/api/v1/scheduled-jobs`)
- `GET /scheduled-jobs`: List automated cron jobs and run history.
- `POST /scheduled-jobs`: Create recurring report generation or anomaly scanner.

### Audit Logs (`/api/v1/audit-logs`)
- `GET /audit-logs`: Inspect immutable ledger of system actions (Admin only).
