"""
Organization and membership management schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr, Field


class OrgRole(str, Enum):
    """Organization member roles ordered by privilege level."""

    OWNER = "owner"
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


# ── Organization CRUD ─────────────────────────────────────────────────────


class OrgCreate(BaseModel):
    """Payload to create a new organization."""

    name: str = Field(
        ..., min_length=2, max_length=100, description="Organization name"
    )


class OrgResponse(BaseModel):
    """Organization details returned by the API."""

    id: uuid.UUID = Field(..., description="Organization unique identifier")
    name: str = Field(..., description="Organization display name")
    slug: str = Field(..., description="URL-safe slug")
    created_at: datetime = Field(..., description="Creation timestamp")
    member_count: int = Field(default=0, description="Number of active members")

    model_config = {"from_attributes": True}


class OrgUpdate(BaseModel):
    """Fields that can be updated on an organization."""

    name: Optional[str] = Field(
        None, min_length=2, max_length=100, description="Updated organization name"
    )
    settings: Optional[Dict[str, Any]] = Field(
        None, description="Organization-level settings (JSON)"
    )


# ── Membership ────────────────────────────────────────────────────────────


class MemberResponse(BaseModel):
    """Representation of an organization member."""

    id: uuid.UUID = Field(..., description="Membership record ID")
    user_id: uuid.UUID = Field(..., description="User unique identifier")
    email: EmailStr = Field(..., description="Member email")
    full_name: str = Field(..., description="Member full name")
    role: OrgRole = Field(..., description="Member role in the organization")
    joined_at: datetime = Field(..., description="When the member joined")

    model_config = {"from_attributes": True}


class InviteMemberRequest(BaseModel):
    """Request to invite a user to the organization."""

    email: EmailStr = Field(..., description="Email of the user to invite")
    role: OrgRole = Field(
        default=OrgRole.VIEWER, description="Role to assign to the invitee"
    )


class UpdateMemberRoleRequest(BaseModel):
    """Request to change a member's role."""

    role: OrgRole = Field(..., description="New role to assign")
