# AI Business Intelligence Agent SaaS

A production-grade, multi-tenant AI Business Intelligence SaaS platform that allows businesses to connect data sources, query their data in natural language, generate validated visualizations, catch unusual trends via statistical anomaly detection, and automate recurring executive workflows.

---

## 🌟 Key Capabilities

- **Zero-Hallucination AI Agent**: Every metric, number, and visualization is generated through verified SQL queries executed against actual database tables.
- **Deterministic SQL Safety**: An Abstract Syntax Tree (AST) validation engine inspects every SQL candidate—blocking DDL/DML, multi-statement injection, dangerous functions (`pg_sleep`, `pg_read_file`), and unpermitted tables.
- **Read-Only Database Isolation**: Queries run inside read-only transactions with strict execution timeouts and row-count limits.
- **Multi-Source Ingestion**: Upload CSV and XLSX files or connect production PostgreSQL databases with Fernet-encrypted stored credentials.
- **Statistical Anomaly Detection**: Automated Z-Score and Interquartile Range (IQR) detection identifies sudden spikes, drops, and trend shifts without claiming unproven business causality.
- **Scheduled Executive Workflows**: Celery & Redis background workers generate recurring report summaries on configurable cron schedules.
- **Enterprise Multi-Tenancy**: Strict tenant isolation across API, query, and storage layers with full Role-Based Access Control (Owner, Admin, Analyst, Viewer).
- **Immutable Audit Trail**: Logs every successful query, rejected SQL statement, login, and administrative action.

---

## 🏗️ Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | Next.js 14 (App Router), TypeScript, React, Tailwind CSS, Recharts, Zustand, Lucide Icons |
| **Backend** | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0 (Async), PostgreSQL, Alembic |
| **SQL Safety** | `sqlglot` AST parser, `sqlparse` |
| **Task Queue** | Redis 7, Celery 5 (Worker + Beat Scheduler) |
| **Security** | `cryptography` (Fernet 128-bit AES), `bcrypt`, `python-jose` (JWT) |
| **DevOps** | Docker, Docker Compose, GitHub Actions CI/CD |

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- Docker & Docker Compose
- Node.js >= 20.x
- Python >= 3.11

### 2. Environment Setup
```bash
cp .env.example .env
```

### 3. Start Full Stack with Docker Compose
```bash
docker compose up -d --build
```

The services will be available at:
- **Frontend Web UI**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Backend**: [http://localhost:8000](http://localhost:8000)
- **Interactive OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **PostgreSQL**: `localhost:5432`
- **Redis**: `localhost:6379`

---

## 🧪 Running Automated Tests

The backend test suite verifies authentication, tenant isolation, SQL parser security, and end-to-end workflows:

```bash
cd backend
python -m pytest tests -v
```

### Test Coverage Highlights:
- `test_sql_validator.py`: Verifies AST-based rejection of `DROP`, `INSERT`, `UPDATE`, `pg_sleep`, multiple statements, and table access violations.
- `test_tenant_isolation.py`: Enforces that User A in Org A cannot query, preview, or access Org B's datasets.
- `test_auth.py`: Tests signup, login, password hashing, and JWT token rotation.
- `test_anomaly_detection.py`: Verifies Z-score and IQR statistical outlier detection.
- `test_e2e_workflow.py`: Exercises full cycle: CSV upload -> schema introspection -> natural language question -> SQL execution -> chart generation.

---

## 📁 Repository Structure

```
BI Agent/
├── backend/
│   ├── alembic/              # Database schema migrations
│   ├── app/
│   │   ├── ai/               # Provider-agnostic LLM client, prompts, tools
│   │   ├── api/v1/           # REST endpoints (auth, datasets, queries, reports)
│   │   ├── connectors/       # PostgreSQL, CSV, and XLSX connectors
│   │   ├── middleware/       # Auth, rate limiting, logging with request IDs
│   │   ├── models/           # SQLAlchemy 2.0 ORM models
│   │   ├── schemas/          # Pydantic v2 validation models
│   │   ├── security/         # Fernet encryption and bcrypt utilities
│   │   ├── services/         # AI orchestrator, SQL validator, anomaly engine
│   │   ├── tasks/            # Celery workers and Beat scheduler
│   │   └── main.py           # FastAPI application factory
│   ├── tests/                # Pytest integration and security suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router pages
│   │   ├── components/       # UI, Charts (Recharts), Chat, Layout
│   │   ├── lib/              # Type-safe API client & TypeScript interfaces
│   │   └── stores/           # Zustand state management
│   ├── Dockerfile
│   └── package.json
├── docs/                     # Deployment, security, and API documentation
├── .github/workflows/ci.yml   # CI/CD pipeline
├── docker-compose.yml        # Development environment
├── docker-compose.prod.yml   # Production environment
└── README.md
```

---

## 📜 Documentation

- [Deployment Guide](docs/deployment.md)
- [Security Architecture & Threat Model](docs/security.md)
- [API Reference](docs/api.md)
- [Production Launch Checklist](docs/launch-checklist.md)

---

## ⚖️ License
Proprietary & Confidential. All rights reserved.
