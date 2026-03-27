from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class EmployeeAgent(BaseModel):
    __tablename__ = "employee_agents"

    # Grants an EMPLOYEE explicit access to a single Agent
    employee_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)

    user = relationship("User")
    agent = relationship("Agent", back_populates="employees")

    # An employee can only be assigned to a specific agent once
    __table_args__ = (
        UniqueConstraint('employee_id', 'agent_id', name='uq_employee_agent'),
    )