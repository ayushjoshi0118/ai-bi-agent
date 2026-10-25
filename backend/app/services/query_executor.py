"""
Safe Read-Only Query Execution Engine.
Hardened with schema-validated query plans, RBAC permission gates, AST safety checks,
database-enforced timeouts, RLS tenant context, and immutable audit logs.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.config import get_settings
from app.connectors.base import QueryResult
from app.models.dataset import Dataset
from app.models.organization import OrgMembership, OrgRole
from app.models.query import ExecutionStatus, QueryExecution, ValidationStatus
from app.monitoring.metrics import metrics_collector
from app.schemas.query_plan import QueryPlan
from app.security.redaction import redact_string
from app.services.audit_service import AuditService
from app.services.data_source_service import DataSourceService
from app.services.sql_validator import SQLValidator

logger = structlog.get_logger(__name__)
settings = get_settings()


class QueryExecutor:
    @staticmethod
    async def execute_query(
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        dataset_id: uuid.UUID,
        sql_query: str,
        message_id: Optional[uuid.UUID] = None,
        custom_timeout: Optional[int] = None,
        query_plan: Optional[QueryPlan] = None,
    ) -> tuple[QueryExecution, Optional[QueryResult]]:
        """
        Validate, audit, and execute an untrusted read-only query against the target dataset's data source.
        Enforces:
        1. Role-based execution authorization (rejects Viewers from arbitrary query execution)
        2. Strict tenant-ownership of dataset
        3. Optional typed QueryPlan schema conformance
        4. AST-based fail-closed SQL validation
        5. Database-level read-only isolation with RLS session variables
        6. Comprehensive audit trail for both accepted and rejected attempts
        """
        # 1. Authorize User Organization Membership and Role
        stmt_mem = select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == user_id,
        )
        mem_res = await db.execute(stmt_mem)
        membership = mem_res.scalar_one_or_none()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have access to this organization",
            )

        if membership.role == OrgRole.VIEWER:
            await AuditService.log_event(
                db,
                org_id=org_id,
                user_id=user_id,
                action="query.forbidden_role",
                resource_type="dataset",
                resource_id=dataset_id,
                details={"role": membership.role.value, "reason": "Viewers cannot execute arbitrary queries"},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Viewer role is not permitted to execute ad-hoc analytical queries",
            )

        # 2. Fetch Dataset with underlying DataSource (strictly scoped by org_id)
        stmt_ds = (
            select(Dataset)
            .options(selectinload(Dataset.data_source))
            .where(Dataset.id == dataset_id, Dataset.org_id == org_id)
        )
        res = await db.execute(stmt_ds)
        dataset = res.scalar_one_or_none()

        if not dataset or not dataset.data_source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset or underlying data source not found in organization",
            )

        # 3. Validate Query Plan if provided
        plan_details = {}
        if query_plan:
            if query_plan.dataset_id != dataset_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Query plan dataset_id does not match execution target dataset",
                )
            plan_details = query_plan.model_dump(mode="json")

        # 4. Determine dialect and allowed tables allowlist
        dialect = "postgres" if dataset.data_source.source_type.value == "postgresql" else "sqlite"
        allowed_tables = {dataset.table_name.lower().strip()}

        validator = SQLValidator(allowed_tables=allowed_tables, dialect=dialect)
        val_result = validator.validate(sql_query)

        # 5. Create immutable QueryExecution record (Audit Trail)
        execution_record = QueryExecution(
            org_id=org_id,
            dataset_id=dataset_id,
            message_id=message_id,
            sql_query=sql_query,
            validation_status=ValidationStatus.VALID if val_result.is_valid else ValidationStatus.REJECTED,
            validation_details={
                "errors": val_result.errors,
                "warnings": val_result.warnings,
                "tables_referenced": val_result.tables_referenced,
                "query_plan": plan_details,
            },
            execution_status=ExecutionStatus.PENDING,
        )
        db.add(execution_record)
        await db.commit()
        await db.refresh(execution_record)

        # 6. Fail-Closed Check: If validation failed, reject immediately. Never contact database!
        if not val_result.is_valid:
            execution_record.execution_status = ExecutionStatus.FAILED
            execution_record.error_message = "; ".join(val_result.errors)
            await db.commit()

            await AuditService.log_event(
                db,
                org_id=org_id,
                user_id=user_id,
                action="query.rejected",
                resource_type="query_execution",
                resource_id=execution_record.id,
                details={
                    "errors": val_result.errors,
                    "tables_referenced": val_result.tables_referenced,
                    "sql": redact_string(sql_query),
                },
            )
            return execution_record, None

        # 7. Execute validated query using read-only connector with RLS context
        execution_record.execution_status = ExecutionStatus.RUNNING
        await db.commit()

        connector = DataSourceService.get_connector(dataset.data_source)
        timeout = custom_timeout or settings.query_timeout_seconds
        max_rows = settings.query_max_rows

        try:
            query_result = await connector.execute_read_only_query(
                sql=val_result.sanitized_sql or sql_query,
                timeout=timeout,
                max_rows=max_rows,
                tenant_id=str(org_id),
                user_id=str(user_id),
            )

            execution_record.execution_status = ExecutionStatus.COMPLETED
            execution_record.row_count = query_result.row_count
            execution_record.execution_time_ms = query_result.execution_time_ms
            metrics_collector.record_query(duration_ms=query_result.execution_time_ms)
            execution_record.result_summary = {
                "columns": query_result.columns,
                "row_count": query_result.row_count,
                "truncated": query_result.truncated,
            }
            # Store first 100 rows preview in DB record for quick retrieval
            execution_record.result_data = query_result.rows[:100]
            await db.commit()

            await AuditService.log_event(
                db,
                org_id=org_id,
                user_id=user_id,
                action="query.execute",
                resource_type="query_execution",
                resource_id=execution_record.id,
                details={
                    "rows": query_result.row_count,
                    "duration_ms": query_result.execution_time_ms,
                    "truncated": query_result.truncated,
                },
            )
            return execution_record, query_result

        except (asyncio.TimeoutError, TimeoutError) as te:
            logger.warning("query_execution_timed_out", sql=redact_string(sql_query), timeout=timeout)
            execution_record.execution_status = ExecutionStatus.TIMEOUT
            execution_record.error_message = f"Query timed out after {timeout} seconds"
            await db.commit()

            await AuditService.log_event(
                db,
                org_id=org_id,
                user_id=user_id,
                action="query.timeout",
                resource_type="query_execution",
                resource_id=execution_record.id,
                details={"timeout_seconds": timeout},
            )
            return execution_record, None

        except Exception as e:
            raw_err = str(e)
            safe_err = redact_string(raw_err)
            logger.error("query_execution_failed", error=safe_err, sql=redact_string(sql_query))
            execution_record.execution_status = ExecutionStatus.FAILED
            execution_record.error_message = safe_err
            await db.commit()

            await AuditService.log_event(
                db,
                org_id=org_id,
                user_id=user_id,
                action="query.failed",
                resource_type="query_execution",
                resource_id=execution_record.id,
                details={"error": safe_err, "sql": redact_string(sql_query)},
            )
            return execution_record, None
        finally:
            await connector.close()
