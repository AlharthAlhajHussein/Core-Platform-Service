import uuid
from pydantic import BaseModel, Field

class SectionCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="The name of the section (e.g., Sales).")

class SectionResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str

    class Config:
        from_attributes = True

class SectionUserRequest(BaseModel):
    user_id: uuid.UUID