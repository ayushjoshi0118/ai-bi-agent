# BI Agent Security Threat Model & Defense Architecture

## 1. Executive Summary

The AI Business Intelligence Agent platform empowers users to query internal databases and uploaded datasets using natural language. Because the platform leverages Large Language Models (LLMs) to synthesize and execute SQL queries dynamically, it represents a high-risk operational boundary. This document outlines the comprehensive threat model (based on STRIDE and OWASP Top 10 for LLMs) and details the defense-in-depth architecture implemented to mitigate these risks.

---

## 2. Threat Modeling (STRIDE Analysis)

| Threat Category | Specific Attack Vector | Potential Impact | Implemented Mitigation |
| :--- | :--- | :--- | :--- |
| **Spoofing** | Attacker impersonates legitimate user or injects fake tenant credentials | Cross-tenant data breach, account takeover | Cryptographically signed JWT tokens, Argon2id password hashing, strict org membership resolution on every API request. |
| **Tampering** | Model prompt injection via database contents or user questions attempts to alter tool permissions or SQL generation | Unauthorized data modifications (INSERT, UPDATE, DELETE, DROP), privilege escalation | **Zero Trust on LLM Output**: Strict Pydantic `QueryPlan` validation, AST-based SQL policy validation, DB-level read-only transactions, unprivileged database roles. |
| **Repudiation** | Malicious queries executed without accountability | Inability to audit security incidents or prove non-involvement | Mandatory `AuditEvent` persistence for every query attempt (approved, rejected, or failed), logging user ID, org ID, query hash, AST metrics, and client IP. |
| **Information Disclosure** | SQL injection via stacked queries, UNION attacks, CTE exfiltration, or accessing PostgreSQL metadata tables (`pg_authid`, `pg_shadow`) | Leaking system credentials, cross-tenant data leaks, PII exposure | AST allowlisting of permitted tables only, blocking `pg_catalog` and `information_schema`, PostgreSQL Row-Level Security (RLS) enforcement, automatic PII/credential redaction in logs and client outputs. |
| **Denial of Service** | Resource exhaustion via Cartesian joins, infinite loops, `pg_sleep()`, oversized result payloads | System downtime, database connection starvation, memory exhaustion | Strict statement timeout (15s), lock timeout (5s), work_mem ceiling (32MB), response byte ceiling (10MB), row limits (5,000 max), SQLite authorizer opcode constraints. |
| **Elevation of Privilege** | Viewers attempting ad-hoc query execution; database connection pool pollution where elevated permissions persist across queries | Viewers accessing unauthorized analytics, attackers executing code on host via DB extensions | RBAC authorization checks on all query paths and tools (`VIEWER` cannot execute queries), session isolation with `RESET ALL; DISCARD TEMP;` upon connection release to pool. |

---

## 3. Defense-in-Depth Architecture

The system enforces six independent security boundaries:

```
[ User Request ]
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Boundary 1: API Authentication & Organization RBAC          │
│ - JWT verification & tenant context binding                 │
│ - OrgRole enforcement (ADMIN, ANALYST, VIEWER [read-only])  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Boundary 2: Prompt Framing & Untrusted Boundary Isolation   │
│ - DB schema comments and sample data enclosed in untrusted  │
│   delimiters: `<<<UNTRUSTED_SCHEMA_CONTEXT>>>`              │
│ - Tool execution authorization check on every invocation    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Boundary 3: Typed QueryPlan Validation                     │
│ - Pydantic schema validation for intent and targets         │
│ - Sanitization of target table identifiers                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Boundary 4: AST-Based SQL Policy Validator (Fail-Closed)   │
│ - sqlglot parsing with PostgreSQL/SQLite dialect awareness  │
│ - Single statement enforcement                              │
│ - Disallow all DDL/DML/TCL/Administrative AST nodes         │
│ - Permitted tables allowlist validation (CTEs & Subqueries) │
│ - System catalogs & dangerous functions blocklist           │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Boundary 5: Database Engine Least-Privilege & RLS           │
│ - Dedicated unprivileged role: `bi_analytics_readonly`      │
│ - PostgreSQL read-only transaction mode (`readonly=True`)   │
│ - Row-Level Security (RLS) bound to `app.current_tenant_id` │
│ - SQLite Engine Authorizer rejecting writes at C-level      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Boundary 6: Resource Governance & Connection Hygiene        │
│ - Statement timeout (15s), lock timeout (5s), work_mem (32MB)│
│ - Max response size (10MB), Max rows (5,000)                │
│ - Connection pool sanitization: `RESET ALL; DISCARD TEMP;`   │
│ - XSS payload rejection on chart specs & output redaction   │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Key Threat Mitigations & Implementation Proof

### 4.1 SQL Injection & Semantic Privilege Escalation
- **AST Parsing**: Every generated SQL string is parsed into an Abstract Syntax Tree using `sqlglot`. Regex is never used as the primary defense.
- **Fail-Closed Validation**: If a query cannot be parsed, contains multiple statements, or contains any node other than `exp.Select` or `exp.Union`, it is rejected before touching the database.
- **Denial Audit Trail**: Every rejected query immediately logs a `query.rejected` audit event with the failure reason and client context.

### 4.2 Cross-Tenant Isolation
- **Application Context**: Queries set session variables `app.current_tenant_id` and `app.current_user_id` inside localized transactions.
- **PostgreSQL Row-Level Security (RLS)**: Enforces `USING (org_id = current_setting('app.current_tenant_id', true)::uuid)` at the database engine level.
- **Connection Pool Hygiene**: Upon transaction completion, connections execute `RESET ALL; DISCARD TEMP;` before returning to the pool, preventing tenant leakage.

### 4.3 Indirect Prompt Injection & Untrusted Data
- User-supplied files (CSV, Excel) and database contents may contain prompt injection attacks designed to trick the LLM into calling destructive functions.
- Schemas and preview data are framed within strict untrusted boundary delimiters.
- Every tool called by the LLM orchestrator verifies that the target dataset belongs to the authorized organization.

### 4.4 Stored XSS via Visualizations
- All chart specifications (`ChartSpec`, `AxisConfig`) are validated using Pydantic regex patterns that reject HTML tags, `<script>`, `javascript:`, and inline DOM event handlers (`onload=`, `onerror=`).
- Frontend rendering uses native SVG/Canvas components with escaped text elements.
