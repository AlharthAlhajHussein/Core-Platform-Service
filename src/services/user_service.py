from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from fastapi import HTTPException, status

from models import User, CompanyUser, SectionUser, Section
from models.company_users import RoleEnum
from models.agents import Agent
from models.employee_agents import EmployeeAgent
from views.user_schemas import UserCreateRequest
from helpers.security import get_password_hash

class UserService:
    async def create_user(
        self, db: AsyncSession, current_user: User, user_data: UserCreateRequest
    ) -> dict:
        # 1. Enforcement checks based on role
        if current_user.current_role == RoleEnum.EMPLOYEE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employees cannot create users.")
        
        if current_user.current_role == RoleEnum.SUPERVISOR and user_data.role != RoleEnum.EMPLOYEE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Supervisors can only create Employees.")

        # Supervisors MUST assign the new employee to a section they manage
        if current_user.current_role == RoleEnum.SUPERVISOR:
            if not user_data.section_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Supervisors must assign new employees to a section.")
            sec_check = await db.execute(
                select(SectionUser).filter(
                    SectionUser.user_id == current_user.id, SectionUser.section_id == user_data.section_id
                )
            )
            if not sec_check.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not manage the specified section.")

        # Enforce multi-tenancy on the requested section (if provided)
        if user_data.section_id:
            section = await db.get(Section, user_data.section_id)
            if not section or str(section.company_id) != current_user.current_company_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found in your company.")

        # 2. Find-or-Create the global User record. This is the core of the "invite" logic.
        result = await db.execute(select(User).filter(User.email == user_data.email))
        target_user = result.scalar_one_or_none()

        if target_user:
            # User already exists globally. Check if they are already in THIS company.
            company_id = UUID(current_user.current_company_id)
            existing_link_result = await db.execute(
                select(CompanyUser).filter(
                    CompanyUser.user_id == target_user.id,
                    CompanyUser.company_id == company_id
                )
            )
            if existing_link_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User with this email is already a member of this company."
                )
            # User exists, but not in this company. We will proceed to link them.
        else:
            # User does not exist globally. Create them.
            target_user = User(
                email=user_data.email,
                hashed_password=get_password_hash(user_data.password),
                first_name=user_data.first_name,
                last_name=user_data.last_name
            )
            db.add(target_user)
            await db.flush() # Gets the UUID generated without fully committing

        # 3. Link the (new or existing) User to the Company
        company_user = CompanyUser(
            user_id=target_user.id,
            company_id=UUID(current_user.current_company_id),
            role=user_data.role
        )
        db.add(company_user)

        # 4. Link User to the Section (if provided)
        if user_data.section_id:
            section_user = SectionUser(user_id=target_user.id, section_id=user_data.section_id)
            db.add(section_user)

        await db.commit()
        
        return {
            "id": target_user.id, 
            "email": target_user.email, 
            "first_name": target_user.first_name,
            "last_name": target_user.last_name,
            "role": user_data.role
        }

    async def update_user_role(
        self, db: AsyncSession, current_user: User, target_user_id: UUID, new_role: RoleEnum
    ) -> dict:
        # Verify target is in the same company
        cu_record = await db.execute(
            select(CompanyUser).filter(
                CompanyUser.user_id == target_user_id, CompanyUser.company_id == UUID(current_user.current_company_id)
            )
        )
        company_user = cu_record.scalar_one_or_none()
        if not company_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in your company.")

        if company_user.role != new_role:
            company_user.role = new_role
            await db.commit()
            # Note: We do NOT add them to the global Redis blocklist here, as that would permanently ban them.
            # Their current access token will expire within an hour. Upon their next /refresh, 
            # the system will naturally issue a new token containing their updated role.

        return {"status": "role_updated", "new_role": new_role}

    async def remove_user_from_company(
        self, db: AsyncSession, current_user: User, target_user_id: UUID
    ):
        if current_user.current_role == RoleEnum.EMPLOYEE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employees cannot remove users.")
            
        if current_user.id == target_user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot remove yourself.")

        cu_record = await db.execute(
            select(CompanyUser).filter(
                CompanyUser.user_id == target_user_id, CompanyUser.company_id == UUID(current_user.current_company_id)
            )
        )
        company_user = cu_record.scalar_one_or_none()
        
        if not company_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in your company.")

        # Supervisor RBAC Check
        if current_user.current_role == RoleEnum.SUPERVISOR:
            if company_user.role != RoleEnum.EMPLOYEE:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Supervisors can only remove Employees.")
            
            overlap_query = select(SectionUser).where(
                SectionUser.user_id == target_user_id,
                SectionUser.section_id.in_(
                    select(SectionUser.section_id).where(SectionUser.user_id == current_user.id)
                )
            )
            overlap_result = await db.execute(overlap_query)
            if not overlap_result.scalars().first():
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not manage this user's section.")

        company_uuid = UUID(current_user.current_company_id)

        # 1. Clean up: Remove user from all sections in this company
        sections_subq = select(Section.id).where(Section.company_id == company_uuid)
        await db.execute(
            delete(SectionUser).where(
                SectionUser.user_id == target_user_id, SectionUser.section_id.in_(sections_subq)
            )
        )

        # 2. Clean up edge case: Remove user from all explicit agent assignments
        agents_subq = select(Agent.id).where(Agent.company_id == company_uuid)
        await db.execute(
            delete(EmployeeAgent).where(
                EmployeeAgent.employee_id == target_user_id, EmployeeAgent.agent_id.in_(agents_subq)
            )
        )

        # 3. Delete the relationship, revoking their access to this tenant.
        await db.delete(company_user)
        await db.commit()

        # Note: Global blocklisting is avoided here so we don't accidentally lock the user out of other companies they might belong to.

    async def list_users(self, db: AsyncSession, current_user: User, section_id: UUID | None = None) -> list[dict]:
        # 1. Block employees entirely from viewing user lists
        if current_user.current_role == RoleEnum.EMPLOYEE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employees cannot view user lists.")

        # 2. Base query: Get users in the same company
        stmt = select(User, CompanyUser.role).join(CompanyUser, User.id == CompanyUser.user_id)
        stmt = stmt.where(CompanyUser.company_id == UUID(current_user.current_company_id))

        # 3. Apply RBAC Filters
        if current_user.current_role == RoleEnum.SUPERVISOR:
            # Supervisors can ONLY see Employees
            stmt = stmt.where(CompanyUser.role == RoleEnum.EMPLOYEE)
            
            if section_id:
                # Verify the supervisor actually manages this specific section
                su_check = await db.execute(select(SectionUser).filter(SectionUser.user_id == current_user.id, SectionUser.section_id == section_id))
                if not su_check.scalar_one_or_none():
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not manage this section.")
                stmt = stmt.join(SectionUser, User.id == SectionUser.user_id).where(SectionUser.section_id == section_id)
            else:
                # If no section is specified, show employees across ALL sections this supervisor manages
                managed_sections = select(SectionUser.section_id).where(SectionUser.user_id == current_user.id)
                stmt = stmt.join(SectionUser, User.id == SectionUser.user_id).where(SectionUser.section_id.in_(managed_sections))

        elif current_user.current_role == RoleEnum.OWNER:
            # Owners see all Supervisors and Employees
            stmt = stmt.where(CompanyUser.role.in_([RoleEnum.SUPERVISOR, RoleEnum.EMPLOYEE]))
            if section_id:
                stmt = stmt.join(SectionUser, User.id == SectionUser.user_id).where(SectionUser.section_id == section_id)

        result = await db.execute(stmt)
        rows = result.all()

        # 4. Deduplicate users (in case an employee is in multiple sections managed by the same supervisor)
        users_map = {}
        for user, role in rows:
            if user.id not in users_map:
                users_map[user.id] = {
                    "id": user.id, 
                    "email": user.email, 
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": role
                }

        return list(users_map.values())

user_service = UserService()