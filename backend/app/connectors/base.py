"""
Abstract Base Connector interface and common dataclasses.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ColumnInfo:
    """Metadata describing a single column in a dataset table."""
    name: str
    data_type: str
    nullable: bool = True
    is_primary_key: bool = False
    sample_values: List[Any] = field(default_factory=list)


@dataclass
class TableInfo:
    """Metadata describing a discovered database table or file sheet."""
    name: str
    schema: Optional[str] = None
    row_count: Optional[int] = None
    columns: List[ColumnInfo] = field(default_factory=list)


@dataclass
class QueryResult:
    """Standardized result wrapper for read-only database query execution."""
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: float
    truncated: bool = False


class BaseConnector(ABC):
    """
    Abstract interface for all data source connectors.
    Enforces read-only behavior, schema discovery, and safe execution.
    """

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """Test whether the data source is reachable and valid."""
        pass

    @abstractmethod
    async def discover_tables(self) -> List[TableInfo]:
        """List all accessible tables/views in the data source."""
        pass

    @abstractmethod
    async def get_table_schema(self, table_name: str) -> List[ColumnInfo]:
        """Return the column schema and types for a specific table."""
        pass

    @abstractmethod
    async def get_row_count(self, table_name: str) -> int:
        """Return the total number of rows in the table."""
        pass

    @abstractmethod
    async def get_sample_data(self, table_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch a limited sample of rows for data profiling and previews."""
        pass

    @abstractmethod
    async def execute_read_only_query(
        self,
        sql: str,
        timeout: int = 30,
        max_rows: int = 5000,
    ) -> QueryResult:
        """
        Execute an untrusted SQL query under strict read-only constraints,
        statement timeout, and maximum row limits.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Release any open connection pools or file handles."""
        pass
