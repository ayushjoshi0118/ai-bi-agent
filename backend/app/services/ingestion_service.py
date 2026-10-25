"""
File ingestion service for CSV and Excel spreadsheets.
Validates file formats, sizes, and manages tenant-isolated storage and background profiling.
"""

from __future__ import annotations

import os
import re
import shutil
import uuid
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.config import get_settings
from app.models.data_source import DataSource, DataSourceStatus, DataSourceType
from app.models.dataset import Dataset
from app.services.audit_service import AuditService
from app.services.schema_discovery import SchemaDiscoveryService

logger = structlog.get_logger(__name__)
settings = get_settings()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


class IngestionService:
    @staticmethod
    async def ingest_file(
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        upload_file: UploadFile,
        dataset_name: str | None = None,
    ) -> tuple[DataSource, Dataset]:
        """
        Validate, save file to tenant folder, create DataSource and Dataset, and profile schema.
        """
        filename = upload_file.filename or "uploaded_data.csv"
        _, ext = os.path.splitext(filename.lower())

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Allowed formats: {sorted(list(ALLOWED_EXTENSIONS))}",
            )

        source_type = DataSourceType.CSV if ext == ".csv" else DataSourceType.XLSX

        # Create isolated tenant directory
        tenant_dir = os.path.join(settings.upload_dir, str(org_id))
        os.makedirs(tenant_dir, exist_ok=True)

        # Generate safe unique filename
        safe_base = re.sub(r"[^a-zA-Z0-9_.-]", "_", os.path.splitext(filename)[0])[:50]
        unique_filename = f"{safe_base}_{uuid.uuid4().hex[:8]}{ext}"
        destination_path = os.path.join(tenant_dir, unique_filename)

        # Stream save file and track size
        total_size = 0
        max_bytes = settings.max_upload_size_mb * 1024 * 1024

        with open(destination_path, "wb") as f_out:
            while chunk := await upload_file.read(1024 * 1024):  # 1MB chunks
                total_size += len(chunk)
                if total_size > max_bytes:
                    os.remove(destination_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum size of {settings.max_upload_size_mb}MB",
                    )
                f_out.write(chunk)

        # Clean table name
        raw_name = dataset_name or safe_base
        table_name = re.sub(r"[^a-zA-Z0-9_]", "_", raw_name.lower()).strip("_") or "dataset"

        # Create DataSource record
        data_source = DataSource(
            org_id=org_id,
            created_by=user_id,
            name=dataset_name or filename,
            source_type=source_type,
            connection_config={
                "file_path": os.path.abspath(destination_path),
                "original_filename": filename,
                "file_size_bytes": total_size,
                "table_name": table_name,
            },
            status=DataSourceStatus.PENDING,
        )
        db.add(data_source)
        await db.commit()
        await db.refresh(data_source)

        # Profile the schema and populate Dataset record
        datasets = await SchemaDiscoveryService.discover_and_profile_source(
            db, org_id=org_id, source_id=data_source.id
        )

        if not datasets:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to extract tables or data from uploaded file",
            )

        dataset = datasets[0]

        await AuditService.log_event(
            db,
            org_id=org_id,
            user_id=user_id,
            action="dataset.upload",
            resource_type="dataset",
            resource_id=dataset.id,
            details={
                "filename": filename,
                "file_size": total_size,
                "rows": dataset.row_count,
            },
        )

        return data_source, dataset
