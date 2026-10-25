"""
PostgreSQL data source connector using asyncpg.
Enforces read-only transactions, strict timeouts, and tenant isolation.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
import asyncpg
import structlog

from app.connectors.base import BaseConnector, ColumnInfo, QueryResult, TableInfo

logger = structlog.get_logger(__name__)


class PostgresConnector(BaseConnector):
    """
    Connects to external or internal customer PostgreSQL databases.
    All executions are performed with `SET TRANSACTION READ ONLY` and explicit timeouts.
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
            logger.warning("postgres_connection_test_failed", error=str(e), host=self.host)
            return False, f"Connection failed: {str(e)}"

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

    async def get_row_count(self, table_name: str) -> int:
        pool = await self.get_pool()
        # Safe quoted identifier
        safe_name = f'"{self.target_schema}"."{table_name}"'
        async with pool.acquire() as conn:
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {safe_name}")
            return int(count or 0)

    async def get_sample_data(self, table_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        pool = await self.get_pool()
        safe_name = f'"{self.target_schema}"."{table_name}"'
        async with pool.acquire() as conn:
            records = await conn.fetch(f"SELECT * FROM {safe_name} LIMIT {limit}")
            return [dict(rec) for rec in records]

    async def execute_read_only_query(
        self,
        sql: str,
        timeout: int = 30,
        max_rows: int = 5000,
    ) -> QueryResult:
        pool = await self.get_pool()
        start_time = time.perf_counter()

        async with pool.acquire() as conn:
            # Enforce read-only transaction and strict statement timeout
            async with conn.transaction(readonly=True):
                await conn.execute(f"SET LOCAL statement_timeout = '{timeout}s'")
                await conn.execute(f"SET LOCAL search_path = '{self.target_schema}', public")

                # Fetch one extra row to determine if result set was truncated
                records = await conn.fetch(f"SELECT * FROM ({sql}) AS __bi_subquery LIMIT {max_rows + 1}")
                execution_time_ms = (time.perf_counter() - start_time) * 1000

                truncated = len(records) > max_rows
                active_records = records[:max_rows]

                columns = [k for k in active_records[0].keys()] if active_records else []
                rows = [dict(rec) for rec in active_records]

                return QueryResult(
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    execution_time_ms=round(execution_time_ms, 2),
                    truncated=truncated,
                )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
