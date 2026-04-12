from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
from routers.dependencies import get_db, get_current_user
from services.overview_service import overview_service
from views.overview_schemas import OverviewResponse

router = APIRouter(
    prefix="/api/v1/overview",
    tags=["Overview Dashboard"]
)

@router.get("", status_code=status.HTTP_200_OK, response_model=OverviewResponse)
async def get_overview_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Retrieves key metrics for the overview dashboard based on the user's role (RBAC).
    """
    return await overview_service.get_overview_stats(db=db, current_user=current_user)