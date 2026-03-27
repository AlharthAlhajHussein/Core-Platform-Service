from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
from routers.dependencies import get_db, get_current_user, oauth2_scheme
from services.auth_service import auth_service
from views.auth_schemas import Token, RefreshTokenRequest, NewAccessTokenResponse

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

@router.post(
    "/login", 
    response_model=Token
)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Logs in a user and returns an access and refresh token.
    Uses OAuth2 standard form data for credentials (username = email).
    """
    token_data = await auth_service.login_for_access_token(
        db=db, email=form_data.username, password=form_data.password
    )
    return token_data

@router.post(
    "/refresh", 
    response_model=NewAccessTokenResponse
)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Issues a new access token using a valid refresh token.
    """
    token_data = await auth_service.refresh_access_token(
        db=db, refresh_token=request.refresh_token
    )
    return token_data

@router.post(
    "/logout", 
    status_code=status.HTTP_204_NO_CONTENT
)
async def logout(
    request: RefreshTokenRequest,
    access_token: Annotated[str, Depends(oauth2_scheme)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Logs out the current user by taking the access token and the provided
    refresh token, and adding both to the Redis blocklist until they expire.
    """
    await auth_service.logout_user(access_token=access_token, refresh_token=request.refresh_token)
    return None # Return No Content