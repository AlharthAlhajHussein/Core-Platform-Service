from typing import Annotated, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError
from pydantic import ValidationError

from helpers.config import settings
from helpers.redis_client import is_token_blocked
from helpers.websocket_manager import manager
from models.users import User
from models.conversations import Conversation
from routers.dependencies import get_db, get_current_user, can_access_conversation
from services.conversation_service import conversation_service
from views.auth_schemas import TokenPayload
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
    section_id: Optional[UUID] = Query(None, description="Filter by section (Available to all roles)"),
    platform: Optional[str] = Query(None, description="Filter by channel (e.g. whatsapp, telegram)"),
    user_id: Optional[UUID] = Query(None, description="Filter by assigned employee or managing supervisor"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Pagination limit")
):
    """
    Returns a paginated list of conversations formatted for the dashboard. 
    Automatically applies RBAC filters to restrict visibility based on role.
    """
    return await conversation_service.list_conversations(db, current_user, skip, limit, status, agent_id, section_id, platform, user_id)

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

@router.websocket("/{conv_id}/ws")
async def conversation_websocket(
    websocket: WebSocket,
    conv_id: UUID,
    token: str = Query(..., description="JWT Token passed as query parameter"),
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for real-time conversation updates.
    Because browsers cannot easily send headers in WebSocket handshakes, 
    authentication is handled via the `token` query parameter.
    """
    # 1. Manual Authentication: Validate the JWT Token
    if await is_token_blocked(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token revoked")
        return

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return

    user = await db.get(User, UUID(token_data.sub))
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
        return
        
    # Attach the session properties expected by our dependencies
    user.current_company_id = token_data.company_id
    user.current_role = token_data.role
    user.is_platform_admin = token_data.is_platform_admin

    # 2. Authorization (RBAC): Verify they are allowed to view THIS conversation
    try:
        await can_access_conversation(conv_id=conv_id, current_user=user, db=db)
    except HTTPException as e:
        # Close connection immediately if they lack permissions (e.g. Employee looking at another Agent's chat)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=e.detail)
        return

    # 3. Connection Accepted!
    await manager.connect(websocket, conv_id)
    try:
        while True:
            # Keep the connection open indefinitely. We wait for client disconnects.
            # (If the frontend sends us data, we would process it here).
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, conv_id)

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