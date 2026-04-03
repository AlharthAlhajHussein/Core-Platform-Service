from typing import Annotated, List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from routers.dependencies import get_db, is_platform_admin
from services.admin_service import admin_service
from views.admin_schemas import TenantOnboardRequest, CompanyResponse

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Platform Administration"],
    dependencies=[Depends(is_platform_admin)] # Secures ALL routes in this file
)

@router.post("/tenants", status_code=status.HTTP_201_CREATED)
async def onboard_new_tenant(
    request: TenantOnboardRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Creates a new Company and provisions the initial Owner account.
    If the user already exists, they are simply linked to the new company as an Owner.
    """
    return await admin_service.onboard_tenant(db=db, request=request)

@router.get("/companies", status_code=status.HTTP_200_OK, response_model=List[CompanyResponse])
async def list_all_companies(
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Lists all companies on the platform."""
    return await admin_service.list_companies(db=db)