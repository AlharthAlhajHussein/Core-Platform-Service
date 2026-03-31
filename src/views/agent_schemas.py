import uuid
from pydantic import BaseModel, Field

class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    system_prompt: str = Field(..., description="The underlying persona and rules for the AI.")
    section_id: uuid.UUID = Field(..., description="The section this agent belongs to.")
    model_type: str = Field("gemini-2.5-flash", description="The LLM model to use.")
    temperature: float = Field(0.1, ge=0.0, le=2.0)
    whatsapp_token: str | None = Field(None, description="Raw Meta API token (will be encrypted).")
    telegram_token: str | None = Field(None, description="Raw Telegram bot token (will be encrypted).")

class AgentUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    system_prompt: str | None = None
    model_type: str | None = None
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    is_active: bool | None = None
    knowledge_bucket_registry_id: uuid.UUID | None = None
    whatsapp_token: str | None = Field(None, description="Provide a new token to update, or empty string to clear.")
    telegram_token: str | None = Field(None, description="Provide a new token to update, or empty string to clear.")

class AgentResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    section_id: uuid.UUID
    name: str
    system_prompt: str | None = None
    model_type: str | None = None
    temperature: float | None = None
    is_active: bool | None = None
    # Encrypted tokens are explicitly EXCLUDED from the response for security.

    class Config:
        from_attributes = True

class AgentEmployeeAssignRequest(BaseModel):
    user_id: uuid.UUID