"""
User profile schemas for API responses and updates.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserResponse(BaseModel):
    """Public representation of a user returned by the API."""

    id: uuid.UUID = Field(..., description="User unique identifier")
    email: EmailStr = Field(..., description="User email address")
    full_name: str = Field(..., description="User full name")
    is_active: bool = Field(..., description="Whether the user account is active")
    created_at: datetime = Field(..., description="Account creation timestamp")

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Fields that a user can update on their own profile."""

    full_name: Optional[str] = Field(
        None, min_length=1, max_length=255, description="Updated full name"
    )
    email: Optional[EmailStr] = Field(None, description="Updated email address")
