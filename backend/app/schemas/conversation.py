"""
Conversation and message schemas for the AI analysis chat interface.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Participant role in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# ── Conversation ─────────────────────────────────────────────────────────


class ConversationCreate(BaseModel):
    """Payload to start a new conversation."""

    title: Optional[str] = Field(
        None, max_length=255, description="Optional conversation title"
    )
    dataset_ids: Optional[List[uuid.UUID]] = Field(
        None, description="Datasets to scope this conversation to"
    )


class ConversationResponse(BaseModel):
    """Conversation details returned by the API."""

    id: uuid.UUID = Field(..., description="Conversation unique identifier")
    title: Optional[str] = Field(None, description="Conversation title")
    message_count: int = Field(default=0, description="Total messages in conversation")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last activity timestamp")

    model_config = {"from_attributes": True}


# ── Messages ─────────────────────────────────────────────────────────────


class MessageCreate(BaseModel):
    """User message sent to the AI assistant."""

    content: str = Field(
        ..., min_length=1, max_length=4000, description="Message text"
    )


class MessageResponse(BaseModel):
    """Single message in a conversation."""

    id: uuid.UUID = Field(..., description="Message unique identifier")
    role: MessageRole = Field(..., description="Who sent the message")
    content: str = Field(..., description="Message text content")
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Extra data: generated SQL, chart specs, confidence scores, etc.",
    )
    created_at: datetime = Field(..., description="Message timestamp")

    model_config = {"from_attributes": True}


# ── Analysis Request ─────────────────────────────────────────────────────


class AnalysisRequest(BaseModel):
    """Top-level request to ask a natural-language analytics question."""

    question: str = Field(
        ..., min_length=3, max_length=2000, description="Natural-language question"
    )
    dataset_ids: Optional[List[uuid.UUID]] = Field(
        None, description="Limit analysis to specific datasets"
    )
    conversation_id: Optional[uuid.UUID] = Field(
        None, description="Continue an existing conversation"
    )
    include_chart: bool = Field(
        default=True, description="Whether the assistant should generate a chart"
    )
