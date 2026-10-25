"""
Organization and workspace management endpoints.
"""

import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_org, get_current_user, get_db, require_role
from app.models.organization import OrgMembership, OrgRole, Organization
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.organization import (
    InviteMemberRequest,
    MemberResponse,
    OrgCreate,
    OrgResponse,
    OrgUpdate,
    UpdateMemberRoleRequest,
)
from app.services.org_service import OrgService

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    req: OrgCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org = await OrgService.create_org(db, current_user.id, req)
    return OrgResponse.model_validate(org)


@router.get("", response_model=List[OrgResponse])
async def list_my_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    orgs = await OrgService.get_user_organizations(db, current_user.id)
    return [OrgResponse.model_validate(o) for o in orgs]


@router.get("/current", response_model=OrgResponse)
async def get_active_organization(
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
):
    org, _ = org_and_role
    return OrgResponse.model_validate(org)


@router.put("/current", response_model=OrgResponse)
async def update_active_organization(
    req: OrgUpdate,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ADMIN)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    updated = await OrgService.update_org(db, org.id, current_user.id, req)
    return OrgResponse.model_validate(updated)


@router.get("/current/members", response_model=List[MemberResponse])
async def list_organization_members(
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    members = await OrgService.list_members(db, org.id)
    out = []
    for m, u in members:
        out.append(
            MemberResponse(
                id=m.id,
                user_id=u.id,
                email=u.email,
                full_name=u.full_name,
                role=m.role,
                joined_at=m.created_at,
            )
        )
    return out


@router.post("/current/members", response_model=SuccessResponse)
async def invite_member(
    req: InviteMemberRequest,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ADMIN)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    await OrgService.invite_member(db, org.id, current_user.id, req)
    return SuccessResponse(message=f"User {req.email} added to organization as {req.role.value}")


@router.put("/current/members/{member_id}/role", response_model=SuccessResponse)
async def update_member_role(
    member_id: uuid.UUID,
    req: UpdateMemberRoleRequest,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ADMIN)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    await OrgService.update_member_role(db, org.id, current_user.id, member_id, req)
    return SuccessResponse(message="Member role updated")


@router.delete("/current/members/{member_id}", response_model=SuccessResponse)
async def remove_member(
    member_id: uuid.UUID,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ADMIN)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    await OrgService.remove_member(db, org.id, current_user.id, member_id)
    return SuccessResponse(message="Member removed from organization")
