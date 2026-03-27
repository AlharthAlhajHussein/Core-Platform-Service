from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status

from models import KnowledgeBucketRegistry, Section
from views.kb_schemas import KnowledgeBucketCreate
from services.rag_proxy_service import rag_proxy_service

class KnowledgeBucketService:
    async def create_bucket(
        self,
        db: AsyncSession,
        kb_data: KnowledgeBucketCreate,
        company_id: UUID,
    ) -> KnowledgeBucketRegistry:
        # Edge Case 1: Verify the target section exists and belongs to the company.
        section_result = await db.execute(
            select(Section).filter(Section.id == kb_data.section_id, Section.company_id == company_id)
        )
        if not section_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Section not found or does not belong to this company.",
            )

        # Step 1: Call the RAG service to create the underlying container.
        # If this fails, the proxy will raise an HTTPException and we won't proceed.
        rag_response = await rag_proxy_service.create_knowledge_bucket(
            name=kb_data.name, company_id=company_id
        )
        rag_container_id = rag_response.get("id")

        # Step 2: Create the registry record in our own database with the ID from the RAG service.
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

knowledge_bucket_service = KnowledgeBucketService()