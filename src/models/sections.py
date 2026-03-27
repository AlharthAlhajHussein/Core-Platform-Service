from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class Section(BaseModel):
    __tablename__ = "sections"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)

    # Relationships
    company = relationship("Company", back_populates="sections")
    users = relationship("SectionUser", back_populates="section", cascade="all, delete-orphan")
    agents = relationship("Agent", back_populates="section", cascade="all, delete-orphan")
    knowledge_buckets = relationship("KnowledgeBucketRegistry", back_populates="section", cascade="all, delete-orphan")