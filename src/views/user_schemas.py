import uuid
from pydantic import BaseModel, EmailStr, Field
from models.company_users import RoleEnum

class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Must be at least 8 characters.")
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    role: RoleEnum
    section_id: uuid.UUID | None = Field(None, description="Required if a Supervisor is creating the user.")

class UserRoleUpdateRequest(BaseModel):
    role: RoleEnum

class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    role: RoleEnum | None = None

    class Config:
        from_attributes = True

class UserCompanyResponse(BaseModel):
    id: uuid.UUID
    name: str
    role: RoleEnum

class UserSectionResponse(BaseModel):
    id: uuid.UUID
    name: str
    company_id: uuid.UUID

class UserDetailResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    is_platform_admin: bool
    current_role: RoleEnum | None = None
    companies: list[UserCompanyResponse] = []
    sections: list[UserSectionResponse] = []