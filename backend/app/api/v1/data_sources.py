"""
Data Source creation, file ingestion, connection testing, and deletion endpoints.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_org, get_current_user, get_db, require_role
from app.models.organization import OrgRole, Organization
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.data_source import DataSourceCreate, DataSourceResponse, DataSourceTestResult, PostgresConnectionConfig
from app.services.data_source_service import DataSourceService
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/data-sources", tags=["Data Sources"])


@router.get("", response_model=List[DataSourceResponse])
async def list_data_sources(
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    sources = await DataSourceService.list_sources(db, org.id)
    out = []
    for s in sources:
        out.append(
            DataSourceResponse(
                id=s.id,
                org_id=s.org_id,
                name=s.name,
                source_type=s.source_type,
                connection_config=s.connection_config,
                status=s.status,
                last_synced_at=s.last_synced_at,
                created_at=s.created_at,
                updated_at=s.updated_at,
                dataset_count=len(s.datasets) if s.datasets else 0,
            )
        )
    return out


@router.post("/postgres", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_postgres_source(
    name: str = Form(...),
    host: str = Form(...),
    port: int = Form(5432),
    database: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    schema_name: str = Form("public"),
    ssl: bool = Form(False),
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ANALYST)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    pg_config = PostgresConnectionConfig(
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
        schema_name=schema_name,
        ssl=ssl,
    )
    source = await DataSourceService.create_postgres_source(
        db, org_id=org.id, user_id=current_user.id, name=name, config=pg_config
    )
    return DataSourceResponse(
        id=source.id,
        org_id=source.org_id,
        name=source.name,
        source_type=source.source_type,
        connection_config=source.connection_config,
        status=source.status,
        last_synced_at=source.last_synced_at,
        created_at=source.created_at,
        updated_at=source.updated_at,
        dataset_count=0,
    )


@router.post("/upload", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset_file(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ANALYST)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    source, dataset = await IngestionService.ingest_file(
        db=db,
        org_id=org.id,
        user_id=current_user.id,
        upload_file=file,
        dataset_name=name,
    )
    return DataSourceResponse(
        id=source.id,
        org_id=source.org_id,
        name=source.name,
        source_type=source.source_type,
        connection_config=source.connection_config,
        status=source.status,
        last_synced_at=source.last_synced_at,
        created_at=source.created_at,
        updated_at=source.updated_at,
        dataset_count=1,
    )


@router.post("/{source_id}/test", response_model=DataSourceTestResult)
async def test_data_source_connection(
    source_id: uuid.UUID,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ANALYST)),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    ok, msg = await DataSourceService.test_source_connection(db, org.id, source_id)
    return DataSourceTestResult(success=ok, message=msg)


@router.delete("/{source_id}", response_model=SuccessResponse)
async def delete_data_source(
    source_id: uuid.UUID,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ADMIN)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    await DataSourceService.delete_source(db, org.id, current_user.id, source_id)
    return SuccessResponse(message="Data source deleted successfully")
