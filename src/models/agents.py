from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class Agent(BaseModel):
    __tablename__ = "agents"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = Column(UUID(as_uuid=True), ForeignKey("sections.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_bucket_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_bucket_registry.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # AI Persona Configuration
    name = Column(String(255), nullable=False, index=True)
    system_prompt = Column(Text, nullable=False)
    model_type = Column(String(50), nullable=False, default="gemini-2.5-flash")
    temperature = Column(Float, nullable=False, default=0.1)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Channel Integrations (Encrypted Strings)
    whatsapp_token_enc = Column(Text, nullable=True)
    telegram_token_enc = Column(Text, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="agents")
    section = relationship("Section", back_populates="agents")
    knowledge_bucket = relationship("KnowledgeBucketRegistry", back_populates="agents")
    employees = relationship("EmployeeAgent", back_populates="agent", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="agent", cascade="all, delete-orphan")
    usage_logs = relationship("UsageLog", back_populates="agent", cascade="all, delete-orphan")