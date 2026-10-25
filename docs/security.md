# Security Architecture & Threat Mitigations

This document outlines the security controls, boundary defenses, and hardening strategies implemented in the AI Business Intelligence Agent SaaS.

---

## 1. Zero-Hallucination & Safe Execution Boundary

1. **Untrusted Data Policy**: All data retrieved from databases, CSV files, and user questions are strictly treated as untrusted strings. They are never executed or rendered as executable system code.
2. **Deterministic SQL AST Parser**:
   - Every generated SQL query must pass `sqlglot` AST validation before execution.
   - Any modifying statement (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT`, `REVOKE`, `PRAGMA`) is rejected immediately.
   - Multiple statements separated by semicolons are blocked.
   - Dangerous PostgreSQL and SQLite internal functions (`pg_read_file`, `pg_sleep`, `lo_import`, `system`, etc.) are unconditionally blacklisted.
   - Queries are checked against an explicit allowlist of authorized table names for the active organization.
3. **Database-Level Read-Only Guarantees**:
   - Connections to external customer databases execute inside an explicit read-only transaction: `SET TRANSACTION READ ONLY`.
   - Hard execution limits enforce `SET statement_timeout = 30s`.
   - Max row returns are bounded by `QUERY_MAX_ROWS = 10,000`.

---

## 2. Multi-Tenant Isolation

1. **Tenant Filtering**:
   - Every database query in the application API explicitly filters by `org_id`.
   - Access to datasets, query histories, anomalies, reports, and audit logs verifies membership in the organization specified in the `X-Org-ID` header.
2. **File Storage Isolation**:
   - Uploaded customer CSV and Excel files are stored in tenant-isolated directories (`uploads/<org_id>/<unique_id>.csv`).
   - Query execution for uploaded files occurs in isolated temporary SQLite databases with read-only connection URIs (`file:...mode=ro`).

---

## 3. Credential Encryption & Secret Protection

1. **Fernet Symmetric Encryption**:
   - Customer database passwords and connection configurations are encrypted before persisting to PostgreSQL using 128-bit AES in CBC mode with HMAC SHA-256 via Python's `cryptography` library.
2. **Redaction**:
   - Raw database credentials are never exposed in API responses or logs.
   - Structured JSON logging scrubs authentication tokens and passwords.

---

## 4. Role-Based Access Control (RBAC)

The system implements four distinct organization roles:
- **Owner**: Full workspace management, billing, and member administration.
- **Admin**: Can connect/delete data sources, invite members, and configure schedules.
- **Analyst**: Can ask questions, run queries, upload datasets, and build reports.
- **Viewer**: Read-only access to published reports and dashboards.

---

## 5. Immutable Audit Trail

All security-sensitive operations are written to the `audit_events` table:
- User login / signups
- Dataset uploads and deletions
- All executed SQL queries
- All rejected/blocked SQL attempts
- Organization role modifications
