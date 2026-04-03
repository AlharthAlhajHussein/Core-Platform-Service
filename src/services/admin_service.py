from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.companies import Company
from models.users import User
from models.company_users import CompanyUser, RoleEnum
from views.admin_schemas import TenantOnboardRequest
from helpers.security import get_password_hash

class AdminService:
    async def onboard_tenant(self, db: AsyncSession, request: TenantOnboardRequest) -> dict:
        # 1. Create the new Company
        new_company = Company(name=request.company_name)
        db.add(new_company)
        await db.flush() # Get the company ID without committing

        # 2. Check if the requested Owner user already exists globally
        result = await db.execute(select(User).filter(User.email == request.owner_email))
        target_user = result.scalar_one_or_none()

        if not target_user:
            # Create the user if they do not exist
            target_user = User(
                email=request.owner_email,
                hashed_password=get_password_hash(request.owner_password),
                first_name=request.owner_first_name,
                last_name=request.owner_last_name
            )
            db.add(target_user)
            await db.flush()
        
        # 3. Link the user to the new company with the OWNER role
        company_user = CompanyUser(
            user_id=target_user.id,
            company_id=new_company.id,
            role=RoleEnum.OWNER
        )
        db.add(company_user)
        await db.commit()
        await db.refresh(new_company)

        return {
            "company": new_company,
            "owner": {
                "id": target_user.id,
                "email": target_user.email,
                "first_name": target_user.first_name,
                "last_name": target_user.last_name
            }
        }
    
    async def list_companies(self, db: AsyncSession):
        result = await db.execute(select(Company))
        return result.scalars().all()

admin_service = AdminService()