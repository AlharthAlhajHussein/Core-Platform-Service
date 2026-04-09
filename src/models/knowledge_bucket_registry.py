from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class KnowledgeBucketRegistry(BaseModel):
    __tablename__ = "knowledge_bucket_registry"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = Column(UUID(as_uuid=True), ForeignKey("sections.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)

    # Relationships
    company = relationship("Company")
    section = relationship("Section", back_populates="knowledge_buckets")
    agents = relationship("Agent", back_populates="knowledge_bucket")
    documents = relationship("Document", back_populates="knowledge_bucket", cascade="all, delete-orphan")