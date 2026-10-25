"""
Pydantic schemas for Audit Logs and Notifications.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AuditEventResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: Optional[uuid.UUID]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[uuid.UUID]
    details: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: Optional[uuid.UUID]
    title: str
    message: str
    notification_type: str
    resource_type: Optional[str]
    resource_id: Optional[uuid.UUID]
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
