"""
PostgreSQL Least-Privilege Role & Row-Level Security Integration Tests.
Executes against an isolated PostgreSQL instance to verify engine-level defenses:
1. Least-privilege role permits SELECT on approved tables only
2. Rejection of INSERT, UPDATE, DELETE, and DROP at the database permission level
3. Rejection of ungranted tables (secret_credentials) and system tables (pg_shadow)
4. Row-Level Security (RLS) enforcement isolating Tenant A from Tenant B
5. Statement timeout cancellation at the engine level
6. Connection pool session cleanup
"""

from __future__ import annotations

import asyncpg
import pytest

from app.connectors.postgres import PostgresConnector

PG_PORT = 5433
PG_DB = "bi_security_test"
PG_USER = "bi_analytics_readonly"
PG_PASS = "readonly_secret_pass"

ORG_A = "11111111-1111-1111-1111-111111111111"
ORG_B = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def pg_connector() -> PostgresConnector:
    connector = PostgresConnector(
        host="localhost",
        port=PG_PORT,
        database=PG_DB,
        user=PG_USER,
        password=PG_PASS,
        schema="public",
        ssl=False,
    )
    return connector


@pytest.mark.asyncio
async def test_postgres_least_privilege_select_and_rls_org_a(pg_connector: PostgresConnector):
    """Verify that Org A can read its own records but cannot see Org B records via RLS."""
    try:
        res = await pg_connector.execute_read_only_query(
            sql="SELECT customer, amount FROM tenant_orders ORDER BY customer",
            tenant_id=ORG_A,
            timeout=10,
        )
        assert res.row_count == 2
        customers = [r["customer"] for r in res.rows]
        assert "Customer Org A 1" in customers
        assert "Customer Org A 2" in customers
        assert "Customer Org B 1" not in customers
    finally:
        await pg_connector.close()


@pytest.mark.asyncio
async def test_postgres_least_privilege_select_and_rls_org_b(pg_connector: PostgresConnector):
    """Verify that Org B can read its own records but cannot see Org A records via RLS."""
    try:
        res = await pg_connector.execute_read_only_query(
            sql="SELECT customer, amount FROM tenant_orders ORDER BY customer",
            tenant_id=ORG_B,
            timeout=10,
        )
        assert res.row_count == 1
        assert res.rows[0]["customer"] == "Customer Org B 1"
    finally:
        await pg_connector.close()


@pytest.mark.asyncio
async def test_postgres_engine_blocks_insert(pg_connector: PostgresConnector):
    """Even if an attacker bypassed the API validator, PostgreSQL itself rejects writes."""
    try:
        # 1. Via query wrapper
        with pytest.raises((asyncpg.exceptions.InsufficientPrivilegeError, asyncpg.exceptions.PostgresSyntaxError)):
            await pg_connector.execute_read_only_query(
                sql=f"INSERT INTO tenant_orders (org_id, customer, amount) VALUES ('{ORG_A}', 'Injected', 999)",
                tenant_id=ORG_A,
            )

        # 2. Directly against connection: InsufficientPrivilegeError / PostgresError
        pool = await pg_connector.get_pool()
        async with pool.acquire() as conn:
            with pytest.raises((asyncpg.exceptions.InsufficientPrivilegeError, asyncpg.exceptions.PostgresError)):
                async with conn.transaction(readonly=True):
                    await conn.execute(f"INSERT INTO tenant_orders (org_id, customer, amount) VALUES ('{ORG_A}', 'Direct', 999)")
    finally:
        await pg_connector.close()


@pytest.mark.asyncio
async def test_postgres_engine_blocks_drop_table(pg_connector: PostgresConnector):
    """PostgreSQL rejects DDL execution for the read-only analytics role."""
    try:
        # 1. Via query wrapper
        with pytest.raises((asyncpg.exceptions.InsufficientPrivilegeError, asyncpg.exceptions.PostgresSyntaxError)):
            await pg_connector.execute_read_only_query(
                sql="DROP TABLE tenant_orders",
                tenant_id=ORG_A,
            )

        # 2. Directly against connection
        pool = await pg_connector.get_pool()
        async with pool.acquire() as conn:
            with pytest.raises((asyncpg.exceptions.InsufficientPrivilegeError, asyncpg.exceptions.PostgresError)):
                async with conn.transaction(readonly=True):
                    await conn.execute("DROP TABLE tenant_orders")
    finally:
        await pg_connector.close()


@pytest.mark.asyncio
async def test_postgres_engine_blocks_unauthorized_table_access(pg_connector: PostgresConnector):
    """PostgreSQL rejects SELECT on tables where no grant exists (secret_credentials)."""
    try:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError, match="permission denied for table secret_credentials"):
            await pg_connector.execute_read_only_query(
                sql="SELECT * FROM secret_credentials",
                tenant_id=ORG_A,
            )
    finally:
        await pg_connector.close()


@pytest.mark.asyncio
async def test_postgres_engine_blocks_pg_shadow_access(pg_connector: PostgresConnector):
    """PostgreSQL rejects system catalog access to sensitive password hashes."""
    try:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError, match="permission denied for (table|view) pg_shadow"):
            await pg_connector.execute_read_only_query(
                sql="SELECT * FROM pg_shadow",
                tenant_id=ORG_A,
            )
    finally:
        await pg_connector.close()


@pytest.mark.asyncio
async def test_postgres_statement_timeout_enforced(pg_connector: PostgresConnector):
    """PostgreSQL engine cancels queries that exceed statement_timeout."""
    try:
        with pytest.raises(asyncpg.exceptions.QueryCanceledError, match="canceling statement due to statement timeout"):
            await pg_connector.execute_read_only_query(
                sql="SELECT pg_sleep(3)",
                timeout=1,
                tenant_id=ORG_A,
            )
    finally:
        await pg_connector.close()


@pytest.mark.asyncio
async def test_postgres_connection_pool_session_cleanup(pg_connector: PostgresConnector):
    """Verify that tenant context does not leak across pooled connection acquisitions."""
    try:
        # Run query with tenant A
        await pg_connector.execute_read_only_query(
            sql="SELECT 1",
            tenant_id=ORG_A,
        )

        pool = await pg_connector.get_pool()
        async with pool.acquire() as conn:
            # Check current_setting without tenant set
            val = await conn.fetchval("SELECT current_setting('app.current_tenant_id', true)")
            # Must be None or empty string
            assert val is None or val == ""
    finally:
        await pg_connector.close()
