"""
Anomaly Detection API endpoints.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_org, get_current_user, get_db, require_role
from app.models.anomaly import AnomalyDetection, AnomalySeverity, AnomalyStatus
from app.models.organization import OrgRole, Organization
from app.models.user import User
from app.schemas.anomaly import AnomalyResponse, AnomalyScanRequest, AnomalyStatusUpdate
from app.schemas.common import SuccessResponse
from app.services.anomaly_service import AnomalyService

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])


@router.get("", response_model=List[AnomalyResponse])
async def list_anomalies(
    dataset_id: Optional[uuid.UUID] = None,
    severity: Optional[AnomalySeverity] = None,
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    stmt = (
        select(AnomalyDetection)
        .where(AnomalyDetection.org_id == org.id)
    )
    if dataset_id:
        stmt = stmt.where(AnomalyDetection.dataset_id == dataset_id)
    if severity:
        stmt = stmt.where(AnomalyDetection.severity == severity)
    stmt = stmt.order_by(AnomalyDetection.detected_at.desc()).limit(100)

    res = await db.execute(stmt)
    records = res.scalars().all()
    return [AnomalyResponse.model_validate(r) for r in records]


@router.post("/scan", response_model=List[AnomalyResponse])
async def trigger_anomaly_scan(
    req: AnomalyScanRequest,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ANALYST)),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    anomalies = await AnomalyService.run_detection(
        db=db,
        org_id=org.id,
        dataset_id=req.dataset_id,
        metric_column=req.metric_column,
        time_column=req.time_column,
        method=req.method,
        sensitivity=req.sensitivity,
        min_sample_size=req.min_sample_size,
    )
    return [AnomalyResponse.model_validate(a) for a in anomalies]


@router.put("/{anomaly_id}/status", response_model=SuccessResponse)
async def update_anomaly_status(
    anomaly_id: uuid.UUID,
    req: AnomalyStatusUpdate,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ANALYST)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    stmt = select(AnomalyDetection).where(
        AnomalyDetection.id == anomaly_id, AnomalyDetection.org_id == org.id
    )
    res = await db.execute(stmt)
    anom = res.scalar_one_or_none()
    if not anom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anomaly not found")

    anom.status = req.status
    if req.status == AnomalyStatus.ACKNOWLEDGED:
        anom.acknowledged_by = current_user.id
    await db.commit()
    return SuccessResponse(message=f"Anomaly status updated to {req.status.value}")
