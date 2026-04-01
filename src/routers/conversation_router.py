from typing import Annotated, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
from models.conversations import Conversation
from routers.dependencies import get_db, get_current_user, can_access_conversation
from services.conversation_service import conversation_service
from views.conversation_schemas import (
    ConversationListResponse, ConversationDetailResponse, 
    ConversationStatusUpdateRequest, ConversationEvaluationRequest
)

router = APIRouter(
    prefix="/api/v1/conversations", 
    tags=["Monitoring & Conversations"]
)

@router.get("", response_model=List[ConversationListResponse])
async def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Optional[str] = Query(None, description="Filter by status (e.g. ACTIVE, PENDING_HUMAN)"),
    agent_id: Optional[UUID] = Query(None, description="Filter by specific agent"),
    section_id: Optional[UUID] = Query(None, description="Filter by section (Ignored unless user is OWNER)"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Pagination limit")
):
    """
    Returns a paginated list of conversations formatted for the dashboard. 
    Automatically applies RBAC filters to restrict visibility based on role.
    """
    return await conversation_service.list_conversations(db, current_user, skip, limit, status, agent_id, section_id)

@router.get("/{conv_id}", response_model=ConversationDetailResponse)
async def get_conversation_detail(
    conv: Annotated[Conversation, Depends(can_access_conversation)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Returns the full conversation details alongside its entire message history."""
    enriched_conv = await conversation_service.get_enriched_single_conversation(db, current_user, conv)
    messages = await conversation_service.get_conversation_messages(db, conv.id)
    return {"conversation": enriched_conv, "messages": messages}

@router.put("/{conv_id}/status", response_model=ConversationListResponse)
async def update_conversation_status(
    conv: Annotated[Conversation, Depends(can_access_conversation)],
    request: ConversationStatusUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Allows humans to update the conversation status (e.g., closing a PENDING_HUMAN escalation)."""
    updated_conv = await conversation_service.update_status(db, conv, request)
    # Re-fetch enriched to maintain the same consistent format expected by the frontend
    return await conversation_service.get_enriched_single_conversation(db, current_user, updated_conv)

@router.put("/{conv_id}/evaluation", response_model=ConversationListResponse)
async def evaluate_conversation(
    conv: Annotated[Conversation, Depends(can_access_conversation)],
    request: ConversationEvaluationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Evaluates the agent's performance in a conversation."""
    # Edge Case: If evaluation is 'OTHERS', force them to provide notes
    if request.evaluation == "OTHERS" and not request.notes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Notes are required when evaluation is set to OTHERS.")
        
    updated_conv = await conversation_service.evaluate_conversation(db, conv, request)
    return await conversation_service.get_enriched_single_conversation(db, current_user, updated_conv)