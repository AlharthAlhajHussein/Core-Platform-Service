from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from models.messages import MessageType


class MessagePayload(BaseModel):
    """Represents a single message in the interaction."""
    text: str | None = None     # user can send voice or image without text
    message_time: datetime
    message_type: MessageType  
    media_url: str | None = None   # if the user sent voice or image we can get it in the Google Cloud Storge on this url

class InteractionSyncSchema(BaseModel):
    """Defines the data sent from the Orchestrator to sync a full interaction."""
    agent_id: UUID
    company_id: UUID
    sender_id: str = Field(..., description="The end-user's identifier, e.g., phone number.")
    platform: str = Field(..., description="The channel, e.g., 'whatsapp', 'telegram'.")
    user_message: MessagePayload
    ai_response: MessagePayload
    tokens_used: int = Field(..., ge=0, description="Total tokens used for this interaction.")