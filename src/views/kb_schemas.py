import uuid
from pydantic import BaseModel, Field

class KnowledgeBucketCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    section_id: uuid.UUID

class KnowledgeBucketResponse(BaseModel):
    id: uuid.UUID
    rag_container_id: uuid.UUID
    company_id: uuid.UUID
    section_id: uuid.UUID
    name: str

    class Config:
        from_attributes = True