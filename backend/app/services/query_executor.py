"""
Safe read-only Query Execution Engine.
Validates SQL through SQLValidator, enforces timeouts, row limits, and records immutable QueryExecution records.
"""

from __future__ import annotations

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
from app.models.query import ExecutionStatus, QueryExecution, ValidationStatus
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
    ) -> tuple[QueryExecution, Optional[QueryResult]]:
        """
        Validate, audit, and execute an untrusted read-only query against the target dataset's data source.
        """
        # 1. Fetch Dataset and DataSource
        stmt = (
            select(Dataset)
            .options(selectinload(Dataset.data_source))
            .where(Dataset.id == dataset_id, Dataset.org_id == org_id)
        )
        res = await db.execute(stmt)
        dataset = res.scalar_one_or_none()

        if not dataset or not dataset.data_source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset or underlying data source not found",
            )

        # 2. Determine dialect and allowed tables
        dialect = "postgres" if dataset.data_source.source_type.value == "postgresql" else "sqlite"
        allowed_tables = {dataset.table_name.lower()}

        validator = SQLValidator(allowed_tables=allowed_tables, dialect=dialect)
        val_result = validator.validate(sql_query)

        # 3. Create QueryExecution record (Audit Trail)
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
            },
            execution_status=ExecutionStatus.PENDING,
        )
        db.add(execution_record)
        await db.commit()
        await db.refresh(execution_record)

        # If validation failed, reject immediately and record
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
                details={"errors": val_result.errors, "sql": sql_query},
            )
            return execution_record, None

        # 4. Execute validated query using read-only connector
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
            )

            execution_record.execution_status = ExecutionStatus.COMPLETED
            execution_record.row_count = query_result.row_count
            execution_record.execution_time_ms = query_result.execution_time_ms
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

        except Exception as e:
            err_msg = str(e)
            logger.error("query_execution_failed", error=err_msg, sql=sql_query)
            execution_record.execution_status = ExecutionStatus.FAILED
            execution_record.error_message = err_msg
            await db.commit()

            await AuditService.log_event(
                db,
                org_id=org_id,
                user_id=user_id,
                action="query.failed",
                resource_type="query_execution",
                resource_id=execution_record.id,
                details={"error": err_msg, "sql": sql_query},
            )
            return execution_record, None
        finally:
            await connector.close()
