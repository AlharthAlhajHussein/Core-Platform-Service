from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
from routers.dependencies import get_db, is_owner
from services.section_service import section_service
from views.section_schemas import SectionCreateRequest, SectionResponse, SectionUserAssignRequest

router = APIRouter(
    prefix="/api/v1/sections",
    tags=["Sections & Group Management"]
)

@router.post("", status_code=status.HTTP_201_CREATED, response_model=SectionResponse)
async def create_section(
    request: SectionCreateRequest,
    current_user: Annotated[User, Depends(is_owner)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Creates a new organizational section. Only Owners can perform this action."""
    return await section_service.create_section(db=db, current_user=current_user, name=request.name)

@router.get("", status_code=status.HTTP_200_OK, response_model=List[SectionResponse])
async def list_sections(
    current_user: Annotated[User, Depends(is_owner)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Lists all organizational sections in the company. Only Owners can perform this action."""
    return await section_service.get_all_sections(db=db, current_user=current_user)

@router.delete("/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    section_id: UUID,
    current_user: Annotated[User, Depends(is_owner)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Deletes a section. Only Owners can perform this action."""
    await section_service.delete_section(db=db, current_user=current_user, section_id=section_id)
    return None

@router.post("/{section_id}/users", status_code=status.HTTP_200_OK)
async def assign_user_to_section(
    section_id: UUID,
    request: SectionUserAssignRequest,
    current_user: Annotated[User, Depends(is_owner)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Assigns a user to a specific section. Only Owners can perform this action."""
    await section_service.assign_user(
        db=db, current_user=current_user, section_id=section_id, target_user_id=request.user_id
    )
    return {"status": "success", "detail": "User assigned to section successfully."}