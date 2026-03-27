from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from helpers.config import settings
from helpers.database import AsyncSessionLocal
from helpers.redis_client import is_blocklisted, is_token_blocked
from models.users import User
from models.company_users import CompanyUser, RoleEnum
from models.agents import Agent
from models.employee_agents import EmployeeAgent
from models.knowledge_bucket_registry import KnowledgeBucketRegistry
from models.section_users import SectionUser
from views.auth_schemas import TokenPayload
from fastapi import Header

# OAuth2PasswordBearer is used to extract the token from the Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_db() -> AsyncSession:
    """Dependency that provides a database session."""
    async with AsyncSessionLocal() as session:
        yield session

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    """
    Decodes and validates the JWT token, checks for blocklisting,
    and fetches the authenticated user from the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # 1. Check if the specific token is blocklisted (e.g., user logged out this session)
    if await is_token_blocked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Decode the JWT token
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        # Validate the payload structure using our Pydantic schema
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise credentials_exception

    # 2. Check if the user is globally blocklisted (e.g., suspended by admin)
    if await is_blocklisted(token_data.sub):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch the user from the database
    user_id = UUID(token_data.sub)
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    
    # Attach company_id and role to the user object for easier access in subsequent dependencies
    # This is an important optimization to avoid re-fetching this data
    user.current_company_id = token_data.company_id
    user.current_role = token_data.role
    user.is_platform_admin = token_data.is_platform_admin

    return user

# --- RBAC Specific Dependencies ---

def is_owner(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """
    Dependency that checks if the current user has the 'OWNER' role.
    Raises a 403 Forbidden error if not.
    """
    if not current_user.is_platform_admin and current_user.current_role != RoleEnum.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted: Requires OWNER role."
        )
    return current_user

async def can_access_agent(
    agent_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> Agent:
    """
    A complex dependency to verify if a user can access a specific agent.
    It checks based on the user's role (OWNER, SUPERVISOR, EMPLOYEE).
    Returns the agent object on success for the route to use.
    """
    # 1. Fetch the agent from the database
    result = await db.execute(select(Agent).filter(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # 2. Handle "God Mode" for platform administrators
    if current_user.is_platform_admin:
        return agent

    # 3. Enforce strict multi-tenancy
    if str(agent.company_id) != current_user.current_company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this resource is forbidden")

    # 4. Apply role-based logic
    role = current_user.current_role
    if role == RoleEnum.OWNER:
        return agent # Owners can access any agent in their company

    if role == RoleEnum.SUPERVISOR:
        # Supervisors can access agents in sections they manage.
        query = select(SectionUser).filter(
            SectionUser.user_id == current_user.id,
            SectionUser.section_id == agent.section_id
        )
        result = await db.execute(query)
        if result.scalar_one_or_none():
            return agent

    if role == RoleEnum.EMPLOYEE:
        # Employees can only access agents they are explicitly assigned to.
        query = select(EmployeeAgent).filter(
            EmployeeAgent.employee_id == current_user.id,
            EmployeeAgent.agent_id == agent_id
        )
        result = await db.execute(query)
        if result.scalar_one_or_none():
            return agent

    # 5. If no permissions match, deny access
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to access this agent.")

async def can_access_kb(
    kb_registry_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> KnowledgeBucketRegistry:
    """
    Dependency to verify if a user can access a specific knowledge bucket.
    Returns the knowledge bucket object on success.
    """
    # 1. Fetch the knowledge bucket from the database
    result = await db.execute(select(KnowledgeBucketRegistry).filter(KnowledgeBucketRegistry.id == kb_registry_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge bucket not found")

    # 2. Handle "God Mode" for platform administrators
    if current_user.is_platform_admin:
        return kb

    # 3. Enforce strict multi-tenancy
    if str(kb.company_id) != current_user.current_company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this resource is forbidden")

    # 4. Apply role-based logic
    role = current_user.current_role
    if role == RoleEnum.OWNER:
        return kb # Owners can access any KB in their company

    if role == RoleEnum.SUPERVISOR:
        # Supervisors and Employees can access KBs in sections they are members of.
        query = select(SectionUser).filter(
            SectionUser.user_id == current_user.id,
            SectionUser.section_id == kb.section_id
        )
        result = await db.execute(query)
        if result.scalar_one_or_none():
            return kb
    
    if role == RoleEnum.EMPLOYEE:
        # Employees can only access a Knowledge Bucket if they are assigned to an Agent
        # that is linked to this specific Knowledge Bucket.
        query = select(EmployeeAgent).join(Agent).filter(
            EmployeeAgent.employee_id == current_user.id,
            Agent.id == EmployeeAgent.agent_id, # Explicit join condition
            Agent.knowledge_bucket_id == kb_registry_id,
            Agent.company_id == UUID(current_user.current_company_id) # Ensure multi-tenancy for the agent
        )
        result = await db.execute(query)
        if result.scalars().first():
            return kb

    # 5. If no permissions match, deny access
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to access this knowledge bucket.")


async def verify_internal_secret(x_internal_secret: Annotated[str | None, Header()] = None):
    """
    Dependency to verify the static secret for internal service-to-service communication.
    """
    # Edge Case: Handle both missing header and incorrect secret value.
    if not x_internal_secret or x_internal_secret != settings.internal_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Internal-Secret header."
        )
