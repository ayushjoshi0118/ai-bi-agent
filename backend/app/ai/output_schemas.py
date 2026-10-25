"""
Pydantic schemas for structured AI outputs and planning.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QueryPlanStep(BaseModel):
    step_number: int
    intent: str
    target_table: str
    target_columns: List[str] = Field(default_factory=list)
    sql_candidate: Optional[str] = None


class StructuredAnalysisPlan(BaseModel):
    business_question: str
    interpretation: str
    relevant_tables: List[str]
    steps: List[QueryPlanStep]


class BusinessInsight(BaseModel):
    executive_summary: str
    key_findings: List[str]
    metric_provenance: Dict[str, Any] = Field(
        default_factory=dict,
        description="Traceable reference of metrics to actual SQL row values",
    )
    potential_caveats: List[str] = Field(default_factory=list)
