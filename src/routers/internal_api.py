from fastapi import APIRouter, Depends, status, HTTPException
from typing import Annotated, Optional
from uuid import UUID

from routers.dependencies import get_db, verify_internal_secret
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from services.interaction_service import interaction_service
from views.interaction_schemas import InteractionSyncSchema
from views.internal_schemas import InternalAgentConfigResponse
from models.agents import Agent
from models.knowledge_bucket_registry import KnowledgeBucketRegistry
from helpers.encryption import decrypt

router = APIRouter(
    prefix="/internal",
    tags=["Internal Service API"],
    # This dependency is applied to ALL routes defined in this file.
    dependencies=[Depends(verify_internal_secret)]
)

@router.get(
    "/agents/config",
    response_model=InternalAgentConfigResponse,
    summary="Fetches decrypted agent configuration for Orchestrator/Gateway"
)
async def get_agent_config(
    db: Annotated[AsyncSession, Depends(get_db)],
    agent_id: Optional[UUID] = None,
    whatsapp_number: Optional[str] = None,
    telegram_bot_username: Optional[str] = None
):
    """
    Retrieves the agent's configuration using agent_id, whatsapp_number, or telegram_bot_username.
    Decodes the WhatsApp and Telegram tokens in-memory so the Orchestrator
    can use them to communicate with the external messaging APIs.
    """
    if not any([agent_id, whatsapp_number, telegram_bot_username]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Must provide at least one identifier: agent_id, whatsapp_number, or telegram_bot_username.")

    stmt = select(Agent)
    if agent_id:
        stmt = stmt.filter(Agent.id == agent_id)
    elif whatsapp_number:
        stmt = stmt.filter(Agent.whatsapp_number == whatsapp_number)
    elif telegram_bot_username:
        stmt = stmt.filter(Agent.telegram_bot_username == telegram_bot_username)

    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

    # 1. Decrypt tokens securely in-memory
    whatsapp_token = decrypt(agent.whatsapp_token_enc) if getattr(agent, "whatsapp_token_enc", None) else None
    telegram_token = decrypt(agent.telegram_token_enc) if getattr(agent, "telegram_token_enc", None) else None

    # 2. Resolve RAG Container ID if a knowledge bucket is attached
    rag_container_id = None
    kb_id = getattr(agent, "knowledge_bucket_id", None)
    if kb_id:
        kb = await db.get(KnowledgeBucketRegistry, kb_id)
        if kb:
            rag_container_id = kb.rag_container_id

    return {"whatsapp_token": whatsapp_token, "telegram_token": telegram_token, "rag_container_id": rag_container_id, **agent.__dict__}


@router.post(
    "/interactions/sync",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Syncs an interaction from the Orchestrator"
)
async def sync_interaction_endpoint(
    payload: InteractionSyncSchema,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Receives interaction data from the AI-Orchestrator, and calls the service
    to sync it to the database for billing and dashboard monitoring.
    """
    await interaction_service.sync_interaction(db=db, payload=payload)
    return {"status": "accepted", "detail": "Interaction data has been accepted for processing."}