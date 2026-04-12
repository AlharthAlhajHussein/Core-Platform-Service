from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from fastapi import HTTPException, status

from models import User, CompanyUser, SectionUser, Section, Company
from models.company_users import RoleEnum
from models.agents import Agent
from models.employee_agents import EmployeeAgent
from views.user_schemas import UserCreateRequest, UserProfileUpdateRequest, UserAccountSettingsUpdateRequest
from helpers.security import get_password_hash, verify_password

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

        company_uuid = UUID(current_user.current_company_id)

        # OWNER LOGIC: Remove user from all sections in this company
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
                    "position": user.position,
                    "profile_image": user.profile_image,
                    "role": role
                }

        return list(users_map.values())

    async def get_user_details(self, db: AsyncSession, current_user: User) -> dict:
        # Fetch all companies the user belongs to along with their role in each
        companies_stmt = select(Company.id, Company.name, CompanyUser.role).join(
            CompanyUser, Company.id == CompanyUser.company_id
        ).where(CompanyUser.user_id == current_user.id)
        companies_result = await db.execute(companies_stmt)
        companies = [
            {"id": row.id, "name": row.name, "role": row.role}
            for row in companies_result.all()
        ]

        # Fetch all sections the user is explicitly assigned to
        sections_stmt = select(Section.id, Section.name, Section.company_id).join(
            SectionUser, Section.id == SectionUser.section_id
        ).where(SectionUser.user_id == current_user.id)
        sections_result = await db.execute(sections_stmt)
        sections = [
            {"id": row.id, "name": row.name, "company_id": row.company_id}
            for row in sections_result.all()
        ]

        return {
            "id": current_user.id, "email": current_user.email, "first_name": current_user.first_name, 
            "last_name": current_user.last_name, "is_platform_admin": current_user.is_platform_admin,
            "position": current_user.position, "bio": current_user.bio, "profile_image": current_user.profile_image,
            "phone_number": current_user.phone_number, "country": current_user.country, "gender": current_user.gender,
            "current_role": current_user.current_role, "companies": companies, "sections": sections
        }

    async def update_user_profile(
        self, db: AsyncSession, current_user: User, update_data: UserProfileUpdateRequest
    ) -> dict:
        
        # Check explicitly set fields to correctly handle `None` values (e.g. unlinking a profile image)
        update_dict = update_data.model_dump(exclude_unset=True) if hasattr(update_data, "model_dump") else update_data.dict(exclude_unset=True)
        
        # We need to explicitly reload the user to avoid session issues and be able to return fresh state
        user = await db.get(User, current_user.id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
            
        if update_data.first_name is not None: user.first_name = update_data.first_name
        if update_data.last_name is not None: user.last_name = update_data.last_name
        
        if "position" in update_dict: user.position = update_dict["position"]
        if "bio" in update_dict: user.bio = update_dict["bio"]
        if "profile_image" in update_dict: user.profile_image = None if update_dict["profile_image"] == "" else update_dict["profile_image"]
        if "phone_number" in update_dict: user.phone_number = update_dict["phone_number"]
        if "country" in update_dict: user.country = update_dict["country"]
        if "gender" in update_dict: user.gender = update_dict["gender"]
        
        await db.commit()
        await db.refresh(user)
        
        # Update current_user so the return payload is built accurately 
        current_user.first_name = user.first_name
        current_user.last_name = user.last_name
        current_user.position = user.position
        current_user.bio = user.bio
        current_user.profile_image = user.profile_image
        current_user.phone_number = user.phone_number
        current_user.country = user.country
        current_user.gender = user.gender
        
        return await self.get_user_details(db, current_user)
        
    async def update_user_account_settings(
        self, db: AsyncSession, current_user: User, update_data: UserAccountSettingsUpdateRequest
    ):
        user = await db.get(User, current_user.id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
            
        # Verify old password
        if not verify_password(update_data.old_password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect old password.")
            
        # Check if email is being updated and verify uniqueness
        if update_data.new_email and update_data.new_email != user.email:
            existing_user = await db.execute(select(User).filter(User.email == update_data.new_email))
            if existing_user.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already in use.")
            user.email = update_data.new_email
            
        # Check if password is being updated
        if update_data.new_password:
            user.hashed_password = get_password_hash(update_data.new_password)
            
        await db.commit()

user_service = UserService()