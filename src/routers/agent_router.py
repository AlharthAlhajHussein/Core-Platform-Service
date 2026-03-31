from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
from models.agents import Agent
from routers.dependencies import get_db, get_current_user, can_access_agent, is_owner
from services.agent_service import agent_service
from views.agent_schemas import (
    AgentCreateRequest, AgentUpdateRequest, AgentResponse, AgentEmployeeAssignRequest
)

router = APIRouter(
    prefix="/api/v1/agents",
    tags=["Agent & Channel Management"]
)

@router.post("", status_code=status.HTTP_201_CREATED, response_model=AgentResponse)
async def create_agent(
    request: AgentCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Creates a new AI Agent. 
    Owners can create in ANY section. Supervisors can ONLY create in sections they manage.
    """
    return await agent_service.create_agent(db=db, current_user=current_user, agent_data=request)

@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    update_data: AgentUpdateRequest,
    agent: Annotated[Agent, Depends(can_access_agent)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Updates an agent's configuration (prompts, models, tokens). 
    Accessible by Owners, Section Supervisors, and explicitly assigned Employees.
    """
    return await agent_service.update_agent(db=db, agent=agent, update_data=update_data)

@router.post("/{agent_id}/assign-employee", status_code=status.HTTP_200_OK)
async def assign_user_to_agent(
    agent_id: UUID,
    request: AgentEmployeeAssignRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Assigns an employee to an agent, giving them permission to update its config.
    Owners and Section Supervisors can perform this.
    """
    await agent_service.assign_employee(db=db, current_user=current_user, agent_id=agent_id, target_user_id=request.user_id)
    return {"status": "success", "detail": "User assigned to agent successfully."}

@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Deletes an agent. Owners can delete any agent. Supervisors can only delete agents in sections they manage."""
    await agent_service.delete_agent(db=db, current_user=current_user, agent_id=agent_id)
    return None