import uuid
from pydantic import BaseModel, Field
from typing import Optional

class AgentBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, description="The public name of the agent.")
    system_prompt: str = Field(..., min_length=10, description="The core instruction or persona for the AI.")
    model_type: str = "gemini-2.5-flash"
    temperature: float = Field(0.7, ge=0.0, le=1.0, description="Controls the creativity of the AI's responses.")
    is_active: bool = True
    section_id: uuid.UUID
    knowledge_bucket_id: Optional[uuid.UUID] = None

class AgentCreate(AgentBase):
    # These fields are for creation only and are not stored directly. They are encrypted.
    whatsapp_token: Optional[str] = None
    telegram_token: Optional[str] = None

class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    system_prompt: Optional[str] = Field(None, min_length=10)
    model_type: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_active: Optional[bool] = None
    section_id: Optional[uuid.UUID] = None
    knowledge_bucket_id: Optional[uuid.UUID] = None
    whatsapp_token: Optional[str] = None
    telegram_token: Optional[str] = None

class AgentResponse(AgentBase):
    id: uuid.UUID
    company_id: uuid.UUID

    class Config:
        from_attributes = True