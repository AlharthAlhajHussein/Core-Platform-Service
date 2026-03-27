from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship
from .base import BaseModel

class Company(BaseModel):
    __tablename__ = "companies"

    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships (to be populated as we build other models)
    users = relationship("CompanyUser", back_populates="company", cascade="all, delete-orphan")
    sections = relationship("Section", back_populates="company", cascade="all, delete-orphan")
    agents = relationship("Agent", back_populates="company", cascade="all, delete-orphan")