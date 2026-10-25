"""
Audit Log Viewer API endpoints.
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_org, get_db, require_role
from app.models.audit import AuditEvent
from app.models.organization import OrgRole, Organization
from app.schemas.audit import AuditEventResponse

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=List[AuditEventResponse])
async def list_audit_logs(
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.org_id == org.id)
        .order_by(AuditEvent.created_at.desc())
        .limit(200)
    )
    res = await db.execute(stmt)
    records = res.scalars().all()
    return [AuditEventResponse.model_validate(r) for r in records]
