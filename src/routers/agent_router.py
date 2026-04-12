from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
from models.agents import Agent
from routers.dependencies import get_db, get_current_user, can_access_agent, is_owner
from services.agent_service import agent_service
from views.agent_schemas import (
    AgentCreateRequest, AgentUpdateRequest, AgentResponse,
    AgentEmployeeAssignRequest, AgentUserResponse
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

@router.get("", status_code=status.HTTP_200_OK, response_model=List[AgentResponse])
async def list_agents(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    section_id: Optional[UUID] = Query(None, description="Filter agents by section (Available to all roles)"),
    user_id: Optional[UUID] = Query(None, description="Filter agents by assigned user (Owners & Supervisors only)")
):
    """
    Retrieves a list of AI agents based on the user's role.
    - Owners see all agents, and can filter by section and user.
    - Supervisors see agents in their managed sections, and can filter by section and assigned user.
    - Employees only see agents explicitly assigned to them, and can filter by section.
    """
    return await agent_service.list_agents(db=db, current_user=current_user, section_id=section_id, user_id=user_id)

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

@router.delete("/{agent_id}/employees", status_code=status.HTTP_204_NO_CONTENT)
async def remove_employee_from_agent(
    agent_id: UUID,
    request: AgentEmployeeAssignRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Removes an employee from an agent, revoking their permission to manage it.
    Owners and Section Supervisors can perform this.
    """
    await agent_service.remove_employee(db=db, current_user=current_user, agent_id=agent_id, target_user_id=request.user_id)
    return None

@router.get("/{agent_id}/users", status_code=status.HTTP_200_OK, response_model=List[AgentUserResponse])
async def list_agent_users(
    agent_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Retrieves users who have access to this agent in roles below the requester.
    - Owners see Supervisors (in the agent's section) and Employees (explicitly assigned).
    - Supervisors see only Employees (explicitly assigned).
    Only accessible by Owners and Supervisors managing the agent's section.
    """
    return await agent_service.list_agent_users(db=db, current_user=current_user, agent_id=agent_id)

@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Deletes an agent. Owners can delete any agent. Supervisors can only delete agents in sections they manage."""
    await agent_service.delete_agent(db=db, current_user=current_user, agent_id=agent_id)
    return None