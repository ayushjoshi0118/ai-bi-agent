"""
FastAPI dependency injection providers.
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.database import get_async_session
from app.middleware.auth import decode_token
from app.models.organization import OrgMembership, OrgRole, Organization
from app.models.user import User

security_scheme = HTTPBearer(auto_error=False)

ROLE_HIERARCHY = {
    OrgRole.VIEWER: 1,
    OrgRole.ANALYST: 2,
    OrgRole.ADMIN: 3,
    OrgRole.OWNER: 4,
}


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    async for session in get_async_session():
        yield session


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate JWT bearer token and return the authenticated User."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(auth.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing subject identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed user ID in token",
        )

    stmt = select(User).where(User.id == user_id, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account is deactivated",
        )

    return user


async def get_current_org(
    x_org_id: Optional[str] = Header(None, alias="X-Org-ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[Organization, OrgRole]:
    """
    Tenant isolation dependency:
    Extracts the organization from X-Org-ID header or defaults to user's first organization,
    and validates that the user is an active member with their assigned role.
    """
    if x_org_id:
        try:
            target_org_id = uuid.UUID(x_org_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed X-Org-ID header",
            )
        stmt = (
            select(OrgMembership)
            .options(selectinload(OrgMembership.organization))
            .where(
                OrgMembership.user_id == current_user.id,
                OrgMembership.org_id == target_org_id,
            )
        )
    else:
        # Fallback to the first organization user is a member of
        stmt = (
            select(OrgMembership)
            .options(selectinload(OrgMembership.organization))
            .where(OrgMembership.user_id == current_user.id)
            .order_by(OrgMembership.created_at.asc())
        )

    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()

    if not membership or not membership.organization:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not a member of the requested organization",
        )

    return membership.organization, membership.role


def require_role(min_role: OrgRole):
    """
    RBAC dependency factory.
    Enforces that the user has at least `min_role` within the active organization.
    """
    async def role_checker(
        org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    ) -> tuple[Organization, OrgRole]:
        org, user_role = org_and_role
        user_level = ROLE_HIERARCHY.get(user_role, 0)
        required_level = ROLE_HIERARCHY.get(min_role, 99)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: '{min_role.value}' role required, but your role is '{user_role.value}'",
            )
        return org, user_role

    return role_checker
