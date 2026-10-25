"""
Tenant Security & Authorization Enforcement Manager.
Enforces multi-tenant isolation across APIs, queries, background workers, and shared caches.
Validates object-level ownership, detects cross-tenant access attempts,
and revalidates user membership and resource permissions at background execution time.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import uuid
from typing import Any, Dict, Optional, Tuple, Type
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.dependencies import ROLE_HIERARCHY
from app.models.base import BaseModel
from app.models.dataset import Dataset
from app.models.organization import OrgMembership, OrgRole, Organization
from app.models.report import Report
from app.models.scheduled_job import ScheduledJob
from app.models.user import User
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)


class SecurityFailureType(str, Enum):
    CROSS_TENANT_ATTEMPT = "cross_tenant_attempt"
    MEMBERSHIP_REVOKED = "membership_revoked"
    INSUFFICIENT_ROLE = "insufficient_role"
    RESOURCE_NOT_FOUND = "resource_not_found"
    USER_DEACTIVATED = "user_deactivated"


@dataclass
class WorkerAuthResult:
    authorized: bool
    reason: Optional[str] = None
    failure_type: Optional[SecurityFailureType] = None
    org_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None


class TenantSecurityManager:
    """
    Centralized tenant isolation and authorization gatekeeper.
    Guarantees that tenant boundaries are verified on the server for every resource.
    """

    @classmethod
    async def validate_membership(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        min_role: OrgRole = OrgRole.VIEWER,
    ) -> OrgMembership:
        """
        Validates that user_id is an active member of org_id with at least min_role.
        Bypasses stale token claims by verifying live database records.
        """
        stmt = select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == user_id,
        )
        membership = (await db.execute(stmt)).scalar_one_or_none()

        if not membership:
            logger.warning(
                "tenant_membership_missing_or_revoked",
                org_id=str(org_id),
                user_id=str(user_id),
            )
            await AuditService.log_event(
                db,
                org_id=org_id,
                user_id=user_id,
                action="security.access_denied",
                resource_type="organization",
                resource_id=org_id,
                details={"reason": "User is not a member of organization"},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Membership revoked or user is not a member of this organization",
            )

        # Check role level
        user_level = ROLE_HIERARCHY.get(membership.role, 0)
        req_level = ROLE_HIERARCHY.get(min_role, 99)
        if user_level < req_level:
            logger.warning(
                "tenant_insufficient_permissions",
                org_id=str(org_id),
                user_id=str(user_id),
                user_role=membership.role.value,
                required_role=min_role.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: '{min_role.value}' role required, but your role is '{membership.role.value}'",
            )

        return membership

    @classmethod
    async def verify_object_ownership(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        model_class: Type[BaseModel],
        object_id: uuid.UUID,
        resource_label: str = "resource",
    ) -> Any:
        """
        Enforces object-level tenant isolation.
        Verifies that object_id belongs strictly to org_id.
        If the object exists under a different tenant, logs a security warning and raises 404
        to prevent cross-tenant enumeration attacks.
        """
        # First check if object exists under this org
        stmt = select(model_class).where(
            model_class.id == object_id,
            model_class.org_id == org_id,
        )
        item = (await db.execute(stmt)).scalar_one_or_none()

        if item:
            return item

        # Check if the resource exists globally under another tenant (Cross-Tenant Attack Detection)
        stmt_cross = select(model_class).where(model_class.id == object_id)
        other_tenant_item = (await db.execute(stmt_cross)).scalar_one_or_none()

        if other_tenant_item:
            logger.error(
                "security_cross_tenant_access_attempt",
                requesting_org_id=str(org_id),
                requesting_user_id=str(user_id),
                target_resource_id=str(object_id),
                resource_type=model_class.__tablename__,
                actual_owner_org_id=str(other_tenant_item.org_id),
            )
            await AuditService.log_event(
                db,
                org_id=org_id,
                user_id=user_id,
                action="security.cross_tenant_attempt",
                resource_type=model_class.__tablename__,
                resource_id=object_id,
                details={
                    "target_resource_id": str(object_id),
                    "resource_type": model_class.__tablename__,
                },
            )
            # Fail closed with 404 to avoid leaking cross-tenant existence
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{resource_label.capitalize()} not found",
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_label.capitalize()} not found",
        )

    @classmethod
    async def revalidate_worker_context(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        resource_type: str,
        resource_id: Optional[uuid.UUID],
    ) -> WorkerAuthResult:
        """
        Invoked by background workers (Celery, scheduled reports, notification dispatchers).
        Revalidates tenant membership, account active status, and resource ownership at execution time.
        Guarantees that jobs scheduled before membership revocation or resource deletion are aborted.
        """
        # 1. Verify Organization exists
        org = await db.get(Organization, org_id)
        if not org:
            logger.error("worker_auth_org_missing", org_id=str(org_id))
            return WorkerAuthResult(
                authorized=False,
                reason=f"Organization {org_id} no longer exists",
                failure_type=SecurityFailureType.RESOURCE_NOT_FOUND,
                org_id=org_id,
                user_id=user_id,
            )

        # 2. If user_id is provided, verify user account is active and still a member
        if user_id:
            user = await db.get(User, user_id)
            if not user or not user.is_active:
                logger.warning("worker_auth_user_deactivated", user_id=str(user_id), org_id=str(org_id))
                return WorkerAuthResult(
                    authorized=False,
                    reason=f"User {user_id} is deactivated or deleted",
                    failure_type=SecurityFailureType.USER_DEACTIVATED,
                    org_id=org_id,
                    user_id=user_id,
                )

            stmt_mem = select(OrgMembership).where(
                OrgMembership.org_id == org_id,
                OrgMembership.user_id == user_id,
            )
            membership = (await db.execute(stmt_mem)).scalar_one_or_none()
            if not membership:
                logger.error(
                    "worker_auth_membership_revoked_at_runtime",
                    user_id=str(user_id),
                    org_id=str(org_id),
                )
                await AuditService.log_event(
                    db,
                    org_id=org_id,
                    user_id=user_id,
                    action="security.worker_revocation_abort",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details={"reason": "User membership was revoked prior to worker execution"},
                )
                return WorkerAuthResult(
                    authorized=False,
                    reason="User membership in organization was revoked",
                    failure_type=SecurityFailureType.MEMBERSHIP_REVOKED,
                    org_id=org_id,
                    user_id=user_id,
                )

        # 3. If resource_id is provided, verify it belongs to org_id
        if resource_id:
            model_map = {
                "report": Report,
                "dataset": Dataset,
                "scheduled_job": ScheduledJob,
            }
            target_model = model_map.get(resource_type.lower())
            if target_model:
                stmt_res = select(target_model).where(
                    target_model.id == resource_id,
                    target_model.org_id == org_id,
                )
                resource_obj = (await db.execute(stmt_res)).scalar_one_or_none()
                if not resource_obj:
                    logger.error(
                        "worker_auth_resource_missing_or_cross_tenant",
                        resource_type=resource_type,
                        resource_id=str(resource_id),
                        org_id=str(org_id),
                    )
                    return WorkerAuthResult(
                        authorized=False,
                        reason=f"Resource {resource_type}:{resource_id} not found in org {org_id}",
                        failure_type=SecurityFailureType.RESOURCE_NOT_FOUND,
                        org_id=org_id,
                        user_id=user_id,
                    )

        # Authorized
        return WorkerAuthResult(authorized=True, org_id=org_id, user_id=user_id)
