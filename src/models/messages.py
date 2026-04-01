import enum
from sqlalchemy import Column, String, Text, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel
from datetime import datetime, timezone

class SenderType(str, enum.Enum):
    USER = "USER"
    AI = "AI"
    HUMAN_AGENT = "HUMAN_AGENT"

class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"

class Message(BaseModel):
    __tablename__ = "messages"

    # Fast lookup for rendering chat history in the Dashboard UI
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_type = Column(Enum(SenderType), nullable=False, index=True)
    message_type = Column(Enum(MessageType), nullable=False, default="text") # "text", "image", "audio"
    media_url = Column(String(250), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    text = Column(Text, nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")