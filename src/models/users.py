from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship
from .base import BaseModel

class User(BaseModel):
    __tablename__ = "users"

    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # "God Mode" switch for your internal tech team
    is_platform_admin = Column(Boolean, default=False, nullable=False)

    # Relationships
    companies = relationship("CompanyUser", back_populates="user", cascade="all, delete-orphan")