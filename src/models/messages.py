import enum
from sqlalchemy import Column, String, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class SenderType(str, enum.Enum):
    USER = "USER"
    AI = "AI"
    HUMAN_AGENT = "HUMAN_AGENT"

class Message(BaseModel):
    __tablename__ = "messages"

    # Fast lookup for rendering chat history in the Dashboard UI
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_type = Column(Enum(SenderType), nullable=False, index=True)
    
    message_type = Column(String(50), nullable=False, default="text") # "text", "image", "audio"
    content = Column(Text, nullable=False)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")