import enum
from sqlalchemy import Column, String, Integer, Boolean, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class PlanTier(str, enum.Enum):
    STARTER = "STARTER"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"

class Subscription(BaseModel):
    __tablename__ = "subscriptions"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    plan_tier = Column(Enum(PlanTier), nullable=False, default=PlanTier.STARTER, index=True)
    billing_cycle_end = Column(DateTime(timezone=True), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_over_limit = Column(Boolean, default=False, nullable=False, index=True)

    company = relationship("Company")

class UsageLog(BaseModel):
    __tablename__ = "usage_logs"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    billing_month = Column(String(7), nullable=False, index=True) # Format: 'YYYY-MM'
    messages_sent = Column(Integer, default=0, nullable=False)
    tokens_used = Column(Integer, default=0, nullable=False)

    agent = relationship("Agent", back_populates="usage_logs")