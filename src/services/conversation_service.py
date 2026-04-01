from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from models.users import User
from models.agents import Agent
from models.sections import Section
from models.section_users import SectionUser
from models.employee_agents import EmployeeAgent
from models.company_users import CompanyUser, RoleEnum
from models.conversations import Conversation
from models.messages import Message

class ConversationService:
    async def list_conversations(
        self, db: AsyncSession, user: User, skip: int, limit: int, 
        status: str | None, agent_id: UUID | None, section_id: UUID | None
    ):
        # 1. Base query joining Conversation -> Agent -> Section
        stmt = select(Conversation, Agent.name.label('agent_name'), Agent.id.label('agent_id'), Section.name.label('section_name'), Section.id.label('section_id'))
        stmt = stmt.join(Agent, Conversation.agent_id == Agent.id)
        stmt = stmt.join(Section, Agent.section_id == Section.id)
        stmt = stmt.where(Conversation.company_id == UUID(user.current_company_id))

        # 2. RBAC Row-Level Security Filters
        if user.current_role == RoleEnum.SUPERVISOR:
            subq = select(SectionUser.section_id).where(SectionUser.user_id == user.id)
            stmt = stmt.where(Agent.section_id.in_(subq))
        elif user.current_role == RoleEnum.EMPLOYEE:
            subq = select(EmployeeAgent.agent_id).where(EmployeeAgent.employee_id == user.id)
            stmt = stmt.where(Agent.id.in_(subq))

        # 3. Explicit Query Filters
        if status:
            stmt = stmt.where(Conversation.status == status)
        if agent_id:
            stmt = stmt.where(Conversation.agent_id == agent_id)
        if section_id and user.current_role == RoleEnum.OWNER:
            stmt = stmt.where(Agent.section_id == section_id)

        # 4. Pagination & Ordering
        stmt = stmt.order_by(desc(Conversation.last_activity_at)).offset(skip).limit(limit)
        
        result = await db.execute(stmt)
        rows = result.all()

        # 5. Data Enrichment (Fetching related supervisors & employees)
        agent_ids = list(set([row.agent_id for row in rows]))
        section_ids = list(set([row.section_id for row in rows]))

        employees_map = {aid: [] for aid in agent_ids}
        if agent_ids and user.current_role in [RoleEnum.OWNER, RoleEnum.SUPERVISOR]:
            emp_stmt = select(EmployeeAgent.agent_id, User.email).join(User, EmployeeAgent.employee_id == User.id).where(EmployeeAgent.agent_id.in_(agent_ids))
            for aid, email in (await db.execute(emp_stmt)).all():
                employees_map[aid].append(email.split('@')[0]) # Use email prefix as display name

        supervisors_map = {sid: [] for sid in section_ids}
        if section_ids and user.current_role == RoleEnum.OWNER:
            sup_stmt = select(SectionUser.section_id, User.email)\
                .join(User, SectionUser.user_id == User.id)\
                .join(CompanyUser, CompanyUser.user_id == User.id)\
                .where(SectionUser.section_id.in_(section_ids), CompanyUser.role == RoleEnum.SUPERVISOR, CompanyUser.company_id == UUID(user.current_company_id))
            for sid, email in (await db.execute(sup_stmt)).all():
                supervisors_map[sid].append(email.split('@')[0])

        # 6. Format Response
        response = []
        for row in rows:
            conv = row.Conversation
            item = {
                "id": conv.id,
                "sender_id": conv.sender_id,
                "status": str(conv.status) if conv.status else "UNKNOWN",
                "language": conv.language,
                "last_message_preview": conv.last_message_preview,
                "last_activity_at": conv.last_activity_at,
                "agent_name": row.agent_name,
            }
            if user.current_role in [RoleEnum.OWNER, RoleEnum.SUPERVISOR]:
                item["assigned_employees"] = employees_map.get(row.agent_id, [])
            if user.current_role == RoleEnum.OWNER:
                item["section_name"] = row.section_name
                item["assigned_supervisors"] = supervisors_map.get(row.section_id, [])
                
            response.append(item)

        return response

    async def get_enriched_single_conversation(self, db: AsyncSession, user: User, conv: Conversation):
        """Re-uses the logic above to fully format a single conversation for the detail view."""
        # We can simply wrap it in a mock list call to apply all the same enrichment rules safely.
        items = await self.list_conversations(
            db=db, user=user, skip=0, limit=1, status=None, 
            agent_id=conv.agent_id, section_id=None
        )
        # Filter down locally to guarantee we get the right one
        for item in items:
            if item["id"] == conv.id:
                return item
        return None

    async def get_conversation_messages(self, db: AsyncSession, conv_id: UUID):
        stmt = select(Message).where(Message.conversation_id == conv_id).order_by(Message.timestamp.asc())
        result = await db.execute(stmt)
        messages = result.scalars().all()
        return [{
            "id": m.id, "sender_type": str(m.sender_type), 
            "text": m.text, "media_url": m.media_url,
            "timestamp": m.timestamp
        } for m in messages]

conversation_service = ConversationService()