import enum
from sqlalchemy import Column, String, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class ConversationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PENDING_HUMAN = "PENDING_HUMAN"
    COMPLETED = "COMPLETED"

class ConversationEvaluation(str, enum.Enum):
    BAD = "BAD"
    NORMAL = "NORMAL"
    GOOD = "GOOD"
    VERY_GOOD = "VERY_GOOD"
    EXCELLENT = "EXCELLENT"
    OTHERS = "OTHERS"

class Conversation(BaseModel):
    __tablename__ = "conversations"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    platform = Column(String(50), nullable=False, index=True) # e.g. "whatsapp", "telegram"
    sender_id = Column(String(255), nullable=False, index=True) # E.g. User's phone number
    language = Column(String(10), nullable=True)
    status = Column(Enum(ConversationStatus), nullable=False, default=ConversationStatus.ACTIVE, index=True)
    last_message_preview = Column(String(500), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True, index=True)
    evaluation = Column(Enum(ConversationEvaluation), nullable=True, index=True)
    evaluation_notes = Column(String(1000), nullable=True)

    # Relationships
    company = relationship("Company")
    agent = relationship("Agent", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")