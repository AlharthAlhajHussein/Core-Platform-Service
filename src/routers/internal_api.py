from fastapi import APIRouter, Depends, status
from typing import Annotated

from routers.dependencies import get_db, verify_internal_secret
from sqlalchemy.ext.asyncio import AsyncSession
from services.interaction_service import interaction_service
from views.interaction_schemas import InteractionSyncSchema

router = APIRouter(
    prefix="/internal",
    tags=["Internal Service API"],
    # This dependency is applied to ALL routes defined in this file.
    dependencies=[Depends(verify_internal_secret)]
)

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