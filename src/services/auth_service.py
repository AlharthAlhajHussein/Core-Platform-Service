from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status
from jose import JWTError, jwt

from models import User, CompanyUser
from helpers.config import settings
from helpers.security import verify_password, create_access_token, create_refresh_token
from helpers.redis_client import add_to_blocklist, is_blocklisted, block_token, is_token_blocked
from views.auth_schemas import TokenPayload

class AuthService:
    async def login_for_access_token(self, db: AsyncSession, email: str, password: str) -> dict:
        # 1. Find the user by email
        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalar_one_or_none()

        # Edge Case: User not found or password incorrect. Use the same error for security.
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 2. Find the user's company and role. For v1, we take the first association.
        company_user_result = await db.execute(
            select(CompanyUser).filter(CompanyUser.user_id == user.id)
        )
        company_user = company_user_result.scalar_one_or_none()

        # Edge Case: User exists but has no company/role assignment. They cannot log in.
        if not company_user and not user.is_platform_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no assigned role or company.",
            )

        # 3. Prepare the JWT payload
        token_payload = TokenPayload(
            sub=str(user.id),
            is_platform_admin=user.is_platform_admin,
            company_id=str(company_user.company_id) if company_user else None,
            role=company_user.role if company_user else None,
        )

        # 4. Create access and refresh tokens
        access_token = create_access_token(data=token_payload.model_dump())
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    async def refresh_access_token(self, db: AsyncSession, refresh_token: str) -> dict:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate refresh token"
        )
        
        if await is_token_blocked(refresh_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")

        try:
            payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.algorithm])
            type = payload.get("token_type")
            if type != "refresh":
                raise credentials_exception
            user_id = payload.get("sub")
            if user_id is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception

        user_uuid = UUID(user_id)
        if await is_blocklisted(user_uuid):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User has been logged out.")

        # Re-fetch user and company info to ensure it's up-to-date
        user = await db.get(User, user_uuid)
        if not user:
            raise credentials_exception

        company_user_result = await db.execute(select(CompanyUser).filter(CompanyUser.user_id == user.id))
        company_user = company_user_result.scalar_one_or_none()

        if not company_user and not user.is_platform_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User has no assigned role.")

        token_payload = TokenPayload(
            sub=str(user.id),
            is_platform_admin=user.is_platform_admin,
            company_id=str(company_user.company_id) if company_user else None,
            role=company_user.role if company_user else None,
        )
        new_access_token = create_access_token(data=token_payload.model_dump())
        return {"access_token": new_access_token, "token_type": "bearer"}

    async def logout_user(self, access_token: str, refresh_token: str):
        """
        Logs out a user by extracting the expiration times from both the access
        and refresh tokens and adding them to the Redis blocklist for their remaining TTL.
        """
        current_time = int(datetime.now(timezone.utc).timestamp())

        # Safely extract unverified claims (since the access token was already verified by the dependency)
        try:
            access_payload = jwt.get_unverified_claims(access_token)
            if "exp" in access_payload:
                ttl = access_payload["exp"] - current_time
                await block_token(access_token, ttl)
        except JWTError:
            pass

        try:
            refresh_payload = jwt.get_unverified_claims(refresh_token)
            if "exp" in refresh_payload:
                ttl = refresh_payload["exp"] - current_time
                await block_token(refresh_token, ttl)
        except JWTError:
            pass

auth_service = AuthService()