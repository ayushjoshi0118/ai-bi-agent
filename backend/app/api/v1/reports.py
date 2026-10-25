"""
Report and Saved Analysis API endpoints.
"""

import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_org, get_current_user, get_db, require_role
from app.models.organization import OrgRole, Organization
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.report import (
    ReportCreate,
    ReportResponse,
    ReportUpdate,
    ReportVersionResponse,
    SavedAnalysisCreate,
    SavedAnalysisResponse,
)
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/analyses", response_model=List[SavedAnalysisResponse])
async def list_saved_analyses(
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    items = await ReportService.list_saved_analyses(db, org.id)
    return [SavedAnalysisResponse.model_validate(i) for i in items]


@router.post("/analyses", response_model=SavedAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def save_analysis(
    req: SavedAnalysisCreate,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ANALYST)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    item = await ReportService.create_saved_analysis(db, org.id, current_user.id, req)
    return SavedAnalysisResponse.model_validate(item)


@router.get("", response_model=List[ReportResponse])
async def list_reports(
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    reports = await ReportService.list_reports(db, org.id)
    out = []
    for r in reports:
        latest = r.versions[-1] if r.versions else None
        latest_schema = ReportVersionResponse.model_validate(latest) if latest else None
        out.append(
            ReportResponse(
                id=r.id,
                org_id=r.org_id,
                created_by=r.created_by,
                title=r.title,
                description=r.description,
                status=r.status,
                config=r.config,
                created_at=r.created_at,
                updated_at=r.updated_at,
                latest_version=latest_schema,
            )
        )
    return out


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    req: ReportCreate,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ANALYST)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    report = await ReportService.create_report(db, org.id, current_user.id, req)
    latest = report.versions[-1] if report.versions else None
    return ReportResponse(
        id=report.id,
        org_id=report.org_id,
        created_by=report.created_by,
        title=report.title,
        description=report.description,
        status=report.status,
        config=report.config,
        created_at=report.created_at,
        updated_at=report.updated_at,
        latest_version=ReportVersionResponse.model_validate(latest) if latest else None,
    )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: uuid.UUID,
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    report = await ReportService.get_report(db, org.id, report_id)
    latest = report.versions[-1] if report.versions else None
    return ReportResponse(
        id=report.id,
        org_id=report.org_id,
        created_by=report.created_by,
        title=report.title,
        description=report.description,
        status=report.status,
        config=report.config,
        created_at=report.created_at,
        updated_at=report.updated_at,
        latest_version=ReportVersionResponse.model_validate(latest) if latest else None,
    )


@router.put("/{report_id}", response_model=ReportResponse)
async def update_report(
    report_id: uuid.UUID,
    req: ReportUpdate,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ANALYST)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    report = await ReportService.update_report(db, org.id, current_user.id, report_id, req)
    latest = report.versions[-1] if report.versions else None
    return ReportResponse(
        id=report.id,
        org_id=report.org_id,
        created_by=report.created_by,
        title=report.title,
        description=report.description,
        status=report.status,
        config=report.config,
        created_at=report.created_at,
        updated_at=report.updated_at,
        latest_version=ReportVersionResponse.model_validate(latest) if latest else None,
    )


@router.delete("/{report_id}", response_model=SuccessResponse)
async def delete_report(
    report_id: uuid.UUID,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ADMIN)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    await ReportService.delete_report(db, org.id, current_user.id, report_id)
    return SuccessResponse(message="Report deleted successfully")
