from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship
from .base import BaseModel

class User(BaseModel):
    __tablename__ = "users"

    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False, server_default="")
    last_name = Column(String(100), nullable=False, server_default="")
    
    # Profile Info
    position = Column(String(100), nullable=True)
    bio = Column(String(500), nullable=True)
    profile_image = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=True)
    country = Column(String(100), nullable=True)
    gender = Column(String(50), nullable=True)

    # "God Mode" switch for your internal tech team
    is_platform_admin = Column(Boolean, default=False, nullable=False)

    # Relationships
    companies = relationship("CompanyUser", back_populates="user", cascade="all, delete-orphan")