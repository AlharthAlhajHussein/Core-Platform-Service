from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class InternalAgentConfigResponse(BaseModel):
    """Schema exclusively used for internal service-to-service communication."""
    id: UUID
    company_id: UUID
    name: str
    system_prompt: Optional[str] = None
    model_type: Optional[str] = None
    temperature: Optional[float] = None
    is_active: bool
    whatsapp_token: Optional[str] = None
    telegram_token: Optional[str] = None
    whatsapp_number: Optional[str] = None
    telegram_bot_username: Optional[str] = None
    rag_container_id: Optional[UUID] = None
