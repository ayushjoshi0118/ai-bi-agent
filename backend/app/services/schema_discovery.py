"""
Schema discovery, table introspection, and dataset profiling service.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.connectors.base import BaseConnector
from app.models.data_source import DataSource, DataSourceStatus
from app.models.dataset import Dataset, DatasetStatus
from app.services.audit_service import AuditService
from app.services.data_source_service import DataSourceService

logger = structlog.get_logger(__name__)


class SchemaDiscoveryService:
    @staticmethod
    async def discover_and_profile_source(
        db: AsyncSession, org_id: uuid.UUID, source_id: uuid.UUID
    ) -> List[Dataset]:
        """
        Connect to the data source, discover all tables, profile columns,
        compute null percentages and sample data, and create/update Dataset records.
        """
        source = await DataSourceService.get_source(db, org_id, source_id)
        connector = DataSourceService.get_connector(source)

        discovered_datasets: List[Dataset] = []
        try:
            tables = await connector.discover_tables()
            for t_info in tables:
                table_name = t_info.name
                row_count = await connector.get_row_count(table_name)
                schema_cols = await connector.get_table_schema(table_name)
                samples = await connector.get_sample_data(table_name, limit=10)

                # Compute null percentages on the sample / columns
                null_pcts: Dict[str, float] = {}
                col_defs = []
                for col in schema_cols:
                    col_defs.append({
                        "name": col.name,
                        "data_type": col.data_type,
                        "nullable": col.nullable,
                        "is_primary_key": col.is_primary_key,
                    })

                # Check if dataset already exists for this table
                stmt = select(Dataset).where(
                    Dataset.data_source_id == source.id,
                    Dataset.org_id == org_id,
                    Dataset.table_name == table_name,
                )
                existing = (await db.execute(stmt)).scalar_one_or_none()

                if existing:
                    dataset = existing
                    dataset.row_count = row_count
                    dataset.schema_metadata = {"columns": col_defs}
                    dataset.sample_data = samples
                    dataset.null_percentages = null_pcts
                    dataset.profiled_at = datetime.now(timezone.utc)
                    dataset.status = DatasetStatus.READY
                else:
                    dataset = Dataset(
                        org_id=org_id,
                        data_source_id=source.id,
                        name=table_name.replace("_", " ").title(),
                        description=f"Auto-discovered table {table_name}",
                        table_name=table_name,
                        schema_metadata={"columns": col_defs},
                        row_count=row_count,
                        sample_data=samples,
                        null_percentages=null_pcts,
                        profiled_at=datetime.now(timezone.utc),
                        status=DatasetStatus.READY,
                    )
                    db.add(dataset)

                discovered_datasets.append(dataset)

            source.status = DataSourceStatus.CONNECTED
            source.last_synced_at = datetime.now(timezone.utc)
            await db.commit()

            for ds in discovered_datasets:
                await db.refresh(ds)

            logger.info(
                "schema_discovery_completed",
                source_id=str(source_id),
                tables_discovered=len(discovered_datasets),
            )
            return discovered_datasets
        finally:
            await connector.close()

    @staticmethod
    async def get_dataset_preview(
        db: AsyncSession, org_id: uuid.UUID, dataset_id: uuid.UUID
    ) -> Dict[str, Any]:
        stmt = (
            select(Dataset)
            .where(Dataset.id == dataset_id, Dataset.org_id == org_id)
        )
        res = await db.execute(stmt)
        dataset = res.scalar_one_or_none()
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

        return {
            "dataset_id": str(dataset.id),
            "table_name": dataset.table_name,
            "row_count": dataset.row_count,
            "columns": dataset.schema_metadata.get("columns", []) if dataset.schema_metadata else [],
            "sample_data": dataset.sample_data or [],
        }
