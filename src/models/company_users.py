import enum
from sqlalchemy import Column, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class RoleEnum(str, enum.Enum):
    OWNER = "OWNER"
    SUPERVISOR = "SUPERVISOR"
    EMPLOYEE = "EMPLOYEE"

class CompanyUser(BaseModel):
    __tablename__ = "company_users"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.EMPLOYEE)

    # Relationships
    user = relationship("User", back_populates="companies")
    company = relationship("Company", back_populates="users")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'company_id', name='uq_user_company'),
    )