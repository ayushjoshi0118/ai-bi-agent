"""
Query execution history and audit endpoints.
"""

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_org, get_db
from app.models.organization import OrgRole, Organization
from app.models.query import QueryExecution
from app.schemas.query import QueryExecutionResponse

router = APIRouter(prefix="/queries", tags=["Queries"])


@router.get("", response_model=List[QueryExecutionResponse])
async def list_query_executions(
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    stmt = (
        select(QueryExecution)
        .where(QueryExecution.org_id == org.id)
        .order_by(QueryExecution.created_at.desc())
        .limit(100)
    )
    res = await db.execute(stmt)
    records = res.scalars().all()
    out = []
    for r in records:
        out.append(
            QueryExecutionResponse(
                id=r.id,
                sql_query=r.sql_query,
                validation_status=r.validation_status.value,
                execution_status=r.execution_status.value,
                result_summary=r.result_summary,
                row_count=r.row_count,
                execution_time_ms=r.execution_time_ms,
                executed_at=r.created_at,
            )
        )
    return out


@router.get("/{query_id}", response_model=QueryExecutionResponse)
async def get_query_execution(
    query_id: uuid.UUID,
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    stmt = select(QueryExecution).where(QueryExecution.id == query_id, QueryExecution.org_id == org.id)
    res = await db.execute(stmt)
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Query record not found")

    return QueryExecutionResponse(
        id=r.id,
        sql_query=r.sql_query,
        validation_status=r.validation_status.value,
        execution_status=r.execution_status.value,
        result_summary=r.result_summary,
        row_count=r.row_count,
        execution_time_ms=r.execution_time_ms,
        executed_at=r.created_at,
    )
