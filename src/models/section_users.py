from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class SectionUser(BaseModel):
    __tablename__ = "section_users"

    section_id = Column(UUID(as_uuid=True), ForeignKey("sections.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    section = relationship("Section", back_populates="users")
    user = relationship("User") 

    # A user can only be added to a specific section once
    __table_args__ = (
        UniqueConstraint('section_id', 'user_id', name='uq_section_user'),
    )