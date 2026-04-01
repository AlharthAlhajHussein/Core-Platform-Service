from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from models.conversations import ConversationStatus, ConversationEvaluation

class ConversationListResponse(BaseModel):
    id: UUID
    sender_id: str
    status: str
    language: Optional[str] = None
    last_message_preview: Optional[str] = None
    last_activity_at: Optional[datetime] = None
    evaluation: Optional[str] = None
    evaluation_notes: Optional[str] = None
    
    # Enriched relational data based on RBAC rules
    agent_name: str
    section_name: Optional[str] = None
    assigned_supervisors: List[str] = []
    assigned_employees: List[str] = []

class MessageResponse(BaseModel):
    id: UUID
    sender_type: str
    text: Optional[str] = None
    media_url: Optional[str] = None
    timestamp: Optional[datetime] = None

class ConversationDetailResponse(BaseModel):
    conversation: ConversationListResponse
    messages: List[MessageResponse]

class ConversationStatusUpdateRequest(BaseModel):
    status: ConversationStatus

class ConversationEvaluationRequest(BaseModel):
    evaluation: ConversationEvaluation
    notes: Optional[str] = None