from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime

class CompanyResponse(BaseModel):
    id: UUID
    name: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TenantOnboardRequest(BaseModel):
    """Schema for onboarding a completely new client company and their first owner."""
    company_name: str = Field(..., min_length=2, max_length=100)
    owner_email: EmailStr
    owner_password: str = Field(..., min_length=8)
    owner_first_name: str = Field(..., min_length=2, max_length=100)
    owner_last_name: str = Field(..., min_length=2, max_length=100)