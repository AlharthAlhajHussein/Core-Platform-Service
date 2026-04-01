from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from fastapi import HTTPException, status

from models import KnowledgeBucketRegistry, Section
from models.users import User
from models.company_users import RoleEnum
from models.section_users import SectionUser
from models.agents import Agent
from models.employee_agents import EmployeeAgent
from views.kb_schemas import KnowledgeBucketCreate
from services.rag_proxy_service import rag_proxy_service

class KnowledgeBucketService:
    async def create_bucket(
        self,
        db: AsyncSession,
        kb_data: KnowledgeBucketCreate,
        current_user: User,
    ) -> KnowledgeBucketRegistry:
        company_id = UUID(current_user.current_company_id)

        # 1. Block employees entirely
        if current_user.current_role == RoleEnum.EMPLOYEE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employees cannot create knowledge buckets.")

        # 2. Supervisor Rules: Must manage the section
        if current_user.current_role == RoleEnum.SUPERVISOR:
            su_check = await db.execute(select(SectionUser).filter(SectionUser.user_id == current_user.id, SectionUser.section_id == kb_data.section_id))
            if not su_check.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Supervisors can only create knowledge buckets in sections they manage.")

        # 3. Verify the target section exists and belongs to the company.
        section_result = await db.execute(
            select(Section).filter(Section.id == kb_data.section_id, Section.company_id == company_id)
        )
        if not section_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Section not found or does not belong to this company.",
            )

        # 4. Call the RAG service to create the underlying container.
        # If this fails, the proxy will raise an HTTPException and we won't proceed.
        rag_response = await rag_proxy_service.create_knowledge_bucket(
            name=kb_data.name, company_id=company_id
        )
        # The RAG service returns the ID under the key "container_id".
        rag_container_id = rag_response.get("container_id")

        # 5. Create the registry record in our own database with the ID from the RAG service.
        new_kb_registry = KnowledgeBucketRegistry(
            name=kb_data.name,
            section_id=kb_data.section_id,
            company_id=company_id,
            rag_container_id=UUID(rag_container_id),
        )
        db.add(new_kb_registry)
        await db.commit()
        await db.refresh(new_kb_registry)

        return new_kb_registry

    async def delete_bucket(self, db: AsyncSession, current_user: User, kb_registry_id: UUID):
        # 1. Block employees entirely
        if current_user.current_role == RoleEnum.EMPLOYEE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employees cannot delete knowledge buckets.")

        kb = await db.get(KnowledgeBucketRegistry, kb_registry_id)
        if not kb or str(kb.company_id) != current_user.current_company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge bucket not found.")

        # 2. Supervisor Rules: Must manage the section
        if current_user.current_role == RoleEnum.SUPERVISOR:
            su_check = await db.execute(select(SectionUser).filter(SectionUser.user_id == current_user.id, SectionUser.section_id == kb.section_id))
            if not su_check.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Supervisors can only delete knowledge buckets in sections they manage.")

        # 3. Edge Case: If an Agent is using this Knowledge Bucket, gracefully unlink it to prevent breaking the Agent.
        await db.execute(
            update(Agent)
            .where(Agent.knowledge_bucket_id == kb_registry_id)
            .values(knowledge_bucket_id=None)
        )

        # Optional: Call rag_proxy_service.delete_knowledge_bucket(rag_container_id=str(kb.rag_container_id)) here.
        
        await db.delete(kb)
        await db.commit()

    async def list_buckets(
        self, db: AsyncSession, current_user: User, section_id: UUID | None = None
    ) -> list[KnowledgeBucketRegistry]:
        
        # Base query: Only buckets in the current user's company
        stmt = select(KnowledgeBucketRegistry).where(KnowledgeBucketRegistry.company_id == UUID(current_user.current_company_id))

        if current_user.current_role == RoleEnum.OWNER:
            if section_id:
                stmt = stmt.where(KnowledgeBucketRegistry.section_id == section_id)
                
        elif current_user.current_role == RoleEnum.SUPERVISOR:
            # Restrict to sections managed by this supervisor
            managed_sections = select(SectionUser.section_id).where(SectionUser.user_id == current_user.id)
            stmt = stmt.where(KnowledgeBucketRegistry.section_id.in_(managed_sections))
            
        elif current_user.current_role == RoleEnum.EMPLOYEE:
            # Employees only see KBs that are linked to agents they are explicitly assigned to manage
            assigned_agents_kbs = (
                select(Agent.knowledge_bucket_id)
                .join(EmployeeAgent, Agent.id == EmployeeAgent.agent_id)
                .where(
                    EmployeeAgent.employee_id == current_user.id,
                    Agent.knowledge_bucket_id.is_not(None) # Only agents that actually have a KB
                )
            )
            stmt = stmt.where(KnowledgeBucketRegistry.id.in_(assigned_agents_kbs))

        result = await db.execute(stmt)
        return result.scalars().all()

knowledge_bucket_service = KnowledgeBucketService()