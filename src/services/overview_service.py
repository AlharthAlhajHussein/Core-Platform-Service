from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from models.users import User
from models.company_users import CompanyUser, RoleEnum
from models.sections import Section
from models.section_users import SectionUser
from models.agents import Agent
from models.employee_agents import EmployeeAgent
from models.conversations import Conversation, ConversationStatus
from models.knowledge_bucket_registry import KnowledgeBucketRegistry
from models.billing import UsageLog

class OverviewService:
    async def get_overview_stats(self, db: AsyncSession, current_user: User) -> dict:
        company_id = UUID(current_user.current_company_id)
        
        stats = {
            "total_sections": 0,
            "total_users": 0,
            "active_agents": 0,
            "suspended_agents": 0,
            "completed_convs": 0,
            "human_handovers": 0,
            "knowledge_bases": 0,
            "total_messages_sent": 0,
            "total_tokens_used": 0
        }

        if current_user.current_role == RoleEnum.OWNER:
            stats["total_sections"] = (await db.execute(select(func.count(Section.id)).where(Section.company_id == company_id))).scalar() or 0
            stats["total_users"] = (await db.execute(select(func.count(CompanyUser.user_id)).where(CompanyUser.company_id == company_id))).scalar() or 0
            stats["active_agents"] = (await db.execute(select(func.count(Agent.id)).where(Agent.company_id == company_id, Agent.is_active == True))).scalar() or 0
            stats["suspended_agents"] = (await db.execute(select(func.count(Agent.id)).where(Agent.company_id == company_id, Agent.is_active == False))).scalar() or 0
            stats["completed_convs"] = (await db.execute(select(func.count(Conversation.id)).where(Conversation.company_id == company_id, Conversation.status == ConversationStatus.COMPLETED))).scalar() or 0
            stats["active_convs"] = (await db.execute(select(func.count(Conversation.id)).where(Conversation.company_id == company_id, Conversation.status == ConversationStatus.ACTIVE))).scalar() or 0
            stats["human_handovers"] = (await db.execute(select(func.count(Conversation.id)).where(Conversation.company_id == company_id, Conversation.status == ConversationStatus.PENDING_HUMAN))).scalar() or 0
            stats["knowledge_bases"] = (await db.execute(select(func.count(KnowledgeBucketRegistry.id)).where(KnowledgeBucketRegistry.company_id == company_id))).scalar() or 0
            stats["total_messages_sent"] = (await db.execute(select(func.sum(UsageLog.messages_sent)).where(UsageLog.company_id == company_id))).scalar() or 0
            stats["total_tokens_used"] = (await db.execute(select(func.sum(UsageLog.tokens_used)).where(UsageLog.company_id == company_id))).scalar() or 0

        elif current_user.current_role == RoleEnum.SUPERVISOR:
            managed_sections = select(SectionUser.section_id).where(SectionUser.user_id == current_user.id)
            
            stats["total_sections"] = (await db.execute(select(func.count(Section.id)).where(Section.id.in_(managed_sections)))).scalar() or 0
            
            # Users (unique employees in managed sections)
            users_stmt = select(func.count(func.distinct(SectionUser.user_id))).join(
                CompanyUser, SectionUser.user_id == CompanyUser.user_id
            ).where(
                SectionUser.section_id.in_(managed_sections),
                CompanyUser.company_id == company_id,
                CompanyUser.role == RoleEnum.EMPLOYEE
            )
            stats["total_users"] = (await db.execute(users_stmt)).scalar() or 0
            
            stats["active_agents"] = (await db.execute(select(func.count(Agent.id)).where(Agent.section_id.in_(managed_sections), Agent.is_active == True))).scalar() or 0
            stats["suspended_agents"] = (await db.execute(select(func.count(Agent.id)).where(Agent.section_id.in_(managed_sections), Agent.is_active == False))).scalar() or 0
            
            managed_agents = select(Agent.id).where(Agent.section_id.in_(managed_sections))
            stats["completed_convs"] = (await db.execute(select(func.count(Conversation.id)).where(Conversation.agent_id.in_(managed_agents), Conversation.status == ConversationStatus.COMPLETED))).scalar() or 0
            stats["active_convs"] = (await db.execute(select(func.count(Conversation.id)).where(Conversation.agent_id.in_(managed_agents), Conversation.status == ConversationStatus.ACTIVE))).scalar() or 0
            stats["human_handovers"] = (await db.execute(select(func.count(Conversation.id)).where(Conversation.agent_id.in_(managed_agents), Conversation.status == ConversationStatus.PENDING_HUMAN))).scalar() or 0
            stats["knowledge_bases"] = (await db.execute(select(func.count(KnowledgeBucketRegistry.id)).where(KnowledgeBucketRegistry.section_id.in_(managed_sections)))).scalar() or 0
            
            stats["total_messages_sent"] = (await db.execute(select(func.sum(UsageLog.messages_sent)).where(UsageLog.agent_id.in_(managed_agents)))).scalar() or 0
            stats["total_tokens_used"] = (await db.execute(select(func.sum(UsageLog.tokens_used)).where(UsageLog.agent_id.in_(managed_agents)))).scalar() or 0

        elif current_user.current_role == RoleEnum.EMPLOYEE:
            assigned_sections = select(SectionUser.section_id).where(SectionUser.user_id == current_user.id)
            assigned_agents = select(EmployeeAgent.agent_id).where(EmployeeAgent.employee_id == current_user.id)
            
            stats["total_sections"] = (await db.execute(select(func.count(Section.id)).where(Section.id.in_(assigned_sections)))).scalar() or 0
            stats["total_users"] = 0 # Employees don't see users
            
            stats["active_agents"] = (await db.execute(select(func.count(Agent.id)).where(Agent.id.in_(assigned_agents), Agent.is_active == True))).scalar() or 0
            stats["suspended_agents"] = (await db.execute(select(func.count(Agent.id)).where(Agent.id.in_(assigned_agents), Agent.is_active == False))).scalar() or 0
            
            stats["completed_convs"] = (await db.execute(select(func.count(Conversation.id)).where(Conversation.agent_id.in_(assigned_agents), Conversation.status == ConversationStatus.COMPLETED))).scalar() or 0
            stats["active_convs"] = (await db.execute(select(func.count(Conversation.id)).where(Conversation.agent_id.in_(assigned_agents), Conversation.status == ConversationStatus.ACTIVE))).scalar() or 0
            stats["human_handovers"] = (await db.execute(select(func.count(Conversation.id)).where(Conversation.agent_id.in_(assigned_agents), Conversation.status == ConversationStatus.PENDING_HUMAN))).scalar() or 0
            
            assigned_kbs = select(Agent.knowledge_bucket_id).where(Agent.id.in_(assigned_agents), Agent.knowledge_bucket_id.is_not(None))
            stats["knowledge_bases"] = (await db.execute(select(func.count(KnowledgeBucketRegistry.id)).where(KnowledgeBucketRegistry.id.in_(assigned_kbs)))).scalar() or 0
            
            stats["total_messages_sent"] = (await db.execute(select(func.sum(UsageLog.messages_sent)).where(UsageLog.agent_id.in_(assigned_agents)))).scalar() or 0
            stats["total_tokens_used"] = (await db.execute(select(func.sum(UsageLog.tokens_used)).where(UsageLog.agent_id.in_(assigned_agents)))).scalar() or 0

        return stats

overview_service = OverviewService()