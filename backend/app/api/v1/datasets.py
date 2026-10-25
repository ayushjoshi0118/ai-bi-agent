"""
Dataset and Schema Inspection API endpoints.
"""

import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_current_org, get_current_user, get_db, require_role
from app.models.dataset import Dataset
from app.models.organization import OrgRole, Organization
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.dataset import ColumnInfoSchema, DatasetResponse, DatasetSchema, DatasetUpdate
from app.services.audit_service import AuditService
from app.services.schema_discovery import SchemaDiscoveryService

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.get("", response_model=List[DatasetResponse])
async def list_datasets(
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    stmt = (
        select(Dataset)
        .where(Dataset.org_id == org.id)
        .order_by(Dataset.created_at.desc())
    )
    res = await db.execute(stmt)
    datasets = res.scalars().all()

    out = []
    for d in datasets:
        cols = d.schema_metadata.get("columns", []) if d.schema_metadata else []
        out.append(
            DatasetResponse(
                id=d.id,
                org_id=d.org_id,
                data_source_id=d.data_source_id,
                name=d.name,
                description=d.description,
                table_name=d.table_name,
                row_count=d.row_count,
                column_count=len(cols),
                status=d.status,
                profiled_at=d.profiled_at,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
        )
    return out


@router.get("/{dataset_id}", response_model=DatasetSchema)
async def get_dataset_details(
    dataset_id: uuid.UUID,
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    stmt = select(Dataset).where(Dataset.id == dataset_id, Dataset.org_id == org.id)
    res = await db.execute(stmt)
    dataset = res.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    cols = dataset.schema_metadata.get("columns", []) if dataset.schema_metadata else []
    columns_list = [
        ColumnInfoSchema(
            name=c.get("name", ""),
            data_type=c.get("data_type", "text"),
            nullable=c.get("nullable", True),
            is_primary_key=c.get("is_primary_key", False),
            sample_values=c.get("sample_values", []),
        )
        for c in cols
    ]

    return DatasetSchema(
        id=dataset.id,
        name=dataset.name,
        table_name=dataset.table_name,
        row_count=dataset.row_count,
        columns=columns_list,
        sample_data=dataset.sample_data or [],
        profiled_at=dataset.profiled_at,
    )


@router.get("/{dataset_id}/preview", response_model=Dict[str, Any])
async def get_dataset_preview(
    dataset_id: uuid.UUID,
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    return await SchemaDiscoveryService.get_dataset_preview(db, org.id, dataset_id)


@router.put("/{dataset_id}", response_model=SuccessResponse)
async def update_dataset_metadata(
    dataset_id: uuid.UUID,
    req: DatasetUpdate,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ANALYST)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    stmt = select(Dataset).where(Dataset.id == dataset_id, Dataset.org_id == org.id)
    res = await db.execute(stmt)
    dataset = res.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    if req.name is not None:
        dataset.name = req.name.strip()
    if req.description is not None:
        dataset.description = req.description

    await db.commit()
    await AuditService.log_event(
        db,
        org_id=org.id,
        user_id=current_user.id,
        action="dataset.update",
        resource_type="dataset",
        resource_id=dataset_id,
    )
    return SuccessResponse(message="Dataset updated successfully")


@router.delete("/{dataset_id}", response_model=SuccessResponse)
async def delete_dataset(
    dataset_id: uuid.UUID,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ADMIN)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    stmt = select(Dataset).where(Dataset.id == dataset_id, Dataset.org_id == org.id)
    res = await db.execute(stmt)
    dataset = res.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    await db.delete(dataset)
    await db.commit()

    await AuditService.log_event(
        db,
        org_id=org.id,
        user_id=current_user.id,
        action="dataset.delete",
        resource_type="dataset",
        resource_id=dataset_id,
    )
    return SuccessResponse(message="Dataset deleted successfully")
