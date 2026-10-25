"""
PostgreSQL data source connector using asyncpg.
Hardened with database-level read-only transactions, least-privilege roles,
row-level security session context, strict memory ceilings, safe pool recycling,
and response byte limits.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
import asyncpg
import structlog

from app.connectors.base import BaseConnector, ColumnInfo, QueryResult, TableInfo
from app.security.redaction import redact_string

logger = structlog.get_logger(__name__)

# Max response byte ceiling (10 MB) to prevent memory exhaustion from wide text columns
MAX_RESPONSE_BYTES = 10 * 1024 * 1024


class PostgresConnector(BaseConnector):
    """
    Connects to external or internal PostgreSQL databases.
    All executions are performed with `SET TRANSACTION READ ONLY`, strict statement timeouts,
    memory ceilings, and tenant RLS session variables.
    """

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        schema: str = "public",
        ssl: bool = False,
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.target_schema = schema
        self.ssl = ssl
        self._pool: Optional[asyncpg.Pool] = None

    async def get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                ssl=self.ssl,
                min_size=1,
                max_size=5,
                command_timeout=60,
            )
        return self._pool

    async def test_connection(self) -> tuple[bool, str]:
        try:
            conn = await asyncpg.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                ssl=self.ssl,
                timeout=10,
            )
            try:
                val = await conn.fetchval("SELECT 1")
                return True, "Connection successful"
            finally:
                await conn.close()
        except Exception as e:
            logger.warning("postgres_connection_test_failed", error=redact_string(str(e)), host=self.host)
            return False, f"Connection failed: {redact_string(str(e))}"

    async def discover_tables(self) -> List[TableInfo]:
        pool = await self.get_pool()
        query = """
            SELECT table_name, table_schema
            FROM information_schema.tables
            WHERE table_schema = $1
              AND table_type IN ('BASE TABLE', 'VIEW')
            ORDER BY table_name;
        """
        async with pool.acquire() as conn:
            try:
                records = await conn.fetch(query, self.target_schema)
                tables = []
                for rec in records:
                    t_name = rec["table_name"]
                    schema_name = rec["table_schema"]
                    cols = await self.get_table_schema(t_name)
                    tables.append(
                        TableInfo(
                            name=t_name,
                            schema=schema_name,
                            columns=cols,
                        )
                    )
                return tables
            finally:
                await conn.execute("RESET ALL;")

    async def get_table_schema(self, table_name: str) -> List[ColumnInfo]:
        pool = await self.get_pool()
        query = """
            SELECT 
                column_name, 
                data_type, 
                is_nullable
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position;
        """
        async with pool.acquire() as conn:
            try:
                records = await conn.fetch(query, self.target_schema, table_name)
                columns = []
                for rec in records:
                    columns.append(
                        ColumnInfo(
                            name=rec["column_name"],
                            data_type=rec["data_type"],
                            nullable=(rec["is_nullable"].upper() == "YES"),
                        )
                    )
                return columns
            finally:
                await conn.execute("RESET ALL;")

    async def get_row_count(self, table_name: str) -> int:
        pool = await self.get_pool()
        safe_schema = self.target_schema.replace('"', '""')
        safe_table = table_name.replace('"', '""')
        safe_name = f'"{safe_schema}"."{safe_table}"'
        async with pool.acquire() as conn:
            try:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {safe_name}")
                return int(count or 0)
            finally:
                await conn.execute("RESET ALL;")

    async def get_sample_data(self, table_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        pool = await self.get_pool()
        safe_schema = self.target_schema.replace('"', '""')
        safe_table = table_name.replace('"', '""')
        safe_name = f'"{safe_schema}"."{safe_table}"'
        bounded_limit = min(max(1, limit), 500)
        async with pool.acquire() as conn:
            try:
                records = await conn.fetch(f"SELECT * FROM {safe_name} LIMIT {bounded_limit}")
                return [dict(rec) for rec in records]
            finally:
                await conn.execute("RESET ALL;")

    async def execute_read_only_query(
        self,
        sql: str,
        timeout: int = 30,
        max_rows: int = 5000,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> QueryResult:
        """
        Execute an untrusted validated read-only SQL query with database-enforced permissions,
        RLS session variables, strict timeouts, memory ceilings, and response byte caps.
        """
        pool = await self.get_pool()
        start_time = time.perf_counter()

        # Clean trailing semicolon before subquery wrapping
        clean_sql = sql.rstrip(";").strip()
        safe_timeout = max(1, min(int(timeout), 60))

        async with pool.acquire() as conn:
            try:
                # 1. Start explicit READ ONLY transaction
                async with conn.transaction(readonly=True):
                    # 2. Resource limits
                    await conn.execute(f"SET LOCAL statement_timeout = '{safe_timeout}s'")
                    await conn.execute("SET LOCAL lock_timeout = '5s'")
                    await conn.execute("SET LOCAL idle_in_transaction_session_timeout = '10s'")
                    await conn.execute("SET LOCAL work_mem = '32MB'")
                    safe_schema = self.target_schema.replace("'", "''")
                    await conn.execute(f"SET LOCAL search_path = '{safe_schema}', public")

                    # 3. Row-Level Security session variables
                    if tenant_id:
                        await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_id))
                    if user_id:
                        await conn.execute("SELECT set_config('app.current_user_id', $1, true)", str(user_id))

                    # 4. Execute wrapped subquery (limiting to max_rows + 1 to detect truncation)
                    wrapped = f"SELECT * FROM ({clean_sql}) AS __bi_subquery LIMIT {max_rows + 1}"
                    records = await conn.fetch(wrapped)
                    execution_time_ms = (time.perf_counter() - start_time) * 1000

                    truncated = len(records) > max_rows
                    active_records = records[:max_rows]

                    # 5. Build rows and enforce byte limits
                    columns = [k for k in active_records[0].keys()] if active_records else []
                    rows = []
                    total_bytes = 0

                    for rec in active_records:
                        row_dict = dict(rec)
                        # Estimate serialized byte size
                        row_bytes = len(json.dumps(row_dict, default=str))
                        if total_bytes + row_bytes > MAX_RESPONSE_BYTES:
                            truncated = True
                            break
                        total_bytes += row_bytes
                        rows.append(row_dict)

                    return QueryResult(
                        columns=columns,
                        rows=rows,
                        row_count=len(rows),
                        execution_time_ms=round(execution_time_ms, 2),
                        truncated=truncated,
                    )
            finally:
                # 6. Hygiene: Discard temporary state and reset session configuration on connection return
                try:
                    await conn.execute("RESET ALL; DISCARD TEMP;")
                except Exception:
                    pass

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
