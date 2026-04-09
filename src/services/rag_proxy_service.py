import httpx
from fastapi import HTTPException, status, UploadFile
from uuid import UUID
from typing import List

from helpers.config import settings

class RAGProxyService:
    """
    A secure proxy service to communicate with the RAG-Engine-Service.
    This ensures the RAG service is never exposed directly to the public internet
    and all requests are authenticated and authorized through the Core Platform.
    """
    def __init__(self):
        self.base_url = settings.rag_service_url
        self.headers = {"X-Internal-Secret": settings.core_internal_secret}

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """A helper to make authenticated async requests to the RAG service."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    headers=self.headers,
                    timeout=30.0, # Set a reasonable timeout
                    **kwargs
                )
                response.raise_for_status() # Raises HTTPStatusError for 4xx/5xx responses
                return response
            except httpx.HTTPStatusError as e:
                # Forward the RAG service's error status and detail if possible
                detail = e.response.json().get("detail", "An error occurred in the RAG service.")
                raise HTTPException(status_code=e.response.status_code, detail=detail)
            except httpx.RequestError:
                # Handle network errors (e.g., connection refused)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="The RAG service is currently unavailable."
                )

    async def create_knowledge_bucket(self, name: str, company_id: UUID) -> dict:
        """
        Sends a request to the RAG service to create a new knowledge container.
        """
        # The RAG service expects company_id at the top level of the payload.
        payload = {"name": name, "company_id": str(company_id)}
        # The RAG service endpoint is /api/v1/containers/
        response = await self._make_request("POST", "/api/v1/containers/", json=payload)
        return response.json()

    async def delete_knowledge_bucket(self, company_id: UUID, container_id: UUID) -> dict | None:
        """
        Sends a request to the RAG service to delete an entire knowledge container and all its mapped documents.
        """
        endpoint = f"/api/v1/containers/{str(company_id)}/{str(container_id)}"
        response = await self._make_request("DELETE", endpoint)
        if response.status_code == 204:
            return None
        return response.json()

    async def upload_documents(self, company_id: UUID, container_id: UUID, files: List[UploadFile]) -> dict:
        """
        Streams a list of files to the RAG service's document upload endpoint.
        """
        # httpx requires files in a specific list-of-tuples format for multipart/form-data
        file_list = []
        for file in files:
            await file.seek(0) # Ensure file pointer is at the beginning
            file_list.append(('files', (file.filename, file.file, file.content_type)))

        endpoint = f"/api/v1/documents_upload/{str(company_id)}/{str(container_id)}"
        
        # The _make_request helper will handle the async call and error propagation.
        response = await self._make_request("POST", endpoint, files=file_list)
        return response.json()

    async def delete_document(self, company_id: UUID, container_id: UUID, document_id: UUID) -> dict | None:
        """
        Sends a request to the RAG service to delete a specific document from a container.
        """
        endpoint = f"/api/v1/documents/{str(company_id)}/{str(container_id)}/{str(document_id)}"
        
        response = await self._make_request("DELETE", endpoint)
        if response.status_code == 204:
            return None
        return response.json()

# Instantiate the service to be used as a singleton
rag_proxy_service = RAGProxyService()