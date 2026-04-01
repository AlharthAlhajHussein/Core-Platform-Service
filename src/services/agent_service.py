from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status

from models.agents import Agent
from models.users import User
from models.sections import Section
from models.section_users import SectionUser
from models.company_users import CompanyUser, RoleEnum
from models.employee_agents import EmployeeAgent
from views.agent_schemas import AgentCreateRequest, AgentUpdateRequest
from helpers.encryption import encrypt
from helpers.redis_client import delete_agent_config_cache

class AgentService:
    async def create_agent(self, db: AsyncSession, current_user: User, agent_data: AgentCreateRequest) -> Agent:
        # 1. Block employees from creating agents
        if current_user.current_role == RoleEnum.EMPLOYEE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employees cannot create agents.")

        # 2. Verify Section exists and enforce multi-tenancy
        section = await db.get(Section, agent_data.section_id)
        if not section or str(section.company_id) != current_user.current_company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found in your company.")

        # 3. Supervisor Rules: Supervisors can ONLY create agents in sections they explicitly manage.
        # Owners bypass this check and can create an agent in ANY section in the company.
        if current_user.current_role == RoleEnum.SUPERVISOR:
            su_check = await db.execute(
                select(SectionUser).filter(
                    SectionUser.user_id == current_user.id, SectionUser.section_id == agent_data.section_id
                )
            )
            if not su_check.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Supervisors can only create agents in sections they manage.")

        # 4. Create the Agent, encrypting tokens securely at rest
        new_agent = Agent(
            company_id=UUID(current_user.current_company_id),
            section_id=agent_data.section_id,
            name=agent_data.name,
            system_prompt=agent_data.system_prompt,
            model_type=agent_data.model_type,
            temperature=agent_data.temperature,
            whatsapp_token_enc=encrypt(agent_data.whatsapp_token) if agent_data.whatsapp_token else None,
            telegram_token_enc=encrypt(agent_data.telegram_token) if agent_data.telegram_token else None,
            whatsapp_number=agent_data.whatsapp_number,
            telegram_bot_username=agent_data.telegram_bot_username
        )
        db.add(new_agent)
        await db.commit()
        await db.refresh(new_agent)
        return new_agent

    async def list_agents(
        self, db: AsyncSession, current_user: User, 
        section_id: UUID | None = None, user_id: UUID | None = None
    ) -> list[Agent]:
        
        # Base query: Only agents in the current user's company
        stmt = select(Agent).where(Agent.company_id == UUID(current_user.current_company_id))

        if current_user.current_role == RoleEnum.OWNER:
            if section_id:
                stmt = stmt.where(Agent.section_id == section_id)
            if user_id:
                stmt = stmt.join(EmployeeAgent, Agent.id == EmployeeAgent.agent_id).where(EmployeeAgent.employee_id == user_id)
                
        elif current_user.current_role == RoleEnum.SUPERVISOR:
            # Restrict to sections managed by this supervisor
            managed_sections = select(SectionUser.section_id).where(SectionUser.user_id == current_user.id)
            stmt = stmt.where(Agent.section_id.in_(managed_sections))
            if user_id:
                stmt = stmt.join(EmployeeAgent, Agent.id == EmployeeAgent.agent_id).where(EmployeeAgent.employee_id == user_id)
                
        elif current_user.current_role == RoleEnum.EMPLOYEE:
            # Employees can only see agents explicitly assigned to them (filters are ignored)
            stmt = stmt.join(EmployeeAgent, Agent.id == EmployeeAgent.agent_id).where(EmployeeAgent.employee_id == current_user.id)

        result = await db.execute(stmt)
        return result.scalars().all()

    async def assign_employee(self, db: AsyncSession, current_user: User, agent_id: UUID, target_user_id: UUID):
        """Assigns an employee to an agent, giving them permission to update its config."""
        if current_user.current_role == RoleEnum.EMPLOYEE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employees cannot manage agent access.")

        agent = await db.get(Agent, agent_id)
        if not agent or str(agent.company_id) != current_user.current_company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

        # Supervisors must manage the section the agent belongs to
        if current_user.current_role == RoleEnum.SUPERVISOR:
            su_check = await db.execute(
                select(SectionUser).filter(
                    SectionUser.user_id == current_user.id, SectionUser.section_id == agent.section_id
                )
            )
            if not su_check.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not manage this agent's section.")

        # Ensure target user belongs to the company
        cu_check = await db.execute(
            select(CompanyUser).filter(
                CompanyUser.user_id == target_user_id, CompanyUser.company_id == UUID(current_user.current_company_id)
            )
        )
        if not cu_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found in your company.")

        # Assign if not already assigned
        ea_check = await db.execute(
            select(EmployeeAgent).filter(EmployeeAgent.employee_id == target_user_id, EmployeeAgent.agent_id == agent_id)
        )
        if not ea_check.scalar_one_or_none():
            db.add(EmployeeAgent(employee_id=target_user_id, agent_id=agent_id))
            await db.commit()

    async def update_agent(self, db: AsyncSession, agent: Agent, update_data: AgentUpdateRequest) -> Agent:
        # The dependency `can_access_agent` in the router already verified the user has permission to do this.
        if update_data.name is not None: agent.name = update_data.name
        if update_data.system_prompt is not None: agent.system_prompt = update_data.system_prompt
        if update_data.model_type is not None: agent.model_type = update_data.model_type
        if update_data.temperature is not None: agent.temperature = update_data.temperature
        if update_data.is_active is not None: agent.is_active = update_data.is_active
        if update_data.knowledge_bucket_registry_id is not None: agent.knowledge_bucket_id = update_data.knowledge_bucket_registry_id
        if update_data.whatsapp_number is not None: agent.whatsapp_number = update_data.whatsapp_number if update_data.whatsapp_number else None
        if update_data.telegram_bot_username is not None: agent.telegram_bot_username = update_data.telegram_bot_username if update_data.telegram_bot_username else None
        
        # Re-encrypt tokens if provided
        if update_data.whatsapp_token is not None:
            agent.whatsapp_token_enc = encrypt(update_data.whatsapp_token) if update_data.whatsapp_token else None
        if update_data.telegram_token is not None:
            agent.telegram_token_enc = encrypt(update_data.telegram_token) if update_data.telegram_token else None

        await db.commit()
        
        # Extremely Important Edge Case: Invalidate the Redis cache for this agent!
        # Next time Gateway/Orchestrator requests this config, they will pull the fresh updates.
        await delete_agent_config_cache(agent.id)
        
        return agent

    async def delete_agent(self, db: AsyncSession, current_user: User, agent_id: UUID):
        # 1. Block employees entirely
        if current_user.current_role == RoleEnum.EMPLOYEE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employees cannot delete agents.")

        # 2. Fetch the agent and verify company tenancy
        agent = await db.get(Agent, agent_id)
        if not agent or str(agent.company_id) != current_user.current_company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

        # 3. Supervisor rules: must manage the section the agent belongs to
        if current_user.current_role == RoleEnum.SUPERVISOR:
            su_check = await db.execute(
                select(SectionUser).filter(
                    SectionUser.user_id == current_user.id, SectionUser.section_id == agent.section_id
                )
            )
            if not su_check.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Supervisors can only delete agents in sections they manage.")

        # 4. Delete the agent and invalidate its config cache in Redis
        await db.delete(agent)
        await db.commit()
        await delete_agent_config_cache(agent_id)

agent_service = AgentService()