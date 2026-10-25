"""
Organization and membership management service.
"""

from __future__ import annotations

import re
import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.organization import OrgMembership, OrgRole, Organization
from app.models.user import User
from app.schemas.organization import InviteMemberRequest, OrgCreate, OrgUpdate, UpdateMemberRoleRequest
from app.services.audit_service import AuditService


class OrgService:
    @staticmethod
    async def create_org(db: AsyncSession, user_id: uuid.UUID, req: OrgCreate) -> Organization:
        base_slug = re.sub(r"[^a-z0-9-]", "", req.name.lower().replace(" ", "-")) or "workspace"
        slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        org = Organization(
            name=req.name.strip(),
            slug=slug,
            created_by=user_id,
            settings={},
        )
        db.add(org)
        await db.flush()

        membership = OrgMembership(
            user_id=user_id,
            org_id=org.id,
            role=OrgRole.OWNER,
        )
        db.add(membership)
        await db.commit()
        await db.refresh(org)

        await AuditService.log_event(
            db,
            org_id=org.id,
            user_id=user_id,
            action="organization.create",
            resource_type="organization",
            resource_id=org.id,
        )
        return org

    @staticmethod
    async def get_user_organizations(db: AsyncSession, user_id: uuid.UUID) -> List[Organization]:
        stmt = (
            select(Organization)
            .join(OrgMembership, OrgMembership.org_id == Organization.id)
            .where(OrgMembership.user_id == user_id)
            .order_by(Organization.created_at.asc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_org(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, req: OrgUpdate) -> Organization:
        stmt = select(Organization).where(Organization.id == org_id)
        res = await db.execute(stmt)
        org = res.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

        if req.name is not None:
            org.name = req.name.strip()
        if req.settings is not None:
            org.settings = req.settings

        await db.commit()
        await db.refresh(org)

        await AuditService.log_event(
            db,
            org_id=org.id,
            user_id=user_id,
            action="organization.update",
            resource_type="organization",
            resource_id=org.id,
        )
        return org

    @staticmethod
    async def list_members(db: AsyncSession, org_id: uuid.UUID) -> List[tuple[OrgMembership, User]]:
        stmt = (
            select(OrgMembership, User)
            .join(User, OrgMembership.user_id == User.id)
            .where(OrgMembership.org_id == org_id)
            .order_by(OrgMembership.created_at.asc())
        )
        res = await db.execute(stmt)
        return list(res.all())

    @staticmethod
    async def invite_member(
        db: AsyncSession, org_id: uuid.UUID, actor_id: uuid.UUID, req: InviteMemberRequest
    ) -> OrgMembership:
        email = req.email.strip().lower()
        # Find user or return friendly notice
        stmt = select(User).where(User.email == email)
        res = await db.execute(stmt)
        target_user = res.scalar_one_or_none()

        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with email '{email}' does not have an account yet. Ask them to sign up first.",
            )

        # Check existing membership
        existing_stmt = select(OrgMembership).where(
            OrgMembership.org_id == org_id, OrgMembership.user_id == target_user.id
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this organization",
            )

        membership = OrgMembership(
            org_id=org_id,
            user_id=target_user.id,
            role=req.role,
        )
        db.add(membership)
        await db.commit()
        await db.refresh(membership)

        await AuditService.log_event(
            db,
            org_id=org_id,
            user_id=actor_id,
            action="member.invite",
            resource_type="user",
            resource_id=target_user.id,
            details={"role": req.role.value, "email": email},
        )
        return membership

    @staticmethod
    async def update_member_role(
        db: AsyncSession, org_id: uuid.UUID, actor_id: uuid.UUID, member_id: uuid.UUID, req: UpdateMemberRoleRequest
    ) -> OrgMembership:
        stmt = select(OrgMembership).where(OrgMembership.id == member_id, OrgMembership.org_id == org_id)
        res = await db.execute(stmt)
        membership = res.scalar_one_or_none()

        if not membership:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

        membership.role = req.role
        await db.commit()
        await db.refresh(membership)

        await AuditService.log_event(
            db,
            org_id=org_id,
            user_id=actor_id,
            action="member.role_update",
            resource_type="org_membership",
            resource_id=membership.id,
            details={"new_role": req.role.value},
        )
        return membership

    @staticmethod
    async def remove_member(
        db: AsyncSession, org_id: uuid.UUID, actor_id: uuid.UUID, member_id: uuid.UUID
    ) -> None:
        stmt = select(OrgMembership).where(OrgMembership.id == member_id, OrgMembership.org_id == org_id)
        res = await db.execute(stmt)
        membership = res.scalar_one_or_none()

        if not membership:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

        if membership.role == OrgRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove organization owner",
            )

        await db.delete(membership)
        await db.commit()

        await AuditService.log_event(
            db,
            org_id=org_id,
            user_id=actor_id,
            action="member.remove",
            resource_type="org_membership",
            resource_id=member_id,
        )
