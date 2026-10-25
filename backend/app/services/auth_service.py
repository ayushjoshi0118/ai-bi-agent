"""
Authentication and user session management service.
"""

from __future__ import annotations

import re
import uuid
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.middleware.auth import create_access_token, create_refresh_token, decode_token
from app.models.organization import OrgMembership, OrgRole, Organization
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse
from app.security.password import hash_password, verify_password
from app.services.audit_service import AuditService


class AuthService:
    @staticmethod
    async def signup(db: AsyncSession, req: SignupRequest, ip_address: Optional[str] = None) -> tuple[User, TokenResponse]:
        # Validate email format
        email = req.email.strip().lower()
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format",
            )

        # Check existing user
        stmt = select(User).where(User.email == email)
        res = await db.execute(stmt)
        if res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists",
            )

        # Create user
        pwd_hash = hash_password(req.password)
        user = User(
            email=email,
            password_hash=pwd_hash,
            full_name=req.full_name.strip(),
            is_active=True,
        )
        db.add(user)
        await db.flush()

        # Create default organization for new user
        slug = f"{email.split('@')[0].lower()}-workspace"
        slug = re.sub(r"[^a-z0-9-]", "", slug) or "my-workspace"
        
        # Check slug collision
        slug_check = await db.execute(select(Organization).where(Organization.slug == slug))
        if slug_check.scalar_one_or_none():
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"

        org = Organization(
            name=f"{user.full_name}'s Workspace",
            slug=slug,
            created_by=user.id,
            settings={},
        )
        db.add(org)
        await db.flush()

        # Assign user as Owner
        membership = OrgMembership(
            user_id=user.id,
            org_id=org.id,
            role=OrgRole.OWNER,
        )
        db.add(membership)
        await db.commit()
        await db.refresh(user)

        # Log audit event
        await AuditService.log_event(
            db,
            org_id=org.id,
            user_id=user.id,
            action="user.signup",
            resource_type="user",
            resource_id=user.id,
            ip_address=ip_address,
        )

        tokens = TokenResponse(
            access_token=create_access_token({"sub": str(user.id), "org_id": str(org.id)}),
            refresh_token=create_refresh_token({"sub": str(user.id)}),
            token_type="bearer",
            expires_in=1800,
        )
        return user, tokens

    @staticmethod
    async def login(db: AsyncSession, req: LoginRequest, ip_address: Optional[str] = None) -> tuple[User, TokenResponse]:
        email = req.email.strip().lower()
        stmt = (
            select(User)
            .options(selectinload(User.memberships))
            .where(User.email == email)
        )
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user or not verify_password(req.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated. Please contact support.",
            )

        first_org_id = user.memberships[0].org_id if user.memberships else None

        tokens = TokenResponse(
            access_token=create_access_token({"sub": str(user.id), "org_id": str(first_org_id) if first_org_id else None}),
            refresh_token=create_refresh_token({"sub": str(user.id)}),
            token_type="bearer",
            expires_in=1800,
        )

        if first_org_id:
            await AuditService.log_event(
                db,
                org_id=first_org_id,
                user_id=user.id,
                action="user.login",
                resource_type="user",
                resource_id=user.id,
                ip_address=ip_address,
            )

        return user, tokens

    @staticmethod
    async def refresh_tokens(db: AsyncSession, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        user_id_str = payload.get("sub")
        try:
            user_id = uuid.UUID(user_id_str)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        stmt = select(User).options(selectinload(User.memberships)).where(User.id == user_id, User.is_active == True)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or deactivated",
            )

        first_org_id = user.memberships[0].org_id if user.memberships else None

        return TokenResponse(
            access_token=create_access_token({"sub": str(user.id), "org_id": str(first_org_id) if first_org_id else None}),
            refresh_token=create_refresh_token({"sub": str(user.id)}),
            token_type="bearer",
            expires_in=1800,
        )
