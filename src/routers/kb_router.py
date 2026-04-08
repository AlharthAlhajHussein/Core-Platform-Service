from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
from models.knowledge_bucket_registry import KnowledgeBucketRegistry
from routers.dependencies import get_db, get_current_user, can_access_kb
from services.knowledge_bucket_service import knowledge_bucket_service
from services.rag_proxy_service import rag_proxy_service
from views.kb_schemas import KnowledgeBucketCreate, KnowledgeBucketResponse

router = APIRouter(
    prefix="/api/v1/knowledge-buckets",
    tags=["Knowledge Base Management"]
)

@router.post("", status_code=status.HTTP_201_CREATED, response_model=KnowledgeBucketResponse)
async def create_knowledge_bucket(
    request: KnowledgeBucketCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Creates a new Knowledge Bucket.
    Owners can create anywhere. Supervisors are restricted to their sections.
    """
    return await knowledge_bucket_service.create_bucket(db=db, current_user=current_user, kb_data=request)

@router.get("", status_code=status.HTTP_200_OK, response_model=List[KnowledgeBucketResponse])
async def list_knowledge_buckets(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    section_id: Optional[UUID] = Query(None, description="Filter KBs by section")
):
    """
    Retrieves a list of Knowledge Buckets based on the user's role.
    - Owners see all KBs, and can filter by section.
    - Supervisors see KBs in their managed sections, and can filter by section.
    - Employees see KBs linked to the agents they are assigned to, and can filter by section.
    """
    return await knowledge_bucket_service.list_buckets(db=db, current_user=current_user, section_id=section_id)

@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_bucket(
    kb_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Deletes a Knowledge Bucket and gracefully unlinks any assigned Agents.
    """
    await knowledge_bucket_service.delete_bucket(db=db, current_user=current_user, kb_registry_id=kb_id)
    return None

@router.post("/{kb_id}/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document_to_bucket(
    kb: Annotated[KnowledgeBucketRegistry, Depends(can_access_kb)],
    files: Annotated[List[UploadFile], File(description="One or more documents to upload to the knowledge bucket.")]
):
    """
    Uploads one or more documents to the RAG service. Accessible by Owners, Supervisors, 
    and Employees who are assigned to an Agent that uses this Knowledge Bucket.
    """
    # The `can_access_kb` dependency has already verified permissions and fetched the KB object.
    # We can now use its properties to call the RAG proxy service.
    return await rag_proxy_service.upload_documents(
        company_id=kb.company_id,
        container_id=kb.rag_container_id,
        files=files
    )