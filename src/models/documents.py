from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class Document(BaseModel):
    __tablename__ = "documents"

    knowledge_bucket_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_bucket_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)

    # Relationships
    knowledge_bucket = relationship("KnowledgeBucketRegistry", back_populates="documents")