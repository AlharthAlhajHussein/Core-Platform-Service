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

class UserProfileUpdateRequest(BaseModel):
    first_name: str | None = Field(None, min_length=2, max_length=100)
    last_name: str | None = Field(None, min_length=2, max_length=100)
    position: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=500)
    profile_image: str | None = Field(None, description="URL of the profile image, or empty string to clear.")
    phone_number: str | None = Field(None, max_length=50)
    country: str | None = Field(None, max_length=100)
    gender: str | None = Field(None, max_length=50)

class UserAccountSettingsUpdateRequest(BaseModel):
    old_password: str = Field(..., description="Required to authorize changes to email or password.")
    new_email: EmailStr | None = Field(None, description="Optional new email address.")
    new_password: str | None = Field(None, min_length=8, description="Optional new password. Must be at least 8 characters.")

class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    position: str | None = None
    profile_image: str | None = None
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
    position: str | None = None
    bio: str | None = None
    profile_image: str | None = None
    phone_number: str | None = None
    country: str | None = None
    gender: str | None = None
    is_platform_admin: bool
    current_role: RoleEnum | None = None
    companies: list[UserCompanyResponse] = []
    sections: list[UserSectionResponse] = []

class ProfileImageUploadResponse(BaseModel):
    url: str