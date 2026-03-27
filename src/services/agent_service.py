from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status

from models import Agent, Section, KnowledgeBucketRegistry
from views.agent_schemas import AgentCreate, AgentUpdate
from helpers.encryption import encrypt_data
from helpers.redis_client import delete_agent_config_cache

class AgentService:
    async def create_agent(
        self, db: AsyncSession, agent_data: AgentCreate, company_id: UUID
    ) -> Agent:
        # Edge Case: Validate that the section and (optional) KB belong to the company.
        section_result = await db.execute(
            select(Section).filter(Section.id == agent_data.section_id, Section.company_id == company_id)
        )
        if not section_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found for this company.")

        if agent_data.knowledge_bucket_id:
            kb_result = await db.execute(
                select(KnowledgeBucketRegistry).filter(
                    KnowledgeBucketRegistry.id == agent_data.knowledge_bucket_id,
                    KnowledgeBucketRegistry.company_id == company_id
                )
            )
            if not kb_result.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge Bucket not found for this company.")

        # Encrypt tokens before saving.
        encrypted_whatsapp = encrypt_data(agent_data.whatsapp_token)
        encrypted_telegram = encrypt_data(agent_data.telegram_token)

        new_agent = Agent(
            **agent_data.model_dump(exclude={"whatsapp_token", "telegram_token"}),
            company_id=company_id,
            whatsapp_token_enc=encrypted_whatsapp,
            telegram_token_enc=encrypted_telegram,
        )
        db.add(new_agent)
        await db.commit()
        await db.refresh(new_agent)
        return new_agent

    async def update_agent(
        self, db: AsyncSession, agent: Agent, update_data: AgentUpdate
    ) -> Agent:
        # The 'agent' object is provided by the `can_access_agent` dependency.

        update_dict = update_data.model_dump(exclude_unset=True)

        # Handle token encryption if new tokens are provided.
        if "whatsapp_token" in update_dict:
            agent.whatsapp_token_enc = encrypt_data(update_dict.pop("whatsapp_token"))
        
        if "telegram_token" in update_dict:
            agent.telegram_token_enc = encrypt_data(update_dict.pop("telegram_token"))

        for key, value in update_dict.items():
            setattr(agent, key, value)

        db.add(agent)
        await db.commit()
        await db.refresh(agent)

        # CRITICAL: Invalidate the Redis cache for this agent after the DB update.
        await delete_agent_config_cache(agent.id)

        return agent

agent_service = AgentService()