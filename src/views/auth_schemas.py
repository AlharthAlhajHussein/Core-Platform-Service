from pydantic import BaseModel, EmailStr
import uuid
from models.company_users import RoleEnum

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: str # This will be the user_id
    company_id: str | None = None
    role: RoleEnum | None = None
    is_platform_admin: bool = False
    exp: int | None = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr

    class Config:
        from_attributes = True