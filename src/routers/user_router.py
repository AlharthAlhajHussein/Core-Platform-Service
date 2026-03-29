from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
from routers.dependencies import get_db, get_current_user, is_owner
from services.user_service import user_service
from views.user_schemas import UserCreateRequest, UserRoleUpdateRequest, UserResponse

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

@router.put("/{target_user_id}/role")
async def update_user_role(
    target_user_id: UUID,
    request: UserRoleUpdateRequest,
    current_user: Annotated[User, Depends(is_owner)], # Only Owners can do this
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Promotes or demotes a user. Will instantly log them out globally."""
    return await user_service.update_user_role(
        db=db, current_user=current_user, target_user_id=target_user_id, new_role=request.role
    )

@router.delete("/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(
    target_user_id: UUID,
    current_user: Annotated[User, Depends(is_owner)], # Only Owners can remove for now
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Removes a user from the company and instantly logs them out globally."""
    await user_service.remove_user_from_company(db=db, current_user=current_user, target_user_id=target_user_id)
    return None