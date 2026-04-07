from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status

from models import Section, SectionUser, CompanyUser, User

class SectionService:
    async def create_section(self, db: AsyncSession, current_user: User, name: str) -> Section:
        new_section = Section(
            company_id=UUID(current_user.current_company_id),
            name=name
        )
        db.add(new_section)
        await db.commit()
        await db.refresh(new_section)
        return new_section

    async def delete_section(self, db: AsyncSession, current_user: User, section_id: UUID):
        section = await db.get(Section, section_id)
        # Multi-tenancy check
        if not section or str(section.company_id) != current_user.current_company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found in your company.")
        
        await db.delete(section)
        await db.commit()

    async def get_all_sections(self, db: AsyncSession, current_user: User):
        stmt = select(Section).filter(Section.company_id == UUID(current_user.current_company_id))
        result = await db.execute(stmt)
        return result.scalars().all()

    async def assign_user(self, db: AsyncSession, current_user: User, section_id: UUID, target_user_id: UUID):
        # 1. Verify section exists and belongs to company
        section = await db.get(Section, section_id)
        if not section or str(section.company_id) != current_user.current_company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found in your company.")

        # 2. Verify the target user actually belongs to the company
        cu_record = await db.execute(
            select(CompanyUser).filter(
                CompanyUser.user_id == target_user_id,
                CompanyUser.company_id == UUID(current_user.current_company_id)
            )
        )
        if not cu_record.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in your company.")

        # 3. Check if they are already assigned to prevent duplicates
        su_record = await db.execute(
            select(SectionUser).filter(SectionUser.user_id == target_user_id, SectionUser.section_id == section_id)
        )
        if not su_record.scalar_one_or_none():
            db.add(SectionUser(user_id=target_user_id, section_id=section_id))
            await db.commit()

    async def remove_user(self, db: AsyncSession, current_user: User, section_id: UUID, target_user_id: UUID):
        # 1. Verify section exists and belongs to company
        section = await db.get(Section, section_id)
        if not section or str(section.company_id) != current_user.current_company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found in your company.")

        # 2. Check if the user is assigned to the section
        su_record = await db.execute(
            select(SectionUser).filter(SectionUser.user_id == target_user_id, SectionUser.section_id == section_id)
        )
        section_user = su_record.scalar_one_or_none()
        if not section_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User is not assigned to this section.")

        # 3. Remove the assignment
        await db.delete(section_user)
        await db.commit()

section_service = SectionService()