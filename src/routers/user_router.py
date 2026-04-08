from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
from routers.dependencies import get_db, get_current_user, is_owner
from services.user_service import user_service
from views.user_schemas import UserCreateRequest, UserRoleUpdateRequest, UserResponse, UserDetailResponse

router = APIRouter(
    prefix="/api/v1/users",
    tags=["User Management"]
)

@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def create_user(
    request: UserCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Creates a new user. Owners can create both Supervisors and Employees.
    Supervisors can only create Employees and must assign them to a section they manage.
    """
    return await user_service.create_user(db=db, current_user=current_user, user_data=request)

@router.get("", status_code=status.HTTP_200_OK, response_model=List[UserResponse])
async def list_users(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    section_id: Optional[UUID] = Query(None, description="Filter users by a specific section.")
):
    """
    Lists users in the company. 
    Owners see all Supervisors and Employees. 
    Supervisors see all Employees in sections they manage.
    """
    return await user_service.list_users(db=db, current_user=current_user, section_id=section_id)

@router.get("/me", status_code=status.HTTP_200_OK, response_model=UserDetailResponse)
async def get_my_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Retrieves detailed profile information for the currently authenticated user, 
    including all associated companies and sections across the platform.
    Accessible by all users.
    """
    return await user_service.get_user_details(db=db, current_user=current_user)

@router.put("/{user_id}/role")
async def update_user_role(
    user_id: UUID,
    request: UserRoleUpdateRequest,
    current_user: Annotated[User, Depends(is_owner)], # Only Owners can do this
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Promotes or demotes a user. Will instantly log them out globally."""
    return await user_service.update_user_role(
        db=db, current_user=current_user, target_user_id=user_id, new_role=request.role
    )

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)], 
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Removes a user from the company. Owners can remove anyone. Supervisors can remove employees in their sections."""
    await user_service.remove_user_from_company(db=db, current_user=current_user, target_user_id=user_id)
    return None