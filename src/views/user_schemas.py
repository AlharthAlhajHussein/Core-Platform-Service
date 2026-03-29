import uuid
from pydantic import BaseModel, EmailStr, Field
from models.company_users import RoleEnum

class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Must be at least 8 characters.")
    role: RoleEnum
    section_id: uuid.UUID | None = Field(None, description="Required if a Supervisor is creating the user.")

class UserRoleUpdateRequest(BaseModel):
    role: RoleEnum

class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: RoleEnum | None = None

    class Config:
        from_attributes = True