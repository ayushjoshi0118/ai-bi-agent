"""
CSV data source connector.
Parses CSV using pandas, creates a dedicated isolated SQLite database for high-performance read-only SQL queries.
"""

from __future__ import annotations

import os
import sqlite3
import time
from typing import Any, Dict, List
import pandas as pd
import structlog

from app.connectors.base import BaseConnector, ColumnInfo, QueryResult, TableInfo

logger = structlog.get_logger(__name__)


class CSVConnector(BaseConnector):
    """
    Connector for CSV file uploads.
    Loads data into an isolated local SQLite file/memory for safe, isolated query execution.
    """

    def __init__(self, file_path: str, table_name: str = "dataset"):
        self.file_path = file_path
        self.table_name = table_name.lower().replace(" ", "_").replace("-", "_")
        self.sqlite_path = f"{file_path}.db"
        self._initialized = False

    def _ensure_sqlite_ready(self) -> None:
        if self._initialized and os.path.exists(self.sqlite_path):
            return

        # Read CSV with pandas
        df = pd.read_csv(self.file_path, low_memory=False)
        # Clean column names to be SQL-safe (lower, alphanumeric + underscore)
        df.columns = [
            "".join(c if c.isalnum() else "_" for c in str(col)).strip("_").lower()
            for col in df.columns
        ]

        # Write to SQLite table
        conn = sqlite3.connect(self.sqlite_path)
        try:
            df.to_sql(self.table_name, conn, if_exists="replace", index=False)
        finally:
            conn.close()

        self._initialized = True

    async def test_connection(self) -> tuple[bool, str]:
        if not os.path.exists(self.file_path):
            return False, f"File does not exist: {self.file_path}"
        try:
            self._ensure_sqlite_ready()
            return True, "CSV file is valid and readable"
        except Exception as e:
            return False, f"Failed to parse CSV: {str(e)}"

    async def discover_tables(self) -> List[TableInfo]:
        self._ensure_sqlite_ready()
        cols = await self.get_table_schema(self.table_name)
        count = await self.get_row_count(self.table_name)
        return [
            TableInfo(
                name=self.table_name,
                schema="default",
                row_count=count,
                columns=cols,
            )
        ]

    async def get_table_schema(self, table_name: str) -> List[ColumnInfo]:
        self._ensure_sqlite_ready()
        conn = sqlite3.connect(self.sqlite_path)
        try:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({self.table_name})")
            rows = cursor.fetchall()
            columns = []
            for r in rows:
                col_name = r[1]
                col_type = r[2] or "TEXT"
                not_null = bool(r[3])
                pk = bool(r[5])
                columns.append(
                    ColumnInfo(
                        name=col_name,
                        data_type=col_type,
                        nullable=not not_null,
                        is_primary_key=pk,
                    )
                )
            return columns
        finally:
            conn.close()

    async def get_row_count(self, table_name: str) -> int:
        self._ensure_sqlite_ready()
        conn = sqlite3.connect(self.sqlite_path)
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            row = cursor.fetchone()
            return int(row[0] if row else 0)
        finally:
            conn.close()

    async def get_sample_data(self, table_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        self._ensure_sqlite_ready()
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {self.table_name} LIMIT {limit}")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    async def execute_read_only_query(
        self,
        sql: str,
        timeout: int = 30,
        max_rows: int = 5000,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> QueryResult:
        self._ensure_sqlite_ready()
        start_time = time.perf_counter()

        clean_sql = sql.rstrip(";").strip()

        # Connect with read-only URI
        uri = f"file:{self.sqlite_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=timeout)
        conn.row_factory = sqlite3.Row

        # Engine-level SQLite Authorizer: fail-closed against any write/DDL
        def _authorizer(action, p1, p2, db_name, trigger_name):
            # 21 = SQLITE_SELECT, 20 = SQLITE_READ, 31 = SQLITE_FUNCTION
            if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION):
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        conn.set_authorizer(_authorizer)

        try:
            cursor = conn.cursor()
            # Wrap query to enforce max row limits
            wrapped_sql = f"SELECT * FROM ({clean_sql}) LIMIT {max_rows + 1}"
            cursor.execute(wrapped_sql)
            rows = cursor.fetchall()
            execution_time_ms = (time.perf_counter() - start_time) * 1000

            truncated = len(rows) > max_rows
            active_rows = rows[:max_rows]

            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            data = []
            total_bytes = 0
            max_bytes = 10 * 1024 * 1024  # 10 MB

            for r in active_rows:
                d = dict(r)
                row_bytes = len(str(d))
                if total_bytes + row_bytes > max_bytes:
                    truncated = True
                    break
                total_bytes += row_bytes
                data.append(d)

            return QueryResult(
                columns=columns,
                rows=data,
                row_count=len(data),
                execution_time_ms=round(execution_time_ms, 2),
                truncated=truncated,
            )
        finally:
            conn.close()

    async def close(self) -> None:
        pass
