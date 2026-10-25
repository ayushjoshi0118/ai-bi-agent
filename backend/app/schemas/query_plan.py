"""
Typed Query Plan Schema for deterministic LLM query validation.
Requires the LLM to structure its query intent, target tables, metrics, filters, and SQL
into an explicit schema before any query execution is permitted.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class FilterPredicate(BaseModel):
    """Structured representation of a single filter condition."""
    column: str = Field(..., max_length=100)
    operator: Literal["=", "!=", ">", ">=", "<", "<=", "IN", "NOT IN", "BETWEEN", "LIKE", "IS NULL", "IS NOT NULL"]
    value: Any


class QueryPlan(BaseModel):
    """
    Strict, typed representation of an analytical query plan.
    All untrusted model outputs must conform to this schema prior to database execution.
    """
    plan_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    dataset_id: uuid.UUID = Field(..., description="Target dataset UUID")
    intent: Literal["aggregation", "filtering", "time_series", "comparison", "trend", "distribution", "lookup"]
    target_tables: List[str] = Field(..., min_length=1, max_length=10, description="List of tables to be queried")
    selected_metrics: List[str] = Field(..., min_length=1, description="Target numeric or aggregated metric columns")
    grouping_dimensions: List[str] = Field(default_factory=list, description="Categorical or time grouping columns")
    filters: List[FilterPredicate] = Field(default_factory=list, description="Filter conditions applied")
    sql_statement: str = Field(..., min_length=5, max_length=10000, description="The proposed read-only SQL query")
    estimated_rows: int = Field(default=100, ge=1, le=50000, description="Estimated row count returned")
    explanation: str = Field(..., min_length=5, max_length=2000, description="Rationale for how this query answers the question")

    @field_validator("target_tables")
    @classmethod
    def validate_tables(cls, v: List[str]) -> List[str]:
        cleaned = []
        for tbl in v:
            name = tbl.strip().lower()
            if not re.match(r"^[a-zA-Z0-9_]+$", name):
                raise ValueError(f"Invalid table identifier '{tbl}' in query plan")
            cleaned.append(name)
        return cleaned

    @field_validator("sql_statement")
    @classmethod
    def validate_sql_not_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("SQL statement cannot be empty")
        # Fail fast if stacked semicolons exist in raw plan
        if ";" in s[:-1]:  # semicolon in the middle
            raise ValueError("Multiple statements or internal semicolons prohibited in query plan")
        return s
