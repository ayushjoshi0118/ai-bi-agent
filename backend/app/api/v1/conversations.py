"""
AI Conversations and Analysis Workspace API endpoints.
"""

import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_current_org, get_current_user, get_db
from app.models.conversation import Conversation, Message
from app.models.organization import OrgRole, Organization
from app.models.user import User
from app.schemas.conversation import (
    AnalysisRequest,
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
)
from app.services.ai_orchestrator import AIOrchestrator

router = APIRouter(prefix="/conversations", tags=["AI Conversations"])


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.org_id == org.id, Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    res = await db.execute(stmt)
    convs = res.scalars().all()
    out = []
    for c in convs:
        out.append(
            ConversationResponse(
                id=c.id,
                org_id=c.org_id,
                user_id=c.user_id,
                title=c.title,
                message_count=len(c.messages) if c.messages else 0,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )
    return out


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    req: ConversationCreate,
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    conv = Conversation(
        org_id=org.id,
        user_id=current_user.id,
        title=req.title or "New Analysis",
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationResponse(
        id=conv.id,
        org_id=conv.org_id,
        user_id=conv.user_id,
        title=conv.title,
        message_count=0,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.get("/{conversation_id}", response_model=Dict[str, Any])
async def get_conversation(
    conversation_id: uuid.UUID,
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.org_id == org.id,
            Conversation.user_id == current_user.id,
        )
    )
    res = await db.execute(stmt)
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    messages_out = [
        {
            "id": str(m.id),
            "role": m.role.value,
            "content": m.content,
            "metadata": m.metadata_,
            "created_at": m.created_at.isoformat(),
        }
        for m in (conv.messages or [])
    ]

    return {
        "id": str(conv.id),
        "title": conv.title,
        "messages": messages_out,
        "created_at": conv.created_at.isoformat(),
    }


@router.post("/{conversation_id}/messages", response_model=Dict[str, Any])
async def send_message(
    conversation_id: uuid.UUID,
    req: MessageCreate,
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    return await AIOrchestrator.analyze(
        db=db,
        org_id=org.id,
        user_id=current_user.id,
        question=req.content,
        conversation_id=conversation_id,
    )


@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_question(
    req: AnalysisRequest,
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    return await AIOrchestrator.analyze(
        db=db,
        org_id=org.id,
        user_id=current_user.id,
        question=req.question,
        conversation_id=req.conversation_id,
        dataset_ids=req.dataset_ids,
    )
